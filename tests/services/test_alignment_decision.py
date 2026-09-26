"""Tests for the whole-track audio stage decision (A5/A6, U3 table, P2a)."""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkedCorrelation,
    ChunkObservation,
    ChunkRun,
    comparison_window,
    plan_audio_chunks,
)
from frame_compare.services.alignment_decision import (
    VIDEO_CHECK_PENDING_REASON,
    compensated_offset_seconds,
    correlation_score,
    decide_aborted_stage,
    decide_completed_stage,
    decide_rejected_stage,
    derive_stability,
    rounded_frame,
    subframe_estimate,
)
from frame_compare.utils.alignment_evidence import AUDIO_ANALYSIS_SAMPLE_RATE
from tests.services.alignment_synthetic_audio import (
    insert_program,
    make_program,
    quiet_program,
    shift_signal,
)

SEED = 11
FPS = Fraction(24000, 1001)


def run_estimate(reference, comparison, max_offset_seconds: float = 30.0) -> ChunkedAudioEstimate:
    plan = plan_audio_chunks(len(reference), len(comparison), max_offset_seconds)
    accumulator = ChunkedCorrelation(plan)
    for index, (start, count) in enumerate(plan.chunks):
        window = comparison_window(comparison, start, count, plan.lag_samples)
        accumulator.add(index, reference[start : start + count], window)
    return accumulator.finish()


def decide(
    reference,
    comparison,
    *,
    reference_audio_start: Fraction = Fraction(0),
    reference_video_start: Fraction = Fraction(0),
    comparison_audio_start: Fraction = Fraction(0),
    comparison_video_start: Fraction = Fraction(0),
    max_offset_seconds: float = 30.0,
):
    plan = plan_audio_chunks(len(reference), len(comparison), max_offset_seconds)
    accumulator = ChunkedCorrelation(plan)
    for index, (start, count) in enumerate(plan.chunks):
        window = comparison_window(comparison, start, count, plan.lag_samples)
        accumulator.add(index, reference[start : start + count], window)
    return decide_completed_stage(
        estimate=accumulator.finish(),
        plan=plan,
        max_offset_seconds=max_offset_seconds,
        reference_audio_start=reference_audio_start,
        reference_video_start=reference_video_start,
        comparison_audio_start=comparison_audio_start,
        comparison_video_start=comparison_video_start,
        fps_reference=FPS,
    )


def test_compensation_sign_matches_reference_minus_comparison() -> None:
    lag = 1600
    offset = compensated_offset_seconds(
        global_lag=lag,
        reference_audio_start=Fraction(0),
        reference_video_start=Fraction(0),
        comparison_audio_start=Fraction(1, 5),
        comparison_video_start=Fraction(0),
    )
    assert offset == pytest.approx(lag / AUDIO_ANALYSIS_SAMPLE_RATE - 0.2)


def test_compensation_adds_reference_delay() -> None:
    lag = 0
    offset = compensated_offset_seconds(
        global_lag=lag,
        reference_audio_start=Fraction(1, 5),
        reference_video_start=Fraction(0),
        comparison_audio_start=Fraction(0),
        comparison_video_start=Fraction(0),
    )
    assert offset == pytest.approx(0.2)


def test_subframe_estimate_and_rounding() -> None:
    assert subframe_estimate(offset_seconds=6.1, fps_reference=Fraction(24, 1)) == pytest.approx(
        146.4
    )
    assert rounded_frame(146.4) == 146
    assert rounded_frame(146.5) == 147
    assert rounded_frame(-2.0) == -2
    assert rounded_frame(-2.5) == -2
    assert rounded_frame(-2.51) == -3


