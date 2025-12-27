"""Contract tests for FramePlan deterministic selection.

These tests verify that select_uniform_seeded_frames() produces the exact
reference outputs specified in the plan review report. These outputs are
frozen and must not change.
"""

from __future__ import annotations

import pytest

from frame_compare.analysis.frame_plan import (
    FramePlan,
    create_uniform_seeded_plan,
    select_uniform_seeded_frames,
)


@pytest.mark.tier_a
class TestSelectUniformSeededFrames:
    """Tests for deterministic uniform frame selection."""

    def test_reference_output_240_5_42(self) -> None:
        """Reference output: (240, 5, 42) => [12, 59, 115, 151, 233]."""
        result = select_uniform_seeded_frames(num_frames=240, count=5, seed=42)
        assert result == [12, 59, 115, 151, 233]

    def test_reference_output_240_10_42(self) -> None:
        """Reference output: (240, 10, 42) => [12, 35, 67, 79, 113, 124, 156, 168, 196, 231]."""
        result = select_uniform_seeded_frames(num_frames=240, count=10, seed=42)
        assert result == [12, 35, 67, 79, 113, 124, 156, 168, 196, 231]

    def test_reference_output_240_1_42(self) -> None:
        """Reference output: (240, 1, 42) => [60]."""
        result = select_uniform_seeded_frames(num_frames=240, count=1, seed=42)
        assert result == [60]

    def test_reference_output_10_5_42(self) -> None:
        """Reference output: (10, 5, 42) => [0, 3, 5, 7, 9]."""
        result = select_uniform_seeded_frames(num_frames=10, count=5, seed=42)
        assert result == [0, 3, 5, 7, 9]

    def test_same_seed_same_result(self) -> None:
        """Same seed produces identical results."""
        result1 = select_uniform_seeded_frames(num_frames=100, count=5, seed=12345)
        result2 = select_uniform_seeded_frames(num_frames=100, count=5, seed=12345)
        assert result1 == result2

    def test_different_seed_different_result(self) -> None:
        """Different seeds produce different results."""
        result1 = select_uniform_seeded_frames(num_frames=100, count=5, seed=42)
        result2 = select_uniform_seeded_frames(num_frames=100, count=5, seed=43)
        assert result1 != result2

    def test_frames_sorted_ascending(self) -> None:
        """Frames are always sorted ascending."""
        result = select_uniform_seeded_frames(num_frames=1000, count=20, seed=999)
        assert result == sorted(result)

    def test_frames_unique(self) -> None:
        """All frames are unique (no duplicates)."""
        result = select_uniform_seeded_frames(num_frames=100, count=10, seed=42)
        assert len(result) == len(set(result))

    def test_frames_within_range(self) -> None:
        """All frames are within [0, num_frames)."""
        result = select_uniform_seeded_frames(num_frames=50, count=10, seed=42)
        assert all(0 <= f < 50 for f in result)

    def test_count_equals_num_frames(self) -> None:
        """Edge case: selecting all frames."""
        result = select_uniform_seeded_frames(num_frames=5, count=5, seed=42)
        assert len(result) == 5
        assert set(result) == {0, 1, 2, 3, 4}

    def test_count_exceeds_num_frames_raises(self) -> None:
        """Cannot select more frames than available (FC-3004)."""
        with pytest.raises(ValueError, match="Cannot select 10 frames"):
            select_uniform_seeded_frames(num_frames=5, count=10, seed=42)

    def test_zero_count_raises(self) -> None:
        """Zero count raises ValueError."""
        with pytest.raises(ValueError, match="count must be positive"):
            select_uniform_seeded_frames(num_frames=100, count=0, seed=42)

    def test_zero_num_frames_raises(self) -> None:
        """Zero num_frames raises ValueError."""
        with pytest.raises(ValueError, match="num_frames must be positive"):
            select_uniform_seeded_frames(num_frames=0, count=5, seed=42)


@pytest.mark.tier_a
class TestCreateUniformSeededPlan:
    """Tests for create_uniform_seeded_plan factory function."""

    def test_creates_plan_with_uniform_seeded_method(self) -> None:
        """Plan uses uniform_seeded method."""
        plan = create_uniform_seeded_plan(
            num_frames=240, count=5, seed=42
        )
        assert plan.method == "uniform_seeded"
        assert plan.frames == [12, 59, 115, 151, 233]

    def test_frames_always_populated(self) -> None:
        """FramePlan.frames is NEVER empty (contract requirement)."""
        plan = create_uniform_seeded_plan(
            num_frames=100, count=5, seed=42
        )
        assert len(plan.frames) == 5
        assert all(isinstance(f, int) for f in plan.frames)

    def test_frame_plan_is_frozen(self) -> None:
        """FramePlan is immutable."""
        plan = FramePlan(frames=[1, 2, 3], method="uniform_seeded", seed=42, num_frames=100)
        with pytest.raises(AttributeError):
            plan.frames = [4, 5, 6]  # type: ignore[misc]

