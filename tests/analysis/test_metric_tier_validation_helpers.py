"""Tests for analysis tier validation helpers."""

from typing import cast

import pytest

from frame_compare.analysis.tier_validation import (
    PerformanceTier,
    SelectionCategory,
    compare_rankings,
    compare_selection_category,
    nearest_frame_distances,
    spearman_rank_correlation,
    tier_category_tolerance,
    top_k_overlap,
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


def test_top_k_overlap_uses_source_offsets_and_stable_ordering() -> None:
    result = top_k_overlap(
        [0.1, 0.9, 0.9, 0.2],
        [0.1, 0.8, 0.7, 0.95],
        k=2,
        largest=True,
        source_offset=100,
    )

    assert result.k == 2
    assert result.quality_indices == [101, 102]
    assert result.candidate_indices == [103, 101]
    assert result.overlap_count == 1


def test_spearman_rank_correlation_handles_identical_reversed_and_tied_arrays() -> None:
    assert spearman_rank_correlation([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)
    assert spearman_rank_correlation([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]) == pytest.approx(-1.0)
    assert spearman_rank_correlation([1.0, 1.0, 2.0], [1.0, 1.0, 2.0]) == pytest.approx(1.0)


def test_compare_rankings_builds_required_top_k_sections() -> None:
    result = compare_rankings(
        quality_luminance=[0.0, 0.2, 1.0],
        candidate_luminance=[0.0, 0.1, 1.0],
        quality_motion=[0.0, 0.8, 0.2],
        candidate_motion=[0.0, 0.1, 0.9],
        dark_count=1,
        bright_count=1,
        motion_count=1,
        source_offset=10,
    )

    assert result.luminance_spearman == pytest.approx(1.0)
    assert result.lowest_luminance_top_k.k == 3
    assert result.highest_luminance_top_k.quality_indices == [12, 11, 10]
    assert result.highest_motion_top_k.candidate_indices == [12, 11, 10]


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"candidate_luminance": [0.0, 0.1]}, "candidate_luminance"),
        ({"candidate_motion": [0.0, 0.1]}, "candidate_motion"),
        ({"quality_motion": [0.0, 0.8]}, "quality_motion"),
    ],
)
def test_compare_rankings_rejects_mismatched_vector_lengths(
    overrides: dict[str, list[float]],
    expected_field: str,
) -> None:
    kwargs = {
        "quality_luminance": [0.0, 0.2, 1.0],
        "candidate_luminance": [0.0, 0.1, 1.0],
        "quality_motion": [0.0, 0.8, 0.2],
        "candidate_motion": [0.0, 0.1, 0.9],
        "dark_count": 1,
        "bright_count": 1,
        "motion_count": 1,
    } | overrides

    with pytest.raises(ValueError, match=f"compare_rankings.*{expected_field}"):
        compare_rankings(**kwargs)
