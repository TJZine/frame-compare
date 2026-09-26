"""Run-local audio alignment diagnostic persistence tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from frame_compare.errors import PathEscapesRootError
from frame_compare.services import alignment_audio, alignment_diagnostics
from frame_compare.services.types import AlignmentResult
from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioAttemptStatus,
    AudioAuthorityRecount,
    AudioChunkColumns,
    AudioChunkRun,
    AudioCollectionFacts,
    AudioCollectionFailure,
    AudioDecisionCandidate,
    AudioDecisionState,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoTargetEvidence,
    VideoTargetPosition,
    evidence_from_payload,
)

_CHUNK_SAMPLES = 40000
_LAG_SAMPLES = 240000
_PLANNED_CHUNKS = 5


def _stream(role: Literal["reference", "comparison"], digest: str) -> SelectedAudioStreamEvidence:
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
        duration_num=120,
        duration_den=1,
        duration_basis="duration_ts",
        video_start_num=0,
        video_start_den=1,
        video_start_basis="default_zero",
    )


def _collection(role: Literal["reference", "comparison"]) -> AudioCollectionFacts:
    return AudioCollectionFacts(
        role=role,
        emitted_samples=200000,
        eof_sample=200000,
        elapsed_seconds=0.25,
        returncode=0,
        stderr_bytes=44,
        stderr_truncated=False,
        cleanup_completed=True,
    )


def _not_observed_video() -> VideoCheckObservation:
    return VideoCheckObservation(
        observation="not_observed",
        scored_offsets=(),
        confirmed_offset=None,
        index_build_seconds=None,
        positions=(),
    )


def audio_attempt() -> AudioAlignmentAttempt:
    lag = 0
    return AudioAlignmentAttempt(
        reference_identity_digest="a" * 64,
        comparison_identity_digest="b" * 64,
        comparison_ordinal=1,
        status="complete",
        estimator_policy="whole-track-chunked-phat-video-check-20260925",
        diagnostic_policy="retained-audio-evidence-v1",
        media_runtime_fingerprint="alignment-runtime",
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe=alignment_audio.normalized_extraction_recipe(),
        fps_num=24,
        fps_den=1,
        selected_streams=(
            _stream("reference", "a" * 64),
            _stream("comparison", "b" * 64),
        ),
        analysis=AudioAnalysisFacts(
            analysis_rate=8000,
            max_offset_seconds=30.0,
            chunk_samples=_CHUNK_SAMPLES,
            lag_samples=_LAG_SAMPLES,
            planned_chunk_count=_PLANNED_CHUNKS,
        ),
        chunks=AudioChunkColumns(
            starts=tuple(index * _CHUNK_SAMPLES for index in range(_PLANNED_CHUNKS)),
            counts=(_CHUNK_SAMPLES,) * _PLANNED_CHUNKS,
            active=(True,) * _PLANNED_CHUNKS,
            lags=(lag,) * _PLANNED_CHUNKS,
            psrs=(88.5,) * _PLANNED_CHUNKS,
            credible=(True,) * _PLANNED_CHUNKS,
            agrees=(True,) * _PLANNED_CHUNKS,
        ),
        runs=(
            AudioChunkRun(
                first_index=0, last_index=_PLANNED_CHUNKS - 1, lag=lag, chunk_count=_PLANNED_CHUNKS
            ),
        ),
        audio=AudioStageOutcome(
            status="agreed",
            global_lag=lag,
            active_chunks=_PLANNED_CHUNKS,
            credible_chunks=_PLANNED_CHUNKS,
            agreeing_chunks=_PLANNED_CHUNKS,
            compensation_seconds=0.0,
            subframe_estimate=0.0,
            rounded_frame=0,
        ),
        collection_observation="not_observed",
        collection=(),
        video_check=_not_observed_video(),
        decision=AudioAlignmentDecision(
            state="provisional",
            candidate=AudioDecisionCandidate(
                frame_offset=0,
                time_offset_seconds=0.0,
                subframe_estimate=0.0,
                basis="audio_only",
            ),
            primary_reason="video_check_pending",
            failed_gates=(),
        ),
        stability=AlignmentStabilitySummary(
            classification="stable",
            valid_windows=_PLANNED_CHUNKS,
            offset_min_frames=0,
            offset_max_frames=0,
            first_offset_frames=0,
            last_offset_frames=0,
            largest_adjacent_jump_frames=0,
            change_position_seconds=None,
        ),
    )


def maximum_audio_attempt() -> AudioAlignmentAttempt:
    planned = 360
    lag = 1177
    subframe = lag / 8000 * 24
    return replace(
        audio_attempt(),
        analysis=AudioAnalysisFacts(
            analysis_rate=8000,
            max_offset_seconds=30.0,
            chunk_samples=240000,
            lag_samples=_LAG_SAMPLES,
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
        runs=(AudioChunkRun(first_index=0, last_index=planned - 1, lag=lag, chunk_count=planned),),
        audio=AudioStageOutcome(
            status="agreed",
            global_lag=lag,
            active_chunks=planned,
            credible_chunks=planned,
            agreeing_chunks=planned,
            compensation_seconds=0.0,
            subframe_estimate=subframe,
            rounded_frame=4,
        ),
        collection_observation="observed",
        collection=(_collection("reference"), _collection("comparison")),
        decision=AudioAlignmentDecision(
            state="provisional",
            candidate=AudioDecisionCandidate(
                frame_offset=4,
                time_offset_seconds=lag / 8000,
                subframe_estimate=subframe,
                basis="audio_only",
            ),
            primary_reason="video_check_pending",
            failed_gates=(),
        ),
        stability=AlignmentStabilitySummary(
            classification="stable",
            valid_windows=planned,
            offset_min_frames=4,
            offset_max_frames=4,
            first_offset_frames=4,
            last_offset_frames=4,
            largest_adjacent_jump_frames=0,
            change_position_seconds=None,
        ),
    )


def test_audio_attempt_rejects_invalid_or_contradictory_states() -> None:
    attempt = audio_attempt()

    with pytest.raises(ValueError, match="must be one of"):
        replace(attempt.decision, state=cast(AudioDecisionState, "invalid"))
    with pytest.raises(ValueError, match="must be one of"):
        replace(attempt, status=cast(AudioAttemptStatus, "invalid"))
    with pytest.raises(ValueError, match="lacks a candidate"):
        replace(attempt.decision, candidate=None)
    with pytest.raises(ValueError, match="share one length"):
        replace(attempt.chunks, starts=attempt.chunks.starts + (999999,))

    def columns_payload(**overrides: object) -> dict[str, Any]:
        payload = asdict(attempt.chunks)
        payload.update(overrides)
        return payload

    with pytest.raises(ValueError, match="inactive chunks cannot carry lag evidence"):
        evidence_from_payload(AudioChunkColumns, columns_payload(active=[False] * _PLANNED_CHUNKS))
    with pytest.raises(ValueError, match="agreeing chunks must be credible"):
        evidence_from_payload(
            AudioChunkColumns, columns_payload(credible=[False] * _PLANNED_CHUNKS)
        )
    for status in ("preanalysis_rejection", "aborted"):
        with pytest.raises(ValueError, match="non-complete audio attempts"):
            replace(attempt, status=status)

    unavailable = replace(attempt.decision, state="unavailable", candidate=None)
    for status in ("preanalysis_rejection", "aborted"):
        assert replace(attempt, status=status, decision=unavailable).status == status


def _facts_payload() -> dict[str, Any]:
    return {
        "role": "reference",
        "emitted_samples": 8000,
        "eof_sample": 8000,
        "elapsed_seconds": 0.25,
        "returncode": 0,
        "stderr_bytes": 44,
        "stderr_truncated": False,
        "cleanup_completed": True,
    }


def _failure_payload() -> dict[str, Any]:
    return {"category": "nonzero_exit", "side": "comparison"}


def test_collection_record_rejects_invalid_counts_and_failure_topology() -> None:
    base = evidence_from_payload(AudioCollectionFacts, _facts_payload())
    assert base.emitted_samples == 8000

    with pytest.raises(ValueError, match="unknown keys"):
        evidence_from_payload(AudioCollectionFacts, {**_facts_payload(), "failure_category": None})
    with pytest.raises(ValueError, match="must be one of"):
        evidence_from_payload(AudioCollectionFacts, {**_facts_payload(), "role": "discovery"})

    failure = evidence_from_payload(AudioCollectionFailure, _failure_payload())
    assert failure.category == "nonzero_exit"
    assert failure.side == "comparison"
    with pytest.raises(ValueError, match="must be one of"):
        evidence_from_payload(AudioCollectionFailure, {**_failure_payload(), "category": "typo"})
    with pytest.raises(ValueError, match="must be one of"):
        evidence_from_payload(AudioCollectionFailure, {**_failure_payload(), "side": "discovery"})
    assert (
        evidence_from_payload(AudioCollectionFailure, {"category": "timeout", "side": None}).side
        is None
    )
    with pytest.raises(ValueError, match="must be an integer"):
        evidence_from_payload(AudioCollectionFacts, {**_facts_payload(), "eof_sample": True})
    with pytest.raises(ValueError, match="must be a finite number"):
        evidence_from_payload(
            AudioCollectionFacts, {**_facts_payload(), "elapsed_seconds": float("inf")}
        )


def _result(attempt: AudioAlignmentAttempt, *, manual: bool = False) -> AlignmentResult:
    return AlignmentResult(
        reference_clip="reference.mkv",
        comparison_clip="comparison.mkv",
        frame_offset=0 if manual else None,
        time_offset_seconds=0.0 if manual else None,
        correlation_score=1.0,
        algorithm=None if manual else "cross_correlation",
        source="manual" if manual else "computed",
        applied=manual,
        diagnostic=None if manual else "video_check_pending",
        stability=attempt.stability,
        audio_attempt=attempt,
    )


def test_diagnostic_is_bounded_pathless_and_preserves_original_digest(tmp_path: Path) -> None:
    attempt = audio_attempt()
    diagnostics_dir = tmp_path / "alignment_diagnostics"
    path, before_digest, before_size = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=diagnostics_dir,
        comparison_ordinal=1,
        reference_label="Reference",
        comparison_label="Comparison 1",
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="pending",
        final_result=_result(attempt),
        final_origin="none",
    )
    _, after_digest, after_size = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=diagnostics_dir,
        comparison_ordinal=1,
        reference_label="Reference",
        comparison_label="Comparison 1",
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="confirmed",
        final_result=_result(attempt, manual=True),
        final_origin="interactive_confirmed_this_run",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 4
    assert before_digest == after_digest == payload["original_attempt_digest"]
    assert before_size < 128 * 1024
    assert after_size < 128 * 1024
    assert payload["review_outcome"] == "confirmed"
    assert payload["final_resolution"]["frame_offset"] == 0
    serialized = path.read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized
    assert payload["original_audio_attempt"]["ffmpeg_version"] == "not_observed"
    assert payload["original_audio_attempt"]["ffprobe_version"] == "not_observed"
    assert payload["original_audio_attempt"]["collection_observation"] == "not_observed"
    assert payload["original_audio_attempt"]["collection"] == []
    assert payload["original_audio_attempt"]["video_check"]["observation"] == "not_observed"
    assert payload["original_audio_attempt"]["extraction_recipe"] == (
        alignment_audio.normalized_extraction_recipe()
    )


def test_diagnostic_artifact_is_compact_json_with_stable_canonical_digest(
    tmp_path: Path,
) -> None:
    attempt = audio_attempt()
    path, digest, size = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=tmp_path / "alignment_diagnostics",
        comparison_ordinal=1,
        reference_label="Reference",
        comparison_label="Comparison 1",
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="not_requested",
        final_result=_result(attempt),
        final_origin="none",
    )

    content = path.read_text(encoding="utf-8")
    assert "\n" not in content
    assert ": " not in content
    assert '"schema_version":4' in content
    assert size < 128 * 1024
    assert digest == alignment_diagnostics.original_attempt_digest(attempt)
    assert (
        digest == hashlib.sha256(alignment_diagnostics.canonical_attempt_bytes(attempt)).hexdigest()
    )
    assert alignment_diagnostics.canonical_attempt_bytes(attempt) == json.dumps(
        asdict(attempt),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def test_failed_final_replacement_preserves_last_valid_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt = audio_attempt()
    diagnostics_dir = tmp_path / "alignment_diagnostics"
    path, _, _ = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=diagnostics_dir,
        comparison_ordinal=1,
        reference_label="Reference",
        comparison_label="Comparison 1",
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="pending",
        final_result=_result(attempt),
        final_origin="none",
    )
    original = path.read_bytes()
    monkeypatch.setattr(
        alignment_diagnostics,
        "write_text_atomic",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError, match="disk full"):
        alignment_diagnostics.write_alignment_diagnostic(
            generated_root=tmp_path.parent,
            diagnostics_dir=diagnostics_dir,
            comparison_ordinal=1,
            reference_label="Reference",
            comparison_label="Comparison 1",
            attempt=attempt,
            evidence_availability="current_attempt",
            review_outcome="confirmed",
            final_result=_result(attempt, manual=True),
            final_origin="interactive_confirmed_this_run",
        )

    assert path.read_bytes() == original


def test_maximum_chunked_artifact_fits_the_fixed_byte_bound(tmp_path: Path) -> None:
    base = maximum_audio_attempt()
    attempt = replace(
        base,
        authority_recount=AudioAuthorityRecount(
            raw_status="agreed",
            raw_agreeing_chunks=360,
            authority_status="agreed",
            authority_agreeing_chunks=360,
            passed=True,
        ),
        video_check=VideoCheckObservation(
            observation="observed",
            scored_offsets=(2, 3, 4, 5, 6),
            confirmed_offset=4,
            index_build_seconds=0.01,
            positions=(),
            targets=tuple(
                VideoTargetEvidence(
                    kind="chunk",
                    first_chunk_index=index,
                    last_chunk_index=index,
                    alternative_offsets=(5, 6, 7),
                    resolution="resolved",
                    positions=(VideoTargetPosition(index, index * 100, 0.1, 1.0, "confirmed"),),
                )
                for index in range(12)
            ),
            check_points=tuple(
                VideoCheckPoint(float(index), index, index + 4) for index in range(5)
            ),
        ),
    )

    path, _, size = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=tmp_path / "alignment_diagnostics",
        comparison_ordinal=1,
        reference_label="R" * 512,
        comparison_label="C" * 512,
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="not_requested",
        final_result=_result(attempt),
        final_origin="none",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert size < 128 * 1024
    assert len(payload["original_audio_attempt"]["chunks"]["starts"]) == 360
    assert len(payload["original_audio_attempt"]["collection"]) == 2
    assert len(payload["pair"]["reference_label"]) == 256
    assert len(payload["pair"]["comparison_label"]) == 256
    serialized = path.read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized


def test_symlinked_diagnostic_directory_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    diagnostics_dir = tmp_path / "alignment_diagnostics"
    try:
        diagnostics_dir.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(PathEscapesRootError):
        alignment_diagnostics.diagnostic_path(tmp_path.parent, diagnostics_dir, 1)


def test_provisional_candidate_cannot_be_constructed_as_applied_authority() -> None:
    attempt = audio_attempt()

    with pytest.raises(ValueError, match="untrusted audio evidence"):
        AlignmentResult(
            reference_clip="reference.mkv",
            comparison_clip="comparison.mkv",
            frame_offset=0,
            time_offset_seconds=0.0,
            correlation_score=1.0,
            algorithm="cross_correlation",
            source="computed",
            applied=True,
            audio_attempt=attempt,
        )
