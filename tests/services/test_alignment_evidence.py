"""Tests for the v4 audio-evidence schema: bounds, round-trips, strict parsing."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.utils.alignment_evidence import (
    MAX_ALIGNMENT_EVIDENCE_BYTES,
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioAuthorityRecount,
    AudioChunkColumns,
    AudioChunkRun,
    AudioCollectionFacts,
    AudioCollectionFailure,
    AudioDecisionCandidate,
    AudioSameFrameContext,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoPositionDifference,
    VideoTargetEvidence,
    VideoTargetPosition,
    audio_attempt_payload,
    evidence_from_payload,
)

DIGEST = "b" * 64
OTHER_DIGEST = "c" * 64
POLICY = "whole-track-chunked-phat-video-check-motion-20260929"


def stream(role: str, digest: str = DIGEST) -> SelectedAudioStreamEvidence:
    return SelectedAudioStreamEvidence(
        role=role,  # type: ignore[arg-type]
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


def collection(role: str) -> AudioCollectionFacts:
    return AudioCollectionFacts(
        role=role,  # type: ignore[arg-type]
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


def test_three_hour_attempt_serializes_within_shared_bound() -> None:
    payload = json.dumps(audio_attempt_payload(attempt_with_chunks(360)), allow_nan=False)
    assert len(payload.encode("utf-8")) <= MAX_ALIGNMENT_EVIDENCE_BYTES


def _populated_video_attempt() -> AudioAlignmentAttempt:
    attempt = attempt_with_chunks(6)
    confirmed = 146
    targets = (
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=0,
            last_chunk_index=0,
            credible=True,
            start_sample=(0) * 240_000,
            end_sample=((0) + 1) * 240_000,
            target_offset=147,
            alternative_offsets=(147, 148),
            resolution="resolved",
            positions=(VideoTargetPosition(0, 100, 0.1, 1.0, "confirmed"),),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=1,
            last_chunk_index=1,
            credible=True,
            start_sample=(1) * 240_000,
            end_sample=((1) + 1) * 240_000,
            target_offset=150,
            alternative_offsets=(149, 150, 151),
            resolution="unresolved",
            positions=(VideoTargetPosition(1, 200, 1.0, 1.0, "neither"),),
        ),
        VideoTargetEvidence(
            kind="run",
            first_chunk_index=2,
            last_chunk_index=3,
            credible=True,
            start_sample=(2) * 240_000,
            end_sample=((3) + 1) * 240_000,
            target_offset=153,
            alternative_offsets=(152, 153, 154),
            resolution="unexamined",
            positions=(),
        ),
        VideoTargetEvidence(
            kind="run",
            first_chunk_index=4,
            last_chunk_index=5,
            credible=True,
            start_sample=(4) * 240_000,
            end_sample=((5) + 1) * 240_000,
            target_offset=155,
            alternative_offsets=(154, 155, 156),
            resolution="alternative_confirmed",
            positions=(VideoTargetPosition(2, 300, 1.0, 0.1, "alternative", 155),),
        ),
    )
    return replace(
        attempt,
        authority_recount=AudioAuthorityRecount(
            raw_status="agreed",
            raw_agreeing_chunks=6,
            authority_status="agreed",
            authority_agreeing_chunks=6,
            passed=True,
        ),
        video_check=VideoCheckObservation(
            observation="observed",
            scored_offsets=(144, 145, confirmed, 147, 148),
            confirmed_offset=confirmed,
            index_build_seconds=0.25,
            positions=(VideoPositionDifference(0, 50, (2.0, 1.0, 0.1, 1.0, 2.0)),),
            targets=targets,
            same_frame_context=(AudioSameFrameContext(2, 120, 146.36, 146),),
            check_points=(VideoCheckPoint(12.5, 300, 154),),
        ),
    )


def test_extended_video_evidence_round_trips_with_all_fields_populated() -> None:
    attempt = _populated_video_attempt()
    attempt = replace(
        attempt,
        selected_streams=tuple(
            replace(entry, timeline_scale_num=25, timeline_scale_den=24)
            for entry in attempt.selected_streams
        ),
    )
    parsed = evidence_from_payload(AudioAlignmentAttempt, asdict(attempt))
    assert parsed == attempt
    assert parsed.selected_streams[0].timeline_scale == Fraction(25, 24)
    assert parsed.selected_streams[1].timeline_scale == Fraction(25, 24)
    assert parsed.authority_recount is not None
    assert parsed.video_check.targets[0].target_offset == 147
    assert parsed.video_check.targets[0].credible is True
    assert (
        parsed.video_check.targets[0].start_sample,
        parsed.video_check.targets[0].end_sample,
    ) == (
        0,
        240_000,
    )
    assert parsed.video_check.targets[3].resolution == "alternative_confirmed"
    assert parsed.video_check.same_frame_context[0].rounded_frame == 146
    assert parsed.video_check.check_points[0].suggested_comparison_frame == 154


@pytest.mark.parametrize(
    "case",
    ("mixed-target-order", "zero-fps-denominator"),
)
def test_plain_attempt_parser_contract(case: str) -> None:
    payload = asdict(_populated_video_attempt())
    if case == "mixed-target-order":
        payload["video_check"]["targets"] = list(reversed(payload["video_check"]["targets"]))
    elif case == "zero-fps-denominator":
        payload["fps_den"] = 0

    before = deepcopy(payload)
    if case == "zero-fps-denominator":
        with pytest.raises(ValueError, match="fps_den"):
            evidence_from_payload(AudioAlignmentAttempt, payload)
        return

    first = evidence_from_payload(AudioAlignmentAttempt, payload)
    second = evidence_from_payload(AudioAlignmentAttempt, payload)
    assert first == second
    assert payload == before
    if case == "mixed-target-order":
        assert tuple(target.target_offset for target in first.video_check.targets) == (
            155,
            153,
            150,
            147,
        )


def test_native_projection_omits_rows_and_retains_authoritative_target_context() -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    projected = _project_audio_attempt_for_review(_populated_video_attempt())
    parsed = evidence_from_payload(AudioAlignmentAttempt, asdict(projected))
    assert projected.chunks.rows_omitted is True
    assert not any(
        (
            projected.chunks.starts,
            projected.chunks.counts,
            projected.chunks.active,
            projected.chunks.lags,
            projected.chunks.psrs,
            projected.chunks.credible,
            projected.chunks.agrees,
        )
    )
    assert projected.chunks.total_samples == 1_440_000
    assert parsed == projected
    assert parsed.video_check.targets[0] == _populated_video_attempt().video_check.targets[0]


def test_partial_final_target_bounds_survive_native_projection() -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    attempt = attempt_with_chunks(4)
    chunks = replace(
        attempt.chunks,
        counts=(240_000, 240_000, 240_000, 120_000),
    )
    target = VideoTargetEvidence(
        kind="run",
        first_chunk_index=2,
        last_chunk_index=3,
        credible=True,
        start_sample=480_000,
        end_sample=840_000,
        target_offset=150,
        alternative_offsets=(149, 150, 151),
        resolution="unexamined",
        positions=(),
    )
    populated = replace(
        attempt,
        chunks=replace(chunks, total_samples=840_000),
        video_check=VideoCheckObservation(
            observation="observed",
            scored_offsets=(144, 145, 146, 147, 148),
            confirmed_offset=146,
            index_build_seconds=0.0,
            positions=(),
            targets=(target,),
        ),
    )

    assert evidence_from_payload(AudioAlignmentAttempt, asdict(populated)) == populated
    projected = _project_audio_attempt_for_review(populated)
    parsed = evidence_from_payload(AudioAlignmentAttempt, asdict(projected))
    assert projected.chunks.rows_omitted is True
    assert projected.chunks.counts == ()
    assert projected.chunks.total_samples == 840_000
    assert parsed.video_check.targets[0] == target
    assert (
        target.start_sample / populated.analysis.analysis_rate,
        target.end_sample / populated.analysis.analysis_rate,
    ) == (60.0, 105.0)


def test_extended_video_evidence_maximum_target_budget_stays_bounded() -> None:
    attempt = attempt_with_chunks(360)
    targets = tuple(
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=index,
            last_chunk_index=index,
            credible=True,
            start_sample=(index) * 240_000,
            end_sample=((index) + 1) * 240_000,
            target_offset=6,
            alternative_offsets=(5, 6, 7),
            resolution="resolved" if index < 3 else "unexamined",
            positions=(
                tuple(
                    VideoTargetPosition(
                        index * 4 + position,
                        index * 100 + position,
                        0.1,
                        1.0,
                        "confirmed",
                    )
                    for position in range(4)
                )
                if index < 3
                else ()
            ),
        )
        for index in range(12)
    )
    populated = replace(
        attempt,
        video_check=VideoCheckObservation(
            observation="observed",
            scored_offsets=(2, 3, 4, 5, 6),
            confirmed_offset=4,
            index_build_seconds=0.0,
            positions=(),
            targets=targets,
            check_points=tuple(
                VideoCheckPoint(float(index), index, index + 4) for index in range(5)
            ),
        ),
    )
    payload = json.dumps(asdict(populated), allow_nan=False)
    assert len(payload.encode("utf-8")) <= MAX_ALIGNMENT_EVIDENCE_BYTES


def test_native_projection_of_large_attempt_omits_rows() -> None:
    from frame_compare.services.alignment import _build_audio_review_map
    from frame_compare.services.alignment_keys import alignment_key
    from frame_compare.services.types import AlignmentProvenance, AlignmentResult

    reference = Path("reference.mkv")
    comparison = Path("comparison.mkv")
    attempt = attempt_with_chunks(2160)
    result = AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=1.0,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic="audio_only",
        stability=attempt.stability,
        audio_attempt=attempt,
    )
    key = alignment_key(reference, comparison)
    payloads = _build_audio_review_map(
        reference=reference,
        comparisons=[comparison],
        results_map={key: result},
        provenances={
            key: AlignmentProvenance(
                result=result,
                comparison_cache_key="key",
                provenance="computed_this_run",
                evidence_availability="current_attempt",
            )
        },
    )
    encoded = payloads[key]
    assert len(encoded.encode("utf-8")) <= 2 * 1024 * 1024
    parsed = evidence_from_payload(AudioAlignmentAttempt, json.loads(encoded)["audio_attempt"])
    assert parsed.chunks.rows_omitted is True
    assert parsed.chunks.starts == ()
    assert parsed.chunks.total_samples == attempt.chunks.total_samples
    assert len(parsed.runs) == 1
    assert parsed.runs[0].lag == 1177
    assert parsed.audio.active_chunks == 2160
    assert parsed.audio.compensation_seconds == 0.0
    assert parsed.audio.subframe_estimate == 146.23
    assert parsed.decision.state == "provisional"


def test_round_trip_complete_rejected_and_aborted() -> None:
    complete = attempt_with_chunks(3)
    assert complete.chunks.total_samples == sum(complete.chunks.counts)
    assert evidence_from_payload(AudioAlignmentAttempt, asdict(complete)) == complete

    rejected_payload = asdict(complete)
    rejected_payload["status"] = "preanalysis_rejection"
    rejected_payload["analysis"] = {
        "analysis_rate": 8000,
        "max_offset_seconds": 30.0,
        "chunk_samples": 0,
        "lag_samples": 0,
        "planned_chunk_count": 0,
    }
    for key in ("starts", "counts", "active", "lags", "psrs", "credible", "agrees"):
        rejected_payload["chunks"][key] = []
    rejected_payload["chunks"]["total_samples"] = 0
    rejected_payload["runs"] = []
    rejected_payload["audio"] = {
        "status": "no_usable_audio",
        "global_lag": None,
        "active_chunks": 0,
        "credible_chunks": 0,
        "agreeing_chunks": 0,
        "compensation_seconds": None,
        "subframe_estimate": None,
        "rounded_frame": None,
    }
    rejected_payload["collection_observation"] = "not_observed"
    rejected_payload["collection"] = []
    rejected_payload["collection_failure"] = None
    rejected_payload["decision"] = {
        "state": "unavailable",
        "candidate": None,
        "primary_reason": "selected_audio_timeline_unavailable",
        "failed_gates": ["selected_audio_timeline_unavailable"],
    }
    rejected_payload["stability"] = {
        "classification": "insufficient_evidence",
        "valid_windows": 0,
        "offset_min_frames": None,
        "offset_max_frames": None,
        "first_offset_frames": None,
        "last_offset_frames": None,
        "largest_adjacent_jump_frames": None,
        "change_position_seconds": None,
    }
    rejected = evidence_from_payload(AudioAlignmentAttempt, rejected_payload)
    assert rejected.status == "preanalysis_rejection"
    assert rejected.chunks.total_samples == 0
    assert rejected.audio.compensation_seconds is None
    assert evidence_from_payload(AudioAlignmentAttempt, asdict(rejected)) == rejected

    aborted_payload = asdict(complete)
    aborted_payload["status"] = "aborted"
    for key in ("starts", "counts", "active", "lags", "psrs", "credible", "agrees"):
        aborted_payload["chunks"][key] = []
    aborted_payload["runs"] = []
    aborted_payload["audio"] = {
        "status": "no_usable_audio",
        "global_lag": None,
        "active_chunks": 0,
        "credible_chunks": 0,
        "agreeing_chunks": 0,
        "compensation_seconds": -0.5,
        "subframe_estimate": None,
        "rounded_frame": None,
    }
    aborted_payload["collection_failure"] = {"category": "timeout", "side": None}
    aborted_payload["decision"] = {
        "state": "unavailable",
        "candidate": None,
        "primary_reason": "timeout",
        "failed_gates": ["timeout"],
    }
    aborted = evidence_from_payload(AudioAlignmentAttempt, aborted_payload)
    assert aborted.status == "aborted"
    assert aborted.chunks.total_samples == complete.chunks.total_samples
    assert aborted.audio.compensation_seconds == -0.5
    assert aborted.collection_failure == AudioCollectionFailure(category="timeout", side=None)
    assert evidence_from_payload(AudioAlignmentAttempt, asdict(aborted)) == aborted


def test_producer_construction_of_invalid_attempt_raises() -> None:
    valid = attempt_with_chunks(2)
    with pytest.raises(ValueError, match="unavailable decision"):
        replace(valid, status="aborted")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be one of"):
        replace(valid, status="finished")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="nest"):
        replace(valid, audio=replace(valid.audio, agreeing_chunks=3))
    with pytest.raises(ValueError, match="must be one of"):
        AudioAlignmentDecision(
            state="pending",  # type: ignore[arg-type]
            candidate=None,
            primary_reason="no_single_offset",
            failed_gates=("no_single_offset",),
        )
    with pytest.raises(ValueError, match="finite number"):
        AudioChunkColumns(
            starts=(0,),
            counts=(240000,),
            active=(True,),
            lags=(0,),
            psrs=(float("inf"),),
            credible=(True,),
            agrees=(True,),
            total_samples=240000,
        )
    with pytest.raises(ValueError, match="must share one length"):
        AudioChunkColumns(
            starts=(0, 240000),
            counts=(240000,),
            active=(True, True),
            lags=(0, 0),
            psrs=(88.5, 88.5),
            credible=(True, True),
            agrees=(True, True),
            total_samples=480000,
        )
    unavailable_timeout = replace(
        valid.decision,
        state="unavailable",
        candidate=None,
        primary_reason="timeout",
        failed_gates=("timeout",),
    )
    # A non-complete attempt keeps covering rows when it has them; only a
    # partial row set disagrees with the plan.
    assert replace(valid, status="aborted", decision=unavailable_timeout).status == "aborted"  # type: ignore[arg-type]
    partial_payload = asdict(valid)
    partial_payload["status"] = "aborted"
    partial_payload["decision"] = {
        "state": "unavailable",
        "candidate": None,
        "primary_reason": "timeout",
        "failed_gates": ["timeout"],
    }
    for key in ("starts", "counts", "active", "lags", "psrs", "credible", "agrees"):
        partial_payload["chunks"][key] = partial_payload["chunks"][key][:1]
    with pytest.raises(ValueError, match="every planned chunk"):
        evidence_from_payload(AudioAlignmentAttempt, partial_payload)


def test_collection_failure_round_trips_at_pair_level() -> None:
    failure = AudioCollectionFailure(category="timeout", side=None)
    assert evidence_from_payload(AudioCollectionFailure, asdict(failure)) == failure
    with pytest.raises(ValueError, match="must be one of"):
        evidence_from_payload(AudioCollectionFailure, {"category": "typo", "side": "reference"})
    attempt = attempt_with_chunks(0)
    assert attempt.collection_failure is None
    with pytest.raises(ValueError, match="unknown keys"):
        evidence_from_payload(
            AudioCollectionFacts,
            {
                "role": "reference",
                "emitted_samples": 0,
                "eof_sample": 0,
                "elapsed_seconds": 0.0,
                "returncode": 0,
                "stderr_bytes": 0,
                "stderr_truncated": False,
                "cleanup_completed": True,
                "failure_category": None,
            },
        )


def test_unbounded_psr_round_trips() -> None:
    attempt = attempt_with_chunks(2)
    payload = asdict(attempt)
    payload["chunks"]["psrs"] = ["unbounded", 88.5]
    parsed = evidence_from_payload(AudioAlignmentAttempt, payload)
    assert parsed.chunks.psrs == ("unbounded", 88.5)
    assert evidence_from_payload(AudioAlignmentAttempt, asdict(parsed)) == parsed
    json.dumps(payload, allow_nan=False)
