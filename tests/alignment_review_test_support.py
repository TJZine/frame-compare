from __future__ import annotations

import json
import math
from dataclasses import replace
from fractions import Fraction

from frame_compare.services.alignment_decision import ALIGNMENT_ESTIMATOR_POLICY
from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioAuthorityRecount,
    AudioChunkColumns,
    AudioChunkRun,
    AudioDecisionCandidate,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
)

REFERENCE_DIGEST = "a" * 64
COMPARISON_DIGEST = "b" * 64
CHUNK_SAMPLES = 40_000

_DIAGNOSTIC_POLICY = "retained-audio-evidence-v1"
_FPS_NUM = 24
_FPS_DEN = 1
_LAG_SAMPLES = 240_000
_MAX_OFFSET_SECONDS = 30.0
_AGREE_PSR = 30.0


def audio_review(suggestion: int | None) -> str:
    return json.dumps(
        {
            "current_authority": {
                "origin": "shared_computed_offsets" if suggestion is not None else "none",
                "frame_offset": suggestion,
            },
            "evidence_availability": (
                "historical_details_unavailable" if suggestion is not None else "not_computed"
            ),
            "audio_attempt": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def frame_lag(frame_offset: int) -> int:
    """Return the nearest 8 kHz lag for a whole-frame offset at the fixture FPS."""
    return round(Fraction(frame_offset * 8_000 * _FPS_DEN, _FPS_NUM))


def subframe_estimate(lag: int) -> float:
    return lag / 8_000 * (_FPS_NUM / _FPS_DEN)


def stream(role: str, digest: str) -> SelectedAudioStreamEvidence:
    return SelectedAudioStreamEvidence(
        role="reference" if role == "reference" else "comparison",  # type: ignore[arg-type]
        source_identity_digest=digest,
        audio_stream_index=0,
        absolute_stream_index=1,
        selection_method="automatic_metadata",
        selection_rank=(0, 0, 0, 0),
        codec_name="aac",
        sample_rate=48_000,
        channels=2,
        channel_layout="stereo",
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        language_match="not_applicable" if role == "reference" else "match",
        commentary_match="not_applicable" if role == "reference" else "match",
        stream_start_num=0,
        stream_start_den=1,
        stream_start_basis="metadata",
        input_start_num=0,
        input_start_den=1,
        input_start_basis="metadata",
        time_base_num=1,
        time_base_den=48_000,
        duration_num=120,
        duration_den=1,
        duration_basis="duration_ts",
        video_start_num=0,
        video_start_den=1,
        video_start_basis="metadata",
        timeline_scale_num=1,
        timeline_scale_den=1,
    )


def analysis(*, planned_chunk_count: int) -> AudioAnalysisFacts:
    planned = planned_chunk_count > 0
    return AudioAnalysisFacts(
        analysis_rate=8_000,
        max_offset_seconds=_MAX_OFFSET_SECONDS,
        chunk_samples=CHUNK_SAMPLES if planned else 0,
        lag_samples=_LAG_SAMPLES if planned else 0,
        planned_chunk_count=planned_chunk_count,
    )


def agreed_columns(*, lag: int, chunk_count: int) -> AudioChunkColumns:
    return AudioChunkColumns(
        starts=tuple(index * CHUNK_SAMPLES for index in range(chunk_count)),
        counts=(CHUNK_SAMPLES,) * chunk_count,
        active=(True,) * chunk_count,
        lags=(lag,) * chunk_count,
        psrs=(_AGREE_PSR,) * chunk_count,
        credible=(True,) * chunk_count,
        agrees=(True,) * chunk_count,
        total_samples=chunk_count * CHUNK_SAMPLES,
    )


def agreed_audio(*, lag: int, frame_offset: int, chunk_count: int) -> AudioStageOutcome:
    return AudioStageOutcome(
        status="agreed",
        global_lag=lag,
        active_chunks=chunk_count,
        credible_chunks=chunk_count,
        agreeing_chunks=chunk_count,
        compensation_seconds=0.0,
        subframe_estimate=subframe_estimate(lag),
        rounded_frame=frame_offset,
    )


def stable_summary(*, frame_offset: int, chunk_count: int) -> AlignmentStabilitySummary:
    return AlignmentStabilitySummary(
        classification="stable",
        valid_windows=chunk_count,
        offset_min_frames=frame_offset,
        offset_max_frames=frame_offset,
        first_offset_frames=frame_offset,
        last_offset_frames=frame_offset,
        largest_adjacent_jump_frames=0,
        change_position_seconds=None,
    )


def _unobserved_video() -> VideoCheckObservation:
    return VideoCheckObservation(
        observation="not_observed",
        scored_offsets=(),
        confirmed_offset=None,
        index_build_seconds=None,
        positions=(),
    )


def attempt_shell(
    *,
    ordinal: int,
    status: str,
    analysis_facts: AudioAnalysisFacts,
    chunks: AudioChunkColumns,
    runs: tuple[AudioChunkRun, ...],
    audio: AudioStageOutcome,
    decision: AudioAlignmentDecision,
    stability: AlignmentStabilitySummary,
) -> AudioAlignmentAttempt:
    return AudioAlignmentAttempt(
        reference_identity_digest=REFERENCE_DIGEST,
        comparison_identity_digest=COMPARISON_DIGEST,
        comparison_ordinal=ordinal,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        estimator_policy=ALIGNMENT_ESTIMATOR_POLICY,
        diagnostic_policy=_DIAGNOSTIC_POLICY,
        media_runtime_fingerprint="alignment-runtime-test",
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe="ffmpeg -i <input> -map 0:a -f f32le -",
        fps_num=_FPS_NUM,
        fps_den=_FPS_DEN,
        selected_streams=(
            stream("reference", REFERENCE_DIGEST),
            stream("comparison", COMPARISON_DIGEST),
        ),
        analysis=analysis_facts,
        chunks=chunks,
        runs=runs,
        audio=audio,
        collection_observation="not_observed",
        collection=(),
        video_check=_unobserved_video(),
        decision=decision,
        stability=stability,
    )


def provisional_audio_attempt(
    *, ordinal: int = 1, frame_offset: int = 0, chunk_count: int = 4
) -> AudioAlignmentAttempt:
    """Agreed audio stage awaiting video confirmation (the U3 applied-nothing state)."""
    lag = frame_lag(frame_offset)
    subframe = subframe_estimate(lag)
    assert math.floor(subframe + 0.5) == frame_offset
    return attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis_facts=analysis(planned_chunk_count=chunk_count),
        chunks=agreed_columns(lag=lag, chunk_count=chunk_count),
        runs=(AudioChunkRun(0, chunk_count - 1, lag, chunk_count),),
        audio=agreed_audio(lag=lag, frame_offset=frame_offset, chunk_count=chunk_count),
        decision=AudioAlignmentDecision(
            state="provisional",
            candidate=AudioDecisionCandidate(
                frame_offset=frame_offset,
                time_offset_seconds=lag / 8_000,
                subframe_estimate=subframe,
                basis="audio_only",
            ),
            primary_reason="audio_only",
            failed_gates=(),
        ),
        stability=stable_summary(frame_offset=frame_offset, chunk_count=chunk_count),
    )


def trusted_audio_attempt(
    *, ordinal: int = 1, frame_offset: int = 0, chunk_count: int = 4
) -> AudioAlignmentAttempt:
    """Audio-plus-video confirmed attempt that may authorize an applied result."""
    lag = frame_lag(frame_offset)
    subframe = subframe_estimate(lag)
    assert math.floor(subframe + 0.5) == frame_offset
    attempt = attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis_facts=analysis(planned_chunk_count=chunk_count),
        chunks=agreed_columns(lag=lag, chunk_count=chunk_count),
        runs=(AudioChunkRun(0, chunk_count - 1, lag, chunk_count),),
        audio=agreed_audio(lag=lag, frame_offset=frame_offset, chunk_count=chunk_count),
        decision=AudioAlignmentDecision(
            state="trusted_automatic",
            candidate=AudioDecisionCandidate(
                frame_offset=frame_offset,
                time_offset_seconds=lag / 8_000,
                subframe_estimate=subframe,
                basis="audio_only",
            ),
            primary_reason="audio_video_confirmed",
            failed_gates=(),
        ),
        stability=stable_summary(frame_offset=frame_offset, chunk_count=chunk_count),
    )
    return replace(
        attempt,
        video_check=VideoCheckObservation(
            observation="observed",
            scored_offsets=tuple(frame_offset + delta for delta in range(-2, 3)),
            confirmed_offset=frame_offset,
            index_build_seconds=0.0,
            positions=(),
        ),
        authority_recount=AudioAuthorityRecount(
            raw_status="agreed",
            raw_agreeing_chunks=chunk_count,
            authority_status="agreed",
            authority_agreeing_chunks=chunk_count,
            passed=True,
        ),
    )


