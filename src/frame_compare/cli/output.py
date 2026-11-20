from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markup import escape

from frame_compare.utils.artifact_paths import (
    absolute_display_path,
    artifact_link,
    format_display_path,
)
from frame_compare.utils.post_upload_actions import PostUploadActionResults
from frame_compare.utils.progress import AlignmentSummaryValue
from frame_compare.utils.run_warnings import RunWarning, WarningSource
from frame_compare.utils.terminal_sections import Section, section_title, take_run_block_separator
from frame_compare.utils.terminal_theme import (
    ACCENT,
    BORDER_FAILED,
    BORDER_NEUTRAL,
    BORDER_PENDING,
    BORDER_SUCCESS,
    FAIL,
    OK,
    VALUE,
    WARN,
    GlyphSet,
    format_duration,
    format_exclusion_duration,
    glyphs_for_console,
    print_with_paths,
)

if TYPE_CHECKING:
    from frame_compare.orchestration.coordinator import RunResult
    from frame_compare.orchestration.run_inputs import AcquiredRunConfig
    from frame_compare.orchestration.types import InterruptedRun


STYLE_UNIT = "dim"
STYLE_PATH = "dim"
STYLE_WARN = "yellow"


def _styled_value(value: str) -> str:
    if VALUE:
        return f"[{VALUE}]{escape(value)}[/]"
    return escape(value)


def _styled_unit(value: str) -> str:
    return f"[{STYLE_UNIT}]{escape(value)}[/]"


def _styled_path(value: str) -> str:
    return f"[{STYLE_PATH}]{escape(value)}[/]"


def _display_path(
    path: Path,
    *,
    root: Path | None,
    verbose: bool = False,
) -> str:
    display = format_display_path(path, root=root)
    rendered = _styled_path(display)
    absolute = absolute_display_path(path, root)
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


def _add_section(table: Section, name: str, value: str) -> None:
    table.add_row(f"[bold {ACCENT} not dim]{name}[/]", value)


def _dot_join(parts: Sequence[str]) -> str:
    return "[dim] · [/]".join(escape(part) for part in parts)


def _lower_first(text: str) -> str:
    if not text:
        return text
    return text[0].lower() + text[1:]


def _format_tools_row(
    *,
    glyphs: GlyphSet,
    ffmpeg_available: bool,
    vsview_requested: bool,
    vsview_status: str | None,
) -> str:
    if ffmpeg_available:
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
    return "[dim] · [/]".join(entries)


def _add_kv(table: Section, key: str, value: str) -> None:
    table.add_row(key, value)


def _add_plan_kv(table: Section, key: str, value: str) -> None:
    table.add_row(f"  {key}", value)


def _add_separator(table: Section) -> None:
    table.add_row("", "")


