from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from rich.columns import Columns
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from frame_compare.utils.post_upload_actions import PostUploadActionResult, PostUploadActionResults
from frame_compare.utils.terminal_theme import (
    ACCENT,
    BORDER_FAILED,
    BORDER_NEUTRAL,
    BORDER_PENDING,
    BORDER_SUCCESS,
    FAIL,
    KEY,
    OK,
    VALUE,
    WARN,
    GlyphSet,
    format_duration,
    glyphs_for_console,
)

if TYPE_CHECKING:
    from frame_compare.config.overrides import TonemapCliOverrides
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.orchestration.coordinator import RunRequest, RunResult
    from frame_compare.vs.types import TonemapSettings

# ── Theme constants ────────────────────────────────────────────────────────────
# Role-based color vocabulary inspired by the legacy CLI layout engine.

STYLE_UNIT = "dim"
STYLE_PATH = "dim"
STYLE_WARN = "yellow"

type WarningPresentationSeverity = Literal["warning", "skipped"]


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
    # S3 VALUE is the terminal default foreground: values carry no style.
    if VALUE:
        return f"[{VALUE}]{escape(value)}[/]"
    return escape(value)


def _styled_unit(value: str) -> str:
    return f"[{STYLE_UNIT}]{escape(value)}[/]"


def _styled_path(value: str) -> str:
    return f"[{STYLE_PATH}]{escape(value)}[/]"


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
) -> str:
    """Render a complete path relative to the workspace when it is contained."""
    display = format_display_path(path, root=root)
    rendered = _styled_path(display)
    absolute = _absolute_display_path(path, root)
    if verbose and root is not None and display != str(absolute):
        rendered += f" {_styled_unit(f'(absolute: {absolute})')}"
    return rendered


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
    table.add_column("key", style=KEY, min_width=22, overflow="fold")
    table.add_column("value", overflow="fold")
    return table


def _add_section(table: Table, name: str, value: str) -> None:
    """Add a section row with the name in accent and the value on the same row."""
    table.add_row(f"[bold {ACCENT}]{name}[/]", value)


def _dot_join(parts: Sequence[str]) -> str:
    """Join plain value segments with the muted `·` separator."""
    return "[dim] · [/]".join(escape(part) for part in parts)


def _lower_first(text: str) -> str:
    """Lower-case the first letter of a sentence-style value."""
    if not text:
        return text
    return text[0].lower() + text[1:]


