"""Tests for the whole-track audio stage decision (A5/A6, U3 table, P2a)."""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkedCorrelation,
    ChunkObservation,
    ChunkPlan,
    ChunkRun,
    comparison_window,
    plan_audio_chunks,
)
from frame_compare.services.alignment_decision import (
    V6_PRIMARY_REASON_ORDER,
    VIDEO_CHECK_PENDING_REASON,
    classify_audio_disagreements,
    compensated_offset_seconds,
    correlation_score,
    decide_aborted_stage,
    decide_after_video,
    decide_completed_stage,
    decide_rejected_stage,
    derive_stability,
    is_trusted_automatic,
    recount_audio_authority,
    rounded_frame,
    subframe_estimate,
    v6_failure_reasons,
)
from frame_compare.utils.alignment_evidence import (
    AUDIO_ANALYSIS_SAMPLE_RATE,
    AudioAuthorityRecount,
    VideoCheckObservation,
    VideoTargetEvidence,
    VideoTargetPosition,
)
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


def _estimate(
    observations: tuple[ChunkObservation, ...],
    *,
    outcome: str = "agreed",
    global_lag: int = 0,
    agreeing_count: int | None = None,
    runs: tuple[ChunkRun, ...] = (),
) -> ChunkedAudioEstimate:
    credible_count = sum(item.credible for item in observations)
    return ChunkedAudioEstimate(
        outcome=outcome,  # type: ignore[arg-type]
        global_lag=global_lag,
        observations=observations,
        runs=runs,
        active_count=sum(item.active for item in observations),
        credible_count=credible_count,
        agreeing_count=(
            agreeing_count
            if agreeing_count is not None
            else sum(item.agrees for item in observations)
        ),
    )


def _plan_for(*observations: ChunkObservation) -> ChunkPlan:
    count = max((item.index for item in observations), default=0) + 1
    return ChunkPlan(
        chunk_samples=240000,
        lag_samples=8000,
        chunks=tuple((index * 240000, 240000) for index in range(count)),
    )


def _authority(*, passed: bool = True, status: str = "agreed") -> AudioAuthorityRecount:
    return AudioAuthorityRecount(
        raw_status="agreed",
        raw_agreeing_chunks=3,
        authority_status=status,  # type: ignore[arg-type]
        authority_agreeing_chunks=3 if passed else 1,
        passed=passed,
    )


def _video(
    *targets: VideoTargetEvidence,
    confirmed_offset: int | None = 0,
    observed: bool = True,
) -> VideoCheckObservation:
    if not observed:
        return VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        )
    return VideoCheckObservation(
        observation="observed",
        scored_offsets=(-2, -1, 0, 1, 2),
        confirmed_offset=confirmed_offset,
        index_build_seconds=0.0,
        positions=(),
        targets=targets,
    )


def _target(
    kind: str,
    first: int,
    last: int,
    resolution: str,
    *,
    position_index: int,
) -> VideoTargetEvidence:
    if resolution == "unexamined":
        positions = ()
    elif resolution == "alternative_confirmed":
        positions = (VideoTargetPosition(position_index, position_index, 1.0, 0.1, "alternative"),)
    elif resolution == "resolved":
        count = 2 if kind == "run" else 1
        positions = tuple(
            VideoTargetPosition(
                position_index + offset,
                position_index + offset,
                0.1,
                1.0,
                "confirmed",
            )
            for offset in range(count)
        )
    else:
        positions = (VideoTargetPosition(position_index, position_index, 1.0, 1.0, "neither"),)
    return VideoTargetEvidence(
        kind=kind,  # type: ignore[arg-type]
        first_chunk_index=first,
        last_chunk_index=last,
        credible=True,
        start_sample=(first) * 240_000,
        end_sample=((last) + 1) * 240_000,
        target_offset=1,
        alternative_offsets=(1, 2),
        resolution=resolution,  # type: ignore[arg-type]
        positions=positions,
    )


def test_a4b_recount_accepts_14_of_20_when_six_lags_share_the_frame() -> None:
    observations = tuple(
        _observation(
            index,
            lag=80 if index >= 14 else 0,
            credible=True,
            agrees=index < 14,
        )
        for index in range(20)
    )
    estimate = _estimate(observations, outcome="no_single_offset", agreeing_count=14)
    recount = recount_audio_authority(
        estimate=estimate,
        plan=_plan_for(*observations),
        confirmed_offset=0,
        fps_reference=Fraction(24),
        compensation_seconds=0.0,
    )
    classification = classify_audio_disagreements(
        estimate=estimate,
        confirmed_offset=0,
        fps_reference=Fraction(24),
        compensation_seconds=0.0,
    )

    assert estimate.outcome == "no_single_offset"
    assert recount.raw_status == "no_single_offset"
    assert recount.raw_agreeing_chunks == 14
    assert recount.authority_agreeing_chunks == 20
    assert recount.authority_status == "agreed"
    assert recount.passed
    assert len(classification.same_frame_context) == 6
    assert classification.credible_disagreements == ()


