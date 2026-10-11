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


@pytest.mark.parametrize(
    ("selected_frames", "breakdown", "expected"),
    [
        pytest.param(
            [0, 1, 2],
            SelectionBreakdown(
                user=[5, 2, 3, 4],
                quantile_dark=[21, 20],
                quantile_bright=[40],
                motion=[72, 70, 71],
                random=[90, 92],
            ),
            FinalSelectionReport(
                final_count=3,
                categories=(
                    SelectionCategoryReport("User", 4, "2-5"),
                    SelectionCategoryReport("Dark", 2, "20-21"),
                    SelectionCategoryReport("Bright", 1, "40"),
                    SelectionCategoryReport("Motion", 3, "70-72"),
                    SelectionCategoryReport("Random", 2, "90, 92"),
                ),
                breakdown_available=True,
            ),
            id="category-order",
        ),
        pytest.param(
            [0],
            SelectionBreakdown(random=[1, 1, 2]),
            FinalSelectionReport(
                final_count=1,
                categories=(SelectionCategoryReport("Random", 3, "1, 1-2"),),
                breakdown_available=True,
            ),
            id="duplicate-sequence",
        ),
        pytest.param(
            [0, 4],
            SelectionBreakdown(user=[105, 100]),
            FinalSelectionReport(
                final_count=2,
                categories=(SelectionCategoryReport("User", 2, "100, 105"),),
                breakdown_available=True,
            ),
            id="user-only",
        ),
    ],
)
def test_build_final_selection_report(
    selected_frames: list[int], breakdown: SelectionBreakdown, expected: FinalSelectionReport
) -> None:
    assert (
        build_final_selection_report(selected_frames=selected_frames, breakdown=breakdown)
        == expected
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


@pytest.mark.parametrize(
    ("selected_frames", "breakdown", "present", "absent"),
    [
        pytest.param(
            [0, 1, 2],
            SelectionBreakdown(user=[10, 11], random=[30]),
            [
                "Final Selection",
                "After Alignment",
                "3 aligned frames",
                "User",
                "2 source frames",
                "10-11",
                "Random",
                "1 source frame",
                "30",
            ],
            ["Dark", "Bright", "Motion", "\x1b["],
            id="available",
        ),
        pytest.param(
            [7], None, ["1 aligned frame", "breakdown", "unavailable"], [], id="unavailable"
        ),
    ],
)
def test_emit_final_selection_report_verbose_human_summary(
    selected_frames: list[int],
    breakdown: SelectionBreakdown | None,
    present: list[str],
    absent: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit_final_selection_report(
        selected_frames=selected_frames,
        breakdown=breakdown,
        verbose=True,
        json_output=False,
        quiet=False,
        no_color=True,
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    for text in present:
        assert text in captured.err
    for text in absent:
        assert text not in captured.err


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
