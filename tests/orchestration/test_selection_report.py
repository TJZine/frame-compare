"""Unit tests for final frame-selection reporting helpers."""

from __future__ import annotations

import pytest

from frame_compare.analysis.types import SelectionBreakdown
from frame_compare.orchestration.selection_report import (
    FinalSelectionReport,
    SelectionCategoryReport,
    build_final_selection_report,
    emit_final_selection_report,
)


def test_build_final_selection_report_compacts_ranges_in_category_order() -> None:
    breakdown = SelectionBreakdown(
        user=[5, 2, 3, 4],
        quantile_dark=[21, 20],
        quantile_bright=[40],
        motion=[72, 70, 71],
        random=[90, 92],
    )

    report = build_final_selection_report(
        selected_frames=[0, 1, 2],
        breakdown=breakdown,
    )

    assert report == FinalSelectionReport(
        final_count=3,
        categories=(
            SelectionCategoryReport("User", 4, "2-5"),
            SelectionCategoryReport("Dark", 2, "20-21"),
            SelectionCategoryReport("Bright", 1, "40"),
            SelectionCategoryReport("Motion", 3, "70-72"),
            SelectionCategoryReport("Random", 2, "90, 92"),
        ),
        breakdown_available=True,
    )


def test_build_final_selection_report_preserves_existing_sequence_count() -> None:
    report = build_final_selection_report(
        selected_frames=[0],
        breakdown=SelectionBreakdown(random=[1, 1, 2]),
    )

    assert report.categories == (SelectionCategoryReport("Random", 3, "1, 1-2"),)


def test_build_final_selection_report_user_only_omits_empty_categories() -> None:
    report = build_final_selection_report(
        selected_frames=[0, 4],
        breakdown=SelectionBreakdown(user=[105, 100]),
    )

    assert report.categories == (SelectionCategoryReport("User", 2, "100, 105"),)


def test_build_final_selection_report_marks_missing_breakdown_unavailable() -> None:
    report = build_final_selection_report(
        selected_frames=[3, 8, 13],
        breakdown=None,
    )

    assert report == FinalSelectionReport(
        final_count=3,
        categories=(),
        breakdown_available=False,
    )


def test_build_final_selection_report_marks_empty_breakdown_available() -> None:
    report = build_final_selection_report(
        selected_frames=[],
        breakdown=SelectionBreakdown(),
    )

    assert report == FinalSelectionReport(
        final_count=0,
        categories=(),
        breakdown_available=True,
    )


def test_emit_final_selection_report_renders_verbose_human_summary_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit_final_selection_report(
        selected_frames=[0, 1, 2],
        breakdown=SelectionBreakdown(user=[10, 11], random=[30]),
        verbose=True,
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Final Selection" in captured.err
    assert "After Alignment" in captured.err
    assert "3 aligned frames" in captured.err
    assert "User" in captured.err
    assert "2 source frames" in captured.err
    assert "10-11" in captured.err
    assert "Random" in captured.err
    assert "1 source frame" in captured.err
    assert "30" in captured.err
    assert "Dark" not in captured.err
    assert "Bright" not in captured.err
    assert "Motion" not in captured.err
    assert "\x1b[" not in captured.err


def test_emit_final_selection_report_renders_unavailable_breakdown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit_final_selection_report(
        selected_frames=[7],
        breakdown=None,
        verbose=True,
        json_output=False,
        quiet=False,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "1 aligned frame" in captured.err
    assert "breakdown" in captured.err
    assert "unavailable" in captured.err


@pytest.mark.parametrize(
    ("verbose", "json_output", "quiet"),
    [
        (False, False, False),
        (True, False, True),
        (True, True, False),
    ],
    ids=["normal", "quiet", "json"],
)
def test_emit_final_selection_report_is_absent_outside_verbose_human_mode(
    verbose: bool,
    json_output: bool,
    quiet: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit_final_selection_report(
        selected_frames=[1, 2],
        breakdown=SelectionBreakdown(user=[10]),
        verbose=verbose,
        json_output=json_output,
        quiet=quiet,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
