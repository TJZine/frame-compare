"""Versioned run-outcome persistence and read-only history discovery."""

from __future__ import annotations

import os
import re
import tomllib
from asyncio import CancelledError
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from stat import S_ISREG
from typing import Annotated, Literal, NotRequired, TypedDict
from urllib.parse import urlsplit

import tomli_w
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    field_validator,
)

from frame_compare.errors import FrameCompareError
from frame_compare.services.errors import HistoryAccessError, HistoryOpenError
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.utils.types import WorkspacePaths

RUN_RESULT_FILENAME = "run_result.toml"
_VERSION = 1
_MAX_WARNING_SUMMARIES = 8
_INTERRUPTED_FAILURE_NAME = "RUN_INTERRUPTED"
_SAFE_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,79}$")
_SLOWPICS_COMPARISON_PATH = re.compile(r"^/c/[A-Za-z0-9_-]+$")

type RunStatus = Literal["completed", "completed_with_warnings", "failed"]
type HistoryStatus = RunStatus | Literal["unavailable"]
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

    @property
    def was_interrupted(self) -> bool:
        return (
            self.status == "failed"
            and self.failure is not None
            and self.failure.name == _INTERRUPTED_FAILURE_NAME
        )


@dataclass(frozen=True, slots=True)
class CompletedRunFacts:
    report_path: Path | None
    screenshot_dir: Path | None
    clip_count: int
    selected_frame_count: int
    warnings: list[RunWarning]
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
    warnings: list[RunWarning] = field(default_factory=list[RunWarning])


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


def _relative_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a run-folder-relative POSIX path")
    if any(segment in ("", ".", "..") for segment in value.split("/")):
        raise ValueError(f"{field} contains an unsafe path segment")
    path = Path(value)
    windows = PureWindowsPath(value)
    if path.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"{field} must be relative")
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


def _safe_relative_path(path: Path | None, run_dir: Path | None) -> str | None:
    """Return a safe artifact path relative to its owning run folder."""
    if path is None or run_dir is None:
        return None
    try:
        relative = path.resolve().relative_to(run_dir.resolve())
        if not relative.parts:
            return None
        return _relative_path(relative.as_posix(), "artifact_path")
    except (OSError, RuntimeError, ValueError):
        return None