def print_at_a_glance(
    console: Console,
    *,
    inputs: AcquiredRunConfig,
    no_cache: bool,
    from_cache_only: bool,
    skip_analysis: bool,
    skip_metadata: bool,
    no_upload_flag: bool,
    verbose: bool = False,
) -> None:
    from frame_compare.orchestration.run_inputs import resolve_run_workspace
    from frame_compare.render.prepare import resolve_tonemap_settings

    config = inputs.config
    root, config_path = inputs.root, inputs.config_path
    workspace = resolve_run_workspace(inputs)
    workspace_root = root.resolve()
    input_path = workspace.input_dir
    analysis = config.analysis
    user_frames = analysis.user_frames
    random_frame_count = analysis.random_frame_count
    dark_frame_count = analysis.dark_frame_count
    bright_frame_count = analysis.bright_frame_count
    motion_frame_count = analysis.motion_frame_count
    random_seed = analysis.random_seed
    requested_total = analysis.requested_frame_count
    overlay_mode = config.screenshots.overlay_mode
    tonemap_enabled = config.color.enable_tonemap
    alignment_enabled = config.audio_alignment.enable
    use_vsview = config.audio_alignment.use_vsview
    force_interactive = config.audio_alignment.force_interactive
    upload_enabled = config.slowpics.auto_upload
    report_confirmed_upload = upload_enabled and config.slowpics.confirm_upload_after_report
    glyphs = glyphs_for_console(console)

    source_policy = config.sources.analysis_source.replace("_", " ")
    cache_policy = (
        "cache only"
        if from_cache_only
        else "refresh current entry"
        if no_cache
        else "read and write"
    )
    if analysis.ignore_lead_seconds == 0.0 and analysis.ignore_trail_seconds == 0.0:
        excluded_window = _styled_value("none")
    else:
        excluded_window = _dot_join(
            [
                f"first {format_exclusion_duration(analysis.ignore_lead_seconds)}",
                f"last {format_exclusion_duration(analysis.ignore_trail_seconds)}",
            ]
        )
    renderer = _styled_value("VapourSynth")
    geometry_text = _dot_join(
        [
            f"{config.screenshots.geometry_mode.value.lower()} geometry",
            f"active area {_humanize(config.screenshots.active_rect_detection.value).lower()}",
        ]
    )
    tonemap_settings = resolve_tonemap_settings(config)
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
    if not config.report.enable:
        review_text = _styled_value("disabled")
    elif config.report.auto_open:
        review_text = _dot_join(["HTML report", "opens when done"])
    else:
        review_text = _styled_value("HTML report")
    metadata_text = "TMDB lookup" if not skip_metadata else "disabled"
    if not upload_enabled:
        publishing_text = _styled_value("disabled by --no-upload" if no_upload_flag else "disabled")
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

    table = Section()

    _add_section(table, "Workspace", _styled_path(str(workspace_root)))
    _add_plan_kv(table, "config", _display_path(config_path, root=workspace_root, verbose=verbose))
    _add_plan_kv(table, "input", _display_path(input_path, root=workspace_root, verbose=verbose))
    _add_plan_kv(
        table,
        "output",
        _display_path(workspace.generated_root, root=workspace_root, verbose=verbose),
    )

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
    _add_plan_kv(table, "mix", _dot_join(categories))
    if user_frames:
        _add_plan_kv(
            table, "user frames", _styled_value(", ".join(str(frame) for frame in user_frames))
        )
    analysis_parts = [
        f"{_humanize(config.analysis.performance_mode.value).lower()} profile",
        f"{source_policy} source",
    ]
    if skip_analysis:
        analysis_parts.append("skipped for this run")
    _add_plan_kv(table, "analysis", _dot_join(analysis_parts))
    _add_plan_kv(table, "cache", _styled_value(cache_policy))
    _add_plan_kv(table, "skip", excluded_window)
    if random_frame_count:
        _add_plan_kv(table, "seed", _styled_value(str(random_seed)))

    _add_separator(table)
    _add_section(table, "Rendering", renderer)
    _add_plan_kv(table, "overlay", _styled_value(overlay_mode.value.lower()))
    _add_plan_kv(table, "geometry", geometry_text)
    _add_plan_kv(table, "tone map", tonemap_text)

    _add_separator(table)
    _add_section(table, "Alignment", _styled_value(alignment_text))
    if alignment_enabled:
        vsview_status: str | None = None
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
        reuse_policy_label = {
            "disabled": "Do not reuse previous offsets",
            "prompt": "Ask before reusing previous offsets",
            "always": "Reuse previous offsets when valid",
        }[config.audio_alignment.previous_offsets]
        tools_text = _format_tools_row(
            glyphs=glyphs,
            ffmpeg_available=ffmpeg_available,
            vsview_requested=use_vsview or force_interactive,
            vsview_status=vsview_status,
        )
        _add_plan_kv(table, "tools", tools_text)
        _add_plan_kv(table, "offsets", _styled_value(_lower_first(reuse_policy_label)))

    _add_separator(table)
    _add_section(table, "Review", review_text)
    _add_plan_kv(table, "metadata", _styled_value(metadata_text))

    _add_separator(table)
    _add_section(table, "Publishing", publishing_text)
    if upload_enabled:
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
        _add_plan_kv(table, "after upload", after_upload_text)
        if config.slowpics.webhook_url:
            _add_plan_kv(table, "webhook", _styled_value("configured"))
        else:
            _add_plan_kv(table, "webhook", "[dim]not configured[/]")
        _add_plan_kv(table, "cleanup", _styled_value(_lower_first(cleanup_text)))

    table.title = section_title("Run plan")
    table.rail_style = BORDER_NEUTRAL
    table.print(console)


