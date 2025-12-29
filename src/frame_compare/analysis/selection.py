"""Frame selection algorithms."""

from __future__ import annotations

import random
from collections.abc import Sequence

from frame_compare.analysis.types import FrameMetrics, FrameSelection, SelectionBreakdown
from frame_compare.config import AnalysisConfig, SelectionMode
from frame_compare.errors import SelectionError

MIN_GAP: int = 5


def select_frames(metrics: FrameMetrics, config: AnalysisConfig) -> FrameSelection:
    """Select frames based on configuration and metrics.

    Args:
        metrics: Calculated frame metrics (luminance, motion).
        config: Analysis configuration including frame count and selection mode.

    Returns:
        A FrameSelection object containing the selected frames and breakdown.

    Raises:
        SelectionError: If metrics are empty or insufficient candidates are found.
    """
    total_frames = metrics.metadata.frame_count
    if total_frames == 0:
        raise SelectionError(reason="empty_metrics", requested=config.frame_count, found=0)

    mode = config.selection_mode
    requested_count = config.frame_count
    seed = config.random_seed

    selected_set: set[int] = set()
    breakdown = SelectionBreakdown()

    if mode == SelectionMode.QUANTILE:
        dark, bright = _select_by_quantile(metrics.luminance, requested_count)
        breakdown = SelectionBreakdown(quantile_dark=dark, quantile_bright=bright)
        selected_set.update(dark)
        selected_set.update(bright)

    elif mode == SelectionMode.MOTION:
        motion_frames = _select_by_motion(metrics.motion, requested_count, selected_set, MIN_GAP)
        breakdown = SelectionBreakdown(motion=motion_frames)
        selected_set.update(motion_frames)

    elif mode == SelectionMode.RANDOM:
        random_frames = _select_random(total_frames, requested_count, seed, selected_set, MIN_GAP)
        breakdown = SelectionBreakdown(random=random_frames)
        selected_set.update(random_frames)

    elif mode == SelectionMode.MIXED:
        # Allocation for MIXED:
        # 40% Quantiles (20% dark, 20% bright)
        # 40% Motion
        # Remaining Random
        quantile_n = int(requested_count * 0.4)
        motion_n = int(requested_count * 0.4)
        random_n = requested_count - quantile_n - motion_n

        dark, bright = _select_by_quantile(metrics.luminance, quantile_n)
        selected_set.update(dark)
        selected_set.update(bright)

        motion_frames = _select_by_motion(metrics.motion, motion_n, selected_set, MIN_GAP)
        selected_set.update(motion_frames)

        random_frames = _select_random(total_frames, random_n, seed, selected_set, MIN_GAP)
        selected_set.update(random_frames)

        breakdown = SelectionBreakdown(
            quantile_dark=dark,
            quantile_bright=bright,
            motion=motion_frames,
            random=random_frames,
        )

    selected_list = sorted(selected_set)

    if len(selected_list) < requested_count:
        raise SelectionError(
            reason="insufficient_candidates",
            requested=requested_count,
            found=len(selected_list),
        )

    return FrameSelection(
        frames=selected_list,
        mode=mode,
        seed=seed,
        breakdown=breakdown,
    )


def _select_by_quantile(luminance: Sequence[float], count: int) -> tuple[list[int], list[int]]:
    """Select frames based on luminance extremes."""
    half = count // 2
    # Enumerate and sort by luminance
    indexed = sorted(enumerate(luminance), key=lambda x: x[1])

    dark = sorted([idx for idx, _ in indexed[:half]])
    bright = sorted([idx for idx, _ in indexed[-(count - half) :]])

    return dark, bright


def _select_by_motion(
    motion: Sequence[float], count: int, exclude: set[int], min_gap: int
) -> list[int]:
    """Select frames based on motion peaks, respecting min_gap."""
    # Enumerate and sort by motion descending
    indexed = sorted(enumerate(motion), key=lambda x: x[1], reverse=True)

    selected: list[int] = []
    for idx, _ in indexed:
        if len(selected) >= count:
            break
        if idx in exclude:
            continue
        if all(abs(idx - s) >= min_gap for s in selected) and all(
            abs(idx - e) >= min_gap for e in exclude
        ):
            selected.append(idx)

    return sorted(selected)


def _select_random(
    total_frames: int, count: int, seed: int, exclude: set[int], min_gap: int
) -> list[int]:
    """Select frames randomly, respecting min_gap and excluding existing."""
    rng = random.Random(seed)
    candidates = list(range(total_frames))
    rng.shuffle(candidates)

    selected: list[int] = []
    for idx in candidates:
        if len(selected) >= count:
            break
        if idx in exclude:
            continue
        if all(abs(idx - s) >= min_gap for s in selected) and all(
            abs(idx - e) >= min_gap for e in exclude
        ):
            selected.append(idx)

    return sorted(selected)
