"""Whole-track audio stage decision from chunk evidence and video confirmation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from statistics import median
from typing import get_args

from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkObservation,
    ChunkPlan,
    ChunkRun,
)
from frame_compare.utils.alignment_evidence import (
    AUDIO_ANALYSIS_SAMPLE_RATE,
    AlignmentStabilitySummary,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioAttemptStatus,
    AudioAuthorityRecount,
    AudioChunkColumns,
    AudioChunkRun,
    AudioDecisionCandidate,
    AudioOutcomeStatus,
    AudioPeakRatio,
    AudioSameFrameContext,
    AudioStageOutcome,
    VideoCheckObservation,
    VideoTargetEvidence,
)
from frame_compare.utils.alignment_policy import (
    compensated_lag_to_frame,
    compensated_offset_seconds,
)
from frame_compare.utils.alignment_policy import (
    rounded_frame as _rounded_frame,
)

ALIGNMENT_ESTIMATOR_POLICY = "whole-track-chunked-phat-video-check-motion-20260929"


@dataclass(frozen=True)
class DecidedAudioStage:
    """Audio-stage decision with the evidence pieces the workflow persists."""

    attempt_status: AudioAttemptStatus
    analysis: AudioAnalysisFacts
    chunks: AudioChunkColumns
    runs: tuple[AudioChunkRun, ...]
    audio: AudioStageOutcome
    decision: AudioAlignmentDecision
    stability: AlignmentStabilitySummary
    correlation_score: float
    video_check: VideoCheckObservation | None = None
    authority_recount: AudioAuthorityRecount | None = None


@dataclass(frozen=True, slots=True)
class AudioFrameDisagreements:
    """Frame-level A4b classification used to choose V3a targets."""

    same_frame_context: tuple[AudioSameFrameContext, ...]
    competing_runs: tuple[ChunkRun, ...]
    credible_disagreements: tuple[ChunkObservation, ...]
    noncredible_disagreements: tuple[ChunkObservation, ...]


V6_PRIMARY_REASON_ORDER = (
    "competing_offset_confirmed_by_video",
    "competing_offset",
    "unresolved_audio_disagreement",
    "video_check_inconclusive",
    "video_check_unavailable",
)


def correlation_score(estimate: ChunkedAudioEstimate) -> float:
    """Agreement fraction: agreeing over credible chunks, else zero."""
    if estimate.credible_count <= 0:
        return 0.0
    return estimate.agreeing_count / estimate.credible_count


def _audio_agrees(left: int, right: int) -> bool:
    return abs(left - right) <= AUDIO_ANALYSIS_SAMPLE_RATE * 2 // 1000


def _observation_frame(
    observation: ChunkObservation,
    *,
    compensation_seconds: float,
    fps_reference: Fraction,
) -> int:
    if observation.lag is None:
        raise ValueError(f"chunk {observation.index} is missing its lag")
    return compensated_lag_to_frame(
        observation.lag,
        compensation_seconds=compensation_seconds,
        fps_reference=fps_reference,
    )


def _adjacent_competing_runs(
    observations: Sequence[ChunkObservation],
) -> tuple[ChunkRun, ...]:
    """Build A4a runs without inheriting U1's non-credible-gap behavior."""
    runs: list[ChunkRun] = []
    members: list[tuple[int, int]] = []

    def close_run() -> None:
        if len(members) < 2:
            return
        lags = [lag for _index, lag in members]
        runs.append(
            ChunkRun(
                first_index=members[0][0],
                last_index=members[-1][0],
                lag=sorted(lags)[(len(lags) - 1) // 2],
                chunk_count=len(members),
            )
        )

    for observation in observations:
        lag = observation.lag
        if lag is None:
            continue
        if not members:
            members = [(observation.index, lag)]
            continue
        previous_index = members[-1][0]
        member_lags = [member_lag for _index, member_lag in members]
        if (
            observation.index == previous_index + 1
            and max(lag, *member_lags) - min(lag, *member_lags)
            <= AUDIO_ANALYSIS_SAMPLE_RATE * 2 // 1000
        ):
            members.append((observation.index, lag))
            continue
        close_run()
        members = [(observation.index, lag)]
    close_run()
    return tuple(runs)


def competing_run_center(
    run: ChunkRun,
    observations: Sequence[ChunkObservation],
) -> float:
    """Return V5a's true median lag for one A4a run."""
    lags = [
        item.lag
        for item in observations
        if run.first_index <= item.index <= run.last_index and item.lag is not None
    ]
    if len(lags) != run.chunk_count:
        raise ValueError("competing run members must all have lags")
    return float(median(lags))


def classify_audio_observations(
    *,
    observations: Sequence[ChunkObservation],
    global_lag: int | None,
    confirmed_offset: int,
    fps_reference: Fraction,
    compensation_seconds: float,
) -> AudioFrameDisagreements:
    """Classify the exact chunk rows shared by the video and decision stages."""
    if global_lag is None:
        return AudioFrameDisagreements((), (), (), ())

    frame_distinct_credible: list[ChunkObservation] = []
    frame_distinct_noncredible: list[ChunkObservation] = []
    same_frame: list[AudioSameFrameContext] = []
    for observation in observations:
        if observation.lag is None or not observation.active:
            continue
        if _audio_agrees(observation.lag, global_lag):
            continue
        frame = _observation_frame(
            observation,
            compensation_seconds=compensation_seconds,
            fps_reference=fps_reference,
        )
        if frame == confirmed_offset:
            if observation.credible:
                assert observation.lag is not None
                offset_seconds = observation.lag / AUDIO_ANALYSIS_SAMPLE_RATE + compensation_seconds
                same_frame.append(
                    AudioSameFrameContext(
                        chunk_index=observation.index,
                        lag_samples=observation.lag,
                        subframe_estimate=offset_seconds * float(fps_reference),
                        rounded_frame=frame,
                    )
                )
            continue
        if observation.credible:
            frame_distinct_credible.append(observation)
        else:
            frame_distinct_noncredible.append(observation)

    competing_runs = _adjacent_competing_runs(frame_distinct_credible)
    run_members = {
        index for run in competing_runs for index in range(run.first_index, run.last_index + 1)
    }
    single_credible = tuple(
        item for item in frame_distinct_credible if item.index not in run_members
    )
    return AudioFrameDisagreements(
        same_frame_context=tuple(same_frame),
        competing_runs=competing_runs,
        credible_disagreements=single_credible,
        noncredible_disagreements=tuple(frame_distinct_noncredible),
    )


def recount_audio_authority(
    *,
    estimate: ChunkedAudioEstimate,
    plan: ChunkPlan,
    confirmed_offset: int,
    fps_reference: Fraction,
    compensation_seconds: float,
) -> AudioAuthorityRecount:
    """Apply A4 to frame-level agreement while retaining U1's raw outcome."""
    if estimate.global_lag is None:
        return AudioAuthorityRecount(
            raw_status=estimate.outcome,
            raw_agreeing_chunks=estimate.agreeing_count,
            authority_status="no_usable_audio",
            authority_agreeing_chunks=0,
            passed=False,
        )
    authority_agreeing = 0
    for observation in estimate.observations:
        if not observation.credible or observation.lag is None:
            continue
        if _audio_agrees(observation.lag, estimate.global_lag) or (
            _observation_frame(
                observation,
                compensation_seconds=compensation_seconds,
                fps_reference=fps_reference,
            )
            == confirmed_offset
        ):
            authority_agreeing += 1
    credible = estimate.credible_count
    required = max(1, min(3, len(estimate.observations)))
    at_search_edge = (
        abs(estimate.global_lag) >= plan.lag_samples - AUDIO_ANALYSIS_SAMPLE_RATE * 2 // 1000
    )
    passed = (
        not at_search_edge
        and authority_agreeing >= required
        and authority_agreeing * 5 >= credible * 4
    )
    authority_status: AudioOutcomeStatus
    if at_search_edge:
        authority_status = "search_edge"
    elif passed:
        authority_status = "agreed"
    else:
        authority_status = "no_single_offset"
    return AudioAuthorityRecount(
        raw_status=estimate.outcome,
        raw_agreeing_chunks=estimate.agreeing_count,
        authority_status=authority_status,
        authority_agreeing_chunks=authority_agreeing,
        passed=passed,
    )


def _target_map(
    targets: Sequence[VideoTargetEvidence],
) -> dict[tuple[str, int, int], VideoTargetEvidence]:
    return {
        (target.kind, target.first_chunk_index, target.last_chunk_index): target
        for target in targets
    }


def v6_failure_reasons(
    *,
    authority_recount: AudioAuthorityRecount,
    video: VideoCheckObservation,
    competing_runs: Sequence[ChunkRun],
    credible_disagreements: Sequence[ChunkObservation],
) -> tuple[str, ...]:
    """Return all V6 failures in the plan's required primary-order sequence."""
    targets = _target_map(video.targets)
    alternative_confirmed = any(
        target.resolution == "alternative_confirmed" for target in video.targets
    )
    unresolved_run = any(
        (target := targets.get(("run", run.first_index, run.last_index))) is None
        or target.resolution != "resolved"
        for run in competing_runs
    )
    unresolved_chunk = any(
        (target := targets.get(("chunk", item.index, item.index))) is None
        or target.resolution != "resolved"
        for item in credible_disagreements
    )
    failures: list[str] = []
    if alternative_confirmed:
        failures.append(V6_PRIMARY_REASON_ORDER[0])
    if unresolved_run:
        failures.append(V6_PRIMARY_REASON_ORDER[1])
    if unresolved_chunk:
        failures.append(V6_PRIMARY_REASON_ORDER[2])
    if video.observation == "observed":
        if video.confirmed_offset is None:
            failures.append(V6_PRIMARY_REASON_ORDER[3])
    else:
        failures.append(V6_PRIMARY_REASON_ORDER[4])
    if not authority_recount.passed:
        failures.append(authority_recount.authority_status)
    return tuple(failures)


def is_trusted_automatic(
    *,
    authority_recount: AudioAuthorityRecount,
    video: VideoCheckObservation,
    competing_runs: Sequence[ChunkRun],
    credible_disagreements: Sequence[ChunkObservation],
) -> bool:
    """The single V6 trusted predicate; every conjunct is independently required."""
    authority_ok = authority_recount.passed
    video_ok = video.observation == "observed" and video.confirmed_offset is not None
    targets = _target_map(video.targets)
    runs_ok = all(
        (target := targets.get(("run", run.first_index, run.last_index))) is not None
        and target.resolution == "resolved"
        for run in competing_runs
    )
    chunks_ok = all(
        (target := targets.get(("chunk", item.index, item.index))) is not None
        and target.resolution == "resolved"
        for item in credible_disagreements
    )
    no_alternative_ok = all(
        target.resolution != "alternative_confirmed" for target in video.targets
    )
    return authority_ok and video_ok and runs_ok and chunks_ok and no_alternative_ok


def _is_sustained_walk(values: list[int]) -> bool:
    """Return whether run lags walk in one direction across three or more runs.

    Two runs are always monotonic, so a walk needs at least three: a sustained
    slope (drift) rather than one jump between plateaus (discontinuity).
    """
    if len(values) < 3 or values[0] == values[-1]:
        return False
    steps = [right - left for left, right in zip(values, values[1:], strict=False)]
    return all(step >= 0 for step in steps) or all(step <= 0 for step in steps)


def derive_stability(
    *,
    estimate: ChunkedAudioEstimate,
    outcome: AudioOutcomeStatus,
    fps_reference: Fraction,
    compensation_seconds: float,
) -> AlignmentStabilitySummary:
    """Derive the P2a stability classification from chunk runs.

    Frame values project compensated lags through A6 rounding, so they match
    the candidate frame for in-sync container delays.
    """
    credible = [item for item in estimate.observations if item.credible]
    if outcome in {"agreed", "search_edge"}:
        classification = "stable"
    elif len(credible) < 3:
        classification = "insufficient_evidence"
    else:
        lags = [run.lag for run in estimate.runs]
        if _is_sustained_walk(lags):
            classification = "possible_drift"
        elif len(set(lags)) >= 2:
            classification = "possible_discontinuity"
        else:
            classification = "variable"
    if classification == "insufficient_evidence" or not credible:
        return AlignmentStabilitySummary(
            classification=classification,
            valid_windows=len(credible),
            offset_min_frames=None,
            offset_max_frames=None,
            first_offset_frames=None,
            last_offset_frames=None,
            largest_adjacent_jump_frames=None,
            change_position_seconds=None,
        )
    frames = [
        compensated_lag_to_frame(
            item.lag or 0,
            compensation_seconds=compensation_seconds,
            fps_reference=fps_reference,
        )
        for item in credible
    ]
    jumps = [abs(later - earlier) for earlier, later in zip(frames, frames[1:], strict=False)]
    jump_index = max(range(len(jumps)), key=lambda index: jumps[index]) if jumps else None
    change_position: float | None = None
    if (
        outcome != "agreed"
        and classification == "possible_discontinuity"
        and jump_index is not None
    ):
        change_position = credible[jump_index + 1].reference_start / AUDIO_ANALYSIS_SAMPLE_RATE
    return AlignmentStabilitySummary(
        classification=classification,
        valid_windows=len(credible),
        offset_min_frames=min(frames),
        offset_max_frames=max(frames),
        first_offset_frames=frames[0],
        last_offset_frames=frames[-1],
        largest_adjacent_jump_frames=max(jumps) if jumps else 0,
        change_position_seconds=change_position,
    )


def _evidence_columns(estimate: ChunkedAudioEstimate) -> AudioChunkColumns:
    """Project U1 observations into compact columnar evidence rows."""
    psrs: list[AudioPeakRatio | None] = []
    for item in estimate.observations:
        if item.psr is None:
            psrs.append(None)
        elif math.isinf(float(item.psr)):
            psrs.append("unbounded")
        else:
            psrs.append(float(item.psr))
    return AudioChunkColumns(
        starts=tuple(item.reference_start for item in estimate.observations),
        counts=tuple(item.reference_count for item in estimate.observations),
        active=tuple(item.active for item in estimate.observations),
        lags=tuple(item.lag for item in estimate.observations),
        psrs=tuple(psrs),
        credible=tuple(item.credible for item in estimate.observations),
        agrees=tuple(item.agrees for item in estimate.observations),
        total_samples=sum(item.reference_count for item in estimate.observations),
        rows_omitted=False,
    )


def _evidence_runs(estimate: ChunkedAudioEstimate) -> tuple[AudioChunkRun, ...]:
    return tuple(
        AudioChunkRun(
            first_index=run.first_index,
            last_index=run.last_index,
            lag=run.lag,
            chunk_count=run.chunk_count,
        )
        for run in estimate.runs
    )


def _empty_evidence(total_samples: int) -> tuple[AudioChunkColumns, tuple[AudioChunkRun, ...]]:
    columns = AudioChunkColumns(
        starts=(),
        counts=(),
        active=(),
        lags=(),
        psrs=(),
        credible=(),
        agrees=(),
        total_samples=total_samples,
        rows_omitted=False,
    )
    return columns, ()


def _insufficient_stability() -> AlignmentStabilitySummary:
    return AlignmentStabilitySummary(
        classification="insufficient_evidence",
        valid_windows=0,
        offset_min_frames=None,
        offset_max_frames=None,
        first_offset_frames=None,
        last_offset_frames=None,
        largest_adjacent_jump_frames=None,
        change_position_seconds=None,
    )


def _unusable_audio_outcome(*, compensation_seconds: float | None) -> AudioStageOutcome:
    return AudioStageOutcome(
        status="no_usable_audio",
        global_lag=None,
        active_chunks=0,
        credible_chunks=0,
        agreeing_chunks=0,
        compensation_seconds=compensation_seconds,
        subframe_estimate=None,
        rounded_frame=None,
    )


def _known_start_compensation(
    *,
    reference_audio_start: Fraction | None,
    reference_video_start: Fraction | None,
    comparison_audio_start: Fraction | None,
    comparison_video_start: Fraction | None,
) -> float | None:
    """Return the real A5 compensation when every start fact is known (m14)."""
    if (
        reference_audio_start is None
        or reference_video_start is None
        or comparison_audio_start is None
        or comparison_video_start is None
    ):
        return None
    return compensated_offset_seconds(
        global_lag=0,
        reference_audio_start=reference_audio_start,
        reference_video_start=reference_video_start,
        comparison_audio_start=comparison_audio_start,
        comparison_video_start=comparison_video_start,
    )


def _analysis_facts(plan: ChunkPlan | None, *, max_offset_seconds: float) -> AudioAnalysisFacts:
    if plan is None:
        return AudioAnalysisFacts(
            analysis_rate=AUDIO_ANALYSIS_SAMPLE_RATE,
            max_offset_seconds=max_offset_seconds,
            chunk_samples=0,
            lag_samples=0,
            planned_chunk_count=0,
        )
    return AudioAnalysisFacts(
        analysis_rate=AUDIO_ANALYSIS_SAMPLE_RATE,
        max_offset_seconds=max_offset_seconds,
        chunk_samples=plan.chunk_samples,
        lag_samples=plan.lag_samples,
        planned_chunk_count=len(plan.chunks),
    )


def decide_after_video(
    *,
    stage: DecidedAudioStage,
    estimate: ChunkedAudioEstimate,
    plan: ChunkPlan,
    video: VideoCheckObservation,
    fps_reference: Fraction,
) -> DecidedAudioStage:
    """Apply A4b and V6 to a completed audio stage after V5 returns."""
    if stage.audio.global_lag is None:
        return replace(stage, video_check=video)
    confirmed_offset = video.confirmed_offset
    if video.observation != "observed" or confirmed_offset is None:
        reason = (
            "video_check_unavailable"
            if video.observation != "observed"
            else "video_check_inconclusive"
        )
        candidate = stage.decision.candidate
        raw_reason = stage.audio.status
        failures = (reason,) + ((raw_reason,) if raw_reason != "agreed" else ())
        decision = replace(
            stage.decision,
            state="provisional" if candidate is not None else "unavailable",
            primary_reason=reason,
            failed_gates=failures,
        )
        return replace(stage, video_check=video, decision=decision)

    compensation_seconds = stage.audio.compensation_seconds
    if compensation_seconds is None:
        raise ValueError("a completed audio stage needs compensation for video authority")
    classification = classify_audio_observations(
        observations=estimate.observations,
        global_lag=estimate.global_lag,
        confirmed_offset=confirmed_offset,
        fps_reference=fps_reference,
        compensation_seconds=compensation_seconds,
    )
    recount = recount_audio_authority(
        estimate=estimate,
        plan=plan,
        confirmed_offset=confirmed_offset,
        fps_reference=fps_reference,
        compensation_seconds=compensation_seconds,
    )
    video = replace(video, same_frame_context=classification.same_frame_context)
    reasons = v6_failure_reasons(
        authority_recount=recount,
        video=video,
        competing_runs=classification.competing_runs,
        credible_disagreements=classification.credible_disagreements,
    )
    trusted = is_trusted_automatic(
        authority_recount=recount,
        video=video,
        competing_runs=classification.competing_runs,
        credible_disagreements=classification.credible_disagreements,
    )
    candidate = stage.decision.candidate
    if candidate is None and stage.audio.status != "search_edge":
        if stage.audio.subframe_estimate is None or stage.audio.compensation_seconds is None:
            raise ValueError("a global audio lag needs sub-frame evidence")
        candidate = AudioDecisionCandidate(
            frame_offset=confirmed_offset,
            time_offset_seconds=stage.audio.global_lag / AUDIO_ANALYSIS_SAMPLE_RATE
            + stage.audio.compensation_seconds,
            subframe_estimate=stage.audio.subframe_estimate,
            basis="audio_only",
        )
    elif candidate is not None:
        candidate = replace(candidate, frame_offset=confirmed_offset)
    if trusted:
        decision = AudioAlignmentDecision(
            state="trusted_automatic",
            candidate=candidate,
            primary_reason="audio_video_confirmed",
            failed_gates=(),
        )
    else:
        primary_reason = reasons[0] if reasons else "no_single_offset"
        decision = AudioAlignmentDecision(
            state="provisional" if candidate is not None else "unavailable",
            candidate=candidate,
            primary_reason=primary_reason,
            failed_gates=reasons or (primary_reason,),
        )
    return replace(
        stage,
        decision=decision,
        video_check=video,
        authority_recount=recount,
    )


def decide_completed_stage(
    *,
    estimate: ChunkedAudioEstimate,
    plan: ChunkPlan,
    max_offset_seconds: float,
    reference_audio_start: Fraction,
    reference_video_start: Fraction,
    comparison_audio_start: Fraction,
    comparison_video_start: Fraction,
    fps_reference: Fraction,
) -> DecidedAudioStage:
    """Decide a finished collection per the U3 table; nothing is applied yet.

    Takes the raw A5 start facts and computes the compensation, the sub-frame
    estimate ``x`` and the rounded frame ``r`` itself, so every frame number
    comes from this module. An agreed audio stage is an internal provisional
    audio-only candidate; every other outcome is ``unavailable`` with its own
    reason and no candidate.
    """
    if estimate.outcome not in get_args(AudioOutcomeStatus.__value__):
        raise ValueError(f"unknown chunked audio outcome: {estimate.outcome!r}")
    outcome: AudioOutcomeStatus = estimate.outcome
    # The A5 compensation is the compensated offset of a zero lag, so the
    # formula lives only in compensated_offset_seconds.
    compensation_seconds = compensated_offset_seconds(
        global_lag=0,
        reference_audio_start=reference_audio_start,
        reference_video_start=reference_video_start,
        comparison_audio_start=comparison_audio_start,
        comparison_video_start=comparison_video_start,
    )
    offset_seconds: float | None = None
    subframe: float | None = None
    rounded: int | None = None
    if estimate.global_lag is not None:
        offset_seconds = estimate.global_lag / AUDIO_ANALYSIS_SAMPLE_RATE + compensation_seconds
        subframe = offset_seconds * float(fps_reference)
        rounded = _rounded_frame(offset_seconds, fps_reference)
    audio = AudioStageOutcome(
        status=outcome if estimate.global_lag is not None else "no_usable_audio",
        global_lag=estimate.global_lag,
        active_chunks=estimate.active_count,
        credible_chunks=estimate.credible_count,
        agreeing_chunks=estimate.agreeing_count,
        compensation_seconds=compensation_seconds,
        subframe_estimate=subframe,
        rounded_frame=rounded,
    )
    if (
        outcome == "agreed"
        and offset_seconds is not None
        and subframe is not None
        and rounded is not None
    ):
        candidate: AudioDecisionCandidate | None = AudioDecisionCandidate(
            frame_offset=rounded,
            time_offset_seconds=offset_seconds,
            subframe_estimate=subframe,
            basis="audio_only",
        )
        decision = AudioAlignmentDecision(
            state="provisional",
            candidate=candidate,
            primary_reason="audio_only",
            failed_gates=(),
        )
    else:
        reason = outcome if outcome != "agreed" else "no_usable_audio"
        decision = AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason=reason,
            failed_gates=(reason,),
        )
    return DecidedAudioStage(
        attempt_status="complete",
        analysis=_analysis_facts(plan, max_offset_seconds=max_offset_seconds),
        chunks=_evidence_columns(estimate),
        runs=_evidence_runs(estimate),
        audio=audio,
        decision=decision,
        stability=derive_stability(
            estimate=estimate,
            outcome=outcome,
            fps_reference=fps_reference,
            compensation_seconds=compensation_seconds,
        ),
        correlation_score=correlation_score(estimate),
    )


