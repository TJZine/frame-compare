from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from frame_compare.utils.post_upload_actions import PostUploadActionResult, PostUploadActionResults

if TYPE_CHECKING:
    from frame_compare.config.overrides import TonemapCliOverrides
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.orchestration.coordinator import RunRequest, RunResult
    from frame_compare.vs.types import TonemapSettings

# ── Theme constants ────────────────────────────────────────────────────────────
# Role-based color vocabulary inspired by the legacy CLI layout engine.

STYLE_KEY = "grey70"
STYLE_VALUE = "bright_white"
STYLE_UNIT = "dim"
STYLE_PATH = "dim"
STYLE_ARTIFACT_PATH = "bright_white"
STYLE_URL = "bright_cyan"
STYLE_SUCCESS = "bold green"
STYLE_WARN = "yellow"
STYLE_SKIPPED = "yellow"
STYLE_FAILURE = "bold red"
STYLE_WAIT = "magenta"
STYLE_HEADER = "bold cyan"
STYLE_SUBHEADER = "bold bright_cyan"
STYLE_METRIC_KEY = "dim"

type WarningPresentationSeverity = Literal["warning", "skipped"]
type StatusPresentation = Literal["OK", "WARN", "SKIP", "FAIL", "WAIT"]


@dataclass(frozen=True)
class WarningPresentation:
    """CLI-local warning presentation row bridged from existing runtime warnings."""

    source: str
    severity: WarningPresentationSeverity
    message: str
    detail: str | None = None
    action: str | None = None


# ── Formatting helpers ─────────────────────────────────────────────────────────


def _styled_value(value: str) -> str:
    return f"[{STYLE_VALUE}]{escape(value)}[/]"


def _styled_unit(value: str) -> str:
    return f"[{STYLE_UNIT}]{escape(value)}[/]"


def _styled_path(value: str) -> str:
    return f"[{STYLE_PATH}]{escape(value)}[/]"


def _styled_artifact_path(value: str) -> str:
    return f"[{STYLE_ARTIFACT_PATH}]{escape(value)}[/]"


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


def format_display_path(path: Path, *, root: Path | None) -> str:
    """Render a plain path relative to its root when it is contained."""
    absolute = _absolute_display_path(path, root)
    if root is None:
        return str(path)

    try:
        relative = absolute.relative_to(root.resolve())
    except ValueError:
        return str(absolute)
    return str(relative) if relative != Path(".") else "."


def _display_path(
    path: Path,
    *,
    root: Path | None,
    verbose: bool = False,
    artifact: bool = False,
) -> str:
    """Render a complete path relative to the workspace when it is contained."""
    display = format_display_path(path, root=root)
    rendered = _styled_artifact_path(display) if artifact else _styled_path(display)
    absolute = _absolute_display_path(path, root)
    if verbose and root is not None and display != str(absolute):
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


def _humanize(value: str) -> str:
    return {
        "auto": "Automatic",
        "bt2390": "BT.2390",
        "quality": "Quality",
        "performance": "Performance",
    }.get(value, value.replace("_", " ").title())


