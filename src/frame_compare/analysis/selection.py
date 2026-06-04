"""Frame selection algorithms."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from fractions import Fraction

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.types import (
    FrameMetrics,
    FrameSelection,
    SelectionBreakdown,
    SelectionDetail,
    SelectionDetailsByFrame,
)
from frame_compare.config.schema import AnalysisConfig

MIN_GAP: int = 5


def select_frames(metrics: FrameMetrics, config: AnalysisConfig) -> FrameSelection:
    """Select frames from explicit user/random/dark/bright/motion requests."""

    total_frames = metrics.metadata.frame_count
    if total_frames == 0:
        raise SelectionError(reason="empty_metrics", requested=_requested_count(config), found=0)

    seed = config.random_seed

    selected_set: set[int] = set()
    user_frames = sorted({frame for frame in config.user_frames if 0 <= frame < total_frames})
    selected_set.update(user_frames)

    dark = _select_dark_frames(
        metrics.luminance,
        config.dark_frame_count,
        dark_quantile=config.dark_quantile,
    )
    dark = [frame for frame in dark if frame not in selected_set]
    selected_set.update(dark)

    bright = _select_bright_frames(
        metrics.luminance,
        config.bright_frame_count,
        bright_quantile=config.bright_quantile,
    )
    bright = [frame for frame in bright if frame not in selected_set]
    selected_set.update(bright)

    motion_frames = _select_by_motion(
        metrics.motion,
        config.motion_frame_count,
        selected_set,
        MIN_GAP,
    )
    selected_set.update(motion_frames)

    random_frames = _select_random(
        total_frames,
        config.random_frame_count,
        seed,
        selected_set,
        MIN_GAP,
    )
    selected_set.update(random_frames)

    breakdown = SelectionBreakdown(
        user=user_frames,
        quantile_dark=dark,
        quantile_bright=bright,
        motion=motion_frames,
        random=random_frames,
    )

    selected_list = sorted(selected_set)
    requested_count = _requested_count(config)

    if len(selected_list) < requested_count and len(selected_list) >= total_frames:
        raise SelectionError(
            reason="insufficient_candidates",
            requested=requested_count,
            found=len(selected_list),
        )

    return FrameSelection(
        frames=selected_list,
        seed=seed,
        breakdown=breakdown,
        selection_details=_build_selection_details_by_frame(
            metrics=metrics,
            breakdown=breakdown,
        ),
    )


def _requested_count(config: AnalysisConfig) -> int:
    return (
        len(config.user_frames)
        + config.random_frame_count
        + config.dark_frame_count
        + config.bright_frame_count
        + config.motion_frame_count
    )


def _build_selection_details_by_frame(
    *,
    metrics: FrameMetrics,
    breakdown: SelectionBreakdown,
) -> SelectionDetailsByFrame:
    details_by_frame: SelectionDetailsByFrame = {}

    def _store_details(
        frames: Sequence[int],
        *,
        label: str,
        category_note: str,
        score_values: Sequence[float] | None,
    ) -> None:
        for frame_index in frames:
            if frame_index in details_by_frame:
                continue
            score = None
            if score_values is not None and 0 <= frame_index < len(score_values):
                score = score_values[frame_index]
            details_by_frame[frame_index] = SelectionDetail(
                frame_index=frame_index,
                label=label,
                source="analysis",
                timecode=_format_selection_timecode(frame_index, metrics.metadata.fps),
                score=score,
                clip_role="analyze",
                notes=category_note,
            )

    _store_details(breakdown.user, label="User", category_note="user", score_values=None)
    _store_details(
        breakdown.quantile_dark,
        label="Dark",
        category_note="quantile_dark",
        score_values=metrics.luminance,
    )
    _store_details(
        breakdown.quantile_bright,
        label="Bright",
        category_note="quantile_bright",
        score_values=metrics.luminance,
    )
    _store_details(
        breakdown.motion,
        label="Motion",
        category_note="motion",
        score_values=metrics.motion,
    )
    _store_details(
        breakdown.random,
        label="Random",
        category_note="random",
        score_values=None,
    )

    return details_by_frame


def _format_selection_timecode(frame_index: int, fps: Fraction) -> str | None:
    if fps <= 0:
        return None
    total_milliseconds = round((Fraction(frame_index, 1) * 1000) / fps)
    total_seconds, milliseconds = divmod(total_milliseconds, 1000)
    total_minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def _select_dark_frames(
    luminance: Sequence[float],
    count: int,
    *,
    dark_quantile: float,
) -> list[int]:
    if count <= 0:
        return []
    indexed = sorted(enumerate(luminance), key=lambda x: x[1])
    n = len(indexed)
    if n == 0:
        return []
    dark_cut = max(1, int(n * dark_quantile))
    dark_pool = [idx for idx, _ in indexed[:dark_cut]]
    if len(dark_pool) < count:
        dark_pool = [idx for idx, _ in indexed[:count]]
    return sorted(_sample_evenly(dark_pool, count))


def _select_bright_frames(
    luminance: Sequence[float],
    count: int,
    *,
    bright_quantile: float,
) -> list[int]:
    if count <= 0:
        return []
    indexed = sorted(enumerate(luminance), key=lambda x: x[1])
    n = len(indexed)
    if n == 0:
        return []
    bright_cut = int(n * bright_quantile)
    if bright_cut >= n:
        bright_cut = n - 1
    bright_pool = [idx for idx, _ in indexed[bright_cut:]]
    if len(bright_pool) < count:
        bright_pool = [idx for idx, _ in indexed[-count:]]
    return sorted(_sample_evenly(bright_pool, count))


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
    """Select frames via a stable seeded ordering, respecting min_gap and exclusions."""
    candidates = sorted(range(total_frames), key=lambda idx: _stable_seeded_order(seed, idx))

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


def _stable_seeded_order(seed: int, frame_index: int) -> bytes:
    """Return a stable seed-derived ordering key for a frame index."""
    payload = f"{seed}:{frame_index}".encode("ascii")
    return hashlib.blake2b(payload, digest_size=16).digest()