def decide_aborted_stage(
    *,
    plan: ChunkPlan | None,
    max_offset_seconds: float,
    reason: str,
    reference_audio_start: Fraction | None = None,
    reference_video_start: Fraction | None = None,
    comparison_audio_start: Fraction | None = None,
    comparison_video_start: Fraction | None = None,
) -> DecidedAudioStage:
    """Decide a failed collection: the accumulator is discarded, never finished.

    Only scalar collection facts survive (recorded by the workflow); chunk rows,
    runs and stability stay empty per A7a. The compensation is the real A5
    value when start facts are known, else null (m14).
    """
    columns, runs = _empty_evidence(
        sum(count for _start, count in plan.chunks) if plan is not None else 0
    )
    return DecidedAudioStage(
        attempt_status="aborted",
        analysis=_analysis_facts(plan, max_offset_seconds=max_offset_seconds),
        chunks=columns,
        runs=runs,
        audio=_unusable_audio_outcome(
            compensation_seconds=_known_start_compensation(
                reference_audio_start=reference_audio_start,
                reference_video_start=reference_video_start,
                comparison_audio_start=comparison_audio_start,
                comparison_video_start=comparison_video_start,
            )
        ),
        decision=AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason=reason,
            failed_gates=(reason,),
        ),
        stability=_insufficient_stability(),
        correlation_score=0.0,
    )


