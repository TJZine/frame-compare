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
from frame_compare.services.alignment import _build_audio_review_map
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.types import AlignmentProvenance, AlignmentResult
from frame_compare.utils.alignment_evidence import (
    MAX_ALIGNMENT_EVIDENCE_BYTES,
    MAX_AUDIO_CHUNKS,
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioAttemptStatus,
    AudioChunkColumns,
    AudioChunkRun,
    AudioCollectionFacts,
    AudioCollectionFailure,
    AudioDecisionCandidate,
    AudioDecisionState,
    AudioSameFrameContext,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
    VideoTargetEvidence,
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
            total_samples=_PLANNED_CHUNKS * _CHUNK_SAMPLES,
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
            primary_reason="audio_only",
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
            total_samples=planned * 240000,
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
            primary_reason="audio_only",
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
        diagnostic=None if manual else "audio_only",
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
    assert before_size < MAX_ALIGNMENT_EVIDENCE_BYTES
    assert after_size < MAX_ALIGNMENT_EVIDENCE_BYTES
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
    assert size < MAX_ALIGNMENT_EVIDENCE_BYTES
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


def _maximum_shape_attempt(shape: str) -> tuple[AudioAlignmentAttempt, tuple[int, int, int]]:
    base = maximum_audio_attempt()
    count = MAX_AUDIO_CHUNKS
    if shape in {"same-frame", "mixed"}:
        same_frame_count = count if shape == "same-frame" else count // 2
    else:
        same_frame_count = 0
    target_count = count // 2 if shape in {"run-targets", "mixed"} else 0
    if shape == "runs":
        run_lags = tuple(((index * 7919) % 478_001) - 239_000 for index in range(count // 2))
        lags = tuple(lag for run_lag in run_lags for lag in (run_lag, run_lag))
    elif shape == "run-targets":
        lags = tuple(
            lag for index in range(count // 2) for lag in (round((2 + index % 7) * 8000 / 24),) * 2
        )
    else:
        lags = tuple(
            (index % 201) - 100 if index < same_frame_count else round((2 + index % 7) * 8000 / 24)
            for index in range(count)
        )
    psrs = tuple(25.125 + (index * 8191 % 100_000) / 97 for index in range(count))
    chunks = AudioChunkColumns(
        starts=tuple(index * 240_000 for index in range(count)),
        counts=(240_000,) * count,
        active=(True,) * count,
        lags=lags,
        psrs=psrs,
        credible=(True,) * count,
        agrees=(False,) * count,
        total_samples=count * 240_000,
    )
    runs = (
        tuple(AudioChunkRun(index, index + 1, lags[index], 2) for index in range(0, count, 2))
        if shape != "mixed"
        else tuple(
            AudioChunkRun(index, index + 1, lags[index], 2)
            for index in range(0, same_frame_count, 2)
        )
        + tuple(
            AudioChunkRun(index, index, lags[index], 1) for index in range(same_frame_count, count)
        )
    )
    targets = tuple(
        VideoTargetEvidence(
            kind="run" if shape == "run-targets" else "chunk",
            first_chunk_index=(index * 2 if shape == "run-targets" else same_frame_count + index),
            last_chunk_index=(
                index * 2 + 1 if shape == "run-targets" else same_frame_count + index
            ),
            credible=True,
            start_sample=(index * 2 if shape == "run-targets" else same_frame_count + index)
            * 240_000,
            end_sample=(index * 2 + 2 if shape == "run-targets" else same_frame_count + index + 1)
            * 240_000,
            target_offset=2 + index % 7,
            alternative_offsets=tuple(range(1 + index % 7, 4 + index % 7)),
            resolution="unexamined",
            positions=(),
        )
        for index in range(target_count)
    )
    video = (
        _not_observed_video()
        if shape == "runs"
        else VideoCheckObservation(
            observation="observed",
            scored_offsets=(-2, -1, 0, 1, 2),
            confirmed_offset=0,
            index_build_seconds=0.01,
            positions=(),
            targets=targets,
            same_frame_context=tuple(
                AudioSameFrameContext(index, lags[index], lags[index] / 8000 * 24, 0)
                for index in range(same_frame_count)
            ),
        )
    )
    attempt = replace(
        base,
        analysis=replace(base.analysis, planned_chunk_count=count),
        chunks=chunks,
        runs=runs,
        audio=replace(
            base.audio,
            status="no_single_offset",
            active_chunks=count,
            credible_chunks=count,
            agreeing_chunks=0,
        ),
        video_check=video,
        stability=replace(base.stability, valid_windows=count),
    )
    return attempt, (len(runs), len(video.same_frame_context), len(video.targets))


@pytest.mark.parametrize("shape", ("runs", "same-frame", "run-targets", "mixed"))
def test_maximum_evidence_shapes_fit_full_and_native_envelopes(tmp_path: Path, shape: str) -> None:
    attempt, populations = _maximum_shape_attempt(shape)
    result = _result(attempt)

    path, _, diagnostic_size = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=tmp_path / "alignment_diagnostics",
        comparison_ordinal=1,
        reference_label="Reference",
        comparison_label="Comparison",
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="not_requested",
        final_result=result,
        final_origin="none",
    )
    diagnostic_payload = json.loads(path.read_text(encoding="utf-8"))
    assert diagnostic_size <= MAX_ALIGNMENT_EVIDENCE_BYTES, (shape, populations, diagnostic_size)
    assert (
        evidence_from_payload(AudioAlignmentAttempt, diagnostic_payload["original_audio_attempt"])
        == attempt
    )

    reference = Path("reference.mkv")
    comparison = Path("comparison.mkv")
    key = alignment_key(reference, comparison)
    native = _build_audio_review_map(
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
    )[key]
    native_size = len(native.encode("utf-8"))
    assert native_size <= MAX_ALIGNMENT_EVIDENCE_BYTES, (shape, populations, native_size)
    projected = json.loads(native)["audio_attempt"]
    assert evidence_from_payload(AudioAlignmentAttempt, projected) == replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            starts=(),
            counts=(),
            active=(),
            lags=(),
            psrs=(),
            credible=(),
            agrees=(),
            rows_omitted=True,
        ),
    )


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
