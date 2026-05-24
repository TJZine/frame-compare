"""Core audio alignment math and type tests."""

# pyright: reportPrivateUsage=false

from dataclasses import FrozenInstanceError
from fractions import Fraction

import numpy as np
import pytest

from frame_compare.services.alignment_math import (
    calculate_alignment_trims,
)
from frame_compare.services.alignment_math import (
    cross_correlate as _cross_correlate,
)
from frame_compare.services.alignment_math import (
    samples_to_frames as _samples_to_frames,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult


def test_alignment_result_is_frozen():
    """Test that AlignmentResult is immutable."""
    res = AlignmentResult("ref", "comp", 0, 0.0, 1.0, "cross_correlation", "computed")
    with pytest.raises(FrozenInstanceError):
        res.frame_offset = 10  # type: ignore


def test_alignment_config_defaults():
    """Test AlignmentConfig default values."""
    cfg = AlignmentConfig()
    assert cfg.enable is True
    assert cfg.sample_rate == 8000
    assert cfg.max_offset_seconds == 30.0
    assert cfg.use_vspreview is False
    assert cfg.force_interactive is False
    assert cfg.cache_results is True


def test_cross_correlate_identical_signals():
    """Test alignment of identical signals."""
    ref = np.array([1.0, 0.5, 0.0, -0.5], dtype=np.float32)
    comp = ref.copy()
    offset, score = _cross_correlate(ref, comp)
    assert offset == 0
    assert score == pytest.approx(1.0, abs=1e-6)  # type: ignore


def test_cross_correlate_positive_shift():
    """Test alignment where comparison starts after reference."""
    ref = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)
    comp = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)
    offset, _ = _cross_correlate(ref, comp)
    assert offset == 2


def test_cross_correlate_negative_shift():
    """Test alignment where comparison starts before reference."""
    ref = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)
    comp = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)
    offset, _ = _cross_correlate(ref, comp)
    assert offset == -2


def test_cross_correlate_zero_norm_raises():
    """Test that zero-norm signals raise AudioAlignmentError."""
    ref = np.zeros(10, dtype=np.float32)
    comp = np.ones(10, dtype=np.float32)
    with pytest.raises(AudioAlignmentError, match="zero-norm"):
        _cross_correlate(ref, comp)


def test_samples_to_frames_integer_fps():
    """Test sample to frame conversion with integer FPS."""
    assert _samples_to_frames(8000, 8000, Fraction(24, 1)) == 24


def test_samples_to_frames_fractional_fps():
    """Test sample to frame conversion with fractional FPS."""
    # 24000/1001 * (8008/8000) = 23.976... * 1.001 = 24.0
    assert _samples_to_frames(8008, 8000, Fraction(24000, 1001)) == 24


def test_cross_correlate_respects_max_offset_window():
    """Bounded offset search should not select peaks outside the configured window."""
    reference = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)
    comparison = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)

    offset, _ = _cross_correlate(reference, comparison, max_offset_samples=1)

    assert abs(offset) <= 1


def test_cross_correlate_empty_signal_raises() -> None:
    """Empty signals must fail fast with a clear alignment error."""
    ref = np.array([], dtype=np.float32)
    comp = np.ones(10, dtype=np.float32)

    with pytest.raises(AudioAlignmentError, match="empty audio signal"):
        _cross_correlate(ref, comp)


def test_calculate_alignment_trims_rejects_mismatched_lengths_when_offsets_are_unknown() -> None:
    """Default trim path must preserve the same length invariant as aligned offsets."""
    with pytest.raises(ValueError, match=r"comp_offsets and comp_num_frames.*1 != 2"):
        calculate_alignment_trims(
            ref_num_frames=100,
            comp_offsets=[None],
            comp_num_frames=[100, 100],
        )