def _group_table() -> Table:
    """Create a borderless two-column table for key-value rows."""
    table = Table(show_header=False, box=None, pad_edge=False, padding=(0, 1, 0, 0))
    table.add_column("key", style=STYLE_KEY, min_width=22, overflow="fold")
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

    vsview_status: str | None = None
    use_vsview = config.audio_alignment.use_vsview or request.force_interactive_alignment
    force_interactive = (
        config.audio_alignment.force_interactive or request.force_interactive_alignment
    )
    if use_vsview or force_interactive:
        from frame_compare.vsview.adapter import (
            VSViewAvailabilityStatus,
            check_vsview_availability,
        )

        availability = check_vsview_availability()
        if availability.is_available:
            vsview_status = "available (true)"
        elif availability.status == VSViewAvailabilityStatus.PROBE_FAILED:
            vsview_status = availability.public_probe_failure_status()
        else:
            vsview_status = "unavailable (false)"

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
    categories = [
        f"{name} {count}"
        for name, count in (
            ("user", len(user_frames)),
            ("random", random_frame_count),
            ("dark", dark_frame_count),
            ("bright", bright_frame_count),
            ("motion", motion_frame_count),
        )
        if count
    ]
    _add_kv(table, "Frames", _styled_value(f"{requested_total} total"))
    _add_kv(table, "", _styled_unit(" | ".join(categories)))
    if user_frames:
        _add_kv(table, "User frames", _styled_value(", ".join(str(frame) for frame in user_frames)))
    if random_frame_count:
        _add_kv(table, "Seed", _styled_value(str(random_seed)))
    analysis_mode = _humanize(config.analysis.performance_mode.value)
    if request.skip_analysis:
        analysis_mode = f"{analysis_mode} (skipped for this run)"
    source_policy = config.sources.analysis_source.replace("_", " ")
    cache_policy = (
        "cache only"
        if request.from_cache_only
        else "cache bypassed"
        if request.no_cache
        else "cache read/write"
    )
    _add_kv(table, "Analysis", _styled_value(f"{analysis_mode} | {source_policy} | {cache_policy}"))
    excluded_window = (
        "none"
        if analysis.ignore_lead_seconds == 0.0 and analysis.ignore_trail_seconds == 0.0
        else (
            f"lead={_format_config_seconds(analysis.ignore_lead_seconds)}, "
            f"trail={_format_config_seconds(analysis.ignore_trail_seconds)}"
        )
    )
    _add_kv(table, "Window", _styled_value(excluded_window))

    # ── Rendering ──
    _add_separator(table)
    _add_subheader(table, "Rendering")
    renderer = "FFmpeg" if config.screenshots.use_ffmpeg else "Automatic | VapourSynth preferred"
    _add_kv(table, "Renderer", _styled_value(renderer))
    _add_kv(
        table,
        "Output",
        _styled_value(
            f"{_humanize(overlay_mode.value)} overlay | {_humanize(config.screenshots.geometry_mode.value)} geometry"
        ),
    )
    _add_kv(
        table,
        "Active area",
        _styled_value(_humanize(config.screenshots.active_rect_detection.value)),
    )
    tonemap_settings = _resolve_preview_tonemap_settings(config, request)
    tonemap_text = (
        "Disabled"
        if not tonemap_enabled
        else (
            f"{_humanize(tonemap_settings.preset.value)} | "
            f"{tonemap_settings.target_nits} nits | {_humanize(tonemap_settings.tone_curve.value)}"
        )
    )
    _add_kv(table, "Tone map", _styled_value(tonemap_text))

    # ── Alignment ──
    _add_separator(table)
    _add_subheader(table, "Alignment")
    _add_kv(table, "Mode", _styled_value("Audio alignment" if alignment_enabled else "Disabled"))
    if alignment_enabled:
        ffmpeg_status: StatusPresentation = "OK" if ffmpeg_available else "WARN"
        ffmpeg_text = "available (true)" if ffmpeg_available else "unavailable (false)"
    else:
        ffmpeg_status = "SKIP"
        ffmpeg_text = "not required (alignment disabled)"
    _add_kv(
        table,
        "FFmpeg audio",
        _status_value(ffmpeg_status, ffmpeg_text),
    )
    reuse_policy_label = {
        "disabled": "Do not reuse previous offsets",
        "prompt": "Ask before reusing previous offsets",
        "always": "Reuse previous offsets when valid",
    }[config.audio_alignment.previous_offsets]
    _add_kv(table, "Offsets", _styled_value(reuse_policy_label))
    manual_review_text: str
    if not use_vsview and not force_interactive:
        manual_review_text = "Not configured"
    elif force_interactive:
        manual_review_text = "VSView required"
    else:
        manual_review_text = "VSView requested"
    _add_kv(table, "Review", _styled_value(manual_review_text))
    if vsview_status is not None:
        preview_status: StatusPresentation = (
            "OK" if vsview_status.startswith("available") else "WARN"
        )
        _add_kv(table, "VSView", _status_value(preview_status, vsview_status))

    # ── Review ──
    _add_separator(table)
    _add_subheader(table, "Review")
    report_text = (
        f"{'enabled' if config.report.enable else 'disabled'}; "
        f"auto-open={'enabled' if config.report.auto_open else 'disabled'}"
    )
    _add_kv(
        table,
        "Report",
        _styled_value(report_text.replace("enabled", "Enabled").replace("disabled", "Disabled")),
    )
    _add_kv(
        table,
        "Metadata",
        _styled_value("Lookup disabled" if request.skip_metadata else "TMDB lookup enabled"),
    )

    # ── Publishing ──
    _add_separator(table)
    _add_subheader(table, "Publishing")
    if not upload_enabled:
        upload_text = "disabled by --no-upload" if request.no_upload else "disabled"
    elif report_confirmed_upload:
        upload_text = "confirm after local report"
    else:
        upload_text = "automatic upload"
    _add_kv(
        table,
        "slow.pics",
        _styled_value(f"{_humanize(config.slowpics.visibility.value)} | {upload_text}"),
    )
    actions_text = (
        f"clipboard={'enabled' if config.slowpics.copy_url_to_clipboard else 'disabled'}; "
        f"browser={'enabled' if config.slowpics.open_in_browser else 'disabled'}; "
        f"shortcut={'enabled' if config.slowpics.create_url_shortcut else 'disabled'}"
    )
    _add_kv(table, "Actions", _styled_value(actions_text))
    _add_kv(
        table,
        "Webhook",
        _styled_value("Configured" if config.slowpics.webhook_url else "Not configured"),
    )
    _add_kv(
        table,
        "Cleanup",
        _styled_value(
            "Delete uploaded screenshots when report-safe"
            if config.slowpics.delete_after_upload
            else "Keep local artifacts"
        ),
    )

    console.print(Panel(table, title=f"[{STYLE_HEADER}]Run plan[/]", border_style="cyan"))


