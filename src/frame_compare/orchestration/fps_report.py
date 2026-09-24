"""Consolidated FPS diagnostics reporting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import structlog
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from frame_compare.orchestration.context import ClipState
from frame_compare.orchestration.presentation import clip_role, report_console_width
from frame_compare.services.release_identity import (
    ReleaseIdentity,
    ShortNameSource,
    common_content_identity,
    format_compact_identity,
    format_content_identity,
    format_release_descriptor,
    short_source_names,
)
from frame_compare.utils.terminal_theme import (
    ACCENT,
    BORDER_NEUTRAL,
    OK,
    WARN,
    format_duration,
    glyphs_for_console,
    human_console,
)

_ANALYSIS_SOURCE_PREFIX = "Analysis source: "

_ANALYSIS_SOURCE_POLICIES = {
    "fastest-source policy": "fastest to decode",
    "configured policy": "configured",
}


def _analysis_source_rich_value(diagnostic: str, *, short_names: Sequence[str]) -> str:
    """Translate the stored analysis-source diagnostic to its Rich line.

    The stored text keeps the original log/JSON wording
    ("Analysis source: {role} | selected by ... policy"); only the Rich
    rendering shows the plan's short-name line.
    """
    value = diagnostic[len(_ANALYSIS_SOURCE_PREFIX) :]
    role, separator, policy = value.partition(" | selected by ")
    if separator and policy in _ANALYSIS_SOURCE_POLICIES:
        for index in range(len(short_names)):
            if clip_role(index) == role:
                return f"{short_names[index]} ({_ANALYSIS_SOURCE_POLICIES[policy]})"
    return value


log = structlog.get_logger()


@dataclass(frozen=True)
class FpsReportClip:
    """Immutable per-clip FPS diagnostics entry."""

    path: Path
    label: str
    width: int
    height: int
    num_frames: int
    is_hdr: bool
    source_fps: Fraction
    effective_fps: Fraction
    fps_divergent: bool
    note: str | None
    size_bytes: int = 0
    release_identity: ReleaseIdentity | None = None
    label_is_explicit: bool = False


def build_consolidated_fps_report(
    reference: ClipState, comparisons: Sequence[ClipState]
) -> tuple[FpsReportClip, ...]:
    """Return a deterministic, ordered per-clip FPS report.

    Reference first, then comparisons in input order.
    """
    ordered = [reference, *comparisons]
    clips: list[FpsReportClip] = []
    for clip in ordered:
        clips.append(
            FpsReportClip(
                path=clip.path,
                label=clip.label,
                width=clip.probe.width,
                height=clip.probe.height,
                num_frames=clip.probe.num_frames,
                is_hdr=clip.probe.is_hdr,
                source_fps=clip.source_fps,
                effective_fps=clip.effective_fps,
                fps_divergent=clip.effective_fps != clip.source_fps,
                note=None,
                size_bytes=clip.probe.fingerprint.size_bytes,
                release_identity=clip.release_identity,
                label_is_explicit=clip.label_is_explicit,
            )
        )
    return tuple(clips)


def _format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _fps_decimal_text(value: Fraction) -> str:
    return f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")


def _format_fps_decimal(value: Fraction) -> str:
    return f"{_fps_decimal_text(value)} fps"


def _format_runtime(num_frames: int, fps: Fraction) -> str:
    """Format H:MM:SS from a frame count and rate, floored."""
    fps_value = float(fps)
    total_seconds = int(num_frames / fps_value) if fps_value > 0 else 0
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _join_names(names: Sequence[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _format_fps_value(value: Fraction) -> str:
    return f"{_format_fps_decimal(value)} ({_format_fraction(value)})"


def _fraction_parts(value: Fraction) -> tuple[int, int]:
    return value.numerator, value.denominator


def _serialize_clip(clip: FpsReportClip) -> dict[str, Any]:
    source_num, source_den = _fraction_parts(clip.source_fps)
    effective_num, effective_den = _fraction_parts(clip.effective_fps)
    return {
        "path": str(clip.path),
        "label": clip.label,
        "width": clip.width,
        "height": clip.height,
        "num_frames": clip.num_frames,
        "is_hdr": clip.is_hdr,
        "source_fps_num": source_num,
        "source_fps_den": source_den,
        "effective_fps_num": effective_num,
        "effective_fps_den": effective_den,
        "fps_divergent": clip.fps_divergent,
        "note": clip.note,
    }


def _stage_label(stage: str) -> str:
    if stage == "after_load_sources":
        return "After Load Sources"
    if stage == "after_align":
        return "After Alignment"
    return stage.replace("_", " ").title()


def _format_fps_transition(clip: FpsReportClip) -> str:
    source_fps = _format_fps_value(clip.source_fps)
    effective_fps = _format_fps_value(clip.effective_fps)
    if clip.fps_divergent:
        return f"{escape(source_fps)} -> {escape(effective_fps)}"
    return escape(effective_fps)


def _format_file_size(size_bytes: int) -> str:
    value = float(size_bytes)
    if value <= 0:
        return ""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024.0
    raise AssertionError("unreachable")


def _display_path(path: Path, *, input_dir: Path | None, verbose: bool) -> str:
    absolute = path.resolve()
    if verbose:
        return str(absolute)
    if input_dir is None:
        return str(path)

    try:
        relative = absolute.relative_to(input_dir.resolve())
    except ValueError:
        return str(absolute)
    return str(relative) if relative != Path(".") else "."


def _render_clip_overview(
    clips: Sequence[FpsReportClip],
    *,
    input_dir: Path | None,
    verbose: bool,
) -> Table:
    table = Table(
        show_header=False,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=False,
    )
    table.add_column("key", style="dim", no_wrap=True, min_width=14, overflow="fold")
    table.add_column("value", overflow="fold")

    identities = [clip.release_identity for clip in clips]
    common_content = (
        common_content_identity([identity for identity in identities if identity is not None])
        if all(identity is not None for identity in identities)
        else None
    )
    if common_content is not None:
        table.add_row("", f"[bold]{escape(format_content_identity(common_content))}[/]")
        table.add_row("", "")

    for index, clip in enumerate(clips):
        if index > 0:
            table.add_row("", "")

        filename = clip.path.name
        if clip.release_identity is not None:
            standard = (
                format_release_descriptor(clip.release_identity, separator=" · ")
                if common_content is not None
                else format_compact_identity(clip.release_identity, separator=" · ")
            )
        else:
            standard = ""
        name_row = f"[bold]{escape(standard or filename)}[/]"
        if index == 0:
            name_row += "  [dim]reference[/]"
        table.add_row("", name_row)
        table.add_row("", _source_detail_line(clip))
        table.add_row("", f"[dim]{escape(filename)}[/]")

    return table


def _source_detail_line(clip: FpsReportClip) -> str:
    """Return the `{w}×{h} · {fps} fps · {frames} ({runtime}) · {size}` line."""
    segments = [
        f"{clip.width}×{clip.height}",
        f"{_fps_decimal_text(clip.effective_fps)} fps",
        (f"{clip.num_frames:,} frames ({_format_runtime(clip.num_frames, clip.effective_fps)})"),
    ]
    size = _format_file_size(clip.size_bytes)
    if size:
        segments.append(size)
    return "[dim] · [/]".join(escape(segment) for segment in segments)


def _clip_short_names(clips: Sequence[FpsReportClip]) -> list[str]:
    """Return the S1 terminal short name for every clip in order."""
    return short_source_names(
        [
            ShortNameSource(
                identity=clip.release_identity,
                label=clip.label,
                label_is_explicit=clip.label_is_explicit,
            )
            for clip in clips
        ],
        roles=[clip_role(index) for index in range(len(clips))],
    )


def _length_difference_lines(
    clips: Sequence[FpsReportClip], short_names: Sequence[str]
) -> list[str]:
    """Return one warning line per distinct comparison length difference."""
    if len(clips) < 2:
        return []
    reference_count = clips[0].num_frames
    reference_fps = float(clips[0].effective_fps)
    reference_short = short_names[0]
    grouped: dict[int, list[str]] = {}
    for clip, short in zip(clips[1:], short_names[1:], strict=True):
        if clip.num_frames != reference_count:
            if clip.num_frames not in grouped:
                grouped[clip.num_frames] = []
            grouped[clip.num_frames].append(short)
    lines: list[str] = []
    for count in sorted(grouped):
        names = grouped[count]
        gap = reference_count - count
        direction = "shorter" if gap > 0 else "longer"
        frames = abs(gap)
        unit = "frame" if frames == 1 else "frames"
        verb = "is" if len(names) == 1 else "are"
        gap_text = ""
        if reference_fps > 0:
            seconds = frames / reference_fps
            gap_text = f" ({seconds:.1f} s)" if seconds < 1.0 else f" ({format_duration(seconds)})"
        lines.append(
            f"[{WARN}]![/] Lengths differ: {escape(_join_names(names))} {verb} "
            f"[bold]{frames} {unit}{gap_text}[/] "
            f"{direction} than {escape(reference_short)}."
        )
    return lines


def _render_load_sources_overview(
    *,
    clips: Sequence[FpsReportClip],
    diagnostics: Sequence[str],
    input_dir: Path | None,
    verbose: bool,
) -> Table:
    table = _render_clip_overview(clips, input_dir=input_dir, verbose=verbose)
    short_names = _clip_short_names(clips)
    other_diagnostics = [
        diagnostic
        for diagnostic in diagnostics
        if not diagnostic.startswith(_ANALYSIS_SOURCE_PREFIX)
    ]
    analysis_lines = [
        diagnostic for diagnostic in diagnostics if diagnostic.startswith(_ANALYSIS_SOURCE_PREFIX)
    ]
    length_lines = _length_difference_lines(clips, short_names)
    if other_diagnostics or length_lines or analysis_lines:
        table.add_row("", "")
        for index, diagnostic in enumerate(other_diagnostics):
            key = "diagnostic" if index == 0 else ""
            table.add_row(key, escape(diagnostic))
        for line in length_lines:
            table.add_row("", line)
        for diagnostic in analysis_lines:
            value = _analysis_source_rich_value(diagnostic, short_names=short_names)
            short, _, reason = value.partition(" (")
            if reason:
                table.add_row(
                    "analysis source",
                    f"{escape(short)} [dim]({escape(reason)}[/]",
                )
            else:
                table.add_row("analysis source", escape(value))
    return table


def _fps_status(clip: FpsReportClip, *, reference_fps: Fraction) -> str:
    if clip.effective_fps != reference_fps:
        return "[red]divergent[/]"
    if clip.fps_divergent:
        return "[yellow]adjusted[/]"
    return "[green]matched[/]"


def _render_fps_table(
    clips: Sequence[FpsReportClip],
    *,
    input_dir: Path | None,
    verbose: bool,
) -> Table:
    table = Table(
        show_header=True,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=False,
    )
    table.add_column("role", style="dim", no_wrap=True, overflow="fold")
    table.add_column("clip", overflow="fold")
    table.add_column("fps", no_wrap=True, overflow="fold")
    table.add_column("status", no_wrap=True, overflow="fold")
    if verbose:
        table.add_column("path", style="dim", overflow="fold")

    if not clips:
        return table
    reference_fps = clips[0].effective_fps
    for index, clip in enumerate(clips):
        status_text = _fps_status(clip, reference_fps=reference_fps)
        if clip.note is not None:
            status_text = f"{status_text} [dim]({escape(clip.note)})[/]"

        descriptor = (
            clip.label
            if clip.label_is_explicit
            else (
                format_release_descriptor(clip.release_identity, separator=" · ")
                if clip.release_identity is not None
                else clip.label
            )
        )
        cells = [
            clip_role(index),
            escape(descriptor or clip.path.name),
            _format_fps_transition(clip),
            status_text,
        ]
        if verbose:
            cells.append(escape(_display_path(clip.path, input_dir=input_dir, verbose=True)))
        table.add_row(*cells)

    return table


def _can_summarize_matching_fps(clips: Sequence[FpsReportClip]) -> bool:
    if not clips or any(clip.fps_divergent for clip in clips):
        return False
    effective_fps = clips[0].effective_fps
    return all(clip.effective_fps == effective_fps for clip in clips)


def _render_human_fps_report(
    *,
    stage: str,
    clips: Sequence[FpsReportClip],
    diagnostics: Sequence[str],
    no_color: bool,
    input_dir: Path | None,
    verbose: bool,
) -> None:
    console = human_console(
        stderr=True,
        no_color=no_color,
        width=report_console_width(),
        height=1000,
    )
    if stage == "after_load_sources":
        title = f"[bold {ACCENT}]Sources[/] [dim]· {len(clips)} loaded[/]"
        table = _render_load_sources_overview(
            clips=clips,
            diagnostics=diagnostics,
            input_dir=input_dir,
            verbose=verbose,
        )
    else:
        if not verbose and _can_summarize_matching_fps(clips):
            effective_fps = _format_fps_value(clips[0].effective_fps)
            glyph = glyphs_for_console(console).ok
            console.print(
                Text.assemble(
                    (glyph, OK),
                    f" frame rates match · {effective_fps}",
                )
            )
            return
        title = f"[bold {ACCENT}]Frame rates[/] [dim]{escape(_stage_label(stage))}[/]"
        table = _render_fps_table(
            clips,
            input_dir=input_dir,
            verbose=verbose,
        )

    console.print(
        Panel(
            table,
            title=title,
            border_style=BORDER_NEUTRAL,
        )
    )


def emit_consolidated_fps_report(
    *,
    stage: str,
    clips: Sequence[FpsReportClip],
    json_output: bool,
    quiet: bool,
    rich_output: bool,
    no_color: bool = False,
    diagnostics: Sequence[str] = (),
    input_dir: Path | None = None,
    verbose: bool = False,
) -> None:
    """Emit the consolidated FPS report in JSON or human-readable form."""
    if quiet:
        return

    if json_output or not rich_output:
        payload = [_serialize_clip(clip) for clip in clips]
        log.info("fps_report", stage=stage, clips=payload, diagnostics=list(diagnostics))
        return

    _render_human_fps_report(
        stage=stage,
        clips=clips,
        diagnostics=diagnostics,
        no_color=no_color,
        input_dir=input_dir,
        verbose=verbose,
    )
