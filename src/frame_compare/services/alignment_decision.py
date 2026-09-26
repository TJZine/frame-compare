"""Whole-track audio stage decision from chunk evidence and video confirmation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import get_args

from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkPlan,
)
from frame_compare.utils.alignment_evidence import (
    AUDIO_ANALYSIS_SAMPLE_RATE,
    AlignmentStabilitySummary,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioAttemptStatus,
    AudioChunkColumns,
    AudioChunkRun,
    AudioDecisionCandidate,
    AudioOutcomeStatus,
    AudioPeakRatio,
    AudioStageOutcome,
)

ALIGNMENT_ESTIMATOR_POLICY = "whole-track-chunked-phat-video-check-20260925"

VIDEO_CHECK_PENDING_REASON = "video_check_pending"


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


def compensated_offset_seconds(
    *,
    global_lag: int,
    reference_audio_start: Fraction,
    reference_video_start: Fraction,
    comparison_audio_start: Fraction,
    comparison_video_start: Fraction,
) -> float:
    """Apply A5 container-start compensation to a chunked global lag (samples)."""
    lag_seconds = global_lag / AUDIO_ANALYSIS_SAMPLE_RATE
    compensation = (reference_audio_start - reference_video_start) - (
        comparison_audio_start - comparison_video_start
    )
    return lag_seconds + float(compensation)


def subframe_estimate(*, offset_seconds: float, fps_reference: Fraction) -> float:
    """Keep the A6 sub-frame estimate ``x = offset_seconds * fps`` as evidence."""
    return offset_seconds * float(fps_reference)


def rounded_frame(subframe: float) -> int:
    """Round the sub-frame estimate to the neighbouring integer frame (A6)."""
    return math.floor(subframe + 0.5)


def correlation_score(estimate: ChunkedAudioEstimate) -> float:
    """Agreement fraction: agreeing over credible chunks, else zero."""
    if estimate.credible_count <= 0:
        return 0.0
    return estimate.agreeing_count / estimate.credible_count


def _compensated_lag_to_frame(
    lag: int,
    *,
    compensation_seconds: float,
    fps_reference: Fraction,
) -> int:
    """Project one chunk lag to frames through A5 compensation and A6 rounding."""
    offset_seconds = lag / AUDIO_ANALYSIS_SAMPLE_RATE + compensation_seconds
    return rounded_frame(
        subframe_estimate(offset_seconds=offset_seconds, fps_reference=fps_reference)
    )


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
    if outcome == "agreed":
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
        _compensated_lag_to_frame(
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


def _empty_evidence() -> tuple[AudioChunkColumns, tuple[AudioChunkRun, ...]]:
    columns = AudioChunkColumns(
        starts=(),
        counts=(),
        active=(),
        lags=(),
        psrs=(),
        credible=(),
        agrees=(),
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
    comes from this module. An agreed audio stage is ``provisional`` with
    reason ``video_check_pending``; every other outcome is ``unavailable``
    with its own reason and no candidate.
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
        subframe = subframe_estimate(offset_seconds=offset_seconds, fps_reference=fps_reference)
        rounded = rounded_frame(subframe)
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
            primary_reason=VIDEO_CHECK_PENDING_REASON,
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
    columns, runs = _empty_evidence()
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
    columns, runs = _empty_evidence()
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
    "VIDEO_CHECK_PENDING_REASON",
    "DecidedAudioStage",
    "compensated_offset_seconds",
    "correlation_score",
    "decide_aborted_stage",
    "decide_completed_stage",
    "decide_rejected_stage",
    "derive_stability",
    "rounded_frame",
    "subframe_estimate",
]
