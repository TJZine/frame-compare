"""Bounded, timeline-distributed audio alignment regressions."""

from __future__ import annotations

import weakref
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from frame_compare.services import alignment_audio, alignment_consensus
from frame_compare.services.alignment_audio import (
    AudioAnalysisBudgetExceeded,
    AudioAnalysisPlan,
    AudioStreamInfo,
    AudioStreamTimeline,
    AudioWindow,
    AudioWindowSpec,
)
from frame_compare.services.alignment_correlation import (
    CorrelationEstimate,
    correlate_audio,
    estimate_alignment_offset,
    refine_aligned_score,
)
from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.ffmpeg_errors import FFmpegError


@pytest.fixture(autouse=True)
def automatic_authority_is_disabled_for_policy_mechanics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep legacy consensus mechanics tests independent from the shipped latch."""
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)


def _stream(duration: int, *, start: int = 0) -> AudioStreamInfo:
    return AudioStreamInfo(
        audio_stream_index=0,
        absolute_stream_index=1,
        codec_name="aac",
        channels=2,
        channel_layout="stereo",
        sample_rate=48000,
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        timeline=AudioStreamTimeline(
            start_time=Fraction(start),
            duration=Fraction(duration),
            time_base=Fraction(1, 48000),
            duration_basis="duration_ts",
        ),
    )


def _plan(*, rate: int, count: int) -> AudioAnalysisPlan:
    specs = tuple(AudioWindowSpec(index * 100, 200, index * 100, 400) for index in range(count))
    return AudioAnalysisPlan(rate, rate, specs, 1024, count * 1024)


def _estimate_windows(
    windows: list[AudioWindow],
    *,
    config: AlignmentConfig,
) -> alignment_consensus.AlignmentConsensus:
    return alignment_consensus.estimate_staged_consensus_offset(
        plan=_plan(rate=config.sample_rate, count=len(windows)),
        config=config,
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(tuple(windows), ()),
        verification_phase_loader=lambda _specs: (_ for _ in ()).throw(
            AssertionError("requested-rate scoring is not expected")
        ),
        verification_spec_builder=lambda _offsets: (),
    )


def _estimate_candidates(
    monkeypatch: pytest.MonkeyPatch,
    estimates: list[CorrelationEstimate],
    *,
    config: AlignmentConfig,
    fps: Fraction = Fraction(24),
) -> alignment_consensus.AlignmentConsensus:
    remaining = iter(estimates)
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: next(remaining),
    )
    windows = [
        AudioWindow(np.ones(20), np.ones(20), index * 100, index * 100)
        for index in range(len(estimates))
    ]
    plan = _plan(rate=config.sample_rate, count=len(windows))
    return alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=config,
        fps=fps,
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(tuple(windows), ()),
        verification_phase_loader=lambda _specs: (_ for _ in ()).throw(
            AssertionError("requested-rate scoring is not expected")
        ),
        verification_spec_builder=lambda _offsets: (),
    )


@pytest.mark.parametrize(
    ("reference_size", "comparison_size", "reference_index", "comparison_index"),
    [(30, 50, 7, 19), (50, 30, 19, 7)],
)
def test_unequal_length_correlation_uses_the_comparison_zero_lag_axis(
    reference_size: int,
    comparison_size: int,
    reference_index: int,
    comparison_index: int,
) -> None:
    pattern = np.array([1, -2, 4, -3, 2], dtype=np.float32)
    reference = np.zeros(reference_size, dtype=np.float32)
    comparison = np.zeros(comparison_size, dtype=np.float32)
    reference[reference_index : reference_index + pattern.size] = pattern
    comparison[comparison_index : comparison_index + pattern.size] = pattern

    estimate = estimate_alignment_offset(
        reference,
        comparison,
        config=AlignmentConfig(sample_rate=100, max_offset_seconds=1),
    )

    assert estimate.sample_offset == reference_index - comparison_index
    assert estimate.score == pytest.approx(1.0)


def test_confidence_is_normalized_over_the_actual_aligned_overlap() -> None:
    rng = np.random.default_rng(7)
    reference = rng.standard_normal(200).astype(np.float32)
    comparison = np.zeros(400, dtype=np.float32)
    comparison[73:273] = reference

    estimate = correlate_audio(reference, comparison, max_offset_samples=100)

    assert estimate.sample_offset == 73
    assert estimate.score == pytest.approx(1.0)


def test_two_sample_boundary_match_is_not_meaningful_overlap() -> None:
    reference = np.zeros(100, dtype=np.float32)
    comparison = np.zeros(100, dtype=np.float32)
    reference[:2] = [1, -1]
    comparison[-2:] = [1, -1]

    with pytest.raises(AudioAlignmentError, match="insufficient aligned overlap"):
        correlate_audio(reference, comparison, max_offset_samples=100)


def test_requested_rate_score_accepts_full_30_second_overlap() -> None:
    rng = np.random.default_rng(41)
    signal = rng.standard_normal(30 * 48000).astype(np.float32)

    correction, score = refine_aligned_score(
        signal,
        signal,
        preprocessing_mode="none",
        correction_bounds_samples=(0, 0),
    )

    assert correction == 0
    assert score == pytest.approx(1.0)


def test_overlap_confidence_threshold_rejects_without_exposing_an_offset() -> None:
    reference = np.array([0, 1, -2, 3, -1, 0], dtype=np.float32)
    comparison = np.concatenate((np.zeros(2, dtype=np.float32), reference))
    result = _estimate_windows(
        [AudioWindow(reference, comparison, 0, 0)],
        config=AlignmentConfig(
            sample_rate=100,
            max_offset_seconds=1,
            confidence_threshold=1.1,
        ),
    )

    assert not result.applied
    assert result.sample_offset is None
    assert result.diagnostic == "low_confidence"


def test_planned_consensus_uses_majority_before_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    estimates = iter(
        [
            CorrelationEstimate(4, 0.51, 2.0),
            CorrelationEstimate(4, 0.52, 2.0),
            CorrelationEstimate(4, 0.53, 2.0),
            CorrelationEstimate(9, 0.99, 2.0),
            CorrelationEstimate(9, 0.98, 2.0),
        ]
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: next(estimates),
    )
    windows = [
        AudioWindow(np.ones(20), np.ones(20), index * 100, index * 100) for index in range(5)
    ]

    result = _estimate_windows(
        windows,
        config=AlignmentConfig(
            sample_rate=100,
            max_offset_seconds=1,
            consensus_minimum_ratio=0.6,
        ),
    )

    assert result.applied
    assert result.sample_offset == 4
    assert result.consensus_windows == 3


@pytest.mark.parametrize(
    ("offsets", "sample_rate", "fps", "expected_sample", "expected_frame"),
    [
        ([1000, 1000, 1001, 1000, 1000], 8000, Fraction(24), 1000, 3),
        ([1000, 1004, 1002, 1003], 8000, Fraction(24), 1002, 3),
        ([-1000, -1004, -1002, -1003], 8000, Fraction(24), -1003, -3),
        ([-1, 0, 1], 8000, Fraction(24), 0, 0),
        ([-1, 1], 48, Fraction(24), -1, 0),
        ([1000, 1001, 1002], 8000, Fraction(24000, 1001), 1001, 3),
    ],
)
def test_frame_equivalent_candidates_reach_consensus_with_observed_representative(
    monkeypatch: pytest.MonkeyPatch,
    offsets: list[int],
    sample_rate: int,
    fps: Fraction,
    expected_sample: int,
    expected_frame: int,
) -> None:
    estimates = [CorrelationEstimate(offset, 0.9, 2.0) for offset in offsets]

    result = _estimate_candidates(
        monkeypatch,
        estimates,
        config=AlignmentConfig(sample_rate=sample_rate),
        fps=fps,
    )

    assert result.applied
    assert result.sample_offset == expected_sample
    assert result.sample_offset in offsets
    assert samples_to_frames(result.sample_offset, sample_rate, fps) == expected_frame
    assert result.consensus_windows == len(offsets)
    assert result.consensus_ratio == 1.0
    assert [item.sample_offset for item in result.window_evidence] == offsets
    assert result.decision is not None
    assert result.decision.candidate is not None
    assert result.decision.candidate.sample_offset == expected_sample


@pytest.mark.parametrize(
    "offsets",
    [
        [1166, 1167],
        [-1166, -1167],
        [1000, 2000],
    ],
)
def test_different_frame_corrections_do_not_reach_default_consensus(
    monkeypatch: pytest.MonkeyPatch,
    offsets: list[int],
) -> None:
    result = _estimate_candidates(
        monkeypatch,
        [CorrelationEstimate(offset, 0.9, 2.0) for offset in offsets],
        config=AlignmentConfig(sample_rate=8000),
    )

    assert not result.applied
    assert result.sample_offset is None
    assert result.diagnostic == "insufficient_consensus"
    assert result.consensus_windows == 1
    assert result.consensus_ratio == 0.5
    assert result.decision is not None
    assert result.decision.state == "unavailable"
    assert result.decision.primary_reason == "no_unique_candidate"


def test_equal_frame_group_sizes_use_score_then_first_encountered_tie_break(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scored = _estimate_candidates(
        monkeypatch,
        [
            CorrelationEstimate(1000, 0.8, 2.0),
            CorrelationEstimate(1167, 0.9, 2.0),
            CorrelationEstimate(1001, 0.7, 2.0),
            CorrelationEstimate(1168, 0.6, 2.0),
        ],
        config=AlignmentConfig(sample_rate=8000, consensus_minimum_ratio=0.5),
    )
    assert scored.sample_offset == 1167

    first = _estimate_candidates(
        monkeypatch,
        [
            CorrelationEstimate(1167, 0.9, 2.0),
            CorrelationEstimate(1000, 0.9, 2.0),
            CorrelationEstimate(1168, 0.6, 2.0),
            CorrelationEstimate(1001, 0.6, 2.0),
        ],
        config=AlignmentConfig(sample_rate=8000, consensus_minimum_ratio=0.5),
    )
    assert first.sample_offset == 1167


def test_frame_consensus_preserves_minimum_window_and_ratio_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    insufficient_windows = _estimate_candidates(
        monkeypatch,
        [CorrelationEstimate(1000, 0.9, 2.0), CorrelationEstimate(1001, 0.9, 2.0)],
        config=AlignmentConfig(sample_rate=8000, minimum_valid_windows=3),
    )
    assert insufficient_windows.diagnostic == "insufficient_valid_windows"

    insufficient_ratio = _estimate_candidates(
        monkeypatch,
        [
            CorrelationEstimate(1000, 0.9, 2.0),
            CorrelationEstimate(1001, 0.9, 2.0),
            CorrelationEstimate(1002, 0.9, 2.0),
            CorrelationEstimate(1167, 0.9, 2.0),
            CorrelationEstimate(1168, 0.9, 2.0),
        ],
        config=AlignmentConfig(sample_rate=8000, consensus_minimum_ratio=0.61),
    )
    assert insufficient_ratio.diagnostic == "insufficient_consensus"
    assert insufficient_ratio.consensus_ratio == 0.6


def test_legacy_rejection_retains_strong_zero_as_unapplied_provisional_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _estimate_candidates(
        monkeypatch,
        [
            CorrelationEstimate(0, 0.99, 2.0),
            CorrelationEstimate(1, 0.98, 2.1),
            CorrelationEstimate(-1, 0.97, 2.2),
            CorrelationEstimate(0, 0.96, 2.3),
            CorrelationEstimate(400, 0.40, 1.1),
        ],
        config=AlignmentConfig(sample_rate=8000),
    )

    assert not result.applied
    assert result.sample_offset is None
    assert result.diagnostic == "insufficient_consensus"
    assert result.score == pytest.approx(0.975)
    assert result.valid_windows == 5
    assert result.consensus_windows == 4
    assert result.consensus_ratio == pytest.approx(0.8)
    assert result.ambiguity_ratio == pytest.approx(2.0)
    assert result.decision is not None
    assert result.decision.state == "provisional"
    assert result.decision.candidate is not None
    assert result.decision.candidate.frame_offset == 0
    assert result.decision.candidate.sample_offset == 0
    assert len(result.decision.candidate.supporting_window_ids) == 4
    assert result.decision.raw_correlated_windows == 5
    assert result.decision.consensus_windows == 4
    assert result.decision.consensus_ratio == pytest.approx(0.8)
    assert result.decision.aggregate_score == pytest.approx(0.975)
    assert result.decision.minimum_peak_ratio == pytest.approx(2.0)
    assert len(result.window_records) == 5
    assert all(record.vote_disposition == "voted" for record in result.window_records)


def test_one_success_and_four_recoverable_failures_preserve_legacy_acceptance_and_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes: Any = iter(
        [
            CorrelationEstimate(0, 0.99, 2.0),
            *[
                AudioAlignmentError(
                    "no useful signal",
                    category="insufficient_signal",
                    stage="correlation",
                )
                for _ in range(4)
            ],
        ]
    )

    def estimate(*_args: object, **_kwargs: object) -> CorrelationEstimate:
        outcome = next(outcomes)
        if isinstance(outcome, AudioAlignmentError):
            raise outcome
        return outcome

    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        estimate,
    )
    result = _estimate_windows(
        [AudioWindow(np.ones(20), np.ones(20), index * 100, index * 100) for index in range(5)],
        config=AlignmentConfig(sample_rate=8000),
    )

    assert result.applied
    assert result.sample_offset == 0
    assert result.score == pytest.approx(0.99)
    assert result.diagnostic == "accepted"
    assert result.valid_windows == 1
    assert result.consensus_windows == 1
    assert result.consensus_ratio == pytest.approx(1.0)
    assert result.ambiguity_ratio == pytest.approx(2.0)
    assert result.decision is not None
    assert result.decision.state == "trusted_automatic"
    assert len(result.window_records) == 5
    assert [record.terminal_category for record in result.window_records] == [
        "correlated",
        "insufficient_signal",
        "insufficient_signal",
        "insufficient_signal",
        "insufficient_signal",
    ]


def test_all_recoverable_failures_are_unavailable_without_inventing_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> CorrelationEstimate:
        raise AudioAlignmentError(
            "no useful signal",
            category="insufficient_signal",
            stage="correlation",
        )

    monkeypatch.setattr(alignment_consensus, "estimate_alignment_offset", fail)
    result = _estimate_windows(
        [AudioWindow(np.ones(20), np.ones(20), index * 100, index * 100) for index in range(5)],
        config=AlignmentConfig(sample_rate=8000),
    )

    assert not result.applied
    assert result.sample_offset is None
    assert result.decision is not None
    assert result.decision.state == "unavailable"
    assert result.decision.candidate is None
    assert len(result.window_records) == 5


def test_fatal_ffmpeg_failure_is_not_converted_to_recoverable_abstention() -> None:
    with pytest.raises(FFmpegError):
        alignment_consensus.estimate_staged_consensus_offset(
            plan=_plan(rate=8000, count=1),
            config=AlignmentConfig(sample_rate=8000),
            fps=Fraction(24),
            discovery_phase_loader=lambda: (_ for _ in ()).throw(FFmpegError("fatal decode", 1)),
            verification_phase_loader=lambda _specs: (_ for _ in ()).throw(AssertionError()),
            verification_spec_builder=lambda _offsets: (),
        )


def test_winning_group_uses_representative_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    estimates = iter(
        [
            CorrelationEstimate(1000, 0.95, 2.0),
            CorrelationEstimate(1001, 0.10, 2.0),
            CorrelationEstimate(1002, 0.10, 2.0),
        ]
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: next(estimates),
    )
    windows = [AudioWindow(np.ones(20), np.ones(20), 0, 0) for _ in range(3)]

    result = _estimate_windows(
        windows,
        config=AlignmentConfig(
            sample_rate=8000,
            confidence_threshold=0.9,
        ),
    )

    assert not result.applied
    assert result.diagnostic == "low_confidence"
    assert result.score == pytest.approx(0.1)


def test_winning_frame_group_uses_minimum_ambiguity_ratio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _estimate_candidates(
        monkeypatch,
        [
            CorrelationEstimate(1000, 0.9, 2.0),
            CorrelationEstimate(1001, 0.9, 1.2),
            CorrelationEstimate(1002, 0.9, 1.8),
        ],
        config=AlignmentConfig(sample_rate=8000, ambiguity_peak_ratio=1.5),
    )

    assert not result.applied
    assert result.diagnostic == "ambiguous_correlation_peak"
    assert result.ambiguity_ratio == 1.2


def test_requested_rate_fallback_votes_in_requested_frame_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    offsets = [6000, 6004, 6002, 6001, 6003]
    plan = AudioAnalysisPlan(
        8000,
        48000,
        tuple(AudioWindowSpec(index * 100, 100, index * 100, 100) for index in range(5)),
        256,
        1280,
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(0, 0.9, 2.0),
    )
    monkeypatch.setattr(
        alignment_consensus,
        "refine_aligned_score",
        lambda *_args, **_kwargs: (0, 0.9),
    )

    specs = tuple(
        alignment_audio.AudioVerificationSpec(index, offset, 100, 0, 100, offset, offset)
        for index, offset in enumerate(offsets)
    )
    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000),
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(
            tuple(AudioWindow(np.ones(100), np.ones(100), 0, 0) for _ in offsets), ()
        ),
        verification_phase_loader=lambda _specs: alignment_audio.CollectedAudioPhase(
            tuple(AudioWindow(np.ones(100), np.ones(100), offset, 0) for offset in offsets), ()
        ),
        verification_spec_builder=lambda _offsets: specs,
    )

    assert result.applied
    assert result.sample_offset == 6002
    assert samples_to_frames(result.sample_offset, 48000, Fraction(24)) == 3
    assert result.consensus_windows == 5


def test_coarse_lag_is_scored_at_requested_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = AudioAnalysisPlan(
        sample_rate=8000,
        requested_sample_rate=48000,
        windows=(AudioWindowSpec(0, 100, 0, 100),),
        peak_fft_points=256,
        total_fft_points=256,
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(0, 0.99, 2.0),
    )
    signal = np.linspace(-1, 1, 600, dtype=np.float32)

    verification_spec = alignment_audio.AudioVerificationSpec(0, 0, 600, 0, 600, -6, 6)
    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(
            sample_rate=48000,
            max_offset_seconds=1,
            confidence_threshold=0.9,
        ),
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(
            (AudioWindow(np.ones(100), np.ones(100), 0, 0),), ()
        ),
        verification_phase_loader=lambda _specs: alignment_audio.CollectedAudioPhase(
            (AudioWindow(signal, -signal, 0, 0),), ()
        ),
        verification_spec_builder=lambda _offsets: (verification_spec,),
    )

    assert not result.applied
    assert result.diagnostic == "low_confidence"
    assert result.score == pytest.approx(-1.0)


def test_discovery_pcm_is_released_before_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    references: list[weakref.ReferenceType[np.ndarray[Any, Any]]] = []
    discovery_windows = tuple(
        AudioWindow(np.ones(20), np.ones(20), index * 100, index * 100) for index in range(2)
    )
    for window in discovery_windows:
        references.extend((weakref.ref(window.reference), weakref.ref(window.comparison)))
    del window
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(0, 1.0, 2.0),
    )
    monkeypatch.setattr(alignment_consensus, "refine_aligned_score", lambda *_a, **_k: (0, 1.0))
    plan = _plan(rate=100, count=2)
    specs = tuple(
        alignment_audio.AudioVerificationSpec(index, index * 200, 20, index * 200, 20, 0, 0)
        for index in range(2)
    )

    def load_discovery() -> alignment_audio.CollectedAudioPhase:
        nonlocal discovery_windows
        phase = alignment_audio.CollectedAudioPhase(discovery_windows, ())
        discovery_windows = ()
        return phase

    def load_verification(
        _specs: tuple[alignment_audio.AudioVerificationSpec, ...],
    ) -> alignment_audio.CollectedAudioPhase:
        assert all(reference() is None for reference in references)
        return alignment_audio.CollectedAudioPhase(
            tuple(
                AudioWindow(np.ones(20), np.ones(20), index * 200, index * 200)
                for index in range(2)
            ),
            (),
        )

    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=replace(plan, requested_sample_rate=200),
        config=AlignmentConfig(sample_rate=200, max_offset_seconds=1),
        fps=Fraction(24),
        discovery_phase_loader=load_discovery,
        verification_phase_loader=load_verification,
        verification_spec_builder=lambda _offsets: specs,
    )

    assert result.valid_windows == 2


@pytest.mark.parametrize("sign", [-1, 1])
def test_requested_rate_correction_cannot_escape_max_offset(
    monkeypatch: pytest.MonkeyPatch,
    sign: int,
) -> None:
    plan = AudioAnalysisPlan(8000, 48000, (AudioWindowSpec(0, 100, 0, 100),), 256, 256)
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(sign * 8000, 1.0, 2.0),
    )
    seen_bounds: list[tuple[int, int]] = []

    def outward_refinement(*_args: object, **kwargs: Any) -> tuple[int, float]:
        seen_bounds.append(kwargs["correction_bounds_samples"])
        return sign * 6, 1.0

    monkeypatch.setattr(alignment_consensus, "refine_aligned_score", outward_refinement)

    requested_center = sign * 48000
    verification_spec = alignment_audio.AudioVerificationSpec(
        0,
        max(0, requested_center),
        600,
        max(0, -requested_center),
        600,
        max(-48000, requested_center - 6),
        min(48000, requested_center + 6),
    )
    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000, max_offset_seconds=1),
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(
            (AudioWindow(np.ones(100), np.ones(100), 0, 0),), ()
        ),
        verification_phase_loader=lambda _specs: alignment_audio.CollectedAudioPhase(
            (
                AudioWindow(
                    np.ones(600),
                    np.ones(600),
                    max(0, requested_center),
                    max(0, -requested_center),
                ),
            ),
            (),
        ),
        verification_spec_builder=lambda _offsets: (verification_spec,),
    )

    assert not result.applied
    assert result.sample_offset is None
    assert seen_bounds == [(-6, 0) if sign > 0 else (0, 6)]


@pytest.mark.parametrize("expected", [-23, 23])
def test_requested_rate_interior_correction_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    expected: int,
) -> None:
    plan = AudioAnalysisPlan(8000, 48000, (AudioWindowSpec(0, 100, 0, 100),), 256, 256)
    coarse = 24 if expected > 0 else -24
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(coarse // 6, 1.0, 2.0),
    )
    monkeypatch.setattr(
        alignment_consensus,
        "refine_aligned_score",
        lambda *_args, **_kwargs: (expected - coarse, 1.0),
    )

    verification_spec = alignment_audio.AudioVerificationSpec(
        0,
        max(0, coarse),
        600,
        max(0, -coarse),
        600,
        coarse - 6,
        coarse + 6,
    )
    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000, max_offset_seconds=1),
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(
            (AudioWindow(np.ones(100), np.ones(100), 0, 0),), ()
        ),
        verification_phase_loader=lambda _specs: alignment_audio.CollectedAudioPhase(
            (
                AudioWindow(
                    np.ones(600),
                    np.ones(600),
                    max(0, coarse),
                    max(0, -coarse),
                ),
            ),
            (),
        ),
        verification_spec_builder=lambda _offsets: (verification_spec,),
    )

    assert result.applied
    assert result.sample_offset == expected


@pytest.mark.parametrize("expected_offset", [-99, 99])
def test_planned_windows_recover_offsets_near_both_search_bounds(
    expected_offset: int,
) -> None:
    rng = np.random.default_rng(19)
    source = rng.standard_normal(1200).astype(np.float32)
    reference_start = 400
    comparison_start = 300
    reference = source[reference_start : reference_start + 200]
    comparison = source[
        comparison_start + expected_offset : comparison_start + expected_offset + 400
    ]
    window = AudioWindow(reference, comparison, reference_start, comparison_start)

    result = _estimate_windows(
        [window],
        config=AlignmentConfig(sample_rate=100, max_offset_seconds=1),
    )

    assert result.applied
    assert result.sample_offset == expected_offset


def test_weak_intro_does_not_hide_strong_late_content() -> None:
    rng = np.random.default_rng(23)
    strong = rng.standard_normal(200).astype(np.float32)
    windows = [AudioWindow(np.zeros(200), np.zeros(300), 0, 0)]
    windows.extend(
        AudioWindow(strong, np.concatenate((np.zeros(20), strong)), index * 1000, index * 1000)
        for index in range(1, 5)
    )

    result = _estimate_windows(
        windows,
        config=AlignmentConfig(
            sample_rate=100,
            max_offset_seconds=1,
            minimum_valid_windows=3,
        ),
    )

    assert result.applied
    assert result.sample_offset == -20
    assert result.valid_windows == 4


@pytest.mark.parametrize("stride_seconds", [0, 60])
def test_plan_uses_selected_stream_duration_and_configured_window_grid(
    stride_seconds: int,
) -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(7200),
        _stream(300),
        config=AlignmentConfig(
            window_length_seconds=60,
            window_stride_seconds=stride_seconds,
        ),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert all(spec.reference_sample_count == 60 * plan.sample_rate for spec in plan.windows)
    assert [spec.reference_start_sample // plan.sample_rate for spec in plan.windows] == [
        0,
        60,
        120,
        180,
        240,
    ]


@pytest.mark.parametrize("requested_rate", [8000, 48000])
def test_long_request_uses_bounded_distributed_coarse_work(requested_rate: int) -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(7200),
        _stream(7200),
        config=AlignmentConfig(sample_rate=requested_rate),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert plan.sample_rate == 8000
    assert plan.requested_sample_rate == requested_rate
    assert len(plan.windows) == 5
    assert plan.peak_fft_points <= 1 << 21
    assert plan.total_fft_points <= 1 << 24


def test_long_48k_fallback_produces_requested_rate_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(65),
        _stream(65),
        config=AlignmentConfig(sample_rate=48000),
    )
    assert isinstance(plan, AudioAnalysisPlan)
    assert plan.sample_rate == 8000
    origin_deltas = iter(
        spec.reference_start_sample - spec.comparison_start_sample for spec in plan.windows
    )
    discovery_windows = tuple(
        AudioWindow(
            np.ones(spec.reference_sample_count),
            np.ones(spec.comparison_sample_count),
            spec.reference_start_sample,
            spec.comparison_start_sample,
        )
        for spec in plan.windows
    )

    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(-next(origin_deltas), 0.99, 2.0),
    )
    monkeypatch.setattr(
        alignment_consensus,
        "refine_aligned_score",
        lambda *_args, **_kwargs: (0, 1.0),
    )
    verification_specs = tuple(
        alignment_audio.AudioVerificationSpec(index, 0, 100, 0, 100, -6, 6)
        for index in range(len(plan.windows))
    )

    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000),
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(discovery_windows, ()),
        verification_phase_loader=lambda _specs: alignment_audio.CollectedAudioPhase(
            tuple(AudioWindow(np.ones(100), np.ones(100), 0, 0) for _ in plan.windows), ()
        ),
        verification_spec_builder=lambda _offsets: verification_specs,
    )

    assert result.applied
    assert result.valid_windows == len(plan.windows)
    assert result.score == pytest.approx(1.0)


def test_tiny_stride_on_huge_timeline_plans_without_materializing_the_grid() -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(1_000_000_000),
        _stream(1_000_000_000),
        config=AlignmentConfig(
            window_length_seconds=1,
            window_stride_seconds=1e-12,
        ),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert 1 < len(plan.windows) <= 16
    assert plan.windows[0].reference_start_sample == 0
    assert plan.windows[-1].reference_start_sample > 1_000_000 * plan.sample_rate


@pytest.mark.parametrize(
    "config",
    [
        AlignmentConfig(max_offset_seconds=600),
        AlignmentConfig(max_offset_seconds=3600),
        AlignmentConfig(minimum_valid_windows=10000),
    ],
)
def test_pathological_valid_config_returns_budget_outcome(config: AlignmentConfig) -> None:
    plan = alignment_audio.plan_audio_analysis(_stream(7200), _stream(7200), config=config)

    assert isinstance(plan, AudioAnalysisBudgetExceeded)
    result = alignment_consensus.analysis_budget_exceeded(config=config, fps=Fraction(24))
    assert not result.applied
    assert result.sample_offset is None
    assert result.diagnostic == "analysis_budget_exceeded"


@pytest.mark.parametrize(
    "config",
    [
        AlignmentConfig(max_offset_seconds=float("inf")),
        AlignmentConfig(window_length_seconds=float("inf")),
        AlignmentConfig(window_stride_seconds=float("inf")),
    ],
)
def test_non_finite_internal_config_returns_budget_outcome(config: AlignmentConfig) -> None:
    result = alignment_audio.plan_audio_analysis(_stream(60), _stream(60), config=config)

    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == "non_finite_analysis_config"


def test_window_count_budget_rejects_tiny_work_with_huge_minimum() -> None:
    result = alignment_audio.plan_audio_analysis(
        _stream(7200),
        _stream(7200),
        config=AlignmentConfig(
            max_offset_seconds=1,
            window_length_seconds=1e-6,
            window_stride_seconds=1e-6,
            minimum_valid_windows=10000,
        ),
    )

    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == "minimum_valid_windows_exceeds_work_budget"


def test_short_clip_remains_a_single_complete_window() -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(2),
        _stream(2),
        config=AlignmentConfig(),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert len(plan.windows) == 1
    assert plan.windows[0].reference_sample_count == 16000


def test_continuous_recipe_is_origin_based_and_endpoint_limited() -> None:
    argv = alignment_audio.continuous_collection_argv(
        Path("reference.mkv"),
        _stream(10),
        sample_rate=8000,
        end_sample=240000,
        channel_strategy="mono_downmix",
    )

    assert argv == [
        "ffmpeg",
        "-i",
        "reference.mkv",
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-af",
        "aresample=8000,atrim=end_sample=240000",
        "-f",
        "f32le",
        "-",
    ]
    assert not {"-ss", "-copyts", "-fs"} & set(argv)


def test_stream_probe_prefers_selected_stream_duration_over_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"time_base":"1/48000",'
        b'"duration_ts":1440000,"duration":"30.0"}],"format":{"duration":"600.0"}}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    selected = alignment_audio.select_reference_audio_stream(Path("short-audio.mkv"))

    assert selected.timeline.duration == 30
    assert selected.timeline.duration_basis == "duration_ts"


def test_stream_probe_does_not_substitute_long_container_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"time_base":"1/48000"}],"format":{"duration":"7200.0"}}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    selected = alignment_audio.select_reference_audio_stream(Path("unknown-audio.mkv"))
    result = alignment_audio.plan_audio_analysis(selected, _stream(7200), config=AlignmentConfig())

    assert selected.timeline.duration is None
    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == "selected_audio_timeline_unavailable"


def test_stream_probe_preserves_negative_selected_stream_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"start_time":"-1.25",'
        b'"time_base":"1/48000","duration_ts":192000}]}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    selected = alignment_audio.select_reference_audio_stream(Path("negative-start.mkv"))

    assert selected.timeline.start_time == Fraction(-5, 4)
    assert selected.timeline.duration == 4


def test_stream_probe_ignores_non_finite_timing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"start_time":"Infinity",'
        b'"duration":"Infinity","time_base":"1/48000"}]}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    selected = alignment_audio.select_reference_audio_stream(Path("invalid-time.mkv"))

    assert selected.timeline.start_time == 0
    assert selected.timeline.duration is None


def test_staged_eof_clamping_preserves_short_and_empty_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = AudioAnalysisPlan(
        sample_rate=8000,
        requested_sample_rate=8000,
        windows=(
            AudioWindowSpec(0, 100, 0, 100),
            AudioWindowSpec(100, 100, 100, 100),
            AudioWindowSpec(200, 100, 200, 100),
        ),
        peak_fft_points=256,
        total_fft_points=768,
    )
    signal = np.random.default_rng(44).standard_normal(100).astype(np.float32)
    phase = alignment_audio.CollectedAudioPhase(
        windows=(
            AudioWindow(signal, signal, 0, 0),
            AudioWindow(signal[:90], signal[:90], 100, 100),
            AudioWindow(signal[:0], signal[:0], 200, 200),
        ),
        summaries=(),
    )

    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=8000),
        fps=Fraction(24),
        discovery_phase_loader=lambda: phase,
        verification_phase_loader=lambda _specs: pytest.fail("unexpected verification"),
        verification_spec_builder=lambda _offsets: (),
    )

    assert len(result.window_records) == 3
    assert [record.coverage_state for record in result.window_records] == [
        "complete",
        "short",
        "not_observed",
    ]
    assert result.window_records[1].pre_eof_expected_overlap == 100
    assert result.window_records[1].actual_coverage == pytest.approx(0.9)
    assert result.window_records[2].actual_reference_count == 0
    assert result.window_records[2].actual_comparison_count == 0
    assert result.window_records[2].pre_eof_expected_overlap is None


def test_full_length_signal_failure_does_not_fabricate_coverage() -> None:
    plan = AudioAnalysisPlan(8000, 8000, (AudioWindowSpec(0, 100, 0, 100),), 256, 256)
    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=8000),
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(
            (AudioWindow(np.zeros(100), np.zeros(100), 0, 0),), ()
        ),
        verification_phase_loader=lambda _specs: pytest.fail("unexpected verification"),
        verification_spec_builder=lambda _offsets: (),
    )

    record = result.window_records[0]
    assert record.actual_reference_count == record.actual_comparison_count == 100
    assert record.terminal_category == "insufficient_signal"
    assert record.continuous_sample_count is None
    assert record.actual_useful_reference_start is None
    assert record.pre_eof_expected_overlap is None
    assert record.actual_coverage is None
    assert record.coverage_state == "not_observed"


def test_verification_failure_does_not_fabricate_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = AudioAnalysisPlan(8000, 48000, (AudioWindowSpec(0, 100, 0, 100),), 256, 256)
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(0, 0.99, 2.0),
    )
    spec = alignment_audio.AudioVerificationSpec(0, 0, 600, 0, 600, -6, 6)

    def fail_verification(
        _specs: tuple[alignment_audio.AudioVerificationSpec, ...],
    ) -> alignment_audio.CollectedAudioPhase:
        raise AudioAlignmentError(
            "verification decode failed",
            category="decode_failed",
            stage="verification",
            role="comparison",
        )

    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000),
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(
            (AudioWindow(np.ones(100), np.ones(100), 0, 0),), ()
        ),
        verification_phase_loader=fail_verification,
        verification_spec_builder=lambda _offsets: (spec,),
    )

    record = result.window_records[0]
    assert record.actual_reference_count == record.actual_comparison_count == 100
    assert record.terminal_stage == "verification"
    assert record.terminal_category == "decode_failed"
    assert record.failed_role == "comparison"
    assert record.continuous_sample_count is None
    assert record.actual_useful_reference_start is None
    assert record.pre_eof_expected_overlap is None
    assert record.actual_coverage is None
    assert record.coverage_state == "not_observed"


def test_verification_scores_original_global_hypotheses_after_halo_shift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = AudioAnalysisPlan(
        sample_rate=8000,
        requested_sample_rate=48000,
        windows=(AudioWindowSpec(100, 100, 50, 200),),
        peak_fft_points=512,
        total_fft_points=512,
        discovery_retained_samples=300,
        verification_reserved_samples=212,
    )
    signal = np.random.default_rng(45).standard_normal(100).astype(np.float32)
    discovery = alignment_audio.CollectedAudioPhase(
        windows=(AudioWindow(signal, np.pad(signal, (40, 60)), 100, 50),),
        summaries=(),
    )
    verification_spec = alignment_audio.AudioVerificationSpec(
        window_index=0,
        reference_start_sample=600,
        reference_sample_count=100,
        comparison_start_sample=530,
        comparison_sample_count=112,
        global_lower_offset=54,
        global_upper_offset=66,
    )
    verification = alignment_audio.CollectedAudioPhase(
        windows=(AudioWindow(signal, np.pad(signal, (10, 2)), 600, 530),),
        summaries=(),
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(-40, 0.99, 2.0),
    )

    def refine(*_args: object, **kwargs: Any) -> tuple[int, float]:
        assert kwargs["correction_bounds_samples"] == (-16, -4)
        return -10, 0.99

    monkeypatch.setattr(alignment_consensus, "refine_aligned_score", refine)

    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000),
        fps=Fraction(24),
        discovery_phase_loader=lambda: discovery,
        verification_phase_loader=lambda specs: (
            verification
            if specs == (verification_spec,)
            else pytest.fail("verification plan changed")
        ),
        verification_spec_builder=lambda offsets: (
            (verification_spec,)
            if offsets == ((0, 10),)
            else pytest.fail("coarse global offset changed")
        ),
    )

    assert result.window_records[0].requested_sample_lag == 60


@pytest.mark.parametrize("requested_rate", [44100, 48000])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("edge", ["lower", "upper"])
def test_fractional_discovery_candidate_preserves_exact_requested_halo_edges(
    monkeypatch: pytest.MonkeyPatch,
    requested_rate: int,
    sign: int,
    edge: str,
) -> None:
    plan = AudioAnalysisPlan(
        sample_rate=8000,
        requested_sample_rate=requested_rate,
        windows=(AudioWindowSpec(800, 100, 800, 100),),
        peak_fft_points=256,
        total_fft_points=256,
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(
            0,
            0.99,
            2.0,
            subsample_offset=sign * 0.5,
        ),
    )
    reference_stream = _stream(10)
    comparison_stream = _stream(10)
    captured_offsets: list[tuple[tuple[int, Fraction], ...]] = []

    def build_specs(
        offsets: tuple[tuple[int, Fraction], ...],
    ) -> tuple[alignment_audio.AudioVerificationSpec, ...]:
        captured_offsets.append(offsets)
        return alignment_audio.verification_specs(
            plan,
            offsets,
            reference_stream=reference_stream,
            comparison_stream=comparison_stream,
            max_offset_seconds=1,
        )

    seen_specs: list[alignment_audio.AudioVerificationSpec] = []

    def load_verification(
        specs: tuple[alignment_audio.AudioVerificationSpec, ...],
    ) -> alignment_audio.CollectedAudioPhase:
        spec = specs[0]
        seen_specs.append(spec)
        return alignment_audio.CollectedAudioPhase(
            (
                AudioWindow(
                    np.ones(spec.reference_sample_count),
                    np.ones(spec.comparison_sample_count),
                    spec.reference_start_sample,
                    spec.comparison_start_sample,
                ),
            ),
            (),
        )

    def choose_edge(*_args: object, **kwargs: Any) -> tuple[int, float]:
        lower, upper = kwargs["correction_bounds_samples"]
        return (lower if edge == "lower" else upper), 0.99

    monkeypatch.setattr(alignment_consensus, "refine_aligned_score", choose_edge)
    result = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=requested_rate, max_offset_seconds=1),
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(
            (AudioWindow(np.ones(100), np.ones(100), 800, 800),), ()
        ),
        verification_phase_loader=load_verification,
        verification_spec_builder=build_specs,
    )

    expected_center = round(Fraction(sign, 2) * requested_rate / 8000)
    halo = -(-requested_rate // 8000)
    spec = seen_specs[0]
    assert captured_offsets == [((0, Fraction(sign, 2)),)]
    assert (spec.global_lower_offset, spec.global_upper_offset) == (
        expected_center - halo,
        expected_center + halo,
    )
    expected = spec.global_lower_offset if edge == "lower" else spec.global_upper_offset
    assert result.window_records[0].requested_sample_lag == expected


def test_short_window_score_position_reservation_is_exact() -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(4),
        _stream(4),
        config=AlignmentConfig(
            sample_rate=48000,
            max_offset_seconds=1,
            window_length_seconds=1,
            window_stride_seconds=1,
        ),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert len(plan.windows) == 4
    assert plan.score_evaluations_per_window == 14
    assert plan.scored_positions == 2_528_000


def test_score_position_boundary_rejects_before_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_audio, "_MAX_SCORED_POSITIONS", 2_527_999)
    result = alignment_audio.plan_audio_analysis(
        _stream(4),
        _stream(4),
        config=AlignmentConfig(
            sample_rate=48000,
            max_offset_seconds=1,
            window_length_seconds=1,
            window_stride_seconds=1,
        ),
    )

    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == "scoring_positions_exceed_work_budget"


@pytest.mark.parametrize(
    ("config", "reason"),
    [
        (AlignmentConfig(max_offset_seconds=600), "window_or_offset_exceeds_peak_budget"),
        (
            AlignmentConfig(
                sample_rate=48000,
                window_length_seconds=32,
                window_stride_seconds=32,
            ),
            "requested_rate_scoring_exceeds_peak_budget",
        ),
        (
            AlignmentConfig(
                sample_rate=48000,
                window_length_seconds=30,
                window_stride_seconds=30,
                minimum_valid_windows=6,
            ),
            "requested_rate_scoring_exceeds_total_budget",
        ),
        (AlignmentConfig(sample_rate=2_048_000), "scoring_evaluations_exceed_window_budget"),
        (
            AlignmentConfig(
                max_offset_seconds=1,
                window_length_seconds=1,
                window_stride_seconds=1,
                minimum_valid_windows=17,
            ),
            "minimum_valid_windows_exceeds_work_budget",
        ),
        (
            AlignmentConfig(
                sample_rate=8000,
                max_offset_seconds=30,
                window_length_seconds=60,
                window_stride_seconds=60,
                minimum_valid_windows=9,
            ),
            "minimum_valid_windows_exceeds_work_budget",
        ),
    ],
)
def test_planner_rejects_resource_neighbors_before_collection(
    config: AlignmentConfig,
    reason: str,
) -> None:
    result = alignment_audio.plan_audio_analysis(_stream(180), _stream(180), config=config)

    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == reason


def test_planner_rejects_retained_pcm_neighbor_before_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_audio, "_MAX_DISCOVERY_RETAINED_SAMPLES", 1)
    result = alignment_audio.plan_audio_analysis(
        _stream(10),
        _stream(10),
        config=AlignmentConfig(max_offset_seconds=1),
    )

    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == "planned_windows_exceed_work_budget"


def test_planner_retries_4000_only_when_8000_cannot_fit_fft() -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(7200),
        _stream(7200),
        config=AlignmentConfig(sample_rate=48000, max_offset_seconds=102),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert plan.sample_rate == 4000
    assert plan.peak_fft_points <= 2_097_152
    assert plan.total_fft_points <= 16_777_216
    assert plan.verification_reserved_samples <= 15_000_000
    assert plan.score_evaluations_per_window <= 512
    assert plan.scored_positions <= 536_870_912
