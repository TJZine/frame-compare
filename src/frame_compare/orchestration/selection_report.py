"""Final frame-selection reporting helpers."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from dataclasses import dataclass

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from frame_compare.analysis.types import SelectionBreakdown

_REPORT_CONSOLE_WIDTH = 180
_MIN_REPORT_CONSOLE_WIDTH = 100


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


def _report_console_width() -> int:
    columns = shutil.get_terminal_size(fallback=(_REPORT_CONSOLE_WIDTH, 24)).columns
    return min(max(columns, _MIN_REPORT_CONSOLE_WIDTH), _REPORT_CONSOLE_WIDTH)


def _format_count(count: int, *, domain: str) -> str:
    unit = "frame" if count == 1 else "frames"
    return f"{count:,} {domain} {unit}"


def _render_human_selection_report(
    report: FinalSelectionReport,
    *,
    no_color: bool,
) -> None:
    table = Table(
        show_header=False,
        box=None,
        pad_edge=False,
        padding=(0, 2, 0, 0),
        expand=False,
    )
    table.add_column("key", style="blue", no_wrap=True, min_width=12, overflow="fold")
    table.add_column("value", overflow="fold")
    table.add_row(
        "final",
        f"[bright_white]{escape(_format_count(report.final_count, domain='aligned'))}[/]",
    )

    for category in report.categories:
        count = _format_count(category.count, domain="source")
        table.add_row(
            category.label,
            f"[bright_white]{escape(count)}[/] [dim]{escape(category.ranges)}[/]",
        )

    if not report.breakdown_available:
        table.add_row("breakdown", "[dim]unavailable[/]")

    console = Console(stderr=True, no_color=no_color, width=_report_console_width())
    console.print(
        Panel(
            table,
            title="[bold cyan]Final Selection[/] [dim]After Alignment[/]",
            border_style="cyan",
        )
    )


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
