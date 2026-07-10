from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from frame_compare.config.overrides import TonemapCliOverrides
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.orchestration.coordinator import RunRequest, RunResult
    from frame_compare.vs.types import TonemapSettings

# ── Theme constants ────────────────────────────────────────────────────────────
# Role-based color vocabulary inspired by the legacy CLI layout engine.

STYLE_KEY = "blue"
STYLE_VALUE = "bright_white"
STYLE_UNIT = "dim"
STYLE_PATH = "dim"
STYLE_BOOL_TRUE = "green"
STYLE_BOOL_FALSE = "red"
STYLE_SUCCESS = "bold green"
STYLE_WARN = "yellow"
STYLE_SKIPPED = "yellow"
STYLE_HEADER = "bold cyan"
STYLE_SUBHEADER = "bold bright_cyan"
STYLE_CHECK = "green"
STYLE_METRIC_KEY = "dim"

type PostUploadActionPresentationKind = Literal["clipboard", "browser", "shortcut", "webhook"]
type WarningPresentationSeverity = Literal["warning", "skipped"]


class PostUploadActionPresentation(Protocol):
    @property
    def kind(self) -> PostUploadActionPresentationKind: ...

    @property
    def success(self) -> bool: ...

    @property
    def detail(self) -> str | None: ...

    @property
    def path(self) -> Path | None: ...

    @property
    def message(self) -> str | None: ...

    @property
    def warning(self) -> str | None: ...


@dataclass(frozen=True)
class PostUploadActionPresentationResult:
    """CLI-local presentation state for optional post-upload side effects."""

    kind: PostUploadActionPresentationKind
    success: bool
    detail: str | None = None
    path: Path | None = None
    message: str | None = None
    warning: str | None = None


type PostUploadActionPresentationResults = tuple[PostUploadActionPresentation, ...]


@dataclass(frozen=True)
class WarningPresentation:
    """CLI-local warning presentation row bridged from existing runtime warnings."""

    source: str
    severity: WarningPresentationSeverity
    message: str
    detail: str | None = None
    action: str | None = None


# ── Formatting helpers ─────────────────────────────────────────────────────────


def _styled_bool(value: bool) -> str:
    """Return a color-coded boolean string."""
    if value:
        return f"[{STYLE_BOOL_TRUE}]true[/]"
    return f"[{STYLE_BOOL_FALSE}]false[/]"


def _styled_value(value: str) -> str:
    return f"[{STYLE_VALUE}]{escape(value)}[/]"


def _styled_unit(value: str) -> str:
    return f"[{STYLE_UNIT}]{escape(value)}[/]"


def _styled_path(value: str) -> str:
    return f"[{STYLE_PATH}]{escape(value)}[/]"


def _group_table() -> Table:
    """Create a borderless two-column table for key-value rows."""
    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1, 0, 0))
    table.add_column("key", style=STYLE_KEY, no_wrap=True, min_width=22)
    table.add_column("value")
    return table


def _add_subheader(table: Table, title: str) -> None:
    """Add a styled sub-header row to a group table."""
    table.add_row(f"[{STYLE_SUBHEADER}]{title}[/]", "")


def _add_kv(table: Table, key: str, value: str) -> None:
    """Add an indented key-value row."""
    table.add_row(f"  {key}", value)


def _add_separator(table: Table) -> None:
    """Add a blank separator row."""
    table.add_row("", "")


# ── Tonemap settings resolution ───────────────────────────────────────────────


def _resolve_preview_tonemap_settings(config: ConfigSchema, request: RunRequest) -> TonemapSettings:
    from frame_compare.render.prepare import resolve_tonemap_settings

    overrides: TonemapCliOverrides = {
        "tm_preset": request.tm_preset,
        "tm_target": request.tm_target_nits,
        "tm_curve": request.tm_curve,
    }
    return resolve_tonemap_settings(config, overrides)


# ── At-a-Glance panel ─────────────────────────────────────────────────────────


