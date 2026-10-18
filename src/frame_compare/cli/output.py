from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.markup import escape

from frame_compare.utils.post_upload_actions import PostUploadActionResult, PostUploadActionResults
from frame_compare.utils.run_warnings import RunWarning, WarningSeverity, WarningSource
from frame_compare.utils.terminal_sections import Section, section_title
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
    glyphs_for_console,
)

if TYPE_CHECKING:
    from frame_compare.orchestration.coordinator import RunResult
    from frame_compare.orchestration.run_inputs import AcquiredRunConfig


STYLE_UNIT = "dim"
STYLE_PATH = "dim"
STYLE_WARN = "yellow"


@dataclass(frozen=True)
class WarningPresentation:
    source: WarningSource
    severity: WarningSeverity
    message: str
    detail: str | None = None
    action: str | None = None


def _styled_value(value: str) -> str:
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
    alignment_enabled: bool,
    ffmpeg_available: bool,
    vsview_requested: bool,
    vsview_status: str | None,
) -> str:
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
    vsview_status: str | None = None
    use_vsview = config.audio_alignment.use_vsview
    force_interactive = config.audio_alignment.force_interactive
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
    input_path = workspace.input_dir
    analysis = config.analysis
    user_frames = analysis.user_frames
    random_frame_count = analysis.random_frame_count
    dark_frame_count = analysis.dark_frame_count
    bright_frame_count = analysis.bright_frame_count
    motion_frame_count = analysis.motion_frame_count
    random_seed = analysis.random_seed
    requested_total = (
        len(user_frames)
        + random_frame_count
        + dark_frame_count
        + bright_frame_count
        + motion_frame_count
    )
    overlay_mode = config.screenshots.overlay_mode
    tonemap_enabled = config.color.enable_tonemap
    alignment_enabled = config.audio_alignment.enable
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
    _add_plan_kv(table, "tools", tools_text)
    _add_plan_kv(table, "offsets", _styled_value(_lower_first(reuse_policy_label)))

    _add_separator(table)
    _add_section(table, "Review", review_text)
    _add_plan_kv(table, "metadata", _styled_value(metadata_text))

    _add_separator(table)
    _add_section(table, "Publishing", publishing_text)
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
        table.add_row("  machine", _dot_join(machine_items))

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
            _add_kv(table, "  shortcut", _shortcut_failure_value(action, glyphs=glyphs))
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

    if result.slowpics_upload_confirmation_status == "report_unavailable":
        _add_kv(table, "slow.pics", "upload skipped because the report could not be confirmed")

    run_segments: list[str] = []
    if result.frame_count > 0:
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
        max_lines = len(warnings) if verbose else 8
        visible = warnings[:max_lines]
        remaining = len(warnings) - len(visible)
        warning_text = _format_warning_panel_text(visible, glyphs=glyphs)
        if remaining > 0:
            warning_text += _format_hidden_warning_counts(warnings[max_lines:], glyphs=glyphs)
        section = Section(
            title=f"[{STYLE_WARN}]{glyphs.warning} Warnings[/]", rail_style=BORDER_PENDING
        )
        for line in warning_text.split("\n"):
            section.add_line(line)
        section.print(console)


def _count_screenshot_files(screenshot_dir: Path) -> int | None:
    try:
        entries = list(screenshot_dir.iterdir())
    except OSError:
        return None
    return sum(1 for entry in entries if entry.is_file() and entry.suffix.lower() == ".png")


def artifact_link(path: Path, *, root: Path | None, verbose: bool = False) -> str:
    display = format_display_path(path, root=root)
    absolute = _absolute_display_path(path, root)
    if not absolute.is_absolute():
        absolute = path.resolve()
    rendered = f"[link={absolute.as_uri()}]{escape(display)}[/link]"
    if verbose and root is not None and display != str(absolute):
        rendered += f" {_styled_unit(f'(absolute: {absolute})')}"
    return rendered


def _slowpics_link(url: str) -> str:
    target = url.replace("[", "%5B").replace("]", "%5D")
    return f"[link={target}][bold {ACCENT} underline]{escape(url)}[/][/link]"


_ROW_WARNING_ACTIONS = ("clipboard", "browser", "shortcut", "webhook")


def _row_warning_count(actions: PostUploadActionResults) -> int:
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
    item = f"[{WARN}]{glyphs.warning}[/] not created"
    reason = None if action.warning is None else action.warning.detail
    if reason:
        item += f" [dim]({escape(reason)})[/]"
    return item


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
                item = f"[{WARN}]{glyphs.warning}[/] browser didn't open"
                reason = None if action.warning is None else action.warning.detail
                if reason:
                    item += f" [dim]({escape(reason)})[/]"
                items.append(item)
    return items


def _warning_presentations(
    warnings: list[RunWarning],
    actions: PostUploadActionResults,
) -> list[WarningPresentation]:
    candidates: list[WarningPresentation] = []
    seen: set[tuple[str, WarningSeverity, str, str | None]] = set()
    action_warnings_by_record = {
        action.warning: _post_upload_warning_presentation(action)
        for action in actions
        if action.warning is not None
    }

    for warning in warnings:
        row = action_warnings_by_record.get(warning)
        if row is None:
            row = WarningPresentation(
                warning.source, warning.severity, warning.message, warning.detail
            )
        key = (row.source, row.severity, row.message, row.detail)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(row)

    for row in action_warnings_by_record.values():
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
    return WarningPresentation(
        source=warning.source,
        severity=warning.severity,
        message=warning.message,
        detail=warning.detail,
        action=action.kind,
    )


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
