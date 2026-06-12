"""Content-sampled active-picture rectangle refinement for orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import ceil
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import numpy as np
import numpy.typing as npt

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection
from frame_compare.orchestration.context import (
    ACTIVE_RECT_RESOLUTION_ALGORITHM,
    ClipActiveRect,
    ClipState,
)

if TYPE_CHECKING:
    from frame_compare.vs.loader import VSLoader


CONTENT_SAMPLE_COUNT = 16
CONTENT_MIN_VALID_FRAME_CANDIDATES = 4
CONTENT_MIN_AGREEMENT_FRACTION = 0.80
CONTENT_MARGIN_CLUSTER_TOLERANCE_PX = 8
CONTENT_MIN_MARGIN_PX = 8
CONTENT_MIN_MARGIN_FRACTION = 0.01
CONTENT_MAX_AXIS_REMOVAL_FRACTION = 0.35
_EDGE_BASELINE_SAMPLE_PX = 4
_BASELINE_NEAR_DELTA = 0.040
_BORDER_MEAN_DELTA = 0.030
_BORDER_MAX_STDDEV = 0.018
_BORDER_MIN_NEAR_FRACTION = 0.97
_INTERIOR_MIN_MEAN_DELTA = 0.040
_INTERIOR_MIN_STDDEV = 0.020


class ActiveRectContentDetectionError(RuntimeError):
    """Raised when auto content probing cannot produce a trustworthy answer."""


@dataclass(frozen=True, slots=True)
class ContentActiveRect:
    """Plain detected content rectangle before provenance is applied."""

    x: int
    y: int
    width: int
    height: int


class ActiveRectFrameSampler(Protocol):
    def sample_luma_frames(
        self,
        clip: ClipState,
        source_frame_indices: Sequence[int],
    ) -> Sequence[npt.NDArray[np.float32]]:
        """Return normalized luma frames for the requested source-frame indices."""
        ...


class VSActiveRectFrameSampler:
    """Lazily sample normalized luma frames through an injected VS loader."""

    def __init__(self, loader: VSLoader) -> None:
        self._loader = loader

    def sample_luma_frames(
        self,
        clip: ClipState,
        source_frame_indices: Sequence[int],
    ) -> Sequence[npt.NDArray[np.float32]]:
        import vapoursynth as vs

        source = self._loader.load(Path(clip.path))
        try:
            node = source.clip
            if node.format.color_family != vs.YUV:
                node = node.resize.Bicubic(format=vs.YUV420P8)
            max_value: float = (
                1.0
                if node.format.sample_type == vs.FLOAT
                else float((1 << node.format.bits_per_sample) - 1)
            )
            frames: list[npt.NDArray[np.float32]] = []
            for index in source_frame_indices:
                frame = node.get_frame(index)
                frames.append(np.asarray(frame[0], dtype=np.float32) / max_value)
                del frame
            return frames
        finally:
            del source


def refine_auto_content_active_rects_for_clips(
    *,
    clips: Sequence[ClipState],
    selection_window: SelectionWindow,
    detection: ScreenshotActiveRectDetection,
    sampler: ActiveRectFrameSampler | None,
    fail_closed: bool,
) -> tuple[list[ClipState], list[str]]:
    """Refine unresolved full-frame active rects when opt-in auto detection is enabled."""
    if detection != ScreenshotActiveRectDetection.AUTO:
        return list(clips), []

    refinable = [clip for clip in clips if _clip_has_full_frame_static_rect(clip)]
    if not refinable:
        return list(clips), []

    if sampler is None:
        return _handle_detection_error(
            clips,
            fail_closed=fail_closed,
            message="active-rect auto detection could not run because no VS loader is available",
        )

    warnings: list[str] = []
    refined_by_path: dict[Path, ClipActiveRect] = {}
    for clip in refinable:
        sample_indices = sample_source_frame_indices(
            clip=clip,
            selection_window=selection_window,
        )
        if len(sample_indices) < CONTENT_MIN_VALID_FRAME_CANDIDATES:
            warnings.append(
                f"active-rect auto detection skipped {clip.path.name}: fewer than "
                f"{CONTENT_MIN_VALID_FRAME_CANDIDATES} sample frames were available."
            )
            continue
        try:
            frames = sampler.sample_luma_frames(clip, sample_indices)
        except Exception as exc:
            message = (
                f"active-rect auto detection failed for {clip.path.name}: "
                f"{type(exc).__name__}: {exc}"
            )
            if fail_closed:
                return _handle_detection_error(
                    clips,
                    fail_closed=fail_closed,
                    message=message,
                )
            warnings.append(message)
            continue

        rect = detect_content_active_rect(
            frames,
            frame_width=clip.probe.width,
            frame_height=clip.probe.height,
        )
        if rect is None:
            continue
        refined_by_path[clip.path] = ClipActiveRect(
            x=rect.x,
            y=rect.y,
            width=rect.width,
            height=rect.height,
            source="content-derived",
            detection_mode="auto",
            algorithm_id=ACTIVE_RECT_RESOLUTION_ALGORITHM,
        )

    if not refined_by_path:
        return list(clips), warnings
    return [
        replace(clip, active_rect=refined_by_path.get(clip.path, clip.active_rect))
        for clip in clips
    ], warnings


def sample_source_frame_indices(
    *,
    clip: ClipState,
    selection_window: SelectionWindow,
    sample_count: int = CONTENT_SAMPLE_COUNT,
) -> tuple[int, ...]:
    """Select deterministic midpoint/bin-centered source-frame indices."""
    start, frame_count = _sample_local_domain(clip=clip, selection_window=selection_window)
    if frame_count <= 0 or sample_count <= 0:
        return ()

    count = min(sample_count, frame_count)
    indices: list[int] = []
    for sample in range(count):
        local = start + int(((sample + 0.5) * frame_count) / count)
        local = min(start + frame_count - 1, max(start, local))
        source_frame = clip.trim.trim_start_frames + local
        if source_frame not in indices:
            indices.append(source_frame)
    return tuple(indices)


def detect_content_active_rect(
    frames: Sequence[npt.NDArray[np.float32]],
    *,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> ContentActiveRect | None:
    """Detect a conservative active rect from normalized luma sample frames."""
    if len(frames) < CONTENT_MIN_VALID_FRAME_CANDIDATES:
        return None

    candidates: list[_Margins] = []
    for frame in frames:
        candidate = _candidate_margins_for_frame(frame)
        if candidate is not None:
            candidates.append(candidate)

    if len(candidates) < CONTENT_MIN_VALID_FRAME_CANDIDATES:
        return None

    cluster = _largest_margin_cluster(candidates)
    if cluster is None:
        return None
    required_support = ceil(len(frames) * CONTENT_MIN_AGREEMENT_FRACTION)
    if len(cluster) < required_support:
        return None

    margins = _median_margins(cluster)
    height, width = frames[0].shape
    if frame_width is not None and width != frame_width:
        return None
    if frame_height is not None and height != frame_height:
        return None
    return _rect_from_margins(margins, width=width, height=height)


def _handle_detection_error(
    clips: Sequence[ClipState],
    *,
    fail_closed: bool,
    message: str,
) -> tuple[list[ClipState], list[str]]:
    if fail_closed:
        raise ActiveRectContentDetectionError(message)
    return list(clips), [message]


def _clip_has_full_frame_static_rect(clip: ClipState) -> bool:
    rect = clip.active_rect
    return (
        rect is not None
        and rect.source == "full-frame"
        and rect.x == 0
        and rect.y == 0
        and rect.width == clip.probe.width
        and rect.height == clip.probe.height
    )


def _sample_local_domain(
    *,
    clip: ClipState,
    selection_window: SelectionWindow,
) -> tuple[int, int]:
    if selection_window.frame_count > 0:
        return selection_window.start_frame, selection_window.frame_count
    return 0, clip.effective_num_frames()


class _Margins(tuple[int, int, int, int]):
    @property
    def left(self) -> int:
        return self[0]

    @property
    def top(self) -> int:
        return self[1]

    @property
    def right(self) -> int:
        return self[2]

    @property
    def bottom(self) -> int:
        return self[3]


def _margins(left: int, top: int, right: int, bottom: int) -> _Margins:
    return _Margins((left, top, right, bottom))


def _candidate_margins_for_frame(frame: npt.NDArray[np.float32]) -> _Margins | None:
    if frame.ndim != 2:
        return None
    height, width = frame.shape
    if height <= 0 or width <= 0:
        return None

    baseline = _edge_black_baseline(frame)
    max_vertical_scan = int(height * CONTENT_MAX_AXIS_REMOVAL_FRACTION)
    max_horizontal_scan = int(width * CONTENT_MAX_AXIS_REMOVAL_FRACTION)
    top = _scan_top(frame, baseline, max_vertical_scan)
    bottom = _scan_bottom(frame, baseline, max_vertical_scan)
    left = _scan_left(frame, baseline, max_horizontal_scan)
    right = _scan_right(frame, baseline, max_horizontal_scan)
    candidate = _margins(left, top, right, bottom)
    if not _margins_are_sane(candidate, width=width, height=height):
        return None

    interior = frame[top : height - bottom, left : width - right]
    if not _interior_has_content(interior, baseline):
        return None
    return candidate


def _edge_black_baseline(frame: npt.NDArray[np.float32]) -> float:
    edge = _edge_samples(frame)
    return float(np.percentile(edge, 10))


def _edge_samples(frame: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
    height, width = frame.shape
    rows = min(_EDGE_BASELINE_SAMPLE_PX, height)
    cols = min(_EDGE_BASELINE_SAMPLE_PX, width)
    return np.concatenate(
        (
            frame[:rows, :].reshape(-1),
            frame[height - rows :, :].reshape(-1),
            frame[:, :cols].reshape(-1),
            frame[:, width - cols :].reshape(-1),
        )
    )


def _scan_top(frame: npt.NDArray[np.float32], baseline: float, limit: int) -> int:
    for index in range(limit):
        if not _line_is_bar_like(frame[index, :], baseline):
            return index
    return limit


def _scan_bottom(frame: npt.NDArray[np.float32], baseline: float, limit: int) -> int:
    height = frame.shape[0]
    for offset in range(limit):
        if not _line_is_bar_like(frame[height - offset - 1, :], baseline):
            return offset
    return limit


def _scan_left(frame: npt.NDArray[np.float32], baseline: float, limit: int) -> int:
    for index in range(limit):
        if not _line_is_bar_like(frame[:, index], baseline):
            return index
    return limit


def _scan_right(frame: npt.NDArray[np.float32], baseline: float, limit: int) -> int:
    width = frame.shape[1]
    for offset in range(limit):
        if not _line_is_bar_like(frame[:, width - offset - 1], baseline):
            return offset
    return limit


def _line_is_bar_like(line: npt.NDArray[np.float32], baseline: float) -> bool:
    if line.size == 0:
        return False
    mean = float(line.mean())
    stddev = float(line.std())
    near_fraction = float(np.count_nonzero(np.abs(line - baseline) <= _BASELINE_NEAR_DELTA))
    near_fraction /= float(line.size)
    return (
        mean <= baseline + _BORDER_MEAN_DELTA
        and stddev <= _BORDER_MAX_STDDEV
        and near_fraction >= _BORDER_MIN_NEAR_FRACTION
    )


def _margins_are_sane(margins: _Margins, *, width: int, height: int) -> bool:
    if margins.left + margins.right >= width or margins.top + margins.bottom >= height:
        return False
    horizontal_removed_fraction = (margins.left + margins.right) / width
    vertical_removed_fraction = (margins.top + margins.bottom) / height
    if horizontal_removed_fraction > CONTENT_MAX_AXIS_REMOVAL_FRACTION:
        return False
    if vertical_removed_fraction > CONTENT_MAX_AXIS_REMOVAL_FRACTION:
        return False

    min_horizontal_margin = max(CONTENT_MIN_MARGIN_PX, int(width * CONTENT_MIN_MARGIN_FRACTION))
    min_vertical_margin = max(CONTENT_MIN_MARGIN_PX, int(height * CONTENT_MIN_MARGIN_FRACTION))
    has_significant_horizontal = max(margins.left, margins.right) >= min_horizontal_margin
    has_significant_vertical = max(margins.top, margins.bottom) >= min_vertical_margin
    return has_significant_horizontal or has_significant_vertical


def _interior_has_content(frame: npt.NDArray[np.float32], baseline: float) -> bool:
    if frame.size == 0:
        return False
    return (
        float(frame.mean()) >= baseline + _INTERIOR_MIN_MEAN_DELTA
        or float(frame.std()) >= _INTERIOR_MIN_STDDEV
    )


def _largest_margin_cluster(candidates: Sequence[_Margins]) -> list[_Margins] | None:
    clusters: list[list[_Margins]] = []
    for candidate in candidates:
        for cluster in clusters:
            if _margins_match(candidate, cluster[0]):
                cluster.append(candidate)
                break
        else:
            clusters.append([candidate])
    if not clusters:
        return None
    return max(clusters, key=len)


def _margins_match(left: _Margins, right: _Margins) -> bool:
    return all(
        abs(left_value - right_value) <= CONTENT_MARGIN_CLUSTER_TOLERANCE_PX
        for left_value, right_value in zip(left, right, strict=True)
    )


def _median_margins(cluster: Sequence[_Margins]) -> _Margins:
    return _margins(
        int(np.median([item.left for item in cluster])),
        int(np.median([item.top for item in cluster])),
        int(np.median([item.right for item in cluster])),
        int(np.median([item.bottom for item in cluster])),
    )


def _rect_from_margins(margins: _Margins, *, width: int, height: int) -> ContentActiveRect | None:
    if not _margins_are_sane(margins, width=width, height=height):
        return None
    x = _normalize_even_offset(margins.left)
    y = _normalize_even_offset(margins.top)
    right = width - _normalize_even_offset(margins.right)
    bottom = height - _normalize_even_offset(margins.bottom)
    rect_width = _normalize_even_size(right - x)
    rect_height = _normalize_even_size(bottom - y)
    if rect_width <= 0 or rect_height <= 0:
        return None
    if x + rect_width > width or y + rect_height > height:
        return None
    return ContentActiveRect(
        x=x,
        y=y,
        width=rect_width,
        height=rect_height,
    )


def _normalize_even_offset(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def _normalize_even_size(value: int) -> int:
    if value <= 1:
        return value
    return value - (value % 2)