def print_at_a_glance(
    console: Console,
    *,
    request: RunRequest,
    config: ConfigSchema,
    root: Path,
    config_path: Path,
) -> None:
    from frame_compare.orchestration.preflight import resolve_paths

    workspace = resolve_paths(config, root)

    vspreview_status: str | None = None
    if config.audio_alignment.use_vspreview or config.audio_alignment.force_interactive:
        from frame_compare.vspreview.adapter import (
            VSPreviewAvailabilityStatus,
            check_vspreview_availability,
        )

        availability = check_vspreview_availability()
        if availability.is_available:
            vspreview_status = "true"
        elif availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
            vspreview_status = availability.public_probe_failure_status()
        else:
            vspreview_status = "false"

    ffmpeg_available = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
    tonemap_settings = _resolve_preview_tonemap_settings(config, request)

    table = _group_table()

    # ── Workspace ──
    _add_subheader(table, "Workspace")
    _add_kv(table, "root", _styled_path(str(root)))
    _add_kv(table, "config", _styled_path(str(config_path)))
    _add_kv(table, "input", _styled_path(str(workspace.input_dir)))
    _add_kv(table, "screenshots", _styled_path(str(workspace.screenshots_dir)))
    _add_kv(table, "generated", _styled_path(str(workspace.generated_dir)))
    run_folder_note = (
        f"{_styled_value('enabled')} {_styled_unit('(screenshots/generated rows are base paths)')}"
        if config.paths.use_run_folders
        else _styled_value("disabled")
    )
    _add_kv(table, "run folders", run_folder_note)

    # ── Analysis ──
    _add_separator(table)
    _add_subheader(table, "Analysis")
    selection_text = (
        f"user={_styled_value(str(len(config.analysis.user_frames)))}, "
        f"random={_styled_value(str(config.analysis.random_frame_count))}, "
        f"dark={_styled_value(str(config.analysis.dark_frame_count))}, "
        f"bright={_styled_value(str(config.analysis.bright_frame_count))}, "
        f"motion={_styled_value(str(config.analysis.motion_frame_count))}, "
        f"seed={_styled_value(str(config.analysis.random_seed))}"
    )
    _add_kv(table, "selection", selection_text)
    _add_kv(table, "analysis mode", _styled_value(str(config.analysis.performance_mode.value)))
    renderer = "ffmpeg" if config.screenshots.use_ffmpeg else "vapoursynth"
    _add_kv(table, "renderer", _styled_value(renderer))
    _add_kv(table, "overlay", _styled_value(str(config.screenshots.overlay_mode.value)))

    # ── Audio Alignment ──
    _add_separator(table)
    _add_subheader(table, "Audio Alignment")
    _add_kv(table, "alignment enabled", _styled_bool(config.audio_alignment.enable))
    _add_kv(table, "FFmpeg audio", _styled_bool(ffmpeg_available))
    _add_kv(table, "previous offsets", _styled_value(config.audio_alignment.previous_offsets))
    _add_kv(table, "interactive alignment", _styled_bool(config.audio_alignment.use_vspreview))
    _add_kv(
        table,
        "force interactive",
        _styled_bool(config.audio_alignment.force_interactive),
    )
    if vspreview_status is not None:
        _add_kv(table, "VSPreview", _styled_value(vspreview_status))

    # ── Tonemap ──
    _add_separator(table)
    _add_subheader(table, "Tonemap")
    _add_kv(table, "tonemap.enabled", _styled_bool(config.color.enable_tonemap))
    _add_kv(table, "tonemap.preset", _styled_value(tonemap_settings.preset.value))
    _add_kv(
        table,
        "tonemap.target_nits",
        f"{_styled_value(str(tonemap_settings.target_nits))} {_styled_unit('nits')}",
    )
    _add_kv(table, "tonemap.curve", _styled_value(tonemap_settings.tone_curve.value))

    # ── Output ──
    _add_separator(table)
    _add_subheader(table, "Output")
    upload_status = "disabled" if request.no_upload else "enabled"
    _add_kv(table, "upload", _styled_value(upload_status))
    slowpics_detail = (
        f"visibility={_styled_value(config.slowpics.visibility.value)}  "
        f"auto_upload={_styled_bool(config.slowpics.auto_upload)}  "
        f"delete_after={_styled_bool(config.slowpics.delete_after_upload)}"
    )
    _add_kv(table, "slow.pics", slowpics_detail)
    report_detail = (
        f"enabled={_styled_bool(config.report.enable)}  "
        f"auto_open={_styled_bool(config.report.auto_open)}"
    )
    _add_kv(table, "report", report_detail)

    console.print(Panel(table, title=f"[{STYLE_HEADER}]At-a-Glance[/]", border_style="cyan"))