def decide_rejected_stage(
    *,
    max_offset_seconds: float,
    reason: str,
    reference_audio_start: Fraction | None = None,
    reference_video_start: Fraction | None = None,
    comparison_audio_start: Fraction | None = None,
    comparison_video_start: Fraction | None = None,
) -> DecidedAudioStage:
    """Decide a preanalysis rejection made before any decode ran.

    The compensation is the real A5 value when start facts are known, else
    null (m14).
    """
    columns, runs = _empty_evidence(0)
    return DecidedAudioStage(
        attempt_status="preanalysis_rejection",
        analysis=_analysis_facts(None, max_offset_seconds=max_offset_seconds),
        chunks=columns,
        runs=runs,
        audio=_unusable_audio_outcome(
            compensation_seconds=_known_start_compensation(
                reference_audio_start=reference_audio_start,
                reference_video_start=reference_video_start,
                comparison_audio_start=comparison_audio_start,
                comparison_video_start=comparison_video_start,
            )
        ),
        decision=AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason=reason,
            failed_gates=(reason,),
        ),
        stability=_insufficient_stability(),
        correlation_score=0.0,
    )


__all__ = [
    "ALIGNMENT_ESTIMATOR_POLICY",
    "AudioFrameDisagreements",
    "V6_PRIMARY_REASON_ORDER",
    "DecidedAudioStage",
    "classify_audio_observations",
    "correlation_score",
    "decide_aborted_stage",
    "decide_completed_stage",
    "decide_after_video",
    "decide_rejected_stage",
    "derive_stability",
    "is_trusted_automatic",
    "recount_audio_authority",
    "v6_failure_reasons",
]
