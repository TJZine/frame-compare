import subprocess
import sys

import pytest
from hypothesis import given
from hypothesis import strategies as st

from frame_compare.analysis.frame_plan import (
    create_frame_plan,
    select_uniform_seeded_frames,
)
from frame_compare.errors import InsufficientFramesError


def test_select_uniform_seeded_frames_deterministic() -> None:
    """Same inputs twice -> Identical frames."""
    num_frames = 1000
    count = 10
    seed = 42

    plan1 = select_uniform_seeded_frames(num_frames, count, seed)
    plan2 = select_uniform_seeded_frames(num_frames, count, seed)

    assert plan1.frames == plan2.frames
    assert plan1.seed == plan2.seed
    assert plan1 == plan2


def test_select_uniform_seeded_frames_cross_session() -> None:
    """Run in subprocess -> Same frames."""
    # We run a small script in a subprocess to print the frames
    script = """
from frame_compare.analysis.frame_plan import select_uniform_seeded_frames
plan = select_uniform_seeded_frames(1000, 10, 42)
print(','.join(map(str, plan.frames)))
"""
    # Current process result
    plan = select_uniform_seeded_frames(1000, 10, 42)
    expected_frames = ",".join(map(str, plan.frames))

    # Subprocess result
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == expected_frames


def test_select_uniform_seeded_frames_single_frame() -> None:
    """count=1 -> Valid frame in range."""
    plan = select_uniform_seeded_frames(100, 1, 42)
    assert len(plan.frames) == 1
    assert 0 <= plan.frames[0] < 100
    assert plan.num_frames == 100
    assert plan.count == 1


def test_select_uniform_seeded_frames_all_frames() -> None:
    """count=num_frames -> All indices 0 to n-1."""
    plan = select_uniform_seeded_frames(10, 10, 42)
    assert plan.frames == list(range(10))
    assert len(plan.frames) == 10


def test_select_uniform_seeded_frames_count_exceeds_available() -> None:
    """10 frames from 5-frame video -> InsufficientFramesError."""
    num_frames = 5
    count = 10
    seed = 42

    with pytest.raises(InsufficientFramesError) as excinfo:
        select_uniform_seeded_frames(num_frames, count, seed)

    # Specific contract assertions
    error = excinfo.value
    assert error.code == "FC-3004"
    assert error.context.details is not None
    assert error.context.details["count"] == num_frames
    assert error.context.details["required"] == count
    # Note: path is cast to str in details
    assert error.context.details["path"] == "<frame-plan>"


def test_select_uniform_seeded_frames_zero_count() -> None:
    """count=0 -> Empty list."""
    plan = select_uniform_seeded_frames(100, 0, 42)
    assert plan.frames == []
    assert plan.count == 0


def test_select_uniform_seeded_frames_negative_inputs_raise() -> None:
    with pytest.raises(ValueError, match="num_frames must be >= 0"):
        select_uniform_seeded_frames(-1, 0, 42)
    with pytest.raises(ValueError, match="count must be >= 0"):
        select_uniform_seeded_frames(10, -1, 42)


def test_create_frame_plan_uses_default_seed_when_none() -> None:
    """seed=None -> Uses 42."""
    plan = create_frame_plan(100, 5, None)
    assert plan.seed == 42


def test_create_frame_plan_uses_default_seed_when_omitted() -> None:
    """seed omitted (default arg) -> Uses 42."""
    plan = create_frame_plan(100, 5)
    assert plan.seed == 42


@given(
    num_frames=st.integers(min_value=1, max_value=10000),
    count=st.integers(min_value=0, max_value=100),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_frame_plan_invariants(num_frames: int, count: int, seed: int) -> None:
    if count > num_frames:
        with pytest.raises(InsufficientFramesError):
            select_uniform_seeded_frames(num_frames, count, seed)
    else:
        plan = select_uniform_seeded_frames(num_frames, count, seed)

        # Invariants
        assert len(plan.frames) == count
        assert all(0 <= f < num_frames for f in plan.frames)
        assert len(set(plan.frames)) == len(plan.frames)  # Unique
        assert plan.frames == sorted(plan.frames)  # Sorted