# ── Result summary ────────────────────────────────────────────────────────────


def print_result_summary(
    console: Console,
    *,
    result: RunResult,
    quiet: bool,
    post_upload_actions: PostUploadActionResults = (),
    root: Path | None = None,
    verbose: bool = False,
) -> None:
    screenshot_dir = str(result.screenshot_dir) if result.screenshot_dir is not None else None

    if quiet:
        if screenshot_dir is not None:
            console.print(f"Screenshots: {escape(screenshot_dir)}", soft_wrap=True)
        return

    all_post_upload_actions: PostUploadActionResults = (
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
        _add_kv(table, "Cache", _styled_value(result.metrics_cache_status))
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
                _display_path(result.report_path, root=root, verbose=verbose, artifact=True),
            )
        if result.screenshot_dir is not None:
            table.add_row(
                f"  {_status_token('OK')} screenshots",
                _display_path(result.screenshot_dir, root=root, verbose=verbose, artifact=True),
            )

    # ── Publishing ──
    if result.slowpics_url is not None or result.slowpics_upload_confirmation_status in {
        "declined",
        "report_unavailable",
    }:
        _add_separator(table)
        _add_subheader(table, "Publishing")
        if result.slowpics_url is not None:
            table.add_row(
                f"  {_status_token('OK')} slow.pics",
                f"[{STYLE_URL}]{escape(result.slowpics_url)}[/]",
            )
        elif result.slowpics_upload_confirmation_status == "declined":
            table.add_row(
                f"  {_status_token('SKIP')} slow.pics",
                _styled_value("Not uploaded — declined"),
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

    console.print(
        Panel(
            table,
            title=f"[{STYLE_HEADER}]{_status_token(headline_status)} {escape(headline)}[/]",
            border_style="cyan",
        )
    )

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
    action: PostUploadActionResult,
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
    actions: PostUploadActionResults,
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
    action: PostUploadActionResult,
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
