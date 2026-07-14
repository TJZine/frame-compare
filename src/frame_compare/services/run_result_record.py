"""Versioned run-outcome persistence and read-only history discovery."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Literal, NotRequired, TypedDict, cast
from urllib.parse import urlsplit

import tomli_w

from frame_compare.errors import FrameCompareError
from frame_compare.services.errors import HistoryAccessError, HistoryOpenError
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.types import WorkspacePaths

RUN_RESULT_FILENAME = "run_result.toml"
_VERSION = 1
_MAX_WARNING_SUMMARIES = 8
_SAFE_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,79}$")
_SLOWPICS_COMPARISON_PATH = re.compile(r"^/c/[A-Za-z0-9_-]+$")

type RunStatus = Literal["completed", "completed_with_warnings", "failed"]
type HistoryStatus = RunStatus | Literal["unknown", "unavailable"]
type FailureCategory = Literal[
    "configuration", "dependency", "input", "processing", "network", "internal"
]
type SlowpicsOutcome = Literal["not_uploaded", "uploaded", "declined", "report_unavailable"]

_FAILURE_MESSAGES: dict[FailureCategory, str] = {
    "configuration": "The run failed because the configuration was invalid.",
    "dependency": "The run failed because a required dependency was unavailable.",
    "input": "The run failed because an input could not be used.",
    "processing": "The run failed during media processing.",
    "network": "The run failed during a network operation.",
    "internal": "The run failed because of an internal error.",
}


class _SlowpicsPayload(TypedDict):
    outcome: SlowpicsOutcome
    url: NotRequired[str]


class _FailurePayload(TypedDict):
    code: str
    name: str
    category: FailureCategory
    message: str


class _RunResultPayload(TypedDict):
    version: int
    status: RunStatus
    started_at: str
    completed_at: str
    duration_seconds: float
    clip_count: int
    selected_frame_count: int
    warning_count: int
    warning_summaries: list[str]
    metrics_cache_status: Literal["skipped", "hit", "miss"]
    report_path: NotRequired[str]
    screenshot_dir: NotRequired[str]
    phase_timings: dict[str, float]
    slowpics: _SlowpicsPayload
    failure: NotRequired[_FailurePayload]


@dataclass(frozen=True, slots=True)
class RunFailure:
    code: str
    name: str
    category: FailureCategory
    message: str


@dataclass(frozen=True, slots=True)
class RunResultRecord:
    status: RunStatus
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    clip_count: int
    selected_frame_count: int
    warning_count: int
    warning_summaries: tuple[str, ...]
    metrics_cache_status: Literal["skipped", "hit", "miss"]
    phase_timings: dict[str, float]
    slowpics_outcome: SlowpicsOutcome
    report_path: str | None = None
    screenshot_dir: str | None = None
    slowpics_url: str | None = None
    failure: RunFailure | None = None
    version: int = _VERSION


@dataclass(frozen=True, slots=True)
class CompletedRunFacts:
    report_path: Path | None
    screenshot_dir: Path | None
    clip_count: int
    selected_frame_count: int
    warnings: tuple[str, ...]
    metrics_cache_status: Literal["skipped", "hit", "miss"]
    phase_timings: dict[str, float]
    slowpics_url: str | None
    slowpics_confirmation_status: Literal[
        "not_applicable", "confirmed", "declined", "report_unavailable"
    ]


@dataclass(frozen=True, slots=True)
class FailedRunFacts:
    clip_count: int = 0
    selected_frame_count: int = 0
    phase_timings: dict[str, float] | None = None
    report_path: Path | None = None
    screenshot_dir: Path | None = None
    metrics_cache_status: Literal["skipped", "hit", "miss"] = "skipped"
    slowpics_url: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    name: str
    status: HistoryStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    report_available: bool
    record: RunResultRecord | None = None
    warning: str | None = None


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_utc(value: datetime) -> str:
    normalized = _normalize_utc(value)
    return normalized.isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be a UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed.astimezone(UTC)


def _nonnegative_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _nonnegative_float(value: object, field: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{field} must be a number")
    result = float(cast(int | float, value))
    if result < 0 or result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{field} must be a finite nonnegative number")
    return result


def _relative_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a workspace-relative POSIX path")
    path = Path(value)
    windows = PureWindowsPath(value)
    if path.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"{field} must be relative")
    if any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"{field} contains an unsafe path segment")
    return path.as_posix()


def _slowpics_url(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("slowpics.url must be a string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("slowpics.url contains a control character")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "slow.pics"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or _SLOWPICS_COMPARISON_PATH.fullmatch(parsed.path) is None
    ):
        raise ValueError("slowpics.url must be a canonical https://slow.pics/c/ URL")
    return value


def _safe_relative_path(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _warning_summaries(warnings: tuple[str, ...]) -> tuple[str, ...]:
    if not warnings:
        return ()
    count = min(len(warnings), _MAX_WARNING_SUMMARIES)
    return tuple("A run warning was reported." for _ in range(count))


def _failure_category(error: BaseException) -> FailureCategory:
    if not isinstance(error, FrameCompareError):
        return "internal"
    category = error.code.removeprefix("FC-")[:1]
    return {
        "1": "configuration",
        "2": "dependency",
        "3": "input",
        "4": "processing",
        "5": "network",
    }.get(category, "internal")  # type: ignore[return-value]


def _failure_from_exception(error: BaseException) -> RunFailure:
    category = _failure_category(error)
    if isinstance(error, FrameCompareError):
        code = error.code if re.fullmatch(r"FC-[0-9]{4}", error.code) else "FC-0001"
        name = error.name if _SAFE_NAME.fullmatch(error.name) else "RUN_FAILED"
    else:
        code = "FC-0001"
        name = "INTERNAL_ERROR"
    return RunFailure(
        code=code,
        name=name,
        category=category,
        message=_FAILURE_MESSAGES[category],
    )


def completed_record(
    *,
    workspace: WorkspacePaths,
    facts: CompletedRunFacts,
    started_at: datetime,
    completed_at: datetime,
) -> RunResultRecord:
    """Build a sanitized completed record from orchestration-owned facts."""
    warning_count = len(facts.warnings)
    slowpics_outcome: SlowpicsOutcome = "not_uploaded"
    safe_url: str | None = None
    if facts.slowpics_url is not None:
        try:
            safe_url = _slowpics_url(facts.slowpics_url)
            slowpics_outcome = "uploaded"
        except ValueError:
            safe_url = None
    elif facts.slowpics_confirmation_status == "declined":
        slowpics_outcome = "declined"
    elif facts.slowpics_confirmation_status == "report_unavailable":
        slowpics_outcome = "report_unavailable"
    utc_started_at = _normalize_utc(started_at)
    utc_completed_at = _normalize_utc(completed_at)
    duration = max(0.0, (utc_completed_at - utc_started_at).total_seconds())
    return RunResultRecord(
        status="completed_with_warnings" if warning_count else "completed",
        started_at=utc_started_at,
        completed_at=utc_completed_at,
        duration_seconds=duration,
        report_path=_safe_relative_path(facts.report_path, workspace.root),
        screenshot_dir=_safe_relative_path(facts.screenshot_dir, workspace.root),
        clip_count=max(0, facts.clip_count),
        selected_frame_count=max(0, facts.selected_frame_count),
        warning_count=warning_count,
        warning_summaries=_warning_summaries(facts.warnings),
        metrics_cache_status=facts.metrics_cache_status,
        phase_timings={key: max(0.0, value) for key, value in sorted(facts.phase_timings.items())},
        slowpics_outcome=slowpics_outcome,
        slowpics_url=safe_url,
    )


def failed_record(
    *,
    error: BaseException,
    started_at: datetime,
    completed_at: datetime,
    facts: FailedRunFacts | None = None,
    workspace: WorkspacePaths | None = None,
) -> RunResultRecord:
    """Build a sanitized failed record without retaining exception text or paths."""
    effective_facts = facts or FailedRunFacts()
    timings = effective_facts.phase_timings or {}
    utc_started_at = _normalize_utc(started_at)
    utc_completed_at = _normalize_utc(completed_at)
    safe_url: str | None = None
    if effective_facts.slowpics_url is not None:
        try:
            safe_url = _slowpics_url(effective_facts.slowpics_url)
        except ValueError:
            safe_url = None
    return RunResultRecord(
        status="failed",
        started_at=utc_started_at,
        completed_at=utc_completed_at,
        duration_seconds=max(0.0, (utc_completed_at - utc_started_at).total_seconds()),
        clip_count=max(0, effective_facts.clip_count),
        selected_frame_count=max(0, effective_facts.selected_frame_count),
        warning_count=len(effective_facts.warnings),
        warning_summaries=_warning_summaries(effective_facts.warnings),
        metrics_cache_status=effective_facts.metrics_cache_status,
        phase_timings={key: max(0.0, value) for key, value in sorted(timings.items())},
        slowpics_outcome="uploaded" if safe_url is not None else "not_uploaded",
        report_path=(
            _safe_relative_path(effective_facts.report_path, workspace.root)
            if workspace is not None
            else None
        ),
        screenshot_dir=(
            _safe_relative_path(effective_facts.screenshot_dir, workspace.root)
            if workspace is not None
            else None
        ),
        slowpics_url=safe_url,
        failure=_failure_from_exception(error),
    )


def serialize_run_result(record: RunResultRecord) -> str:
    """Serialize a validated V1 record deterministically without null values."""
    payload: _RunResultPayload = {
        "version": record.version,
        "status": record.status,
        "started_at": _format_utc(record.started_at),
        "completed_at": _format_utc(record.completed_at),
        "duration_seconds": record.duration_seconds,
        "clip_count": record.clip_count,
        "selected_frame_count": record.selected_frame_count,
        "warning_count": record.warning_count,
        "warning_summaries": list(record.warning_summaries),
        "metrics_cache_status": record.metrics_cache_status,
        "phase_timings": dict(sorted(record.phase_timings.items())),
        "slowpics": {"outcome": record.slowpics_outcome},
    }
    if record.report_path is not None:
        payload["report_path"] = record.report_path
    if record.screenshot_dir is not None:
        payload["screenshot_dir"] = record.screenshot_dir
    if record.slowpics_url is not None:
        payload["slowpics"]["url"] = record.slowpics_url
    if record.failure is not None:
        payload["failure"] = {
            "code": record.failure.code,
            "name": record.failure.name,
            "category": record.failure.category,
            "message": record.failure.message,
        }
    parse_run_result(payload)
    return tomli_w.dumps(payload)


def write_run_result(run_dir: Path, record: RunResultRecord) -> None:
    """Atomically write one run outcome below an existing reserved run folder."""
    if not run_dir.is_dir():
        raise FileNotFoundError("reserved run folder is unavailable")
    write_text_atomic(run_dir / RUN_RESULT_FILENAME, serialize_run_result(record), encoding="utf-8")


def _require_keys(table: dict[str, object], allowed: set[str], required: set[str]) -> None:
    if not required.issubset(table) or not set(table).issubset(allowed):
        raise ValueError("record fields do not match the supported schema")


def parse_run_result(payload: object) -> RunResultRecord:
    """Validate an untrusted decoded TOML object as the exact V1 schema."""
    if not isinstance(payload, dict):
        raise ValueError("record root must be a table")
    table = cast(dict[str, object], payload)
    required = {
        "version",
        "status",
        "started_at",
        "completed_at",
        "duration_seconds",
        "clip_count",
        "selected_frame_count",
        "warning_count",
        "warning_summaries",
        "metrics_cache_status",
        "phase_timings",
        "slowpics",
    }
    _require_keys(table, required | {"report_path", "screenshot_dir", "failure"}, required)
    if type(table["version"]) is not int or table["version"] != _VERSION:
        raise ValueError("unsupported run-result version")
    status = table["status"]
    if status not in ("completed", "completed_with_warnings", "failed"):
        raise ValueError("status is invalid")
    started_at = _parse_utc(table["started_at"], "started_at")
    completed_at = _parse_utc(table["completed_at"], "completed_at")
    if completed_at < started_at:
        raise ValueError("completed_at precedes started_at")
    summaries_value = table["warning_summaries"]
    if not isinstance(summaries_value, list):
        raise ValueError("warning_summaries must be a bounded list")
    summary_items = cast(list[object], summaries_value)
    if len(summary_items) > _MAX_WARNING_SUMMARIES:
        raise ValueError("warning_summaries must be a bounded list")
    if any(item != "A run warning was reported." for item in summary_items):
        raise ValueError("warning_summaries contains unsafe text")
    summaries = tuple(cast(str, item) for item in summary_items)
    warning_count = _nonnegative_int(table["warning_count"], "warning_count")
    if len(summaries) != min(warning_count, _MAX_WARNING_SUMMARIES):
        raise ValueError("warning_summaries does not match warning_count")
    if status == "completed" and warning_count != 0:
        raise ValueError("completed records cannot contain warnings")
    if status == "completed_with_warnings" and warning_count == 0:
        raise ValueError("completed_with_warnings requires a warning")
    cache_status = table["metrics_cache_status"]
    if cache_status not in ("skipped", "hit", "miss"):
        raise ValueError("metrics_cache_status is invalid")
    timings_value = table["phase_timings"]
    if not isinstance(timings_value, dict):
        raise ValueError("phase_timings must be a table")
    timings: dict[str, float] = {}
    for key, value in cast(dict[object, object], timings_value).items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise ValueError("phase timing name is invalid")
        timings[key] = _nonnegative_float(value, f"phase_timings.{key}")
    slowpics_value = table["slowpics"]
    if not isinstance(slowpics_value, dict):
        raise ValueError("slowpics must be a table")
    slowpics = cast(dict[str, object], slowpics_value)
    _require_keys(slowpics, {"outcome", "url"}, {"outcome"})
    outcome = slowpics["outcome"]
    if outcome not in ("not_uploaded", "uploaded", "declined", "report_unavailable"):
        raise ValueError("slowpics.outcome is invalid")
    url = _slowpics_url(slowpics["url"]) if "url" in slowpics else None
    if (outcome == "uploaded") != (url is not None):
        raise ValueError("slowpics uploaded outcome and URL must agree")
    failure_value = table.get("failure")
    failure: RunFailure | None = None
    if failure_value is not None:
        if not isinstance(failure_value, dict):
            raise ValueError("failure must be a table")
        failure_table = cast(dict[str, object], failure_value)
        _require_keys(
            failure_table,
            {"code", "name", "category", "message"},
            {"code", "name", "category", "message"},
        )
        code, name, category, message = (
            failure_table["code"],
            failure_table["name"],
            failure_table["category"],
            failure_table["message"],
        )
        if not isinstance(code, str) or not re.fullmatch(r"FC-[0-9]{4}", code):
            raise ValueError("failure.code is invalid")
        if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
            raise ValueError("failure.name is invalid")
        if category not in (
            "configuration",
            "dependency",
            "input",
            "processing",
            "network",
            "internal",
        ):
            raise ValueError("failure.category is invalid")
        if not isinstance(message, str) or message != _FAILURE_MESSAGES.get(category):
            raise ValueError("failure.message is unsafe")
        failure = RunFailure(code, name, category, message)
    if (status == "failed") != (failure is not None):
        raise ValueError("failed status and failure table must agree")
    return RunResultRecord(
        version=_VERSION,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=_nonnegative_float(table["duration_seconds"], "duration_seconds"),
        report_path=_relative_path(table["report_path"], "report_path")
        if "report_path" in table
        else None,
        screenshot_dir=_relative_path(table["screenshot_dir"], "screenshot_dir")
        if "screenshot_dir" in table
        else None,
        clip_count=_nonnegative_int(table["clip_count"], "clip_count"),
        selected_frame_count=_nonnegative_int(
            table["selected_frame_count"], "selected_frame_count"
        ),
        warning_count=warning_count,
        warning_summaries=summaries,
        metrics_cache_status=cache_status,
        phase_timings=dict(sorted(timings.items())),
        slowpics_outcome=outcome,
        slowpics_url=url,
        failure=failure,
    )


def read_run_result(path: Path) -> RunResultRecord:
    """Read and validate one result record."""
    with path.open("rb") as handle:
        return parse_run_result(tomllib.load(handle))


def _report_path(record: RunResultRecord, workspace_root: Path) -> Path | None:
    if record.report_path is None:
        return None
    return workspace_root.resolve() / record.report_path


def _contained_regular_file(path: Path, owner_dir: Path) -> Path:
    try:
        owner = owner_dir.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except RuntimeError as exc:
        raise ValueError("persisted record file has an invalid symlink chain") from exc
    if not resolved.is_relative_to(owner) or not resolved.is_file():
        raise ValueError("persisted record file escapes its run directory")
    return resolved


def _legacy_started_at(run_dir: Path) -> datetime | None:
    try:
        path = _contained_regular_file(run_dir / "run_info.toml", run_dir)
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
        return _parse_utc(cast(dict[str, object], payload).get("created_at"), "created_at")
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return None


def _history_entry(
    run_dir: Path,
    workspace_root: Path,
    generated_root: Path,
) -> HistoryEntry:
    record_path = run_dir / RUN_RESULT_FILENAME
    try:
        record_path.lstat()
    except FileNotFoundError:
        return HistoryEntry(
            run_dir.name,
            "unknown",
            _legacy_started_at(run_dir),
            None,
            None,
            False,
        )
    except OSError:
        return HistoryEntry(
            run_dir.name,
            "unavailable",
            None,
            None,
            None,
            False,
            warning="A run result record could not be read.",
        )
    try:
        record = read_run_result(_contained_regular_file(record_path, run_dir))
        report = _report_path(record, workspace_root)
        available = False
        if report is not None:
            try:
                resolved_report = report.resolve(strict=True)
                available = (
                    resolved_report.is_relative_to(generated_root) and resolved_report.is_file()
                )
            except (OSError, RuntimeError):
                available = False
        return HistoryEntry(
            run_dir.name,
            record.status,
            record.started_at,
            record.completed_at,
            record.duration_seconds,
            available,
            record=record,
        )
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return HistoryEntry(
            run_dir.name,
            "unavailable",
            None,
            None,
            None,
            False,
            warning="A run result record is unreadable or unsupported.",
        )


def list_history(workspace_root: Path, generated_root: Path) -> list[HistoryEntry]:
    """List contained immediate run-folder children newest first."""
    root = generated_root.resolve()
    try:
        root.stat()
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise HistoryAccessError(
            "Run history could not be accessed.",
            "Check permissions for the configured generated directory.",
        ) from exc
    try:
        children = list(root.iterdir())
    except OSError as exc:
        raise HistoryAccessError(
            "Run history could not be listed.",
            "Check permissions for the configured generated directory.",
        ) from exc
    entries: list[HistoryEntry] = []
    for child in children:
        if (
            child.is_symlink()
            or child.name == "cache"
            or any(ord(character) < 32 or ord(character) == 127 for character in child.name)
        ):
            continue
        try:
            resolved = child.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_dir():
                continue
        except (OSError, RuntimeError):
            if not child.is_symlink():
                entries.append(
                    HistoryEntry(
                        child.name,
                        "unavailable",
                        None,
                        None,
                        None,
                        False,
                        warning="A run folder could not be inspected.",
                    )
                )
            continue
        entries.append(_history_entry(resolved, workspace_root, root))
    entries.sort(key=lambda entry: entry.name)
    entries.sort(
        key=lambda entry: (
            entry.completed_at or entry.started_at or datetime.min.replace(tzinfo=UTC)
        ),
        reverse=True,
    )
    return entries


def resolve_run_directory(generated_root: Path, run_name: str) -> Path:
    """Resolve an exact single-child run name beneath the generated root."""
    windows = PureWindowsPath(run_name)
    if (
        not run_name
        or run_name in (".", "..")
        or "/" in run_name
        or "\\" in run_name
        or Path(run_name).is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or any(ord(character) < 32 or ord(character) == 127 for character in run_name)
    ):
        raise HistoryAccessError(
            "Run name is invalid.", "Use an exact folder name shown by 'history list'."
        )
    root = generated_root.resolve()
    candidate = root / run_name
    try:
        if candidate.is_symlink():
            raise ValueError("symlinked run directories are not history entries")
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise HistoryAccessError(
            "Run was not found.", "Use an exact folder name shown by 'history list'."
        ) from exc
    except ValueError as exc:
        raise HistoryAccessError(
            "Run is outside the configured history directory.",
            "Use an exact folder name shown by 'history list'.",
        ) from exc
    except RuntimeError as exc:
        raise HistoryAccessError(
            "Run is outside the configured history directory.",
            "Use an exact folder name shown by 'history list'.",
        ) from exc
    if not resolved.is_relative_to(root) or not resolved.is_dir():
        raise HistoryAccessError(
            "Run is outside the configured history directory.",
            "Use an exact folder name shown by 'history list'.",
        )
    return resolved


def resolve_history_report(workspace_root: Path, generated_root: Path, run_name: str) -> Path:
    """Resolve a valid record's report and enforce generated-root containment."""
    run_dir = resolve_run_directory(generated_root, run_name)
    try:
        record_path = _contained_regular_file(run_dir / RUN_RESULT_FILENAME, run_dir)
        record = read_run_result(record_path)
    except FileNotFoundError as exc:
        raise HistoryOpenError(
            "This run has no result record.", "Only completed recorded reports can be opened."
        ) from exc
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise HistoryOpenError(
            "This run's result record is unavailable.", "Inspect or recreate the run."
        ) from exc
    if record.report_path is None:
        raise HistoryOpenError(
            "This run has no recorded report.", "Enable report generation for a future run."
        )
    root = generated_root.resolve()
    try:
        report = (workspace_root.resolve() / record.report_path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HistoryOpenError(
            "The recorded report is missing.", "Check whether generated files were moved."
        ) from exc
    if not report.is_relative_to(root) or not report.is_file():
        raise HistoryOpenError(
            "The recorded report is outside the configured history directory.",
            "Open that report directly only if you trust its location.",
        )
    return report
