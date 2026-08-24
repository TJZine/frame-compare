"""Pure offset-stability classification and bounded evidence tests."""

from fractions import Fraction
from unittest.mock import patch

import numpy as np

from frame_compare.services.alignment_consensus import estimate_consensus_offset
from frame_compare.services.alignment_correlation import CorrelationEstimate
from frame_compare.services.alignment_stability import classify_alignment_stability
from frame_compare.services.types import AlignmentConfig, AlignmentWindowEvidence


def _evidence(*offsets: int) -> tuple[AlignmentWindowEvidence, ...]:
    return tuple(
        AlignmentWindowEvidence(index * 100, (index + 1) * 100, offset, 0.9, 2.0)
        for index, offset in enumerate(offsets)
    )


def _classify(*offsets: int):
    return classify_alignment_stability(
        _evidence(*offsets),
        sample_rate=24,
        fps=Fraction(24, 1),
    )


def test_constant_offset_is_stable() -> None:
    assert _classify(4, 4, 4).classification == "stable"


def test_gradual_monotonic_change_is_possible_drift() -> None:
    assert _classify(0, 1, 2, 3).classification == "possible_drift"


def test_one_dominant_jump_is_possible_discontinuity() -> None:
    summary = _classify(0, 0, 4, 4)

    assert summary.classification == "possible_discontinuity"
    assert summary.change_position_seconds == 200 / 24


def test_scattered_material_variation_is_variable() -> None:
    assert _classify(0, 1, 0, 1, 2, 1).classification == "variable"


def test_fewer_than_three_windows_is_insufficient() -> None:
    assert _classify(0, 3).classification == "insufficient_evidence"


def test_one_frame_noise_is_stable() -> None:
    assert _classify(5, 6, 5, 6).classification == "stable"


@patch("frame_compare.services.alignment_consensus.estimate_alignment_offset")
def test_supplemental_evidence_is_bounded_and_does_not_change_selected_estimate(
    mock_estimate,
) -> None:
    mock_estimate.side_effect = [
        CorrelationEstimate(7, 0.9, 2.0),
        CorrelationEstimate(7, 0.9, 2.0),
        CorrelationEstimate(7, 0.9, 2.0),
    ]
    signal = np.ones(200, dtype=np.float64)

    result = estimate_consensus_offset(
        signal,
        signal,
        config=AlignmentConfig(
            sample_rate=1,
            max_offset_seconds=1,
            confidence_threshold=0.5,
            ambiguity_peak_ratio=1.5,
        ),
        fps=Fraction(1, 1),
    )

    assert mock_estimate.call_count == 3
    assert all(call.args[0].size <= 90 for call in mock_estimate.call_args_list[1:])
    assert result.sample_offset == 7
    assert result.applied is True
    assert [item.sample_offset for item in result.window_evidence] == [7, 7, 7]
    assert result.stability is not None
    assert result.stability.classification == "stable"


@patch("frame_compare.services.alignment_consensus.estimate_alignment_offset")
def test_low_confidence_and_ambiguous_windows_do_not_create_false_variation(
    mock_estimate,
) -> None:
    mock_estimate.side_effect = [
        CorrelationEstimate(7, 0.9, 2.0),
        CorrelationEstimate(-20, 0.1, 2.0),
        CorrelationEstimate(30, 0.9, 1.0),
        CorrelationEstimate(-20, 0.1, 2.0),
        CorrelationEstimate(30, 0.9, 1.0),
        CorrelationEstimate(-20, 0.1, 2.0),
    ]
    signal = np.ones(200, dtype=np.float64)

    result = estimate_consensus_offset(
        signal,
        signal,
        config=AlignmentConfig(
            sample_rate=1,
            max_offset_seconds=1,
            confidence_threshold=0.5,
            ambiguity_peak_ratio=1.5,
        ),
        fps=Fraction(1, 1),
    )

    assert result.stability is not None
    assert result.stability.classification == "insufficient_evidence"
    assert result.stability.valid_windows == 1
    assert mock_estimate.call_count == 6
