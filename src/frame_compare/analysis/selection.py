"""Frame selection algorithms."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from fractions import Fraction
from math import ceil

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.types import (
    FrameMetrics,
    FrameSelection,
    SelectionBreakdown,
    SelectionDetail,
    SelectionDetailsByFrame,
)
from frame_compare.config.schema import AnalysisConfig

PREFERRED_GAP_SECONDS = Fraction(1, 2)


def preferred_frame_gap(fps: Fraction) -> int:
    """Return the preferred frame separation for an effective selection FPS.

    The half-second target is rounded up exactly to a whole frame and clamped
    to one frame so automatic selections always remain unique.
    """
    return max(1, ceil(fps * PREFERRED_GAP_SECONDS))


def select_random_frames(
    total_frames: int,
    count: int,
    seed: int,
    exclude: set[int] | None = None,
    *,
    selection_fps: Fraction,
) -> list[int]:
    """Select deterministic random frames using the reference-domain FPS."""
    return _select_random(
        total_frames,
        count,
        seed,
        exclude or set(),
        preferred_frame_gap(selection_fps),
    )


def select_frames(
    metrics: FrameMetrics,
    config: AnalysisConfig,
    *,
    selection_fps: Fraction | None = None,
) -> FrameSelection:
    """Select frames from explicit and automatic requests.

    ``selection_fps`` identifies the frame domain that will be rendered. When
    omitted, the metric metadata FPS is used for direct analysis-domain calls.
    """

    total_frames = metrics.eligible_frame_count
    if total_frames == 0:
        raise SelectionError(reason="empty_metrics", requested=_requested_count(config), found=0)

    seed = config.random_seed
    effective_selection_fps = metrics.metadata.fps if selection_fps is None else selection_fps
    preferred_gap = preferred_frame_gap(effective_selection_fps)

    selected_set: set[int] = set()
    user_frames = sorted({frame for frame in config.user_frames if 0 <= frame < total_frames})
    selected_set.update(user_frames)

    metric_source_frames = [
        source_frame - metrics.metadata.metric_source_start
        for source_frame in metrics.source_frames()
    ]
    luminance_by_frame = list(zip(metric_source_frames, metrics.luminance, strict=True))
    motion_by_frame = list(zip(metric_source_frames, metrics.motion, strict=True))

    dark = _select_dark_frames(
        luminance_by_frame,
        config.dark_frame_count,
        selected_set,
        total_frames=total_frames,
        preferred_gap=preferred_gap,
        dark_quantile=config.dark_quantile,
    )
    selected_set.update(dark)

    bright = _select_bright_frames(
        luminance_by_frame,
        config.bright_frame_count,
        selected_set,
        total_frames=total_frames,
        preferred_gap=preferred_gap,
        bright_quantile=config.bright_quantile,
    )
    selected_set.update(bright)

    motion_frames = _select_by_motion(
        motion_by_frame,
        config.motion_frame_count,
        selected_set,
        total_frames,
        preferred_gap,
    )
    selected_set.update(motion_frames)

    random_frames = select_random_frames(
        total_frames,
        config.random_frame_count,
        seed,
        selected_set,
        selection_fps=effective_selection_fps,
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
    requested_count = _requested_count(config, accepted_user_frame_count=len(user_frames))

    if len(selected_list) < requested_count:
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
            fps=effective_selection_fps,
        ),
    )


def _requested_count(
    config: AnalysisConfig,
    *,
    accepted_user_frame_count: int | None = None,
) -> int:
    return (
        (
            len(config.user_frames)
            if accepted_user_frame_count is None
            else accepted_user_frame_count
        )
        + config.random_frame_count
        + config.dark_frame_count
        + config.bright_frame_count
        + config.motion_frame_count
    )


def _build_selection_details_by_frame(
    *,
    metrics: FrameMetrics,
    breakdown: SelectionBreakdown,
    fps: Fraction,
) -> SelectionDetailsByFrame:
    details_by_frame: SelectionDetailsByFrame = {}
    luminance_scores = {
        source_frame - metrics.metadata.metric_source_start: value
        for source_frame, value in zip(metrics.source_frames(), metrics.luminance, strict=True)
    }
    motion_scores = {
        source_frame - metrics.metadata.metric_source_start: value
        for source_frame, value in zip(metrics.source_frames(), metrics.motion, strict=True)
    }

    def _store_details(
        frames: Sequence[int],
        *,
        label: str,
        category_note: str,
        score_values: dict[int, float] | None,
    ) -> None:
        for frame_index in frames:
            if frame_index in details_by_frame:
                continue
            score = None
            if score_values is not None:
                score = score_values.get(frame_index)
            details_by_frame[frame_index] = SelectionDetail(
                frame_index=frame_index,
                label=label,
                source="analysis",
                timecode=_format_selection_timecode(frame_index, fps),
                score=score,
                clip_role="analyze",
                notes=category_note,
            )

    _store_details(breakdown.user, label="User", category_note="user", score_values=None)
    _store_details(
        breakdown.quantile_dark,
        label="Dark",
        category_note="quantile_dark",
        score_values=luminance_scores,
    )
    _store_details(
        breakdown.quantile_bright,
        label="Bright",
        category_note="quantile_bright",
        score_values=luminance_scores,
    )
    _store_details(
        breakdown.motion,
        label="Motion",
        category_note="motion",
        score_values=motion_scores,
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
    luminance: Sequence[tuple[int, float]],
    count: int,
    exclude: set[int],
    *,
    total_frames: int,
    preferred_gap: int,
    dark_quantile: float,
) -> list[int]:
    if count <= 0:
        return []
    indexed = sorted(luminance, key=lambda item: (item[1], item[0]))
    n = len(indexed)
    if n == 0:
        return []
    dark_cut = max(1, int(n * dark_quantile))
    dark_pool = [idx for idx, _ in indexed[:dark_cut] if idx not in exclude]
    if len(dark_pool) < count:
        dark_pool = [idx for idx, _ in indexed if idx not in exclude]
    return _select_stratified(dark_pool, count, exclude, total_frames, preferred_gap)


def _select_bright_frames(
    luminance: Sequence[tuple[int, float]],
    count: int,
    exclude: set[int],
    *,
    total_frames: int,
    preferred_gap: int,
    bright_quantile: float,
) -> list[int]:
    if count <= 0:
        return []
    indexed = sorted(luminance, key=lambda item: (-item[1], item[0]))
    n = len(indexed)
    if n == 0:
        return []
    bright_count = max(1, n - int(n * bright_quantile))
    bright_pool = [idx for idx, _ in indexed[:bright_count] if idx not in exclude]
    if len(bright_pool) < count:
        bright_pool = [idx for idx, _ in indexed if idx not in exclude]
    return _select_stratified(bright_pool, count, exclude, total_frames, preferred_gap)


def _select_stratified(
    ranked_candidates: Sequence[int],
    count: int,
    exclude: set[int],
    total_frames: int,
    preferred_gap: int,
) -> list[int]:
    """Select ranked candidates across strata with progressive gap relaxation."""
    if count <= 0:
        return []

    selected: list[int] = []

    def available(frame: int, *, required_gap: int) -> bool:
        if frame in exclude or frame in selected:
            return False
        return all(abs(frame - other) >= required_gap for other in exclude) and all(
            abs(frame - other) >= required_gap for other in selected
        )

    strata: list[list[int]] = [[] for _ in range(count)]
    for frame in ranked_candidates:
        stratum = min(frame * count // total_frames, count - 1)
        strata[stratum].append(frame)

    for candidates in strata:
        candidate = next(
            (frame for frame in candidates if available(frame, required_gap=preferred_gap)),
            None,
        )
        if candidate is not None:
            selected.append(candidate)

    for required_gap in range(preferred_gap, 0, -1):
        for frame in ranked_candidates:
            if len(selected) >= count:
                return sorted(selected)
            if available(frame, required_gap=required_gap):
                selected.append(frame)

    return sorted(selected)


def _select_by_motion(
    motion: Sequence[tuple[int, float]],
    count: int,
    exclude: set[int],
    total_frames: int,
    preferred_gap: int,
) -> list[int]:
    """Select temporally stratified frames ranked by descending motion."""
    candidates = [idx for idx, _ in sorted(motion, key=lambda item: (-item[1], item[0]))]
    return _select_stratified(candidates, count, exclude, total_frames, preferred_gap)


def _select_random(
    total_frames: int, count: int, seed: int, exclude: set[int], preferred_gap: int
) -> list[int]:
    """Select temporally stratified frames via a stable seeded ordering."""
    candidates = sorted(range(total_frames), key=lambda idx: _stable_seeded_order(seed, idx))
    return _select_stratified(candidates, count, exclude, total_frames, preferred_gap)


def _stable_seeded_order(seed: int, frame_index: int) -> bytes:
    """Return a stable seed-derived ordering key for a frame index."""
    payload = f"{seed}:{frame_index}".encode("ascii")
    return hashlib.blake2b(payload, digest_size=16).digest()
