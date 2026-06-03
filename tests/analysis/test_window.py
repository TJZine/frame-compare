"""Tests for selectable analysis-window math."""

from __future__ import annotations

from fractions import Fraction

import pytest

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.window import ClipWindowInput, compute_shared_selection_window


def _clip(frame_count: int = 240, fps: Fraction = Fraction(24, 1)) -> ClipWindowInput:
    return ClipWindowInput(frame_count=frame_count, fps=fps)


def test_lead_only_exclusion_uses_ceiling_start_frame() -> None:
    window = compute_shared_selection_window(
        [_clip()],
        ignore_lead_seconds=1.25,
        ignore_trail_seconds=0.0,
        min_window_seconds=0.0,
    )

    assert window.start_frame == 30
    assert window.end_frame_exclusive == 240


def test_trail_only_exclusion_uses_exclusive_end_frame() -> None:
    window = compute_shared_selection_window(
        [_clip()],
        ignore_lead_seconds=0.0,
        ignore_trail_seconds=2.0,
        min_window_seconds=0.0,
    )

    assert window.start_frame == 0
    assert window.end_frame_exclusive == 192


def test_lead_and_trail_exclusion_intersects_all_clips() -> None:
    window = compute_shared_selection_window(
        [_clip(frame_count=240), _clip(frame_count=180)],
        ignore_lead_seconds=1.0,
        ignore_trail_seconds=1.0,
        min_window_seconds=0.0,
    )

    assert window.start_frame == 24
    assert window.end_frame_exclusive == 156


def test_collapsed_window_expands_end_first_then_start() -> None:
    window = compute_shared_selection_window(
        [_clip(frame_count=100)],
        ignore_lead_seconds=3.8,
        ignore_trail_seconds=0.5,
        min_window_seconds=1.0,
    )

    assert window.start_frame == 76
    assert window.end_frame_exclusive == 100


def test_min_window_at_or_above_duration_uses_full_clip_domain() -> None:
    window = compute_shared_selection_window(
        [_clip(frame_count=120)],
        ignore_lead_seconds=2.0,
        ignore_trail_seconds=2.0,
        min_window_seconds=5.0,
    )

    assert window.start_frame == 0
    assert window.end_frame_exclusive == 120


def test_no_shared_selectable_window_raises_selection_error() -> None:
    with pytest.raises(SelectionError, match="leave no selectable frames"):
        compute_shared_selection_window(
            [_clip(frame_count=48), _clip(frame_count=24)],
            ignore_lead_seconds=1.5,
            ignore_trail_seconds=0.75,
            min_window_seconds=0.0,
        )


def test_rounding_boundary_uses_ceiling_with_small_epsilon() -> None:
    window = compute_shared_selection_window(
        [_clip(frame_count=100, fps=Fraction(24000, 1001))],
        ignore_lead_seconds=float(Fraction(1001, 24000) * 10),
        ignore_trail_seconds=0.0,
        min_window_seconds=0.0,
    )

    assert window.start_frame == 10
