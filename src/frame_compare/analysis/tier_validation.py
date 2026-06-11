"""Validation helpers for comparing analysis performance tiers."""

from __future__ import annotations

import math
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


@dataclass(frozen=True, slots=True)
class TopKOverlap:
    """Top-K overlap metrics for one score vector."""

    k: int
    overlap_count: int
    jaccard_overlap: float
    quality_indices: list[int]
    candidate_indices: list[int]


@dataclass(frozen=True, slots=True)
class RankingComparison:
    """Ranking metrics for luminance and motion arrays."""

    luminance_spearman: float | None
    motion_spearman: float | None
    lowest_luminance_top_k: TopKOverlap
    highest_luminance_top_k: TopKOverlap
    highest_motion_top_k: TopKOverlap


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


def top_k_for_requested_count(*, window_frame_count: int, requested_category_count: int) -> int:
    """Return the diagnostic Top-K value from the Phase 5 plan."""
    if window_frame_count <= 0:
        return 0
    requested_floor = 50 if requested_category_count <= 0 else 5 * requested_category_count
    return min(window_frame_count, max(50, requested_floor))


def top_k_overlap(
    quality_scores: Sequence[float],
    candidate_scores: Sequence[float],
    *,
    k: int,
    largest: bool,
    source_offset: int = 0,
) -> TopKOverlap:
    """Compare the top-K source-frame indices for two score arrays."""
    if len(quality_scores) != len(candidate_scores):
        raise ValueError("score arrays must have matching lengths")
    bounded_k = min(max(0, k), len(quality_scores))
    quality_indices = _top_k_indices(
        quality_scores, k=bounded_k, largest=largest, source_offset=source_offset
    )
    candidate_indices = _top_k_indices(
        candidate_scores,
        k=bounded_k,
        largest=largest,
        source_offset=source_offset,
    )
    quality_set = set(quality_indices)
    candidate_set = set(candidate_indices)
    union_count = len(quality_set | candidate_set)
    overlap_count = len(quality_set & candidate_set)
    return TopKOverlap(
        k=bounded_k,
        overlap_count=overlap_count,
        jaccard_overlap=0.0 if union_count == 0 else overlap_count / union_count,
        quality_indices=quality_indices,
        candidate_indices=candidate_indices,
    )


def spearman_rank_correlation(
    quality_scores: Sequence[float],
    candidate_scores: Sequence[float],
) -> float | None:
    """Compute Spearman rank correlation with average ranks for ties."""
    if len(quality_scores) != len(candidate_scores):
        raise ValueError("score arrays must have matching lengths")
    if len(quality_scores) < 2:
        return None
    quality_ranks = _average_ranks(quality_scores)
    candidate_ranks = _average_ranks(candidate_scores)
    return _pearson(quality_ranks, candidate_ranks)


def compare_rankings(
    *,
    quality_luminance: Sequence[float],
    candidate_luminance: Sequence[float],
    quality_motion: Sequence[float],
    candidate_motion: Sequence[float],
    dark_count: int,
    bright_count: int,
    motion_count: int,
    source_offset: int = 0,
) -> RankingComparison:
    """Build ranking diagnostics for one candidate tier."""
    vector_lengths = {
        "quality_luminance": len(quality_luminance),
        "candidate_luminance": len(candidate_luminance),
        "quality_motion": len(quality_motion),
        "candidate_motion": len(candidate_motion),
    }
    if len(set(vector_lengths.values())) != 1:
        raise ValueError(f"compare_rankings requires matching vector lengths: {vector_lengths}")

    window_frame_count = vector_lengths["quality_luminance"]
    return RankingComparison(
        luminance_spearman=spearman_rank_correlation(quality_luminance, candidate_luminance),
        motion_spearman=spearman_rank_correlation(quality_motion, candidate_motion),
        lowest_luminance_top_k=top_k_overlap(
            quality_luminance,
            candidate_luminance,
            k=top_k_for_requested_count(
                window_frame_count=window_frame_count,
                requested_category_count=dark_count,
            ),
            largest=False,
            source_offset=source_offset,
        ),
        highest_luminance_top_k=top_k_overlap(
            quality_luminance,
            candidate_luminance,
            k=top_k_for_requested_count(
                window_frame_count=window_frame_count,
                requested_category_count=bright_count,
            ),
            largest=True,
            source_offset=source_offset,
        ),
        highest_motion_top_k=top_k_overlap(
            quality_motion,
            candidate_motion,
            k=top_k_for_requested_count(
                window_frame_count=window_frame_count,
                requested_category_count=motion_count,
            ),
            largest=True,
            source_offset=source_offset,
        ),
    )


def _top_k_indices(
    values: Sequence[float],
    *,
    k: int,
    largest: bool,
    source_offset: int,
) -> list[int]:
    if k <= 0:
        return []
    if largest:
        ordered = sorted(enumerate(values), key=lambda item: (-item[1], item[0]))
    else:
        ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    return [index + source_offset for index, _value in ordered[:k]]


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        for position in range(start, end):
            ranks[ordered[position][0]] = average_rank
        start = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_centered = [value - left_mean for value in left]
    right_centered = [value - right_mean for value in right]
    numerator = sum(a * b for a, b in zip(left_centered, right_centered, strict=True))
    left_denominator = math.sqrt(sum(value * value for value in left_centered))
    right_denominator = math.sqrt(sum(value * value for value in right_centered))
    denominator = left_denominator * right_denominator
    if denominator == 0.0:
        return 1.0 if list(left) == list(right) else 0.0
    return numerator / denominator


def _median_ints(values: Sequence[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[midpoint])
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


__all__ = [
    "RankingComparison",
    "SelectionCategory",
    "SelectionCategoryComparison",
    "TopKOverlap",
    "compare_rankings",
    "compare_selection_category",
    "nearest_frame_distances",
    "spearman_rank_correlation",
    "tier_category_tolerance",
    "top_k_for_requested_count",
    "top_k_overlap",
]