def _format_tools_row(
    *,
    glyphs: GlyphSet,
    alignment_enabled: bool,
    ffmpeg_available: bool,
    vsview_requested: bool,
    vsview_status: str | None,
) -> str:
    """Format the Run plan tools row with availability notes."""
    if not alignment_enabled:
        ffmpeg_entry = f"{glyphs.skipped} FFmpeg audio"
    elif ffmpeg_available:
        ffmpeg_entry = f"[{OK}]{glyphs.ok}[/] FFmpeg audio"
    else:
        ffmpeg_entry = f"[{WARN}]{glyphs.warning}[/] FFmpeg audio [dim](unavailable)[/]"
    entries = [ffmpeg_entry]
    if vsview_requested:
        if vsview_status is not None and not vsview_status.startswith("available"):
            vsview_entry = f"[{WARN}]{glyphs.warning}[/] VSView"
            if vsview_status.startswith("VSView auto-detection failed"):
                vsview_entry += f" {escape(vsview_status)}"
            elif vsview_status.startswith("probe failed"):
                vsview_entry += f" [dim]{escape(vsview_status)}[/]"
            else:
                vsview_entry += " [dim](unavailable)[/]"
        else:
            vsview_entry = f"[{OK}]{glyphs.ok}[/] VSView"
        entries.append(vsview_entry)
    return "   ".join(entries)


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
    glyphs = glyphs_for_console(console)

    source_policy = config.sources.analysis_source.replace("_", " ")
    cache_policy = (
        "cache only"
        if request.from_cache_only
        else "bypassed"
        if request.no_cache
        else "read and write"
    )
    if analysis.ignore_lead_seconds == 0.0 and analysis.ignore_trail_seconds == 0.0:
        excluded_window = _styled_value("none")
    else:
        excluded_window = _dot_join(
            [
                f"first {format_duration(analysis.ignore_lead_seconds)}",
                f"last {format_duration(analysis.ignore_trail_seconds)}",
            ]
        )
    if config.screenshots.use_ffmpeg:
        renderer = _styled_value("FFmpeg")
    else:
        renderer = _dot_join(["automatic", "VapourSynth preferred"])
    geometry_text = _dot_join(
        [
            f"{config.screenshots.geometry_mode.value.lower()} geometry",
            f"active area {_humanize(config.screenshots.active_rect_detection.value).lower()}",
        ]
    )
    tonemap_settings = _resolve_preview_tonemap_settings(config, request)
    if not tonemap_enabled:
        tonemap_text = _styled_value("disabled")
    else:
        tonemap_text = _dot_join(
            [
                f"{_humanize(tonemap_settings.tone_curve.value)} "
                f"{tonemap_settings.preset.value.lower()}",
                f"{tonemap_settings.target_nits} nits",
            ]
        )
    if not alignment_enabled:
        alignment_text = "disabled"
    elif force_interactive:
        alignment_text = "audio, VSView required"
    elif use_vsview:
        alignment_text = "audio, then VSView review"
    else:
        alignment_text = "audio"
    reuse_policy_label = {
        "disabled": "Do not reuse previous offsets",
        "prompt": "Ask before reusing previous offsets",
        "always": "Reuse previous offsets when valid",
    }[config.audio_alignment.previous_offsets]
    tools_text = _format_tools_row(
        glyphs=glyphs,
        alignment_enabled=alignment_enabled,
        ffmpeg_available=ffmpeg_available,
        vsview_requested=use_vsview or force_interactive,
        vsview_status=vsview_status,
    )
    if not config.report.enable:
        review_text = _styled_value("disabled")
    elif config.report.auto_open:
        review_text = _dot_join(["HTML report", "opens when done"])
    else:
        review_text = _styled_value("HTML report")
    metadata_text = "TMDB lookup" if not request.skip_metadata else "disabled"
    if not upload_enabled:
        publishing_text = _styled_value(
            "disabled by --no-upload" if request.no_upload else "disabled"
        )
    elif report_confirmed_upload:
        publishing_text = _dot_join(
            [
                "slow.pics",
                config.slowpics.visibility.value.lower(),
                "ask after the local report",
            ]
        )
    else:
        publishing_text = _dot_join(
            [
                "slow.pics",
                config.slowpics.visibility.value.lower(),
                "automatic upload",
            ]
        )
    enabled_actions: list[str] = []
    if config.slowpics.copy_url_to_clipboard:
        enabled_actions.append("copy URL")
    if config.slowpics.open_in_browser:
        enabled_actions.append("open browser")
    if config.slowpics.create_url_shortcut:
        enabled_actions.append("create shortcut")
    after_upload_text = _dot_join(enabled_actions) if enabled_actions else _styled_value("none")
    cleanup_text = (
        "Delete uploaded screenshots when report-safe"
        if config.slowpics.delete_after_upload
        else "Keep local artifacts"
    )

    table = _group_table()

    # ── Workspace ──
    _add_section(table, "Workspace", _styled_path(str(workspace_root)))
    _add_kv(table, "config", _display_path(config_path, root=workspace_root, verbose=verbose))
    _add_kv(table, "input", _display_path(input_path, root=workspace_root, verbose=verbose))
    _add_kv(
        table,
        "output",
        _display_path(workspace.generated_root, root=workspace_root, verbose=verbose),
    )

    # ── Frames ──
    _add_separator(table)
    _add_section(table, "Frames", _styled_value(f"{requested_total} total"))
    categories = [
        f"{count} {name}"
        for name, count in (
            ("user", len(user_frames)),
            ("random", random_frame_count),
            ("dark", dark_frame_count),
            ("bright", bright_frame_count),
            ("motion", motion_frame_count),
        )
        if count
    ]
    _add_kv(table, "mix", _dot_join(categories))
    if user_frames:
        _add_kv(table, "user frames", _styled_value(", ".join(str(frame) for frame in user_frames)))
    analysis_parts = [
        f"{_humanize(config.analysis.performance_mode.value).lower()} profile",
        f"{source_policy} source",
    ]
    if request.skip_analysis:
        analysis_parts.append("skipped for this run")
    _add_kv(table, "analysis", _dot_join(analysis_parts))
    _add_kv(table, "cache", _styled_value(cache_policy))
    _add_kv(table, "skip", excluded_window)
    if random_frame_count:
        _add_kv(table, "seed", _styled_value(str(random_seed)))

    # ── Rendering ──
    _add_separator(table)
    _add_section(table, "Rendering", renderer)
    _add_kv(table, "overlay", _styled_value(overlay_mode.value.lower()))
    _add_kv(table, "geometry", geometry_text)
    _add_kv(table, "tone map", tonemap_text)

    # ── Alignment ──
    _add_separator(table)
    _add_section(table, "Alignment", _styled_value(alignment_text))
    _add_kv(table, "tools", tools_text)
    _add_kv(table, "offsets", _styled_value(_lower_first(reuse_policy_label)))

    # ── Review ──
    _add_separator(table)
    _add_section(table, "Review", review_text)
    _add_kv(table, "metadata", _styled_value(metadata_text))

    # ── Publishing ──
    _add_separator(table)
    _add_section(table, "Publishing", publishing_text)
    _add_kv(table, "after upload", after_upload_text)
    if config.slowpics.webhook_url:
        _add_kv(table, "webhook", _styled_value("configured"))
    else:
        _add_kv(table, "webhook", "[dim]not configured[/]")
    _add_kv(table, "cleanup", _styled_value(_lower_first(cleanup_text)))

    console.print(
        Panel(
            table,
            title=f"[bold {ACCENT}]Run plan[/]",
            title_align="left",
            border_style=BORDER_NEUTRAL,
        )
    )


