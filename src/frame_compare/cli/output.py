from __future__ import annotations

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
STYLE_FAILURE = "bold red"
STYLE_WAIT = "magenta"
STYLE_HEADER = "bold cyan"
STYLE_SUBHEADER = "bold bright_cyan"
STYLE_METRIC_KEY = "dim"

type PostUploadActionPresentationKind = Literal["clipboard", "browser", "shortcut", "webhook"]
type WarningPresentationSeverity = Literal["warning", "skipped"]
type StatusPresentation = Literal["OK", "WARN", "SKIP", "FAIL", "WAIT"]


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


def _status_token(status: StatusPresentation) -> str:
    styles: dict[StatusPresentation, str] = {
        "OK": STYLE_SUCCESS,
        "WARN": STYLE_WARN,
        "SKIP": STYLE_SKIPPED,
        "FAIL": STYLE_FAILURE,
        "WAIT": STYLE_WAIT,
    }
    return f"[{styles[status]}][{status}][/]"


def _status_value(status: StatusPresentation, value: str) -> str:
    return f"{_status_token(status)} {_styled_value(value)}"


def _absolute_display_path(path: Path, root: Path | None) -> Path:
    if path.is_absolute():
        return path.resolve()
    if root is None:
        return path
    return (root.resolve() / path).resolve()


def _display_path(path: Path, *, root: Path | None, verbose: bool = False) -> str:
    """Render a complete path relative to the workspace when it is contained."""
    absolute = _absolute_display_path(path, root)
    if root is None:
        return _styled_path(str(path))

    resolved_root = root.resolve()
    try:
        relative = absolute.relative_to(resolved_root)
    except ValueError:
        display = str(absolute)
    else:
        display = str(relative) if relative != Path(".") else "."

    rendered = _styled_path(display)
    if verbose and display != str(absolute):
        rendered += f" {_styled_unit(f'(absolute: {absolute})')}"
    return rendered


def _format_duration(seconds: float) -> str:
    """Format a run duration for a human summary."""
    total_seconds = max(0.0, seconds)
    if total_seconds < 1.0:
        return f"{total_seconds * 1000:.0f} ms"
    if total_seconds < 60.0:
        return f"{total_seconds:.1f} s"

    whole_seconds = int(total_seconds)
    minutes, remaining_seconds = divmod(whole_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:02d}s"

    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes:02d}m {remaining_seconds:02d}s"


def _format_config_seconds(seconds: float) -> str:
    return f"{seconds:g}s"


def _group_table() -> Table:
    """Create a borderless two-column table for key-value rows."""
    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1, 0, 0))
    table.add_column("key", style=STYLE_KEY, no_wrap=True, min_width=22)
    table.add_column("value", overflow="fold")
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


# ── Run plan ──────────────────────────────────────────────────────────────────


