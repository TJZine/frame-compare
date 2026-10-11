"""Validation helpers for comparing analysis performance tiers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

type SelectionCategory = Literal["dark", "bright", "motion"]
type PerformanceTier = Literal["performance"]


@dataclass(frozen=True, slots=True)
class SelectionCategoryComparison:
    """Selection drift metrics for one category."""

    quality_frames: list[int]
    candidate_frames: list[int]
    overlap_count: int
    jaccard_overlap: float
    nearest_quality_distances: list[int | None]
    max_nearest_distance: int | None
    median_nearest_distance: float | None
    miss_rate_at_tolerance: float
    tolerance_frames: int


def tier_category_tolerance(tier: PerformanceTier, category: SelectionCategory) -> int:
    """Return the v1 review tolerance for a tier/category pair."""
    if category not in ("dark", "bright", "motion"):
        raise ValueError(f"Unsupported SelectionCategory for tier_category_tolerance: {category!r}")
    if tier == "performance":
        return 3 if category == "motion" else 2
    raise ValueError(f"Unsupported PerformanceTier for tier_category_tolerance: {tier!r}")


def nearest_frame_distances(
    quality_frames: Sequence[int],
    candidate_frames: Sequence[int],
) -> list[int | None]:
    """Return nearest quality-frame distance for every candidate frame."""
    quality = sorted(quality_frames)
    if not quality:
        return [None for _frame in candidate_frames]
    return [
        min(abs(candidate - quality_frame) for quality_frame in quality)
        for candidate in candidate_frames
    ]


def compare_selection_category(
    *,
    quality_frames: Sequence[int],
    candidate_frames: Sequence[int],
    tolerance_frames: int,
) -> SelectionCategoryComparison:
    """Compare one selected-frame category against the quality baseline."""
    quality = sorted(set(quality_frames))
    candidate = sorted(set(candidate_frames))
    quality_set = set(quality)
    candidate_set = set(candidate)
    union_count = len(quality_set | candidate_set)
    overlap_count = len(quality_set & candidate_set)
    distances = nearest_frame_distances(quality, candidate)
    finite_distances = [distance for distance in distances if distance is not None]
    misses = [distance for distance in finite_distances if distance > tolerance_frames]
    missing_baseline_misses = len([distance for distance in distances if distance is None])
    denominator = len(candidate)
    miss_count = len(misses) + missing_baseline_misses
    return SelectionCategoryComparison(
        quality_frames=quality,
        candidate_frames=candidate,
        overlap_count=overlap_count,
        jaccard_overlap=0.0 if union_count == 0 else overlap_count / union_count,
        nearest_quality_distances=distances,
        max_nearest_distance=max(finite_distances) if finite_distances else None,
        median_nearest_distance=_median_ints(finite_distances),
        miss_rate_at_tolerance=0.0 if denominator == 0 else miss_count / denominator,
        tolerance_frames=tolerance_frames,
    )


def _median_ints(values: Sequence[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[midpoint])
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


__all__ = [
    "SelectionCategory",
    "SelectionCategoryComparison",
    "compare_selection_category",
    "nearest_frame_distances",
    "tier_category_tolerance",
]