# ── Result summary ────────────────────────────────────────────────────────────


def _add_time_rows(table: Table, *, result: RunResult) -> None:
    """Add the machine/user time rows to the result summary.

    The review wait is memory-only telemetry: machine times exclude it, and it
    is never added to phase timings, the run record, or JSON output.
    """
    timings = result.phase_timings
    review_seconds = max(0.0, result.vsview_review_seconds)
    table.add_row("time", f"{format_duration(result.duration_seconds)} total")

    machine_items: list[str] = []
    setup_seconds = timings.get("preflight", 0.0) + timings.get("load_sources", 0.0)
    if setup_seconds > 0.0:
        machine_items.append(f"setup {format_duration(setup_seconds)}")
    analyze_seconds = timings.get("analyze", 0.0)
    if analyze_seconds > 0.0:
        machine_items.append(f"analyze {format_duration(analyze_seconds)}")
    align_seconds = max(0.0, timings.get("align", 0.0) - review_seconds)
    if align_seconds > 0.0:
        machine_items.append(f"align {format_duration(align_seconds)}")
    render_seconds = timings.get("render", 0.0)
    if render_seconds > 0.0:
        machine_items.append(f"render {format_duration(render_seconds)}")
    upload_seconds = timings.get("publish", 0.0)
    if upload_seconds > 0.0:
        machine_items.append(f"upload {format_duration(upload_seconds)}")
    if machine_items:
        table.add_row("  machine", Columns(machine_items, equal=False, padding=(0, 4)))

    you_items: list[str] = []
    if review_seconds > 0.0:
        you_items.append(f"VSView review {format_duration(review_seconds)}")
    prompts_seconds = timings.get("confirm_slowpics_upload", 0.0)
    if prompts_seconds > 0.0:
        you_items.append(f"prompts {format_duration(prompts_seconds)}")
    if you_items:
        table.add_row("  you", Columns(you_items, equal=False, padding=(0, 4)))


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
    row_warning_count = _row_warning_count(all_post_upload_actions)
    warnings = [
        presentation
        for presentation in _warning_presentations(result.warnings, all_post_upload_actions)
        if presentation.action not in _ROW_WARNING_ACTIONS
    ]
    glyphs = glyphs_for_console(console)
    if not result.success:
        title = f"[bold {FAIL}]{glyphs.failed} Comparison failed[/]"
        border_style = BORDER_FAILED
    elif warnings or row_warning_count:
        warning_count = row_warning_count + len(warnings)
        noun = "warning" if warning_count == 1 else "warnings"
        title = (
            f"[bold {WARN}]{glyphs.warning} Comparison complete[/] [dim]· {warning_count} {noun}[/]"
        )
        border_style = BORDER_PENDING
    else:
        title = f"[bold {OK}]{glyphs.ok} Comparison complete[/]"
        border_style = BORDER_SUCCESS
    table = _group_table()

    # ── slow.pics ──
    if result.slowpics_url is not None or result.slowpics_upload_confirmation_status in {
        "declined",
        "report_unavailable",
    }:
        if result.slowpics_url is not None:
            slowpics_value = _slowpics_link(result.slowpics_url)
        elif result.slowpics_upload_confirmation_status == "declined":
            slowpics_value = "[dim]not uploaded (declined)[/]"
        else:
            slowpics_value = _styled_value(
                "upload skipped because report confirmation was unavailable"
            )
        _add_kv(table, "slow.pics", slowpics_value)

    # ── Follow-up actions ──
    followup_items = _followup_action_items(all_post_upload_actions, glyphs=glyphs)
    if followup_items:
        table.add_row("", Columns(followup_items, equal=False, padding=(0, 4)))

    # ── Shortcut ──
    for action in all_post_upload_actions:
        if action.kind != "shortcut":
            continue
        if action.success and action.path is not None:
            _add_kv(
                table,
                "  shortcut",
                _artifact_link(action.path, root=root, verbose=verbose),
            )
            break
        if not action.success:
            _add_kv(table, "  shortcut", _shortcut_failure_value(action, glyphs=glyphs))
            break

    # ── Webhook ──
    for action in all_post_upload_actions:
        if action.kind != "webhook":
            continue
        if action.success:
            _add_kv(table, "  webhook", f"[{OK}]{glyphs.ok} delivered[/]")
        else:
            _add_kv(table, "  webhook", f"[{WARN}]{glyphs.warning} delivery failed[/]")
        break

    # ── Report and screenshots ──
    if result.report_path is not None:
        _add_kv(table, "report", _artifact_link(result.report_path, root=root, verbose=verbose))
    if result.screenshot_dir is not None:
        screenshots_value = _artifact_link(result.screenshot_dir, root=root, verbose=verbose)
        screenshot_total = _count_screenshot_files(result.screenshot_dir)
        if screenshot_total is not None:
            unit = "file" if screenshot_total == 1 else "files"
            screenshots_value += f"  [dim]{screenshot_total} {unit}[/]"
        _add_kv(table, "screenshots", screenshots_value)

    # ── Run ──
    run_segments: list[str] = []
    if result.frame_count > 0:
        unit = "frame" if result.frame_count == 1 else "frames"
        run_segments.append(f"{result.frame_count} {unit}")
    if result.clips_processed > 0:
        unit = "source" if result.clips_processed == 1 else "sources"
        run_segments.append(f"{result.clips_processed} {unit}")
    if (
        result.metrics_cache_status != "skipped"
        or result.frame_count > 0
        or result.clips_processed > 0
    ):
        run_segments.append(f"cache {result.metrics_cache_status}")
    if run_segments:
        if table.rows:
            table.add_row("", "")
        _add_kv(table, "run", _dot_join(run_segments))

    # ── Time (machine vs user) ──
    if table.rows:
        table.add_row("", "")
    _add_time_rows(table, result=result)

    console.print(
        Panel(
            table,
            title=title,
            title_align="left",
            border_style=border_style,
        )
    )

    if warnings:
        max_lines = len(warnings) if verbose else 8
        visible = warnings[:max_lines]
        remaining = len(warnings) - len(visible)
        warning_text = _format_warning_panel_text(visible, glyphs=glyphs)
        if remaining > 0:
            warning_text += _format_hidden_warning_counts(warnings[max_lines:], glyphs=glyphs)
        console.print(
            Panel(
                warning_text,
                title=f"[{STYLE_WARN}]Warnings[/]",
                border_style=BORDER_PENDING,
                expand=False,
            )
        )