def print_at_a_glance(
    console: Console,
    *,
    request: RunRequest,
    config: ConfigSchema,
    root: Path,
    config_path: Path,
    verbose: bool = False,
) -> None:
    from frame_compare.orchestration.preflight import resolve_paths

    workspace = resolve_paths(config, root)

    vspreview_status: str | None = None
    use_vspreview = config.audio_alignment.use_vspreview or request.force_interactive_alignment
    force_interactive = (
        config.audio_alignment.force_interactive or request.force_interactive_alignment
    )
    if use_vspreview or force_interactive:
        from frame_compare.vspreview.adapter import (
            VSPreviewAvailabilityStatus,
            check_vspreview_availability,
        )

        availability = check_vspreview_availability()
        if availability.is_available:
            vspreview_status = "available (true)"
        elif availability.status == VSPreviewAvailabilityStatus.PROBE_FAILED:
            vspreview_status = availability.public_probe_failure_status()
        else:
            vspreview_status = "unavailable (false)"

    from frame_compare.utils.subproc import resolve_executable

    try:
        resolve_executable("ffmpeg")
        resolve_executable("ffprobe")
    except FileNotFoundError:
        ffmpeg_available = False
    else:
        ffmpeg_available = True
    workspace_root = root.resolve()
    input_path = request.input_dir if request.input_dir is not None else workspace.input_dir
    analysis = config.analysis
    user_frames = request.user_frames if request.user_frames is not None else analysis.user_frames
    random_frame_count = (
        request.random_frame_count
        if request.random_frame_count is not None
        else analysis.random_frame_count
    )
    dark_frame_count = (
        request.dark_frame_count
        if request.dark_frame_count is not None
        else analysis.dark_frame_count
    )
    bright_frame_count = (
        request.bright_frame_count
        if request.bright_frame_count is not None
        else analysis.bright_frame_count
    )
    motion_frame_count = (
        request.motion_frame_count
        if request.motion_frame_count is not None
        else analysis.motion_frame_count
    )
    random_seed = request.seed if request.seed is not None else analysis.random_seed
    requested_total = (
        len(user_frames)
        + random_frame_count
        + dark_frame_count
        + bright_frame_count
        + motion_frame_count
    )
    overlay_mode = request.overlay_mode or config.screenshots.overlay_mode
    tonemap_enabled = config.color.enable_tonemap
    alignment_enabled = config.audio_alignment.enable
    upload_enabled = config.slowpics.auto_upload and not request.no_upload
    report_confirmed_upload = upload_enabled and config.slowpics.confirm_upload_after_report

    table = _group_table()

    # ── Workspace ──
    _add_subheader(table, "Workspace")
    _add_kv(table, "root", _styled_path(str(workspace_root)))
    _add_kv(table, "config", _display_path(config_path, root=workspace_root, verbose=verbose))
    _add_kv(table, "input", _display_path(input_path, root=workspace_root, verbose=verbose))
    _add_kv(
        table,
        "generated",
        _display_path(workspace.generated_root, root=workspace_root, verbose=verbose),
    )

    # ── Frame selection ──
    _add_separator(table)
    _add_subheader(table, "Frame selection")
    selection_text = (
        f"user={len(user_frames)}, "
        f"random={random_frame_count}, "
        f"dark={dark_frame_count}, "
        f"bright={bright_frame_count}, "
        f"motion={motion_frame_count}"
    )
    _add_kv(table, "requested", _styled_value(selection_text))
    _add_kv(table, "total frames", _styled_value(str(requested_total)))
    _add_kv(table, "seed", _styled_value(str(random_seed)))
    _add_kv(table, "analysis source", _styled_value(config.sources.analysis_source))
    analysis_mode = config.analysis.performance_mode.value
    if request.skip_analysis:
        analysis_mode = f"{analysis_mode} (skipped for this run)"
    _add_kv(table, "analysis mode", _styled_value(analysis_mode))
    cache_policy = (
        "cache-only" if request.from_cache_only else "bypassed" if request.no_cache else "normal"
    )
    _add_kv(table, "analysis cache", _styled_value(cache_policy))
    excluded_window = (
        "none"
        if analysis.ignore_lead_seconds == 0.0 and analysis.ignore_trail_seconds == 0.0
        else (
            f"lead={_format_config_seconds(analysis.ignore_lead_seconds)}, "
            f"trail={_format_config_seconds(analysis.ignore_trail_seconds)}"
        )
    )
    _add_kv(table, "exclusion window", _styled_value(excluded_window))

    # ── Rendering ──
    _add_separator(table)
    _add_subheader(table, "Rendering")
    renderer = "ffmpeg" if config.screenshots.use_ffmpeg else "auto (VapourSynth preferred)"
    _add_kv(table, "renderer", _styled_value(renderer))
    _add_kv(table, "overlay", _styled_value(str(overlay_mode.value)))
    _add_kv(table, "geometry", _styled_value(config.screenshots.geometry_mode.value))
    _add_kv(
        table,
        "active-picture policy",
        _styled_value(config.screenshots.active_rect_detection.value),
    )
    tonemap_settings = _resolve_preview_tonemap_settings(config, request)
    tonemap_text = (
        f"{'enabled' if tonemap_enabled else 'disabled'}; "
        f"preset={tonemap_settings.preset.value}; "
        f"target={tonemap_settings.target_nits} nits; "
        f"curve={tonemap_settings.tone_curve.value}"
    )
    _add_kv(
        table,
        "tone mapping",
        _status_value("OK" if tonemap_enabled else "SKIP", tonemap_text),
    )

    # ── Alignment ──
    _add_separator(table)
    _add_subheader(table, "Alignment")
    _add_kv(
        table,
        "audio alignment",
        _status_value(
            "OK" if alignment_enabled else "SKIP",
            "enabled" if alignment_enabled else "disabled",
        ),
    )
    ffmpeg_text = "available (true)" if ffmpeg_available else "unavailable (false)"
    _add_kv(
        table,
        "FFmpeg audio",
        _status_value("OK" if ffmpeg_available else "WARN", ffmpeg_text),
    )
    reuse_policy = {
        "disabled": "do not reuse previous offsets (disabled)",
        "prompt": "ask before reusing previous offsets (prompt)",
        "always": "reuse previous offsets when valid (always)",
    }[config.audio_alignment.previous_offsets]
    reuse_status_by_policy: dict[str, StatusPresentation] = {
        "disabled": "SKIP",
        "prompt": "WAIT",
        "always": "OK",
    }
    reuse_status = reuse_status_by_policy[config.audio_alignment.previous_offsets]
    _add_kv(table, "previous offsets", _status_value(reuse_status, reuse_policy))
    _add_kv(table, "interactive alignment", _styled_bool(use_vspreview))
    _add_kv(table, "force interactive", _styled_bool(force_interactive))
    manual_review_status: StatusPresentation
    manual_review_text: str
    if not use_vspreview and not force_interactive:
        manual_review_status, manual_review_text = "SKIP", "not configured"
    elif force_interactive:
        manual_review_status, manual_review_text = "WAIT", "VSPreview required"
    else:
        manual_review_status, manual_review_text = "WAIT", "VSPreview requested"
    _add_kv(table, "manual review", _status_value(manual_review_status, manual_review_text))
    if vspreview_status is not None:
        preview_status: StatusPresentation = (
            "OK" if vspreview_status.startswith("available") else "WARN"
        )
        _add_kv(table, "VSPreview", _status_value(preview_status, vspreview_status))

    # ── Review ──
    _add_separator(table)
    _add_subheader(table, "Review")
    report_text = (
        f"{'enabled' if config.report.enable else 'disabled'}; "
        f"auto-open={'enabled' if config.report.auto_open else 'disabled'}"
    )
    _add_kv(
        table,
        "report",
        _status_value("OK" if config.report.enable else "SKIP", report_text),
    )
    _add_kv(
        table,
        "metadata",
        _status_value(
            "SKIP" if request.skip_metadata else "OK",
            "lookup skipped" if request.skip_metadata else "lookup enabled",
        ),
    )

    # ── Publishing ──
    _add_separator(table)
    _add_subheader(table, "Publishing")
    if not upload_enabled:
        upload_status: StatusPresentation = "SKIP"
        upload_text = "disabled by --no-upload" if request.no_upload else "disabled"
    elif report_confirmed_upload:
        upload_status, upload_text = "WAIT", "confirm after local report"
    else:
        upload_status, upload_text = "OK", "automatic upload"
    _add_kv(table, "slow.pics", _status_value(upload_status, upload_text))
    _add_kv(table, "visibility", _styled_value(config.slowpics.visibility.value))
    _add_kv(
        table,
        "confirmation",
        _status_value(
            "WAIT" if report_confirmed_upload else "SKIP",
            "required after report" if report_confirmed_upload else "not required",
        ),
    )
    actions_text = (
        f"clipboard={'enabled' if config.slowpics.copy_url_to_clipboard else 'disabled'}; "
        f"browser={'enabled' if config.slowpics.open_in_browser else 'disabled'}; "
        f"shortcut={'enabled' if config.slowpics.create_url_shortcut else 'disabled'}; "
        f"webhook={'configured' if config.slowpics.webhook_url else 'not configured'}"
    )
    _add_kv(table, "post-upload actions", _styled_value(actions_text))
    _add_kv(
        table,
        "delete after upload",
        _status_value(
            "OK" if config.slowpics.delete_after_upload else "SKIP",
            "enabled (report-safe only)" if config.slowpics.delete_after_upload else "disabled",
        ),
    )

    console.print(Panel(table, title=f"[{STYLE_HEADER}]Run plan[/]", border_style="cyan"))


