"""Tests for analysis tier validation helpers."""

from typing import cast

import pytest

from frame_compare.analysis.tier_validation import (
    PerformanceTier,
    SelectionCategory,
    compare_selection_category,
    nearest_frame_distances,
    tier_category_tolerance,
)


def test_nearest_frame_distances_returns_one_distance_per_candidate() -> None:
    assert nearest_frame_distances([10, 20], [9, 18, 30]) == [1, 2, 10]
    assert nearest_frame_distances([], [1, 2]) == [None, None]


def test_compare_selection_category_reports_overlap_and_miss_rate() -> None:
    result = compare_selection_category(
        quality_frames=[10, 20, 30],
        candidate_frames=[10, 22, 50],
        tolerance_frames=3,
    )

    assert result.overlap_count == 1
    assert result.jaccard_overlap == pytest.approx(1 / 5)
    assert result.nearest_quality_distances == [0, 2, 20]
    assert result.max_nearest_distance == 20
    assert result.median_nearest_distance == 2.0
    assert result.miss_rate_at_tolerance == pytest.approx(1 / 3)


def test_tier_category_tolerance_handles_known_tiers_and_categories() -> None:
    assert tier_category_tolerance("performance", "dark") == 2
    assert tier_category_tolerance("performance", "bright") == 2
    assert tier_category_tolerance("performance", "motion") == 3


def test_tier_category_tolerance_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="Unsupported PerformanceTier"):
        tier_category_tolerance(cast(PerformanceTier, "quality"), "motion")

    with pytest.raises(ValueError, match="Unsupported SelectionCategory"):
        tier_category_tolerance("performance", cast(SelectionCategory, "invalid"))