def _add_time_rows(table: Section, *, result: RunResult) -> None:
    timings = result.phase_timings
    review_seconds = max(0.0, result.vsview_review_seconds)
    _add_kv(table, "time", f"{format_duration(result.duration_seconds)} total")

    phase_items: list[str] = []
    setup_seconds = timings.get("preflight", 0.0) + timings.get("load_sources", 0.0)
    if setup_seconds > 0.0:
        phase_items.append(f"setup {format_duration(setup_seconds)}")
    analyze_seconds = timings.get("analyze", 0.0)
    if analyze_seconds > 0.0:
        phase_items.append(f"analyze {format_duration(analyze_seconds)}")
    align_seconds = max(0.0, timings.get("align", 0.0) - review_seconds)
    if align_seconds > 0.0:
        phase_items.append(f"align {format_duration(align_seconds)}")
    render_seconds = timings.get("render", 0.0)
    if render_seconds > 0.0:
        phase_items.append(f"render {format_duration(render_seconds)}")
    upload_seconds = timings.get("publish", 0.0)
    if upload_seconds > 0.0:
        phase_items.append(f"upload {format_duration(upload_seconds)}")
    if phase_items:
        table.add_row("  phases", _dot_join(phase_items))

    you_items: list[str] = []
    if review_seconds > 0.0:
        you_items.append(f"VSView review {format_duration(review_seconds)}")
    prompts_seconds = timings.get("confirm_slowpics_upload", 0.0)
    if prompts_seconds > 0.0:
        you_items.append(f"prompts {format_duration(prompts_seconds)}")
    if you_items:
        table.add_row("  you", _dot_join(you_items))