# ── Result summary ────────────────────────────────────────────────────────────


def print_result_summary(
    console: Console,
    *,
    result: RunResult,
    quiet: bool,
    post_upload_actions: PostUploadActionPresentationResults = (),
) -> None:
    screenshot_dir = str(result.screenshot_dir) if result.screenshot_dir is not None else None

    if quiet:
        if screenshot_dir is not None:
            console.print(f"Screenshots: {escape(screenshot_dir)}", soft_wrap=True)
        return

    table = _group_table()
    all_post_upload_actions: PostUploadActionPresentationResults = (
        *result.post_upload_actions,
        *post_upload_actions,
    )

    # Artifact rows with checkmarks
    has_artifacts = False
    if screenshot_dir is not None:
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_CHECK}]\u2713[/] screenshots",
            _styled_path(screenshot_dir),
        )
    if result.slowpics_url is not None:
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_CHECK}]\u2713[/] slow.pics",
            _styled_value(result.slowpics_url),
        )
    elif result.slowpics_upload_confirmation_status == "declined":
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_SKIPPED}]-[/] slow.pics",
            _styled_value("slow.pics upload skipped by confirmation"),
        )
    elif result.slowpics_upload_confirmation_status == "report_unavailable":
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_SKIPPED}]-[/] slow.pics",
            _styled_value("slow.pics upload skipped because report confirmation was unavailable"),
        )
    for action in all_post_upload_actions:
        if not action.success:
            continue
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_CHECK}]\u2713[/] {action.kind}",
            _styled_value(_post_upload_action_detail(action)),
        )
    if result.report_path is not None:
        has_artifacts = True
        table.add_row(
            f"  [{STYLE_CHECK}]\u2713[/] report",
            _styled_path(str(result.report_path)),
        )

    if not has_artifacts:
        table.add_row(f"  [{STYLE_CHECK}]\u2713[/] status", _styled_value("success"))

    # Metrics section
    has_metrics = (
        result.frame_count > 0 or result.clips_processed > 0 or result.duration_seconds > 0.0
    )
    if has_metrics:
        _add_separator(table)
        if result.frame_count > 0:
            _add_kv(table, "frames", _styled_value(str(result.frame_count)))
        if result.clips_processed > 0:
            _add_kv(table, "clips", _styled_value(str(result.clips_processed)))
        if result.duration_seconds > 0.0:
            _add_kv(
                table,
                "duration",
                f"{_styled_value(f'{result.duration_seconds:.1f}')}{_styled_unit('s')}",
            )
        _add_kv(
            table,
            "cache",
            _styled_value(result.metrics_cache_status),
        )

    console.print(Panel(table, title=f"[{STYLE_HEADER}]Result[/]", border_style="cyan"))

    warnings = _warning_presentations(result.warnings, all_post_upload_actions)
    if warnings:
        max_lines = 8
        visible = warnings[:max_lines]
        remaining = len(warnings) - len(visible)
        warning_text = _format_warning_panel_text(visible)
        if remaining > 0:
            warning_text += _format_hidden_warning_counts(warnings[max_lines:])
        console.print(
            Panel(
                warning_text,
                title=f"[{STYLE_WARN}]Warnings[/]",
                border_style="yellow",
                expand=False,
            )
        )


def _post_upload_action_detail(action: PostUploadActionPresentation) -> str:
    if action.path is not None:
        return str(action.path)
    if action.detail is not None:
        return action.detail
    if action.message is not None:
        return action.message
    return "completed"