def _warning_summaries(warnings: list[RunWarning]) -> tuple[str, ...]:
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
        name = (
            _INTERRUPTED_FAILURE_NAME
            if isinstance(error, (CancelledError, KeyboardInterrupt))
            else "INTERNAL_ERROR"
        )
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
        report_path=_safe_relative_path(facts.report_path, workspace.run_dir),
        screenshot_dir=_safe_relative_path(facts.screenshot_dir, workspace.run_dir),
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
            _safe_relative_path(effective_facts.report_path, workspace.run_dir)
            if workspace is not None
            else None
        ),
        screenshot_dir=(
            _safe_relative_path(effective_facts.screenshot_dir, workspace.run_dir)
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
    _StoredRunResult.model_validate(payload)
    return tomli_w.dumps(payload)


def write_run_result(run_dir: Path, record: RunResultRecord) -> None:
    """Atomically write one run outcome below an existing reserved run folder."""
    if not run_dir.is_dir():
        raise FileNotFoundError("reserved run folder is unavailable")
    write_text_atomic(
        run_dir / RUN_RESULT_FILENAME,
        serialize_run_result(record),
        encoding="utf-8",
        publish_guard=None if record.status == "failed" else raise_if_cancelling,
    )


_NonnegativeCount = Annotated[StrictInt, Field(ge=0)]
_NonnegativeSeconds = Annotated[StrictFloat, Field(ge=0, allow_inf_nan=False)]


class _StoredSlowpics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    outcome: SlowpicsOutcome
    url: str | None = None


class _StoredFailure(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    name: str
    category: FailureCategory
    message: str

    def to_failure(self) -> RunFailure:
        return RunFailure(self.code, self.name, self.category, self.message)


class _StoredRunResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: Literal[1]
    status: RunStatus
    started_at: AwareDatetime
    completed_at: AwareDatetime
    duration_seconds: _NonnegativeSeconds
    clip_count: _NonnegativeCount
    selected_frame_count: _NonnegativeCount
    warning_count: _NonnegativeCount
    warning_summaries: tuple[str, ...]
    metrics_cache_status: Literal["skipped", "hit", "miss"]
    phase_timings: dict[str, _NonnegativeSeconds]
    report_path: str | None = None
    screenshot_dir: str | None = None
    slowpics: _StoredSlowpics
    failure: _StoredFailure | None = None

    @field_validator("version", mode="before")
    @classmethod
    def require_integer_version(cls, value: object) -> int:
        if type(value) is not int:
            raise ValueError("run-result version must be an integer")
        return value

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def parse_timestamp_text(cls, value: object) -> datetime:
        if not isinstance(value, str):
            raise ValueError("run-result timestamp must be ISO datetime text")
        return datetime.fromisoformat(value)

    def to_record(self) -> RunResultRecord:
        return RunResultRecord(
            version=self.version,
            status=self.status,
            started_at=self.started_at.astimezone(UTC),
            completed_at=self.completed_at.astimezone(UTC),
            duration_seconds=self.duration_seconds,
            clip_count=self.clip_count,
            selected_frame_count=self.selected_frame_count,
            warning_count=self.warning_count,
            warning_summaries=self.warning_summaries,
            metrics_cache_status=self.metrics_cache_status,
            phase_timings=dict(sorted(self.phase_timings.items())),
            report_path=self.report_path,
            screenshot_dir=self.screenshot_dir,
            slowpics_outcome=self.slowpics.outcome,
            slowpics_url=self.slowpics.url,
            failure=self.failure.to_failure() if self.failure is not None else None,
        )


def read_run_result(path: Path) -> RunResultRecord:
    """Read and validate one result record."""
    if not S_ISREG(path.stat().st_mode):
        raise ValueError("run result is not a regular file")
    with path.open("rb") as handle:
        try:
            payload = tomllib.load(handle)
        except RecursionError:
            raise ValueError("run result exceeds TOML parser limits") from None
    return _StoredRunResult.model_validate(payload).to_record()


_HISTORY_ROOT_HINT = (
    "Reconnect the selected generated-data location, correct its permissions, or "
    "choose another paths.generated_dir."
)


def _history_root_unavailable(root: Path) -> HistoryAccessError:
    """Build the actionable error for an unavailable selected history root."""
    return HistoryAccessError(
        f"Configured generated-data history root is unavailable: {root}",
        _HISTORY_ROOT_HINT,
    )


def _require_history_root(generated_root: Path) -> Path:
    """Resolve and verify the configured history root without creating it."""
    try:
        root = generated_root.resolve()
    except (OSError, RuntimeError) as exc:
        raise _history_root_unavailable(generated_root) from exc
    try:
        root.stat()
        if not root.is_dir():
            raise NotADirectoryError(root)
    except (OSError, RuntimeError) as exc:
        raise _history_root_unavailable(root) from exc
    return root


def _history_entry(run_dir: Path) -> HistoryEntry | None:
    record_path = run_dir / RUN_RESULT_FILENAME
    try:
        record_path.lstat()
    except FileNotFoundError:
        return None
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
        record = read_run_result(record_path)
    except Exception:
        return HistoryEntry(
            run_dir.name,
            "unavailable",
            None,
            None,
            None,
            False,
            warning="A run result record is unreadable or unsupported.",
        )

    try:
        report_available = (
            record.report_path == "report.html" and (run_dir / "report.html").is_file()
        )
    except OSError:
        report_available = False
    return HistoryEntry(
        run_dir.name,
        record.status,
        record.started_at,
        record.completed_at,
        record.duration_seconds,
        report_available,
        record=record,
    )


def list_history(generated_root: Path) -> list[HistoryEntry]:
    """List recorded immediate run-folder children newest first."""
    root = _require_history_root(generated_root)
    if os.name == "posix" and not os.access(root, os.X_OK):
        raise _history_root_unavailable(root)
    try:
        children = list(root.iterdir())
    except (OSError, RuntimeError) as exc:
        raise _history_root_unavailable(root) from exc
    entries: list[HistoryEntry] = []
    for child in children:
        if child.name == "cache" or any(
            ord(character) < 32 or ord(character) == 127 for character in child.name
        ):
            continue
        try:
            if not child.is_dir():
                continue
        except (OSError, RuntimeError) as exc:
            if (
                os.name == "posix"
                and isinstance(exc, PermissionError)
                and not os.access(root, os.X_OK)
            ):
                raise _history_root_unavailable(root) from exc
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
        entry = _history_entry(child)
        if entry is not None:
            entries.append(entry)
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
    root = _require_history_root(generated_root)
    candidate = root / run_name
    try:
        is_dir = candidate.is_dir()
    except OSError as exc:
        raise _history_root_unavailable(root) from exc
    if not is_dir:
        raise HistoryAccessError(
            "Run was not found.", "Use an exact folder name shown by 'history list'."
        )
    return candidate


def resolve_history_report(generated_root: Path, run_name: str) -> Path:
    """Find the canonical report named by a run's result record."""
    run_dir = resolve_run_directory(generated_root, run_name)
    try:
        record = read_run_result(run_dir / RUN_RESULT_FILENAME)
    except FileNotFoundError as exc:
        raise HistoryOpenError(
            "This run has no result record.", "Only completed recorded reports can be opened."
        ) from exc
    except (OSError, ValueError, OverflowError) as exc:
        raise HistoryOpenError(
            "This run's result record is unavailable.", "Inspect or recreate the run."
        ) from exc
    if record.report_path is None:
        raise HistoryOpenError(
            "This run has no recorded report.", "Enable report generation for a future run."
        )
    if record.report_path != "report.html":
        raise HistoryOpenError(
            "The result record does not name the canonical report.html.",
            "Inspect or recreate the run.",
        )
    report = run_dir / "report.html"
    try:
        report_exists = report.is_file()
    except OSError as exc:
        raise HistoryOpenError(
            "The recorded report is missing.", "Check whether generated files were moved."
        ) from exc
    if not report_exists:
        raise HistoryOpenError(
            "The recorded report is missing.", "Check whether generated files were moved."
        )
    return report
