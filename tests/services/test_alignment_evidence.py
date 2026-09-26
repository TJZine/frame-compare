"""Tests for the v4 audio-evidence schema: bounds, round-trips, strict parsing."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioChunkColumns,
    AudioChunkRun,
    AudioCollectionFacts,
    AudioCollectionFailure,
    AudioDecisionCandidate,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
    evidence_from_payload,
)

DIGEST = "b" * 64
OTHER_DIGEST = "c" * 64
POLICY = "whole-track-chunked-phat-video-check-20260925"


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
            primary_reason="video_check_pending",
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


def test_three_hour_attempt_serializes_within_128kib() -> None:
    payload = json.dumps(asdict(attempt_with_chunks(360)), allow_nan=False)
    assert len(payload.encode("utf-8")) <= 128 * 1024


def test_native_projection_of_large_attempt_stays_within_bound() -> None:
    """M2: a 2160-chunk attempt embeds with empty rows and non-empty runs."""
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
        diagnostic="video_check_pending",
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
    assert len(encoded.encode("utf-8")) <= 128 * 1024
    parsed = evidence_from_payload(AudioAlignmentAttempt, json.loads(encoded)["audio_attempt"])
    assert parsed.chunks.rows_omitted is True
    assert parsed.chunks.starts == ()
    assert len(parsed.runs) == 1
    assert parsed.runs[0].lag == 1177
    assert parsed.audio.active_chunks == 2160
    assert parsed.audio.compensation_seconds == 0.0
    assert parsed.audio.subframe_estimate == 146.23
    assert parsed.decision.state == "provisional"


def test_round_trip_complete_rejected_and_aborted() -> None:
    complete = attempt_with_chunks(3)
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
    assert aborted.audio.compensation_seconds == -0.5
    assert aborted.collection_failure == AudioCollectionFailure(category="timeout", side=None)
    assert evidence_from_payload(AudioAlignmentAttempt, asdict(aborted)) == aborted


def test_parser_rejects_unknown_and_missing_keys() -> None:
    payload = asdict(attempt_with_chunks(2))
    with pytest.raises(ValueError, match="unknown keys"):
        evidence_from_payload(AudioAlignmentAttempt, {**payload, "legacy_windows": []})
    with pytest.raises(ValueError, match="missing keys"):
        evidence_from_payload(
            AudioAlignmentAttempt,
            {key: value for key, value in payload.items() if key != "decision"},
        )
    nested = asdict(attempt_with_chunks(2))
    nested["audio"]["agreed"] = True
    with pytest.raises(ValueError, match="unknown keys"):
        evidence_from_payload(AudioAlignmentAttempt, nested)
    nested = asdict(attempt_with_chunks(2))
    del nested["chunks"]["rows_omitted"]
    with pytest.raises(ValueError, match="missing keys"):
        evidence_from_payload(AudioAlignmentAttempt, nested)


def test_parser_rejects_bool_as_int_and_non_finite() -> None:
    payload = asdict(attempt_with_chunks(2))
    payload["comparison_ordinal"] = True
    with pytest.raises(ValueError):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["chunks"]["starts"] = [0, False]
    with pytest.raises(ValueError):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["audio"]["compensation_seconds"] = float("nan")
    with pytest.raises(ValueError):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["audio"]["compensation_seconds"] = float("inf")
    with pytest.raises(ValueError):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["chunks"]["psrs"] = [float("nan"), 88.5]
    with pytest.raises(ValueError):
        evidence_from_payload(AudioAlignmentAttempt, payload)


def test_parser_rejects_wrong_literal_values() -> None:
    payload = asdict(attempt_with_chunks(2))
    payload["status"] = "finished"
    with pytest.raises(ValueError, match="must be one of"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["decision"]["state"] = "pending"
    with pytest.raises(ValueError, match="must be one of"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["collection_observation"] = "sometimes"
    with pytest.raises(ValueError, match="must be one of"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["selected_streams"][0]["selection_method"] = "auto"
    with pytest.raises(ValueError, match="must be one of"):
        evidence_from_payload(AudioAlignmentAttempt, payload)


def test_parser_rejects_out_of_bounds_values() -> None:
    payload = asdict(attempt_with_chunks(2))
    payload["audio"]["agreeing_chunks"] = 3
    with pytest.raises(ValueError, match="nest"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["audio"]["global_lag"] = 240001
    with pytest.raises(ValueError, match="search radius"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["chunks"]["lags"] = [1177, None]
    with pytest.raises(ValueError, match="require a lag"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(3))
    for key in ("starts", "counts", "active", "lags", "psrs", "credible", "agrees"):
        payload["chunks"][key] = payload["chunks"][key][:2]
    with pytest.raises(ValueError, match="every planned chunk"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["reference_identity_digest"] = "not-a-digest"
    with pytest.raises(ValueError, match="digest"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["fps_den"] = 0
    with pytest.raises(ValueError):
        evidence_from_payload(AudioAlignmentAttempt, payload)


def test_parser_rejects_inconsistent_evidence() -> None:
    payload = asdict(attempt_with_chunks(2))
    payload["selected_streams"] = list(reversed(payload["selected_streams"]))
    with pytest.raises(ValueError, match="reference and comparison"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["status"] = "aborted"
    with pytest.raises(ValueError, match="unavailable decision"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["video_check"] = {
        "observation": "not_observed",
        "scored_offsets": [144],
        "confirmed_offset": None,
        "index_build_seconds": None,
        "positions": [],
    }
    with pytest.raises(ValueError, match="must not carry evidence"):
        evidence_from_payload(AudioAlignmentAttempt, payload)

    payload = asdict(attempt_with_chunks(2))
    payload["decision"] = {
        "state": "unavailable",
        "candidate": {
            "frame_offset": 146,
            "time_offset_seconds": 0.147,
            "subframe_estimate": 146.23,
            "basis": "audio_only",
        },
        "primary_reason": "no_single_offset",
        "failed_gates": ["no_single_offset"],
    }
    with pytest.raises(ValueError, match="unavailable decision lacks a candidate"):
        evidence_from_payload(AudioAlignmentAttempt, payload)


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
