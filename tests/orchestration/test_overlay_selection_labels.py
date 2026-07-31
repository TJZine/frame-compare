from __future__ import annotations

from frame_compare.analysis.types import SelectionBreakdown
from frame_compare.orchestration.execution import selection_label_for_frame


def test_selection_label_for_frame_maps_breakdown_categories() -> None:
    breakdown = SelectionBreakdown(
        quantile_dark=[10],
        quantile_bright=[11],
        motion=[12],
        random=[13],
    )

    assert selection_label_for_frame(10, breakdown) == "Dark"
    assert selection_label_for_frame(11, breakdown) == "Bright"
    assert selection_label_for_frame(12, breakdown) == "Motion"
    assert selection_label_for_frame(13, breakdown) == "Random"
    assert selection_label_for_frame(99, breakdown) is None


def test_selection_label_for_frame_none_breakdown_returns_none() -> None:
    assert selection_label_for_frame(10, None) is None


def test_selection_label_for_frame_overlap_prefers_first_category() -> None:
    breakdown = SelectionBreakdown(
        quantile_dark=[10],
        motion=[10],
        random=[10],
    )
    assert selection_label_for_frame(10, breakdown) == "Dark"
