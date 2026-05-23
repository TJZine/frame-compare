"""Frame selection algorithms."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.types import FrameMetrics, FrameSelection, SelectionBreakdown
from frame_compare.config.schema import AnalysisConfig, SelectionMode

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
        dark, bright = _select_by_quantile(
            metrics.luminance,
            requested_count,
            dark_quantile=config.dark_quantile,
            bright_quantile=config.bright_quantile,
        )
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

        dark, bright = _select_by_quantile(
            metrics.luminance,
            quantile_n,
            dark_quantile=config.dark_quantile,
            bright_quantile=config.bright_quantile,
        )
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


def _select_by_quantile(
    luminance: Sequence[float],
    count: int,
    *,
    dark_quantile: float,
    bright_quantile: float,
) -> tuple[list[int], list[int]]:
    """Select frames based on luminance extremes bounded by configured quantiles.

    `dark_quantile` and `bright_quantile` define rank cutoffs (not luminance values):
    - Dark candidates are the lowest `int(N * dark_quantile)` frames by luminance.
    - Bright candidates are the highest frames starting at rank `int(N * bright_quantile)`.

    When the candidate pool is larger than needed, selections are evenly sampled
    across the pool to make the quantile thresholds meaningful.
    """
    if count <= 0:
        return ([], [])

    half = count // 2
    dark_needed = half
    bright_needed = count - half

    indexed = sorted(enumerate(luminance), key=lambda x: x[1])
    n = len(indexed)

    if n == 0:
        return ([], [])

    dark_cut = max(1, int(n * dark_quantile))
    bright_cut = int(n * bright_quantile)
    if bright_cut >= n:
        bright_cut = n - 1

    dark_pool = [idx for idx, _ in indexed[:dark_cut]]
    bright_pool = [idx for idx, _ in indexed[bright_cut:]]

    # Ensure pools can satisfy requested counts.
    if len(dark_pool) < dark_needed:
        dark_pool = [idx for idx, _ in indexed[:dark_needed]]
    if len(bright_pool) < bright_needed:
        bright_pool = [idx for idx, _ in indexed[-bright_needed:]]

    dark = sorted(_sample_evenly(dark_pool, dark_needed))
    bright = sorted(_sample_evenly(bright_pool, bright_needed))
    return (dark, bright)


def _sample_evenly(items: Sequence[int], count: int) -> list[int]:
    """Select `count` items evenly across an ordered sequence."""
    if count <= 0:
        return []
    if len(items) <= count:
        return list(items)
    if count == 1:
        return [items[0]]

    last = len(items) - 1
    positions: list[int] = []
    for i in range(count):
        raw = i * last / (count - 1)
        pos = int(math.floor(raw + 0.5))  # round-half-up
        if positions:
            pos = max(pos, positions[-1] + 1)
        remaining = count - i - 1
        pos = min(pos, last - remaining)
        positions.append(pos)

    return [items[p] for p in positions]


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
