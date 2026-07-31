"""Unit tests for orchestration runtime context types."""

from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)


@pytest.fixture
def mock_probe() -> ClipProbeSnapshot:
    """Provide a mock probe snapshot with 10 frames."""
    fingerprint = ClipFingerprint(Path("video.mkv"), 1000, 12345)
    return ClipProbeSnapshot(
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=10,
        fps=Fraction(24000, 1001),
        is_hdr=False,
    )


@pytest.fixture
def base_clip_state(mock_probe: ClipProbeSnapshot) -> ClipState:
    """Provide a base ClipState using the mock probe."""
    return ClipState(
        path=Path("video.mkv"),
        label="Reference",
        probe=mock_probe,
        source_fps=mock_probe.fps,
        effective_fps=mock_probe.fps,
    )


def test_clip_state_effective_num_frames_clamps_and_never_negative(
    base_clip_state: ClipState,
):
    """Verify effective_num_frames logic per SSOT test table."""
    # Source num_frames is 10 (valid indices 0-9)

    # 1. GIVEN num_frames=10 WHEN trim window is start=0,end=None THEN effective_num_frames()==10
    state = base_clip_state.with_trim(trim_start_frames=0, trim_end_frame_inclusive=None)
    assert state.effective_num_frames() == 10

    # 2. GIVEN num_frames=10 WHEN trim window is start=9,end=None THEN effective_num_frames()==1
    state = base_clip_state.with_trim(trim_start_frames=9, trim_end_frame_inclusive=None)
    assert state.effective_num_frames() == 1

    # 3. GIVEN num_frames=10 WHEN trim window is start>=num_frames THEN effective_num_frames()==0
    state = base_clip_state.with_trim(trim_start_frames=10, trim_end_frame_inclusive=None)
    assert state.effective_num_frames() == 0
    state = base_clip_state.with_trim(trim_start_frames=15, trim_end_frame_inclusive=None)
    assert state.effective_num_frames() == 0

    # 4. GIVEN num_frames=10 WHEN trim window has end_inclusive < start THEN effective_num_frames()==0
    state = base_clip_state.with_trim(trim_start_frames=5, trim_end_frame_inclusive=4)
    assert state.effective_num_frames() == 0

    # 5. GIVEN any trim settings THEN effective_num_frames() returns an int and is never negative
    # (Testing invalid end_inclusive)
    state = base_clip_state.with_trim(trim_start_frames=0, trim_end_frame_inclusive=-1)
    assert state.effective_num_frames() == 0
    assert isinstance(state.effective_num_frames(), int)

    # 6. GIVEN end_inclusive beyond num_frames THEN it clamps to num_frames-1
    state = base_clip_state.with_trim(trim_start_frames=0, trim_end_frame_inclusive=20)
    assert state.effective_num_frames() == 10


def test_clip_state_with_trim_rejects_negative_trim_start_frames(
    base_clip_state: ClipState,
):
    """Assert ValueError on trim_start_frames < 0 (trim-first invariant)."""
    with pytest.raises(ValueError, match="trim_start_frames must be >= 0"):
        base_clip_state.with_trim(trim_start_frames=-1, trim_end_frame_inclusive=None)


def test_clip_state_immutability(base_clip_state: ClipState):
    """Verify with_trim returns a new instance and doesn't mutate."""
    original_trim = base_clip_state.trim
    new_state = base_clip_state.with_trim(trim_start_frames=5, trim_end_frame_inclusive=None)

    assert base_clip_state.trim == original_trim
    assert new_state.trim.trim_start_frames == 5
    assert new_state is not base_clip_state
