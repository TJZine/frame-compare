"""Pure offset-stability classification and bounded evidence tests."""

from fractions import Fraction

from frame_compare.services.alignment_stability import classify_alignment_stability
from frame_compare.services.types import AlignmentWindowEvidence


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
