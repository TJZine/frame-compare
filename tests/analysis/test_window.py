"""Tests for selectable analysis-window math."""

from __future__ import annotations

from fractions import Fraction

import pytest

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.window import ClipWindowInput, compute_shared_selection_window


def _clip(frame_count: int = 240, fps: Fraction = Fraction(24, 1)) -> ClipWindowInput:
    return ClipWindowInput(frame_count=frame_count, fps=fps)


def test_no_shared_selectable_window_raises_selection_error() -> None:
    with pytest.raises(SelectionError, match="leave no selectable frames"):
        compute_shared_selection_window(
            [_clip(frame_count=48), _clip(frame_count=24)],
            ignore_lead_seconds=1.5,
            ignore_trail_seconds=0.75,
            min_window_seconds=0.0,
        )


@pytest.mark.parametrize(
    "clips, lead, trail, minimum, expected_start, expected_end",
    [
        pytest.param([_clip()], 1.25, 0.0, 0.0, 30, 240, id="lead_only"),
        pytest.param([_clip()], 0.0, 2.0, 0.0, 0, 192, id="trail_only"),
        pytest.param([_clip(240), _clip(180)], 1.0, 1.0, 0.0, 24, 156, id="lead_and_trail"),
        pytest.param([_clip(100)], 3.8, 0.5, 1.0, 76, 100, id="collapsed"),
        pytest.param([_clip(120)], 2.0, 2.0, 5.0, 0, 120, id="minimum_full_domain"),
        pytest.param(
            [_clip(100, Fraction(24000, 1001))],
            float(Fraction(1001, 24000) * 10),
            0.0,
            0.0,
            10,
            None,
            id="rounding_boundary",
        ),
    ],
)
def test_selection_window_cases(
    clips: list[ClipWindowInput],
    lead: float,
    trail: float,
    minimum: float,
    expected_start: int,
    expected_end: int | None,
) -> None:
    window = compute_shared_selection_window(
        clips, ignore_lead_seconds=lead, ignore_trail_seconds=trail, min_window_seconds=minimum
    )
    assert window.start_frame == expected_start
    if expected_end is not None:
        assert window.end_frame_exclusive == expected_end