def unavailable_audio_attempt(*, ordinal: int = 1) -> AudioAlignmentAttempt:
    """Two credible runs at different lags: no single offset, never applied."""
    near_lag = frame_lag(12)
    far_lag = frame_lag(24)
    chunk_count = 4
    return attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis_facts=analysis(planned_chunk_count=chunk_count),
        chunks=AudioChunkColumns(
            starts=tuple(index * CHUNK_SAMPLES for index in range(chunk_count)),
            counts=(CHUNK_SAMPLES,) * chunk_count,
            active=(True,) * chunk_count,
            lags=(near_lag, near_lag, far_lag, far_lag),
            psrs=(_AGREE_PSR,) * chunk_count,
            credible=(True,) * chunk_count,
            agrees=(True, True, False, False),
            total_samples=chunk_count * CHUNK_SAMPLES,
        ),
        runs=(
            AudioChunkRun(0, 1, near_lag, 2),
            AudioChunkRun(2, 3, far_lag, 2),
        ),
        audio=AudioStageOutcome(
            status="no_single_offset",
            global_lag=near_lag,
            active_chunks=chunk_count,
            credible_chunks=chunk_count,
            agreeing_chunks=2,
            compensation_seconds=0.0,
            subframe_estimate=subframe_estimate(near_lag),
            rounded_frame=12,
        ),
        decision=AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason="no_single_offset",
            failed_gates=("no_single_offset",),
        ),
        stability=AlignmentStabilitySummary(
            classification="possible_discontinuity",
            valid_windows=chunk_count,
            offset_min_frames=12,
            offset_max_frames=24,
            first_offset_frames=12,
            last_offset_frames=24,
            largest_adjacent_jump_frames=12,
            change_position_seconds=10.0,
        ),
    )