def _warning_presentations(
    warnings: list[str],
    actions: PostUploadActionPresentationResults,
) -> list[WarningPresentation]:
    candidates: list[WarningPresentation] = []
    seen: set[str] = set()
    action_warnings_by_message = {
        action.warning: _post_upload_warning_presentation(action)
        for action in actions
        if action.warning is not None
    }

    for warning in warnings:
        row = action_warnings_by_message.get(warning)
        if row is None:
            row = _warning_presentation_from_string(warning)
        if row.message in seen:
            continue
        seen.add(row.message)
        candidates.append(row)

    for row in action_warnings_by_message.values():
        if row.message in seen:
            continue
        seen.add(row.message)
        candidates.append(row)

    return _group_warnings_by_source(candidates)


def _post_upload_warning_presentation(
    action: PostUploadActionPresentation,
) -> WarningPresentation:
    warning = action.warning
    if warning is None:
        raise ValueError("post-upload warning presentation requires action.warning")
    row = _warning_presentation_from_string(warning)
    return WarningPresentation(
        source=row.source,
        severity=row.severity,
        message=row.message,
        detail=row.detail,
        action=action.kind,
    )


def _warning_presentation_from_string(warning: str) -> WarningPresentation:
    stripped = warning.strip()
    severity: WarningPresentationSeverity = (
        "skipped" if "skipped" in stripped.lower() else "warning"
    )

    source = "run"
    message = stripped
    detail: str | None = None

    if ":" in stripped:
        prefix, _remainder = stripped.split(":", 1)
        normalized_prefix = prefix.strip()
        if normalized_prefix:
            source = _normalize_warning_source(normalized_prefix)
    elif stripped.lower().startswith("slow.pics "):
        source = "slow.pics"

    if " because " in message:
        _message, detail = message.split(" because ", 1)
        detail = f"because {detail.strip()}"

    return WarningPresentation(
        source=source,
        severity=severity,
        message=message,
        detail=detail,
    )


def _normalize_warning_source(source: str) -> str:
    normalized = source.lower().replace("_", " ").replace("-", " ").strip()
    if normalized.startswith("slow.pics"):
        return "slow.pics"
    if normalized in {"align", "alignment"}:
        return "alignment"
    return normalized


def _group_warnings_by_source(warnings: list[WarningPresentation]) -> list[WarningPresentation]:
    sources: list[str] = []
    grouped: dict[str, list[WarningPresentation]] = {}
    for warning in warnings:
        if warning.source not in grouped:
            sources.append(warning.source)
            grouped[warning.source] = []
        grouped[warning.source].append(warning)
    return [warning for source in sources for warning in grouped[source]]


def _format_warning_panel_text(warnings: list[WarningPresentation]) -> str:
    lines: list[str] = []
    current_source: str | None = None
    for warning in warnings:
        if warning.source != current_source:
            if lines:
                lines.append("")
            lines.append(f"[{STYLE_SUBHEADER}]{escape(warning.source)}[/]")
            current_source = warning.source
        lines.append(
            f"[{STYLE_WARN}]\u2022[/] {escape(warning.message)} "
            f"[{STYLE_METRIC_KEY}]({warning.severity})[/]"
        )
        if warning.detail is not None:
            lines.append(f"  [{STYLE_METRIC_KEY}]detail[/] {escape(warning.detail)}")
        if warning.action is not None:
            lines.append(f"  [{STYLE_METRIC_KEY}]action[/] {escape(warning.action)}")
    return "\n".join(lines)


def _format_hidden_warning_counts(hidden: list[WarningPresentation]) -> str:
    counts_by_source: dict[str, int] = {}
    for warning in hidden:
        counts_by_source[warning.source] = counts_by_source.get(warning.source, 0) + 1

    count_text = ", ".join(
        f"{escape(source)}={count}" for source, count in sorted(counts_by_source.items())
    )
    return f"\n[{STYLE_WARN}]\u2022[/] ... ({len(hidden)} more) hidden by source: {count_text}"
