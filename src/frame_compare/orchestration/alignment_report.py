"""Frame alignment diagnostics reporting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from frame_compare.orchestration.context import ClipState
from frame_compare.orchestration.presentation import report_console_width
from frame_compare.services.release_identity import format_release_descriptor
from frame_compare.services.types import AlignmentSource, AlignmentStabilitySummary

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
                    format_release_descriptor(comparison.release_identity)
                    if comparison.release_identity is not None
                    else comparison.label
                )
            ),
            stability=None if comparison.alignment is None else comparison.alignment.stability,
        )
        for comparison in comparisons
    )


def _trim_range(clip: ClipState) -> tuple[int, int]:
    start = clip.trim.trim_start_frames
    end = (
        clip.trim.trim_end_frame_inclusive
        if clip.trim.trim_end_frame_inclusive is not None
        else clip.probe.num_frames - 1
    )
    return start, min(end, clip.probe.num_frames - 1)


def _stage_label(stage: str) -> str:
    if stage == "after_align":
        return "After Alignment"
    return stage.replace("_", " ").title()


def _format_offset(offset: int | None) -> str:
    if offset is None:
        return "none"
    return f"{offset:+d}f"


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
    if summary.change_position_seconds is not None:
        seconds = round(summary.change_position_seconds)
        text += f"; change near {seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return text


def _has_material_alignment_info(
    *,
    comparisons: Sequence[AlignmentReportComparison],
    alignment_warnings: Sequence[str],
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
    alignment_warnings: Sequence[str],
    verbose: bool,
) -> Table:
    table = Table(
        show_header=False,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=False,
    )
    table.add_column("key", style="blue", no_wrap=True, min_width=12, overflow="fold")
    table.add_column("value", overflow="fold")

    for index, comparison in enumerate(comparisons):
        if index > 0:
            table.add_row("", "")

        source = comparison.alignment_source if comparison.alignment_source is not None else "none"
        display_name = (
            comparison.label if verbose else (comparison.presentation_name or comparison.label)
        )
        table.add_row("comparison", f"[bright_white]{escape(display_name)}[/]")
        table.add_row(
            "  offset",
            f"[bright_white]{escape(_format_offset(comparison.relative_offset_frames))}[/]",
        )
        stability = comparison.stability
        if stability is not None and (
            verbose
            or stability.classification in {"possible_drift", "possible_discontinuity", "variable"}
        ):
            value = _format_stability(stability)
            if verbose:
                value += f"; {stability.valid_windows} valid windows"
            table.add_row("  stability", f"[bright_white]{escape(value)}[/]")
        elif verbose:
            table.add_row("  stability", "[dim]unavailable (legacy cache entry)[/]")
        table.add_row("  source", f"[bright_white]{escape(source)}[/]")
        table.add_row(
            "  trims",
            "[bright_white]"
            f"Reference {escape(_format_range(comparison.reference_trim_range))}, "
            f"{escape(display_name)} "
            f"{escape(_format_range(comparison.comparison_trim_range))}"
            "[/]",
        )
        if selected_frames:
            table.add_row(
                "  frames",
                f"[bright_white]aligned {escape(_format_selected_frames(selected_frames))}[/]",
            )

    if alignment_warnings:
        if comparisons:
            table.add_row("", "")
        table.add_row("warnings", "")
        for warning in alignment_warnings:
            table.add_row("  rejected", f"[yellow]{escape(warning)}[/]")

    if verbose:
        for comparison in comparisons:
            table.add_row("", "")
            table.add_row("details", f"[bright_white]{escape(comparison.label)}[/]")
            table.add_row(
                "  row 0",
                "[bright_white]"
                f"Reference source {comparison.reference_row_zero_source_frame}"
                f" <-> {escape(comparison.label)} source "
                f"{comparison.comparison_row_zero_source_frame}"
                "[/]",
            )
            if comparison.reference_path is not None:
                table.add_row(
                    "  reference path",
                    f"[dim]{escape(str(comparison.reference_path.resolve()))}[/]",
                )
            if comparison.comparison_path is not None:
                table.add_row(
                    "  comparison path",
                    f"[dim]{escape(str(comparison.comparison_path.resolve()))}[/]",
                )

    return table


def _render_human_alignment_report(
    *,
    stage: str,
    comparisons: Sequence[AlignmentReportComparison],
    selected_frames: Sequence[int],
    alignment_warnings: Sequence[str],
    no_color: bool,
    verbose: bool,
) -> None:
    console = Console(
        stderr=True,
        no_color=no_color,
        width=report_console_width(),
        height=1000,
    )
    console.print(
        Panel(
            _render_alignment_table(
                comparisons=comparisons,
                selected_frames=selected_frames,
                alignment_warnings=alignment_warnings,
                verbose=verbose,
            ),
            title=f"[bold cyan]Frame Alignment[/] [dim]{escape(_stage_label(stage))}[/]",
            border_style="cyan",
        )
    )


def emit_frame_alignment_report(
    *,
    stage: str,
    comparisons: Sequence[AlignmentReportComparison],
    selected_frames: Sequence[int],
    alignment_warnings: Sequence[str],
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