# ── Result summary ────────────────────────────────────────────────────────────


def print_result_summary(
    console: Console,
    *,
    result: RunResult,
    quiet: bool,
    post_upload_actions: PostUploadActionPresentationResults = (),
    root: Path | None = None,
    verbose: bool = False,
) -> None:
    screenshot_dir = str(result.screenshot_dir) if result.screenshot_dir is not None else None

    if quiet:
        if screenshot_dir is not None:
            console.print(f"Screenshots: {escape(screenshot_dir)}", soft_wrap=True)
        return

    all_post_upload_actions: PostUploadActionPresentationResults = (
        *result.post_upload_actions,
        *post_upload_actions,
    )
    warnings = _warning_presentations(result.warnings, all_post_upload_actions)
    headline_status: StatusPresentation
    if not result.success:
        headline_status = "FAIL"
        headline = "Comparison failed"
    elif warnings:
        headline_status = "WARN"
        suffix = "warning" if len(warnings) == 1 else "warnings"
        headline = f"Comparison completed with {len(warnings)} {suffix}"
    else:
        headline_status = "OK"
        headline = "Comparison completed"
    console.print(f"{_status_token(headline_status)} {escape(headline)}")

    table = _group_table()

    # ── Run facts ──
    _add_subheader(table, "Run facts")
    has_facts = False
    if result.frame_count > 0:
        has_facts = True
        _add_kv(table, "frames", _styled_value(str(result.frame_count)))
    if result.clips_processed > 0:
        has_facts = True
        _add_kv(table, "sources", _styled_value(str(result.clips_processed)))
    if result.duration_seconds > 0.0:
        has_facts = True
        _add_kv(table, "duration", _styled_value(_format_duration(result.duration_seconds)))
    if (
        result.metrics_cache_status != "skipped"
        or result.frame_count > 0
        or result.clips_processed > 0
    ):
        has_facts = True
        _add_kv(table, "Analysis cache", _styled_value(result.metrics_cache_status))
    if not has_facts:
        _add_kv(
            table,
            "status",
            _status_value(
                "OK" if result.success else "FAIL", "completed" if result.success else "failed"
            ),
        )

    # ── Review ──
    if result.report_path is not None or result.screenshot_dir is not None:
        _add_separator(table)
        _add_subheader(table, "Review")
        if result.report_path is not None:
            table.add_row(
                f"  {_status_token('OK')} report",
                _display_path(result.report_path, root=root, verbose=verbose),
            )
        if result.screenshot_dir is not None:
            table.add_row(
                f"  {_status_token('OK')} screenshots",
                _display_path(result.screenshot_dir, root=root, verbose=verbose),
            )

    # ── Published ──
    if result.slowpics_url is not None or result.slowpics_upload_confirmation_status in {
        "declined",
        "report_unavailable",
    }:
        _add_separator(table)
        _add_subheader(table, "Published")
        if result.slowpics_url is not None:
            table.add_row(
                f"  {_status_token('OK')} slow.pics",
                _styled_value(result.slowpics_url),
            )
        elif result.slowpics_upload_confirmation_status == "declined":
            table.add_row(
                f"  {_status_token('SKIP')} slow.pics",
                _styled_value("upload skipped by confirmation"),
            )
        else:
            table.add_row(
                f"  {_status_token('SKIP')} slow.pics",
                _styled_value("upload skipped because report confirmation was unavailable"),
            )

    # ── Follow-up actions ──
    successful_actions = [action for action in all_post_upload_actions if action.success]
    if successful_actions:
        _add_separator(table)
        _add_subheader(table, "Follow-up actions")
        for action in successful_actions:
            table.add_row(
                f"  {_status_token('OK')} {action.kind}",
                _post_upload_action_detail(action, root=root, verbose=verbose),
            )

    console.print(Panel(table, title=f"[{STYLE_HEADER}]Result[/]", border_style="cyan"))

    if warnings:
        max_lines = len(warnings) if verbose else 8
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