def print_result_summary(
    console: Console,
    *,
    result: RunResult,
    quiet: bool,
    planned_frames: int | None = None,
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
    glyphs = glyphs_for_console(console)
    if not result.success:
        title = f"[bold {FAIL}]{glyphs.failed} Comparison failed[/]"
        border_style = BORDER_FAILED
    elif warnings:
        warning_count = len(warnings)
        noun = "warning" if warning_count == 1 else "warnings"
        title = (
            f"[bold {WARN}]{glyphs.warning} Comparison complete[/] [dim]· {warning_count} {noun}[/]"
        )
        border_style = BORDER_PENDING
    else:
        title = f"[bold {OK}]{glyphs.ok} Comparison complete[/]"
        border_style = BORDER_SUCCESS
    table = Section()

    if result.slowpics_url is not None:
        _add_kv(table, "slow.pics", _slowpics_link(result.slowpics_url))

    followup_items = _followup_action_items(all_post_upload_actions, glyphs=glyphs)
    if followup_items:
        table.add_row("", "[dim] · [/]".join(followup_items))

    for action in all_post_upload_actions:
        if action.kind != "shortcut":
            continue
        if action.success and action.path is not None:
            _add_kv(
                table,
                "  shortcut",
                artifact_link(action.path, root=root, verbose=verbose),
            )
            break
        if not action.success:
            _add_kv(table, "  shortcut", f"[{WARN}]{glyphs.warning}[/] not created")
            break

    for action in all_post_upload_actions:
        if action.kind != "webhook":
            continue
        if action.success:
            _add_kv(table, "  webhook", f"[{OK}]{glyphs.ok} delivered[/]")
        else:
            _add_kv(table, "  webhook", f"[{WARN}]{glyphs.warning} delivery failed[/]")
        break

    if result.report_path is not None:
        _add_kv(table, "report", artifact_link(result.report_path, root=root, verbose=verbose))
    if result.screenshot_dir is not None:
        screenshots_value = artifact_link(result.screenshot_dir, root=root, verbose=verbose)
        screenshot_total = _count_screenshot_files(result.screenshot_dir)
        if screenshot_total is not None:
            unit = "file" if screenshot_total == 1 else "files"
            screenshots_value += f"  [dim]{screenshot_total} {unit}[/]"
        _add_kv(table, "screenshots", screenshots_value)

    if result.alignment_summary is not None:
        table.add_row("alignment", AlignmentSummaryValue(result.alignment_summary))
    if result.alignment_diagnostics_dir is not None:
        _add_kv(
            table,
            "diagnostics",
            artifact_link(result.alignment_diagnostics_dir, root=root, verbose=verbose),
        )

    if result.slowpics_upload_confirmation_status == "report_unavailable":
        _add_kv(table, "slow.pics", "upload skipped because the report could not be confirmed")

    run_segments: list[str] = []
    if planned_frames is not None and result.frame_count != planned_frames:
        unit = "frame" if planned_frames == 1 else "frames"
        run_segments.append(f"{result.frame_count} of {planned_frames} {unit}")
    elif result.frame_count > 0:
        unit = "frame" if result.frame_count == 1 else "frames"
        run_segments.append(f"{result.frame_count} {unit}")
    if result.clips_processed > 0:
        unit = "source" if result.clips_processed == 1 else "sources"
        run_segments.append(f"{result.clips_processed} {unit}")
    if result.metrics_cache_status == "hit":
        run_segments.append("analysis cached")
    elif result.metrics_cache_status == "miss":
        run_segments.append("analysis computed")
    if run_segments:
        if table.rows:
            table.add_row("", "")
        _add_kv(table, "run", _dot_join(run_segments))

    _add_time_rows(table, result=result)

    table.title = title
    table.rail_style = border_style
    table.print(console)

    if warnings:
        warning_text = _format_warning_panel_text(warnings, glyphs=glyphs)
        section = Section(
            title=f"[{STYLE_WARN}]{glyphs.warning} Warnings[/]", rail_style=BORDER_PENDING
        )
        for line in warning_text.split("\n"):
            section.add_line(line)
        section.print(console)


def print_interruption(
    console: Console, interruption: InterruptedRun | None, *, root: Path
) -> None:
    if take_run_block_separator():
        console.print()
    glyph = glyphs_for_console(console).warning
    phase = None if interruption is None else interruption.phase
    title = "Interrupted" if phase is None else f"Interrupted during {phase}"
    console.print(f"[bold {WARN}]{glyph} {escape(title)}[/]")
    if interruption is None:
        return

    workspace = interruption.workspace
    if workspace is not None and workspace.run_dir is not None:
        kept = _count_screenshot_files(workspace.screenshots_dir, missing_is_empty=True)
        if kept is not None:
            path = format_display_path(workspace.run_dir, root=root)
            print_with_paths(
                console,
                f"  kept      {kept} of {interruption.planned_screenshots} screenshots · {escape(path)}",
                (path,),
            )

    reusable = [
        name
        for name, written in (
            ("analysis", interruption.analysis_cache_written),
            ("alignment", interruption.alignment_cache_written),
        )
        if written
    ]
    if reusable:
        console.print(f"  next run  reuses cached {' and '.join(reusable)}")


def _count_screenshot_files(screenshot_dir: Path, *, missing_is_empty: bool = False) -> int | None:
    try:
        entries = list(screenshot_dir.iterdir())
    except FileNotFoundError:
        return 0 if missing_is_empty else None
    except OSError:
        return None
    return sum(1 for entry in entries if entry.is_file() and entry.suffix.lower() == ".png")


def _slowpics_link(url: str) -> str:
    target = url.replace("[", "%5B").replace("]", "%5D")
    return f"[link={target}][bold {ACCENT} underline]{escape(url)}[/][/link]"


def _followup_action_items(actions: PostUploadActionResults, *, glyphs: GlyphSet) -> list[str]:
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
                items.append(f"[{WARN}]{glyphs.warning}[/] browser didn't open")
    return items


def _warning_presentations(
    warnings: list[RunWarning],
    actions: PostUploadActionResults,
) -> list[RunWarning]:
    recorded = [*warnings, *(action.warning for action in actions if action.warning is not None)]
    grouped: dict[WarningSource, dict[RunWarning, None]] = {}
    for warning in recorded:
        grouped.setdefault(warning.source, {})[warning] = None
    return [warning for group in grouped.values() for warning in group]


def _format_warning_panel_text(warnings: list[RunWarning], *, glyphs: GlyphSet) -> str:
    lines: list[str] = []
    group_by_source = len({warning.source for warning in warnings}) > 1
    current_source: str | None = None
    for warning in warnings:
        if group_by_source and warning.source != current_source:
            if lines:
                lines.append("")
            lines.append(f"[bold {ACCENT}]{escape(warning.source)}[/]")
            current_source = warning.source
        message = escape(warning.message)
        if warning.severity == "skipped":
            lines.append(f"[dim]{glyphs.skipped} {message}[/]")
        else:
            lines.append(f"[{WARN}]{glyphs.warning}[/] {message}")
        if warning.detail is not None:
            lines.append(f"  [dim]{escape(warning.detail)}[/]")
    return "\n".join(lines)