def test_agreed_decision_is_provisional_pending_video_check() -> None:
    reference = make_program(SEED, 35.0)
    comparison = shift_signal(reference, 1668)
    decided = decide(reference, comparison)

    assert decided.attempt_status == "complete"
    assert decided.audio.status == "agreed"
    assert decided.audio.global_lag == -1668
    assert decided.decision.state == "provisional"
    assert decided.decision.primary_reason == VIDEO_CHECK_PENDING_REASON == "video_check_pending"
    assert decided.decision.failed_gates == ()
    candidate = decided.decision.candidate
    assert candidate is not None
    assert candidate.basis == "audio_only"
    expected_subframe = -1668 / AUDIO_ANALYSIS_SAMPLE_RATE * float(FPS)
    assert candidate.subframe_estimate == pytest.approx(expected_subframe)
    assert candidate.frame_offset == math.floor(expected_subframe + 0.5)
    assert candidate.time_offset_seconds == pytest.approx(-1668 / AUDIO_ANALYSIS_SAMPLE_RATE)
    assert decided.audio.rounded_frame == candidate.frame_offset
    assert decided.correlation_score == pytest.approx(1.0)
    assert decided.stability.classification == "stable"


def test_compensation_flows_into_candidate() -> None:
    reference = make_program(SEED, 35.0)
    comparison = shift_signal(reference, 0)
    decided = decide(reference, comparison, reference_audio_start=Fraction(1, 5))

    candidate = decided.decision.candidate
    assert candidate is not None
    assert candidate.time_offset_seconds == pytest.approx(0.2)
    expected_subframe = 0.2 * float(FPS)
    assert candidate.subframe_estimate == pytest.approx(expected_subframe)
    assert candidate.frame_offset == math.floor(expected_subframe + 0.5)
    assert decided.audio.compensation_seconds == pytest.approx(0.2)


def test_completed_stage_compensates_delayed_comparison() -> None:
    """A +0.5 s comparison audio start lands on a negative candidate frame."""
    reference = make_program(SEED, 35.0)
    comparison = shift_signal(reference, 0)
    decided = decide(reference, comparison, comparison_audio_start=Fraction(1, 2))

    assert decided.audio.global_lag == 0
    assert decided.audio.compensation_seconds == pytest.approx(-0.5)
    candidate = decided.decision.candidate
    assert candidate is not None
    assert candidate.time_offset_seconds == pytest.approx(-0.5)
    expected_subframe = -0.5 * float(FPS)
    assert candidate.subframe_estimate == pytest.approx(expected_subframe)
    assert candidate.frame_offset == math.floor(expected_subframe + 0.5) == -12


def test_completed_stage_compensates_delayed_reference() -> None:
    """A +0.5 s reference audio start lands on a positive candidate frame."""
    reference = make_program(SEED, 35.0)
    comparison = shift_signal(reference, 0)
    decided = decide(reference, comparison, reference_audio_start=Fraction(1, 2))

    assert decided.audio.global_lag == 0
    assert decided.audio.compensation_seconds == pytest.approx(0.5)
    candidate = decided.decision.candidate
    assert candidate is not None
    assert candidate.time_offset_seconds == pytest.approx(0.5)
    expected_subframe = 0.5 * float(FPS)
    assert candidate.subframe_estimate == pytest.approx(expected_subframe)
    assert candidate.frame_offset == math.floor(expected_subframe + 0.5) == 12


def test_half_second_in_sync_delay_stability_matches_zero_candidate() -> None:
    """Lag +0.5 s with compensation -0.5 s: stability frames equal candidate 0."""
    reference = make_program(SEED, 35.0)
    comparison = shift_signal(reference, -4000)
    decided = decide(reference, comparison, comparison_audio_start=Fraction(1, 2))

    assert decided.audio.global_lag == 4000
    assert decided.audio.compensation_seconds == pytest.approx(-0.5)
    candidate = decided.decision.candidate
    assert candidate is not None
    assert candidate.time_offset_seconds == pytest.approx(0.0)
    assert candidate.frame_offset == 0
    assert decided.audio.rounded_frame == 0
    stability = decided.stability
    assert stability.classification == "stable"
    assert stability.offset_min_frames == 0
    assert stability.offset_max_frames == 0
    assert stability.first_offset_frames == 0
    assert stability.last_offset_frames == 0