def _post_upload_action_detail(
    action: PostUploadActionPresentation,
    *,
    root: Path | None,
    verbose: bool,
) -> str:
    if action.path is not None:
        return _display_path(action.path, root=root, verbose=verbose)
    if action.detail is not None:
        return _styled_value(action.detail)
    if action.message is not None:
        return _styled_value(action.message)
    return _styled_value("completed")


def _warning_presentations(
    warnings: list[str],
    actions: PostUploadActionPresentationResults,
) -> list[WarningPresentation]:
    candidates: list[WarningPresentation] = []
    seen: set[tuple[str, WarningPresentationSeverity, str, str | None]] = set()
    action_warnings_by_message = {
        action.warning: _post_upload_warning_presentation(action)
        for action in actions
        if action.warning is not None
    }

    for warning in warnings:
        row = action_warnings_by_message.get(warning)
        if row is None:
            row = _warning_presentation_from_string(warning)
        key = (row.source, row.severity, row.message, row.detail)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(row)

    for row in action_warnings_by_message.values():
        key = (row.source, row.severity, row.message, row.detail)
        if key in seen:
            continue
        seen.add(key)
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
        message, reason = message.split(" because ", 1)
        detail = f"because {reason.strip()}"

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
        status: StatusPresentation = "SKIP" if warning.severity == "skipped" else "WARN"
        lines.append(f"{_status_token(status)} {escape(warning.message)}")
        if warning.detail is not None:
            lines.append(f"  [{STYLE_METRIC_KEY}]{escape(warning.detail)}[/]")
        if warning.action is not None:
            lines.append(f"  [{STYLE_METRIC_KEY}]action: {escape(warning.action)}[/]")
    return "\n".join(lines)


def _format_hidden_warning_counts(hidden: list[WarningPresentation]) -> str:
    counts_by_source: dict[str, int] = {}
    for warning in hidden:
        counts_by_source[warning.source] = counts_by_source.get(warning.source, 0) + 1

    count_text = ", ".join(
        f"{escape(source)}={count}" for source, count in sorted(counts_by_source.items())
    )
    return f"\n{_status_token('WARN')} ... ({len(hidden)} more) hidden by source: {count_text}"
