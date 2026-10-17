"""Shared literal audio-evidence builders for service and presentation tests."""

from __future__ import annotations

from dataclasses import replace

from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioChunkColumns,
    AudioChunkRun,
    AudioCollectionFacts,
    AudioDecisionCandidate,
    AudioPairSide,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
)

DIGEST = "b" * 64
OTHER_DIGEST = "c" * 64
POLICY = "whole-track-chunked-phat-video-check-motion-20260929"


def stream(role: AudioPairSide, digest: str = DIGEST) -> SelectedAudioStreamEvidence:
    return SelectedAudioStreamEvidence(
        role=role,
        source_identity_digest=digest,
        audio_stream_index=0,
        absolute_stream_index=1,
        selection_method="automatic_metadata",
        selection_rank=(0, 0, 0, 0),
        codec_name="aac",
        sample_rate=48000,
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
        stream_start_basis="default_zero",
        input_start_num=0,
        input_start_den=1,
        input_start_basis="default_zero",
        time_base_num=1,
        time_base_den=48000,
        duration_num=360,
        duration_den=1,
        duration_basis="stream_duration",
        video_start_num=0,
        video_start_den=1,
        video_start_basis="default_zero",
        timeline_scale_num=1,
        timeline_scale_den=1,
    )


def retimed_comparison_stream() -> SelectedAudioStreamEvidence:
    """Shared R5 fixture: a comparison retimed 25/24 against an unretimed reference."""
    return replace(
        stream("comparison", OTHER_DIGEST),
        timeline_scale_num=25,
        timeline_scale_den=24,
    )


def collection(role: AudioPairSide) -> AudioCollectionFacts:
    return AudioCollectionFacts(
        role=role,
        emitted_samples=2880000,
        eof_sample=2880000,
        elapsed_seconds=12.5,
        returncode=0,
        stderr_bytes=44,
        stderr_truncated=False,
        cleanup_completed=True,
    )


def attempt_with_chunks(planned: int, *, lag: int = 1177) -> AudioAlignmentAttempt:
    lag_samples = 240000
    return AudioAlignmentAttempt(
        reference_identity_digest=DIGEST,
        comparison_identity_digest=OTHER_DIGEST,
        comparison_ordinal=1,
        status="complete",
        estimator_policy=POLICY,
        diagnostic_policy="retained-audio-evidence-v1",
        media_runtime_fingerprint="ffmpeg/7.1",
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe="recipe",
        fps_num=24000,
        fps_den=1001,
        selected_streams=(stream("reference"), stream("comparison", OTHER_DIGEST)),
        analysis=AudioAnalysisFacts(
            analysis_rate=8000,
            max_offset_seconds=30.0,
            chunk_samples=240000,
            lag_samples=lag_samples,
            planned_chunk_count=planned,
        ),
        chunks=AudioChunkColumns(
            starts=tuple(index * 240000 for index in range(planned)),
            counts=(240000,) * planned,
            active=(True,) * planned,
            lags=(lag,) * planned,
            psrs=(88.5,) * planned,
            credible=(True,) * planned,
            agrees=(True,) * planned,
            total_samples=planned * 240000,
        ),
        runs=(AudioChunkRun(first_index=0, last_index=planned - 1, lag=lag, chunk_count=planned),)
        if planned
        else (),
        audio=AudioStageOutcome(
            status="agreed",
            global_lag=lag,
            active_chunks=planned,
            credible_chunks=planned,
            agreeing_chunks=planned,
            compensation_seconds=0.0,
            subframe_estimate=146.23,
            rounded_frame=146,
        ),
        collection_observation="observed",
        collection=(collection("reference"), collection("comparison")),
        video_check=VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        ),
        decision=AudioAlignmentDecision(
            state="provisional",
            candidate=AudioDecisionCandidate(
                frame_offset=146,
                time_offset_seconds=0.147,
                subframe_estimate=146.23,
                basis="audio_only",
            ),
            primary_reason="audio_only",
            failed_gates=(),
        ),
        stability=AlignmentStabilitySummary(
            classification="stable",
            valid_windows=planned,
            offset_min_frames=146,
            offset_max_frames=146,
            first_offset_frames=146,
            last_offset_frames=146,
            largest_adjacent_jump_frames=0,
            change_position_seconds=None,
        ),
    )