def test_run_spanning_a_quiet_chunk_is_valid_evidence() -> None:
    """Real films have quiet chunks between agreeing ones; runs skip them."""
    reference = make_program(SEED, 120.0)
    quiet = slice(30 * AUDIO_ANALYSIS_SAMPLE_RATE, 60 * AUDIO_ANALYSIS_SAMPLE_RATE)
    reference[quiet] = 0.0
    comparison = shift_signal(reference, 1668)
    decided = decide(reference, comparison)

    assert decided.audio.status == "agreed"
    assert decided.decision.state == "provisional"
    (run,) = decided.runs
    assert (run.first_index, run.last_index, run.chunk_count) == (0, 3, 3)


def test_search_edge_is_unavailable() -> None:
    reference = make_program(SEED, 60.0)
    comparison = shift_signal(reference, 8000 - 10)
    decided = decide(reference, comparison, max_offset_seconds=1.0)

    assert decided.audio.status == "search_edge"
    assert decided.decision.state == "unavailable"
    assert decided.decision.primary_reason == "search_edge"
    assert decided.decision.candidate is None
    assert decided.decision.failed_gates == ("search_edge",)


def test_no_single_offset_keeps_runs() -> None:
    reference = make_program(SEED, 70.0)
    comparison = insert_program(SEED, 70.0, 999)
    decided = decide(reference, comparison)

    assert decided.audio.status == "no_single_offset"
    assert decided.decision.state == "unavailable"
    assert decided.decision.primary_reason == "no_single_offset"
    assert decided.decision.candidate is None
    assert decided.decision.failed_gates == ("no_single_offset",)
    assert len(decided.runs) >= 2
    assert decided.stability.classification == "possible_discontinuity"


def test_unusable_audio_has_no_lag() -> None:
    reference = quiet_program(SEED, 35.0)
    comparison = quiet_program(SEED, 35.0)
    decided = decide(reference, comparison)

    assert decided.audio.status == "no_usable_audio"
    assert decided.audio.global_lag is None
    assert decided.audio.subframe_estimate is None
    assert decided.audio.rounded_frame is None
    assert decided.decision.state == "unavailable"
    assert decided.decision.primary_reason == "no_usable_audio"
    assert decided.decision.candidate is None
    assert decided.correlation_score == 0.0


def test_correlation_score_is_agreeing_over_credible() -> None:
    reference = make_program(SEED, 70.0)
    comparison = shift_signal(reference, 800)
    estimate = run_estimate(reference, comparison)
    assert estimate.credible_count > 0
    assert correlation_score(estimate) == pytest.approx(
        estimate.agreeing_count / estimate.credible_count
    )


def _observation(index: int, *, lag: int | None, credible: bool, agrees: bool) -> ChunkObservation:
    return ChunkObservation(
        index=index,
        reference_start=index * 240000,
        reference_count=240000,
        active=lag is not None,
        lag=lag,
        psr=30.0 if credible else 5.0,
        credible=credible,
        agrees=agrees,
    )


def test_stability_insufficient_evidence_below_three_credible() -> None:
    estimate = ChunkedAudioEstimate(
        outcome="no_single_offset",
        global_lag=100,
        observations=(
            _observation(0, lag=100, credible=True, agrees=True),
            _observation(1, lag=200, credible=True, agrees=False),
        ),
        runs=(
            ChunkRun(first_index=0, last_index=0, lag=100, chunk_count=1),
            ChunkRun(first_index=1, last_index=1, lag=200, chunk_count=1),
        ),
        active_count=2,
        credible_count=2,
        agreeing_count=1,
    )
    summary = derive_stability(
        estimate=estimate, outcome="no_single_offset", fps_reference=FPS, compensation_seconds=0.0
    )
    assert summary.classification == "insufficient_evidence"
    assert summary.valid_windows == 2
    assert summary.offset_min_frames is None


def test_stability_drift_from_sustained_walk() -> None:
    observations = (
        _observation(0, lag=0, credible=True, agrees=True),
        _observation(1, lag=-40, credible=True, agrees=False),
        _observation(2, lag=-80, credible=True, agrees=False),
    )
    estimate = ChunkedAudioEstimate(
        outcome="no_single_offset",
        global_lag=0,
        observations=observations,
        runs=(
            ChunkRun(first_index=0, last_index=0, lag=0, chunk_count=1),
            ChunkRun(first_index=1, last_index=1, lag=-40, chunk_count=1),
            ChunkRun(first_index=2, last_index=2, lag=-80, chunk_count=1),
        ),
        active_count=3,
        credible_count=3,
        agreeing_count=1,
    )
    summary = derive_stability(
        estimate=estimate, outcome="no_single_offset", fps_reference=FPS, compensation_seconds=0.0
    )
    assert summary.classification == "possible_drift"
    assert summary.valid_windows == 3