def _count_screenshot_files(screenshot_dir: Path) -> int | None:
    """Count the image files in the screenshots directory, if it exists."""
    try:
        entries = list(screenshot_dir.iterdir())
    except OSError:
        return None
    return sum(1 for entry in entries if entry.is_file() and entry.suffix.lower() == ".png")


def _artifact_link(path: Path, *, root: Path | None, verbose: bool = False) -> str:
    """Render an artifact path as a Rich hyperlink with a workspace-relative label."""
    display = format_display_path(path, root=root)
    absolute = _absolute_display_path(path, root)
    if not absolute.is_absolute():
        absolute = path.resolve()
    rendered = f"[link={absolute.as_uri()}]{escape(display)}[/link]"
    if verbose and root is not None and display != str(absolute):
        rendered += f" {_styled_unit(f'(absolute: {absolute})')}"
    return rendered


def _slowpics_link(url: str) -> str:
    """Render the slow.pics URL as an accent hyperlink safe for bracketed URLs."""
    target = url.replace("[", "%5B").replace("]", "%5D")
    return f"[link={target}][bold {ACCENT} underline]{escape(url)}[/][/link]"


_BROWSER_FAILURE_PREFIX = "slow.pics browser: failed to open URL"


_ROW_WARNING_ACTIONS = ("clipboard", "browser", "shortcut", "webhook")