def test_decide_after_video_trusts_the_recounted_authority() -> None:
    observations = tuple(
        _observation(
            index,
            lag=80 if index >= 14 else 0,
            credible=True,
            agrees=index < 14,
        )
        for index in range(20)
    )
    estimate = _estimate(observations, outcome="no_single_offset", agreeing_count=14)
    plan = _plan_for(*observations)
    stage = decide_completed_stage(
        estimate=estimate,
        plan=plan,
        max_offset_seconds=1.0,
        reference_audio_start=Fraction(0),
        reference_video_start=Fraction(0),
        comparison_audio_start=Fraction(0),
        comparison_video_start=Fraction(0),
        fps_reference=Fraction(24),
    )

    decided = decide_after_video(
        stage=stage,
        estimate=estimate,
        plan=plan,
        video=_video(),
        fps_reference=Fraction(24),
    )

    assert decided.decision.state == "trusted_automatic"
    assert decided.decision.primary_reason == "audio_video_confirmed"
    assert decided.decision.candidate is not None
    assert decided.decision.candidate.frame_offset == 0
    assert decided.authority_recount is not None
    assert decided.authority_recount.raw_status == "no_single_offset"


def test_a4a_requires_index_adjacency_for_competing_runs() -> None:
    observations = (
        _observation(2, lag=1600, credible=True, agrees=False),
        _observation(15, lag=1600, credible=True, agrees=False),
    )
    estimate = _estimate(
        observations,
        outcome="no_single_offset",
        runs=(ChunkRun(first_index=2, last_index=15, lag=1600, chunk_count=2),),
    )

    classification = classify_audio_disagreements(
        estimate=estimate,
        confirmed_offset=0,
        fps_reference=Fraction(24),
        compensation_seconds=0.0,
    )

    assert classification.competing_runs == ()
    assert tuple(item.index for item in classification.credible_disagreements) == (2, 15)


def test_a4b_boundary_run_drives_trusted_or_provisional_video_outcome() -> None:
    observations = (
        _observation(0, lag=0, credible=True, agrees=True),
        _observation(1, lag=166, credible=True, agrees=False),
        _observation(2, lag=167, credible=True, agrees=False),
        _observation(3, lag=168, credible=True, agrees=False),
    )
    estimate = _estimate(observations, outcome="no_single_offset", agreeing_count=1)
    classification = classify_audio_disagreements(
        estimate=estimate,
        confirmed_offset=0,
        fps_reference=Fraction(24),
        compensation_seconds=0.0,
    )

    assert [
        (run.first_index, run.last_index, run.chunk_count) for run in classification.competing_runs
    ] == [(2, 3, 2)]
    assert tuple(item.index for item in classification.credible_disagreements) == ()
    assert is_trusted_automatic(
        authority_recount=_authority(),
        video=_video(_target("run", 2, 3, "resolved", position_index=0)),
        competing_runs=classification.competing_runs,
        credible_disagreements=classification.credible_disagreements,
    )
    assert not is_trusted_automatic(
        authority_recount=_authority(),
        video=_video(
            _target("chunk", 2, 2, "resolved", position_index=0),
            _target("chunk", 3, 3, "resolved", position_index=2),
        ),
        competing_runs=classification.competing_runs,
        credible_disagreements=classification.credible_disagreements,
    )


@pytest.mark.parametrize(
    ("authority", "video", "runs", "credible", "expected"),
    [
        (True, _video(), (), (), True),
        (False, _video(), (), (), False),
        (True, _video(observed=False), (), (), False),
        (
            True,
            _video(_target("run", 2, 3, "unexamined", position_index=0)),
            (ChunkRun(first_index=2, last_index=3, lag=1600, chunk_count=2),),
            (),
            False,
        ),
        (
            True,
            _video(),
            (),
            (_observation(5, lag=1600, credible=True, agrees=False),),
            False,
        ),
        (
            True,
            _video(_target("chunk", 9, 9, "alternative_confirmed", position_index=0)),
            (),
            (),
            False,
        ),
    ],
)
def test_v6_trusted_predicate_requires_each_conjunct(
    authority: bool,
    video: VideoCheckObservation,
    runs: tuple[ChunkRun, ...],
    credible: tuple[ChunkObservation, ...],
    expected: bool,
) -> None:
    assert (
        is_trusted_automatic(
            authority_recount=_authority(passed=authority),
            video=video,
            competing_runs=runs,
            credible_disagreements=credible,
        )
        is expected
    )


def test_v6_reason_ordering_uses_the_plan_order() -> None:
    run = ChunkRun(first_index=2, last_index=3, lag=1600, chunk_count=2)
    credible = _observation(5, lag=1600, credible=True, agrees=False)
    ordered = v6_failure_reasons(
        authority_recount=_authority(),
        video=_video(
            _target("run", 2, 3, "unresolved", position_index=0),
            _target("chunk", 5, 5, "unresolved", position_index=2),
            _target("chunk", 9, 9, "alternative_confirmed", position_index=3),
        ),
        competing_runs=(run,),
        credible_disagreements=(credible,),
    )
    assert ordered[:3] == V6_PRIMARY_REASON_ORDER[:3]


@pytest.mark.parametrize(
    ("video", "expected"),
    [
        (_video(confirmed_offset=None), ("video_check_inconclusive",)),
        (_video(observed=False), ("video_check_unavailable",)),
    ],
)
def test_v6_reason_ordering_covers_video_terminal_reasons(
    video: VideoCheckObservation,
    expected: tuple[str, ...],
) -> None:
    assert (
        v6_failure_reasons(
            authority_recount=_authority(),
            video=video,
            competing_runs=(),
            credible_disagreements=(),
        )
        == expected
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