def test_stability_variable_for_single_run() -> None:
    estimate = ChunkedAudioEstimate(
        outcome="no_single_offset",
        global_lag=100,
        observations=(
            _observation(0, lag=100, credible=True, agrees=True),
            _observation(1, lag=100, credible=True, agrees=True),
            _observation(2, lag=100, credible=True, agrees=True),
        ),
        runs=(ChunkRun(first_index=0, last_index=2, lag=100, chunk_count=3),),
        active_count=3,
        credible_count=3,
        agreeing_count=3,
    )
    summary = derive_stability(
        estimate=estimate, outcome="no_single_offset", fps_reference=FPS, compensation_seconds=0.0
    )
    assert summary.classification == "variable"


def test_aborted_stage_discards_estimate() -> None:
    reference = make_program(SEED, 35.0)
    comparison = shift_signal(reference, 800)
    plan = plan_audio_chunks(len(reference), len(comparison), 30.0)
    decided = decide_aborted_stage(plan=plan, max_offset_seconds=30.0, reason="timeout")

    assert decided.attempt_status == "aborted"
    assert decided.audio.status == "no_usable_audio"
    assert decided.chunks.starts == ()
    assert decided.runs == ()
    assert decided.decision.state == "unavailable"
    assert decided.decision.primary_reason == "timeout"
    assert decided.decision.failed_gates == ("timeout",)
    assert decided.analysis.planned_chunk_count == len(plan.chunks)
    assert decided.stability.classification == "insufficient_evidence"
    assert decided.correlation_score == 0.0


def test_rejected_stage_has_no_plan() -> None:
    decided = decide_rejected_stage(
        max_offset_seconds=30.0, reason="selected_audio_timeline_unavailable"
    )

    assert decided.attempt_status == "preanalysis_rejection"
    assert decided.analysis.planned_chunk_count == 0
    assert decided.analysis.chunk_samples == 0
    assert decided.decision.state == "unavailable"
    assert decided.decision.primary_reason == "selected_audio_timeline_unavailable"
    assert decided.audio.compensation_seconds is None


def test_aborted_stage_records_real_compensation_when_starts_known() -> None:
    reference = make_program(SEED, 35.0)
    comparison = shift_signal(reference, 800)
    plan = plan_audio_chunks(len(reference), len(comparison), 30.0)
    decided = decide_aborted_stage(
        plan=plan,
        max_offset_seconds=30.0,
        reason="timeout",
        reference_audio_start=Fraction(0),
        reference_video_start=Fraction(0),
        comparison_audio_start=Fraction(1, 2),
        comparison_video_start=Fraction(0),
    )

    assert decided.attempt_status == "aborted"
    assert decided.audio.compensation_seconds == pytest.approx(-0.5)
    assert decided.audio.global_lag is None
    assert decided.decision.primary_reason == "timeout"


def test_aborted_stage_compensation_is_null_without_starts() -> None:
    reference = make_program(SEED, 35.0)
    comparison = shift_signal(reference, 800)
    plan = plan_audio_chunks(len(reference), len(comparison), 30.0)
    decided = decide_aborted_stage(plan=plan, max_offset_seconds=30.0, reason="timeout")

    assert decided.audio.compensation_seconds is None


def test_rejected_stage_records_real_compensation_when_starts_known() -> None:
    decided = decide_rejected_stage(
        max_offset_seconds=30.0,
        reason="selected_audio_timeline_unavailable",
        reference_audio_start=Fraction(1, 5),
        reference_video_start=Fraction(0),
        comparison_audio_start=Fraction(0),
        comparison_video_start=Fraction(0),
    )

    assert decided.audio.compensation_seconds == pytest.approx(0.2)
