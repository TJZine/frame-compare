"""Selectable analysis-window math."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from frame_compare.analysis.errors import SelectionError

_ROUNDING_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class ClipWindowInput:
    """Clip domain values needed to calculate selectable analysis windows."""

    frame_count: int
    fps: Fraction


@dataclass(frozen=True, slots=True)
class SelectionWindow:
    """Shared selectable window relative to each clip's base trimmed domain."""

    start_frame: int
    end_frame_exclusive: int

    @property
    def frame_count(self) -> int:
        return max(0, self.end_frame_exclusive - self.start_frame)


def compute_shared_selection_window(
    clips: list[ClipWindowInput],
    *,
    ignore_lead_seconds: float,
    ignore_trail_seconds: float,
    min_window_seconds: float,
) -> SelectionWindow:
    """Compute the shared selectable aligned-domain window for all clips."""
    if not clips:
        raise SelectionError("no clips available for selection", 1, 0)

    windows = [
        _clip_selection_window(
            clip,
            ignore_lead_seconds=ignore_lead_seconds,
            ignore_trail_seconds=ignore_trail_seconds,
            min_window_seconds=min_window_seconds,
        )
        for clip in clips
    ]
    shared_start = max(window.start_frame for window in windows)
    shared_end = min(window.end_frame_exclusive for window in windows)
    if shared_end <= shared_start:
        raise SelectionError("analysis ignore windows leave no selectable frames", 1, 0)
    return SelectionWindow(start_frame=shared_start, end_frame_exclusive=shared_end)


def _clip_selection_window(
    clip: ClipWindowInput,
    *,
    ignore_lead_seconds: float,
    ignore_trail_seconds: float,
    min_window_seconds: float,
) -> SelectionWindow:
    if clip.frame_count <= 0:
        return SelectionWindow(start_frame=0, end_frame_exclusive=0)
    if clip.fps <= 0:
        raise SelectionError("clip fps must be positive for analysis windowing", 1, 0)

    duration_seconds = float(Fraction(clip.frame_count, 1) / clip.fps)
    if min_window_seconds >= duration_seconds:
        return SelectionWindow(start_frame=0, end_frame_exclusive=clip.frame_count)

    start_frame = _seconds_to_start_frame(ignore_lead_seconds, clip.fps)
    end_frame = _seconds_to_end_frame(duration_seconds - ignore_trail_seconds, clip.fps)
    start_frame = _clamp_frame(start_frame, 0, clip.frame_count)
    end_frame = _clamp_frame(end_frame, 0, clip.frame_count)

    min_frames = min(
        clip.frame_count,
        _seconds_to_start_frame(min_window_seconds, clip.fps),
    )
    if end_frame - start_frame < min_frames:
        end_frame = min(clip.frame_count, start_frame + min_frames)
        start_frame = max(0, end_frame - min_frames)

    return SelectionWindow(start_frame=start_frame, end_frame_exclusive=end_frame)


def _seconds_to_start_frame(seconds: float, fps: Fraction) -> int:
    return int(math.ceil(seconds * float(fps) - _ROUNDING_EPSILON))


def _seconds_to_end_frame(seconds: float, fps: Fraction) -> int:
    return int(math.ceil(seconds * float(fps) - _ROUNDING_EPSILON))


def _clamp_frame(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


__all__ = ["ClipWindowInput", "SelectionWindow", "compute_shared_selection_window"]
