"""Final frame-selection reporting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rich.markup import escape

from frame_compare.analysis.types import SelectionBreakdown
from frame_compare.orchestration.presentation import report_console_width
from frame_compare.utils.terminal_sections import Section, section_title
from frame_compare.utils.terminal_theme import human_console


@dataclass(frozen=True, slots=True)
class SelectionCategoryReport:
    """One source-frame selection category prepared for presentation."""

    label: str
    count: int
    ranges: str


@dataclass(frozen=True, slots=True)
class FinalSelectionReport:
    """Final aligned count and available source-frame category facts."""

    final_count: int
    categories: tuple[SelectionCategoryReport, ...]
    breakdown_available: bool


def _format_ranges(frames: Sequence[int]) -> str:
    ordered = sorted(frames)
    if not ordered:
        return ""

    ranges: list[str] = []
    start = ordered[0]
    end = start
    for frame in ordered[1:]:
        if frame == end + 1:
            end = frame
            continue
        ranges.append(str(start) if start == end else f"{start}-{end}")
        start = frame
        end = frame
    ranges.append(str(start) if start == end else f"{start}-{end}")
    return ", ".join(ranges)


def _category_report(label: str, frames: Sequence[int]) -> SelectionCategoryReport | None:
    if not frames:
        return None
    return SelectionCategoryReport(
        label=label,
        count=len(frames),
        ranges=_format_ranges(frames),
    )


def build_final_selection_report(
    *,
    selected_frames: Sequence[int],
    breakdown: SelectionBreakdown | None,
) -> FinalSelectionReport:
    """Build a report without translating or reconciling frame domains."""
    if breakdown is None:
        return FinalSelectionReport(
            final_count=len(selected_frames),
            categories=(),
            breakdown_available=False,
        )

    candidates = (
        _category_report("User", breakdown.user),
        _category_report("Dark", breakdown.quantile_dark),
        _category_report("Bright", breakdown.quantile_bright),
        _category_report("Motion", breakdown.motion),
        _category_report("Random", breakdown.random),
    )
    return FinalSelectionReport(
        final_count=len(selected_frames),
        categories=tuple(category for category in candidates if category is not None),
        breakdown_available=True,
    )


def _format_count(count: int, *, domain: str) -> str:
    unit = "frame" if count == 1 else "frames"
    return f"{count:,} {domain} {unit}"


def _render_human_selection_report(
    report: FinalSelectionReport,
    *,
    no_color: bool,
) -> None:
    section = Section(section_title("Final selection"))
    section.add_row(
        "final",
        escape(_format_count(report.final_count, domain="aligned")),
    )

    for category in report.categories:
        count = _format_count(category.count, domain="source")
        section.add_row(
            category.label,
            f"{escape(count)} [dim]{escape(category.ranges)}[/]",
        )

    if not report.breakdown_available:
        section.add_row("breakdown", "[dim]unavailable[/]")

    console = human_console(stderr=True, no_color=no_color, width=report_console_width())
    section.print(console)


def emit_final_selection_report(
    *,
    selected_frames: Sequence[int],
    breakdown: SelectionBreakdown | None,
    verbose: bool,
    json_output: bool,
    quiet: bool,
    no_color: bool = False,
) -> None:
    """Emit the final selection summary only for verbose human runs."""
    if not verbose or quiet or json_output:
        return

    _render_human_selection_report(
        build_final_selection_report(
            selected_frames=selected_frames,
            breakdown=breakdown,
        ),
        no_color=no_color,
    )
