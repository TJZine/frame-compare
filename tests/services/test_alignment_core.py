"""Core audio alignment math and type tests."""

# pyright: reportPrivateUsage=false

from dataclasses import FrozenInstanceError
from fractions import Fraction

import numpy as np
import pytest

from frame_compare.services.alignment_correlation import (
    _candidate_offsets,
    correlate_audio,
    estimate_alignment_offset,
)
from frame_compare.services.alignment_math import (
    calculate_alignment_trims,
)
from frame_compare.services.alignment_math import (
    samples_to_frames as _samples_to_frames,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentRefinementMode,
    AlignmentResult,
)


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
    assert cfg.use_vsview is False
    assert cfg.force_interactive is False
    assert cfg.cache_results is True
    assert cfg.correlation_mode == "raw_fft"
    assert cfg.preprocessing_mode == "none"
    assert cfg.channel_strategy == "mono_downmix"
    assert cfg.confidence_threshold == 0.0
    assert cfg.ambiguity_peak_ratio == 1.0
    assert cfg.window_length_seconds == 0.0
    assert cfg.window_stride_seconds == 0.0
    assert cfg.minimum_valid_windows == 1
    assert cfg.consensus_minimum_ratio == 1.0
    assert cfg.refinement_mode == "disabled"
    assert cfg.refinement_sample_rate is None
    assert cfg.reference_stream is None
    assert cfg.comparison_streams == {}


def test_samples_to_frames_integer_fps():
    """Test sample to frame conversion with integer FPS."""
    assert _samples_to_frames(8000, 8000, Fraction(24, 1)) == 24


def test_samples_to_frames_fractional_fps():
    """Test sample to frame conversion with fractional FPS."""
    # 24000/1001 * (8008/8000) = 23.976... * 1.001 = 24.0
    assert _samples_to_frames(8008, 8000, Fraction(24000, 1001)) == 24


@pytest.mark.parametrize("refinement_mode", ["disabled", "local"])
def test_estimate_alignment_offset_uses_reference_minus_comparison_sign(
    refinement_mode: AlignmentRefinementMode,
) -> None:
    """The configured estimator converts correlation lag to the alignment contract."""
    reference = np.array([0, 0, 1, 2, 3, 0, 0], dtype=np.float32)
    comparison = np.array([0, 0, 0, 0, 1, 2, 3], dtype=np.float32)

    estimate = estimate_alignment_offset(
        reference,
        comparison,
        config=AlignmentConfig(
            sample_rate=8000,
            max_offset_seconds=1.0,
            correlation_mode="raw_fft",
            preprocessing_mode="none",
            refinement_mode=refinement_mode,
        ),
    )

    assert estimate.sample_offset == -2


def test_gcc_phat_standard_preprocessing_recovers_offset_with_dc_and_gain() -> None:
    """Standard preprocessing removes DC/gain differences before robust correlation."""
    reference = np.array([0, 0, 1, -2, 3, -1, 0, 0], dtype=np.float32)
    comparison = np.array([0, 0, 0, 0, 2, -4, 6, -2], dtype=np.float32) + 100.0

    estimate = correlate_audio(
        reference,
        comparison,
        max_offset_samples=4,
        correlation_mode="gcc_phat",
        preprocessing_mode="standard",
    )

    assert estimate.sample_offset == 2


def test_correlation_rejects_non_finite_samples() -> None:
    reference = np.array([0, 1, np.nan], dtype=np.float32)
    comparison = np.array([0, 1, 0], dtype=np.float32)

    with pytest.raises(AudioAlignmentError, match="non-finite"):
        correlate_audio(reference, comparison, correlation_mode="gcc_phat")


def test_local_refinement_candidates_stay_inside_local_and_global_bounds() -> None:
    candidates = _candidate_offsets(
        coarse_offset=9,
        sample_rate=8000,
        refinement_sample_rate=48000,
        max_offset_samples=100,
    )

    assert candidates
    assert all(-100 <= candidate <= 100 for candidate in candidates)
    assert all(abs(candidate - 9) <= 40 for candidate in candidates)


def test_calculate_alignment_trims_rejects_mismatched_lengths_when_offsets_are_unknown() -> None:
    """Default trim path must preserve the same length invariant as aligned offsets."""
    with pytest.raises(ValueError, match=r"comp_offsets and comp_num_frames.*1 != 2"):
        calculate_alignment_trims(
            ref_num_frames=100,
            comp_offsets=[None],
            comp_num_frames=[100, 100],
        )