_SHORTCUT_FAILURE_PREFIX = "slow.pics shortcut:"


def _row_warning_count(actions: PostUploadActionResults) -> int:
    """Count follow-up failures shown on their own summary row."""
    count = sum(
        1 for action in actions if not action.success and action.kind in ("clipboard", "browser")
    )
    for kind in ("shortcut", "webhook"):
        for action in actions:
            if action.kind == kind:
                if not action.success:
                    count += 1
                break
    return count


def _shortcut_failure_value(action: PostUploadActionResult, *, glyphs: GlyphSet) -> str:
    """Render a failed shortcut action for the `  shortcut` summary row."""
    item = f"[{WARN}]{glyphs.warning}[/] not created"
    reason = ""
    if action.warning is not None and action.warning.startswith(_SHORTCUT_FAILURE_PREFIX):
        reason = action.warning[len(_SHORTCUT_FAILURE_PREFIX) :].lstrip(": ")
    elif action.warning is not None:
        reason = action.warning
    if reason:
        item += f" [dim]({escape(reason)})[/]"
    return item


def _followup_action_items(actions: PostUploadActionResults, *, glyphs: GlyphSet) -> list[str]:
    """Build the unlabelled follow-up result items for the Columns row."""
    items: list[str] = []
    for action in actions:
        if action.kind == "clipboard":
            if action.success:
                items.append(f"[{OK}]{glyphs.ok}[/] URL copied")
            else:
                items.append(f"[{WARN}]{glyphs.warning}[/] URL not copied")
        elif action.kind == "browser":
            if action.success:
                items.append(f"[{OK}]{glyphs.ok}[/] opened in browser")
            else:
                item = f"[{WARN}]{glyphs.warning}[/] browser didn't open"
                reason = ""
                if action.warning is not None and action.warning.startswith(
                    _BROWSER_FAILURE_PREFIX
                ):
                    reason = action.warning[len(_BROWSER_FAILURE_PREFIX) :].lstrip(": ")
                elif action.warning is not None:
                    reason = action.warning
                if reason:
                    item += f" [dim]({escape(reason)})[/]"
                items.append(item)
    return items


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


def _format_warning_panel_text(warnings: list[WarningPresentation], *, glyphs: GlyphSet) -> str:
    lines: list[str] = []
    current_source: str | None = None
    for warning in warnings:
        if warning.source != current_source:
            if lines:
                lines.append("")
            lines.append(f"[bold {ACCENT}]{escape(warning.source)}[/]")
            current_source = warning.source
        if warning.severity == "skipped":
            lines.append(f"[dim]{glyphs.skipped} {escape(warning.message)}[/]")
        else:
            lines.append(f"[{WARN}]{glyphs.warning}[/] {escape(warning.message)}")
        if warning.detail is not None:
            lines.append(f"  [dim]{escape(warning.detail)}[/]")
    return "\n".join(lines)


def _format_hidden_warning_counts(hidden: list[WarningPresentation], *, glyphs: GlyphSet) -> str:
    counts_by_source: dict[str, int] = {}
    for warning in hidden:
        counts_by_source[warning.source] = counts_by_source.get(warning.source, 0) + 1

    count_text = ", ".join(
        f"{escape(source)}={count}" for source, count in sorted(counts_by_source.items())
    )
    return f"\n[{WARN}]{glyphs.warning}[/] ... ({len(hidden)} more) hidden by source: {count_text}"
