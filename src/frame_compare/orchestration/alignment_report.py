"""Frame alignment diagnostics reporting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.markup import escape
from rich.text import Text

from frame_compare.orchestration.context import ClipState
from frame_compare.orchestration.presentation import report_console_width
from frame_compare.services.release_identity import (
    ShortNameSource,
    format_release_descriptor,
    short_source_names,
)
from frame_compare.services.types import AlignmentSource
from frame_compare.utils.alignment_evidence import AlignmentStabilitySummary
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.utils.terminal_sections import Section, section_title
from frame_compare.utils.terminal_theme import human_console

_MAX_SELECTED_FRAMES = 8


@dataclass(frozen=True)
class AlignmentReportComparison:
    """Immutable per-comparison frame alignment diagnostics entry."""

    label: str
    alignment_source: AlignmentSource | None
    relative_offset_frames: int | None
    reference_row_zero_source_frame: int
    comparison_row_zero_source_frame: int
    reference_trim_range: tuple[int, int]
    comparison_trim_range: tuple[int, int]
    reference_path: Path | None = None
    comparison_path: Path | None = None
    presentation_name: str | None = None
    stability: AlignmentStabilitySummary | None = None
    short_name: str | None = None
    reference_short_name: str | None = None


def build_frame_alignment_report(
    *,
    reference: ClipState,
    comparisons: Sequence[ClipState],
) -> tuple[AlignmentReportComparison, ...]:
    """Return deterministic, ordered frame alignment diagnostics.

    Each entry compares the final post-alignment reference domain to one
    comparison clip. The values are already normalized into the aligned frame
    domain used by rendering.
    """
    clips = [reference, *comparisons]
    short_names = short_source_names(
        [
            ShortNameSource(
                identity=clip.release_identity,
                label=clip.label,
                label_is_explicit=clip.label_is_explicit,
            )
            for clip in clips
        ],
        roles=["Reference", *(f"Comparison {index}" for index in range(1, len(clips)))],
    )
    reference_short_name = short_names[0] if short_names else reference.label
    return tuple(
        AlignmentReportComparison(
            label=comparison.label,
            alignment_source=None if comparison.alignment is None else comparison.alignment.source,
            relative_offset_frames=None
            if comparison.alignment is None
            else comparison.alignment.relative_offset_frames,
            reference_row_zero_source_frame=reference.trim.trim_start_frames,
            comparison_row_zero_source_frame=comparison.trim.trim_start_frames,
            reference_trim_range=_trim_range(reference),
            comparison_trim_range=_trim_range(comparison),
            reference_path=reference.path,
            comparison_path=comparison.path,
            presentation_name=(
                comparison.label
                if comparison.label_is_explicit
                else (
                    format_release_descriptor(comparison.release_identity, separator=" · ")
                    if comparison.release_identity is not None
                    else comparison.label
                )
            ),
            stability=None if comparison.alignment is None else comparison.alignment.stability,
            short_name=short_names[index + 1],
            reference_short_name=reference_short_name,
        )
        for index, comparison in enumerate(comparisons)
    )


def _trim_range(clip: ClipState) -> tuple[int, int]:
    start = clip.trim.trim_start_frames
    end = (
        clip.trim.trim_end_frame_inclusive
        if clip.trim.trim_end_frame_inclusive is not None
        else clip.probe.num_frames - 1
    )
    return start, min(end, clip.probe.num_frames - 1)


def _format_range(trim_range: tuple[int, int]) -> str:
    start, end = trim_range
    if end < start:
        return "empty"
    return f"{start}..{end}"


def _format_selected_frames(selected_frames: Sequence[int]) -> str:
    shown = [str(frame) for frame in selected_frames[:_MAX_SELECTED_FRAMES]]
    if len(selected_frames) > _MAX_SELECTED_FRAMES:
        shown.append(f"... ({len(selected_frames)} total)")
    return ", ".join(shown)


def _format_stability(summary: AlignmentStabilitySummary) -> str:
    text = summary.classification.replace("_", " ")
    if summary.offset_min_frames is not None and summary.offset_max_frames is not None:
        text += f"; {summary.offset_min_frames:+d}..{summary.offset_max_frames:+d} frames"
    text += f"; scoped to {summary.valid_windows} credible chunks"
    if summary.change_position_seconds is not None:
        seconds = round(summary.change_position_seconds)
        text += (
            "; approximate interval between observations around "
            f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
        )
    return text


def _has_material_alignment_info(
    *,
    comparisons: Sequence[AlignmentReportComparison],
    alignment_warnings: list[RunWarning],
) -> bool:
    return any(
        comparison.relative_offset_frames not in (None, 0)
        or (
            comparison.alignment_source is not None
            and (
                comparison.reference_trim_range != comparison.comparison_trim_range
                or (
                    comparison.reference_row_zero_source_frame
                    != comparison.comparison_row_zero_source_frame
                )
            )
        )
        for comparison in comparisons
    ) or bool(alignment_warnings)


def _render_alignment_table(
    *,
    comparisons: Sequence[AlignmentReportComparison],
    selected_frames: Sequence[int],
    alignment_warnings: list[RunWarning],
    verbose: bool,
) -> Section:
    section = Section(section_title("Frame alignment"))
    reference_name = (
        comparisons[0].reference_short_name
        if comparisons and comparisons[0].reference_short_name
        else "Reference"
    )
    for index, comparison in enumerate(comparisons):
        if index > 0:
            section.add_line()

        display_name = (
            comparison.label
            if verbose
            else (comparison.short_name or comparison.presentation_name or comparison.label)
        )
        trim_name = comparison.short_name or comparison.presentation_name or comparison.label
        section.add_line(f"[bold]{escape(display_name)}[/]")
        section.add_row(
            "  trims",
            Text(
                f"{reference_name} {_format_range(comparison.reference_trim_range)} · "
                f"{trim_name} {_format_range(comparison.comparison_trim_range)}"
            ),
        )
        stability = comparison.stability
        if stability is not None and (
            verbose
            or stability.classification in {"possible_drift", "possible_discontinuity", "variable"}
        ):
            value = _format_stability(stability)
            if verbose:
                value += f"; {stability.valid_windows} credible chunks"
            section.add_row("  stability", Text(value))
        if selected_frames:
            section.add_row(
                "  frames",
                Text(f"aligned {_format_selected_frames(selected_frames)}"),
            )

    if alignment_warnings:
        if comparisons:
            section.add_line()
        for warning in alignment_warnings:
            section.add_note(warning.text)

    if verbose:
        for comparison in comparisons:
            section.add_line()
            section.add_row("details", Text(comparison.label))
            section.add_row(
                "  row 0",
                Text(
                    f"Reference source {comparison.reference_row_zero_source_frame}"
                    f" <-> {comparison.label} source {comparison.comparison_row_zero_source_frame}"
                ),
            )
            if comparison.reference_path is not None:
                section.add_row(
                    "  reference path",
                    f"[dim]{escape(str(comparison.reference_path.resolve()))}[/]",
                )
            if comparison.comparison_path is not None:
                section.add_row(
                    "  comparison path",
                    f"[dim]{escape(str(comparison.comparison_path.resolve()))}[/]",
                )

    return section


def _render_human_alignment_report(
    *,
    stage: str,
    comparisons: Sequence[AlignmentReportComparison],
    selected_frames: Sequence[int],
    alignment_warnings: list[RunWarning],
    no_color: bool,
    verbose: bool,
) -> None:
    console = human_console(
        stderr=True,
        no_color=no_color,
        width=report_console_width(),
        height=1000,
    )
    _ = stage
    _render_alignment_table(
        comparisons=comparisons,
        selected_frames=selected_frames,
        alignment_warnings=alignment_warnings,
        verbose=verbose,
    ).print(console)


def emit_frame_alignment_report(
    *,
    stage: str,
    comparisons: Sequence[AlignmentReportComparison],
    selected_frames: Sequence[int],
    alignment_warnings: list[RunWarning],
    json_output: bool,
    quiet: bool,
    no_color: bool = False,
    verbose: bool = False,
) -> None:
    """Emit the frame alignment report for human-readable runs."""
    if quiet or json_output:
        return
    if not _has_material_alignment_info(
        comparisons=comparisons,
        alignment_warnings=alignment_warnings,
    ):
        return

    _render_human_alignment_report(
        stage=stage,
        comparisons=comparisons,
        selected_frames=selected_frames,
        alignment_warnings=alignment_warnings,
        no_color=no_color,
        verbose=verbose,
    )
