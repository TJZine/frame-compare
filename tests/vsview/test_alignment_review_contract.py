from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from typing import cast

import pytest

from frame_compare.services.alignment import _build_audio_review_map
from frame_compare.services.alignment_decision import ALIGNMENT_ESTIMATOR_POLICY
from frame_compare.services.types import AlignmentProvenance, AlignmentResult
from frame_compare.utils.alignment_evidence import (
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioChunkColumns,
    AudioChunkRun,
    AudioCollectionFacts,
    AudioDecisionCandidate,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
    VideoTargetEvidence,
    VideoTargetPosition,
)
from frame_compare.vsview.alignment_review_contract import (
    ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
    ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY,
    ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
    ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
    ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
    ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
    ALIGNMENT_REVIEW_METADATA_VERSION,
    ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
    ALIGNMENT_REVIEW_RESULT_VERSION,
    AlignmentReviewContractError,
    AlignmentReviewExpectedComparison,
    AlignmentReviewOutputCandidate,
    AlignmentReviewResult,
    AlignmentReviewSession,
    ConfirmedAlignmentReviewDecision,
    KeepCurrentAlignmentReviewDecision,
    alignment_review_session_from_script,
    parse_alignment_review_workspace_metadata,
    read_alignment_review_result,
    write_alignment_review_result,
)

_SESSION_ID = "12345678123456781234567812345678"

_REFERENCE_DIGEST = "a" * 64
_COMPARISON_DIGEST = "b" * 64
_DIAGNOSTIC_POLICY = "retained-audio-evidence-v1"
_FPS_NUM = 24
_FPS_DEN = 1
_CHUNK_SAMPLES = 40000
_LAG_SAMPLES = 240000
_MAX_OFFSET_SECONDS = 30.0
_AGREE_PSR = 30.0


def _frame_lag(frame_offset: int) -> int:
    """Return the exact 8 kHz lag for the whole-frame offsets used by fixtures."""
    lag = frame_offset * 8000 // _FPS_NUM
    assert lag * _FPS_NUM == frame_offset * 8000
    return lag


def _subframe_estimate(lag: int) -> float:
    return lag / 8000 * (_FPS_NUM / _FPS_DEN)


def _stream(role: str, digest: str) -> SelectedAudioStreamEvidence:
    return SelectedAudioStreamEvidence(
        role="reference" if role == "reference" else "comparison",  # type: ignore[arg-type]
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
        stream_start_basis="metadata",
        input_start_num=0,
        input_start_den=1,
        input_start_basis="metadata",
        time_base_num=1,
        time_base_den=48000,
        duration_num=120,
        duration_den=1,
        duration_basis="duration_ts",
        video_start_num=0,
        video_start_den=1,
        video_start_basis="metadata",
    )


def _analysis(*, planned_chunk_count: int) -> AudioAnalysisFacts:
    planned = planned_chunk_count > 0
    return AudioAnalysisFacts(
        analysis_rate=8000,
        max_offset_seconds=_MAX_OFFSET_SECONDS,
        chunk_samples=_CHUNK_SAMPLES if planned else 0,
        lag_samples=_LAG_SAMPLES if planned else 0,
        planned_chunk_count=planned_chunk_count,
    )


def _agreed_columns(*, lag: int, chunk_count: int) -> AudioChunkColumns:
    return AudioChunkColumns(
        starts=tuple(index * _CHUNK_SAMPLES for index in range(chunk_count)),
        counts=tuple(_CHUNK_SAMPLES for _ in range(chunk_count)),
        active=tuple(True for _ in range(chunk_count)),
        lags=tuple(lag for _ in range(chunk_count)),
        psrs=tuple(_AGREE_PSR for _ in range(chunk_count)),
        credible=tuple(True for _ in range(chunk_count)),
        agrees=tuple(True for _ in range(chunk_count)),
    )


def _single_run(*, lag: int, chunk_count: int) -> tuple[AudioChunkRun, ...]:
    return (
        AudioChunkRun(
            first_index=0,
            last_index=chunk_count - 1,
            lag=lag,
            chunk_count=chunk_count,
        ),
    )


def _agreed_audio(*, lag: int, frame_offset: int, chunk_count: int) -> AudioStageOutcome:
    return AudioStageOutcome(
        status="agreed",
        global_lag=lag,
        active_chunks=chunk_count,
        credible_chunks=chunk_count,
        agreeing_chunks=chunk_count,
        compensation_seconds=0.0,
        subframe_estimate=_subframe_estimate(lag),
        rounded_frame=frame_offset,
    )


def _stable_summary(*, frame_offset: int, chunk_count: int) -> AlignmentStabilitySummary:
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


def _insufficient_summary() -> AlignmentStabilitySummary:
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


def _unobserved_video() -> VideoCheckObservation:
    return VideoCheckObservation(
        observation="not_observed",
        scored_offsets=(),
        confirmed_offset=None,
        index_build_seconds=None,
        positions=(),
    )


def _attempt_shell(
    *,
    ordinal: int,
    status: str,
    analysis: AudioAnalysisFacts,
    chunks: AudioChunkColumns,
    runs: tuple[AudioChunkRun, ...],
    audio: AudioStageOutcome,
    decision: AudioAlignmentDecision,
    stability: AlignmentStabilitySummary,
) -> AudioAlignmentAttempt:
    return AudioAlignmentAttempt(
        reference_identity_digest=_REFERENCE_DIGEST,
        comparison_identity_digest=_COMPARISON_DIGEST,
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
            _stream("reference", _REFERENCE_DIGEST),
            _stream("comparison", _COMPARISON_DIGEST),
        ),
        analysis=analysis,
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
    lag = _frame_lag(frame_offset)
    subframe = _subframe_estimate(lag)
    assert math.floor(subframe + 0.5) == frame_offset
    return _attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis=_analysis(planned_chunk_count=chunk_count),
        chunks=_agreed_columns(lag=lag, chunk_count=chunk_count),
        runs=_single_run(lag=lag, chunk_count=chunk_count),
        audio=_agreed_audio(lag=lag, frame_offset=frame_offset, chunk_count=chunk_count),
        decision=AudioAlignmentDecision(
            state="provisional",
            candidate=AudioDecisionCandidate(
                frame_offset=frame_offset,
                time_offset_seconds=lag / 8000,
                subframe_estimate=subframe,
                basis="audio_only",
            ),
            primary_reason="video_check_pending",
            failed_gates=(),
        ),
        stability=_stable_summary(frame_offset=frame_offset, chunk_count=chunk_count),
    )


def trusted_audio_attempt(
    *, ordinal: int = 1, frame_offset: int = 0, chunk_count: int = 4
) -> AudioAlignmentAttempt:
    """Audio-plus-video confirmed attempt that may authorize an applied result."""
    lag = _frame_lag(frame_offset)
    subframe = _subframe_estimate(lag)
    assert math.floor(subframe + 0.5) == frame_offset
    return _attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis=_analysis(planned_chunk_count=chunk_count),
        chunks=_agreed_columns(lag=lag, chunk_count=chunk_count),
        runs=_single_run(lag=lag, chunk_count=chunk_count),
        audio=_agreed_audio(lag=lag, frame_offset=frame_offset, chunk_count=chunk_count),
        decision=AudioAlignmentDecision(
            state="trusted_automatic",
            candidate=AudioDecisionCandidate(
                frame_offset=frame_offset,
                time_offset_seconds=lag / 8000,
                subframe_estimate=subframe,
                basis="audio_only",
            ),
            primary_reason="audio_video_confirmed",
            failed_gates=(),
        ),
        stability=_stable_summary(frame_offset=frame_offset, chunk_count=chunk_count),
    )


def unavailable_audio_attempt(*, ordinal: int = 1) -> AudioAlignmentAttempt:
    """Two credible runs at different lags: no single offset, never applied."""
    near_lag = _frame_lag(12)
    far_lag = _frame_lag(24)
    chunk_count = 4
    return _attempt_shell(
        ordinal=ordinal,
        status="complete",
        analysis=_analysis(planned_chunk_count=chunk_count),
        chunks=AudioChunkColumns(
            starts=tuple(index * _CHUNK_SAMPLES for index in range(chunk_count)),
            counts=tuple(_CHUNK_SAMPLES for _ in range(chunk_count)),
            active=(True, True, True, True),
            lags=(near_lag, near_lag, far_lag, far_lag),
            psrs=(_AGREE_PSR, _AGREE_PSR, _AGREE_PSR, _AGREE_PSR),
            credible=(True, True, True, True),
            agrees=(True, True, False, False),
        ),
        runs=(
            AudioChunkRun(first_index=0, last_index=1, lag=near_lag, chunk_count=2),
            AudioChunkRun(first_index=2, last_index=3, lag=far_lag, chunk_count=2),
        ),
        audio=AudioStageOutcome(
            status="no_single_offset",
            global_lag=near_lag,
            active_chunks=chunk_count,
            credible_chunks=chunk_count,
            agreeing_chunks=2,
            compensation_seconds=0.0,
            subframe_estimate=_subframe_estimate(near_lag),
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


def rejected_audio_attempt(
    *,
    ordinal: int = 1,
    status: str = "preanalysis_rejection",
    reason: str = "selected_audio_timeline_unavailable",
) -> AudioAlignmentAttempt:
    """Empty-evidence refusal from before (rejection) or during (abort) collection."""
    empty = AudioChunkColumns(
        starts=(),
        counts=(),
        active=(),
        lags=(),
        psrs=(),
        credible=(),
        agrees=(),
    )
    return _attempt_shell(
        ordinal=ordinal,
        status=status,
        analysis=_analysis(planned_chunk_count=0),
        chunks=empty,
        runs=(),
        audio=AudioStageOutcome(
            status="no_usable_audio",
            global_lag=None,
            active_chunks=0,
            credible_chunks=0,
            agreeing_chunks=0,
            compensation_seconds=0.0,
            subframe_estimate=None,
            rounded_frame=None,
        ),
        decision=AudioAlignmentDecision(
            state="unavailable",
            candidate=None,
            primary_reason=reason,
            failed_gates=(reason,),
        ),
        stability=_insufficient_summary(),
    )


def _collection_facts(role: str) -> AudioCollectionFacts:
    return AudioCollectionFacts(
        role="reference" if role == "reference" else "comparison",  # type: ignore[arg-type]
        emitted_samples=8000,
        eof_sample=8000,
        elapsed_seconds=0.25,
        returncode=0,
        stderr_bytes=512,
        stderr_truncated=False,
        cleanup_completed=True,
    )


def _mutable_attempt_dict(attempt: AudioAlignmentAttempt) -> dict[str, object]:
    """Return the JSON-shape payload the contract parses (tuples become arrays)."""
    return cast(dict[str, object], json.loads(json.dumps(asdict(attempt))))


def _observed_attempt_dict() -> dict[str, object]:
    attempt = _mutable_attempt_dict(provisional_audio_attempt())
    attempt["collection_observation"] = "observed"
    attempt["collection"] = [
        asdict(_collection_facts("reference")),
        asdict(_collection_facts("comparison")),
    ]
    return attempt


def _provisional_review(*, ordinal: int = 1, frame_offset: int = 0) -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(
                provisional_audio_attempt(ordinal=ordinal, frame_offset=frame_offset)
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _audio_review(suggestion: int | None) -> str:
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


@pytest.fixture
def symlinks_supported(tmp_path: Path) -> None:
    target = tmp_path / "symlink-probe-target"
    link = tmp_path / "symlink-probe"
    target.touch()
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symbolic links unavailable: {type(exc).__name__}")
    else:
        link.unlink()


def _reference_output(
    output_id: int,
    *,
    session_id: str = _SESSION_ID,
    frame_count: int = 100,
) -> AlignmentReviewOutputCandidate:
    return AlignmentReviewOutputCandidate(
        output_id=output_id,
        source_frame_count=frame_count,
        metadata={
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_METADATA_VERSION,
            ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY: session_id,
            ALIGNMENT_REVIEW_METADATA_ROLE_KEY: "reference",
            ALIGNMENT_REVIEW_METADATA_NAME_KEY: "Reference",
        },
    )


def _comparison_output(
    output_id: int,
    ordinal: int,
    *,
    key: str = "ref:a",
    suggestion: int | None = 12,
    session_id: str = _SESSION_ID,
    frame_count: int = 100,
    audio_review: str | None = None,
) -> AlignmentReviewOutputCandidate:
    return AlignmentReviewOutputCandidate(
        output_id=output_id,
        source_frame_count=frame_count,
        metadata={
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_METADATA_VERSION,
            ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY: session_id,
            ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY: key,
            ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY: ordinal,
            ALIGNMENT_REVIEW_METADATA_ROLE_KEY: "comparison",
            ALIGNMENT_REVIEW_METADATA_NAME_KEY: f"Comparison {ordinal}",
            ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY: suggestion,
            ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY: (
                _audio_review(suggestion) if audio_review is None else audio_review
            ),
        },
    )


def test_workspace_metadata_accepts_one_reference_and_ordered_comparisons() -> None:
    workspace = parse_alignment_review_workspace_metadata(
        (
            _comparison_output(2, 2, key="ref:b", suggestion=None),
            _reference_output(0),
            _comparison_output(1, 1),
        )
    )

    assert workspace.session_id == _SESSION_ID
    assert workspace.reference.output_id == 0
    assert workspace.reference.source_frame_count == 100
    assert [comparison.comparison_key for comparison in workspace.comparisons] == [
        "ref:a",
        "ref:b",
    ]
    assert workspace.comparisons[0].comparison_key == "ref:a"
    assert workspace.comparisons[0].source_frame_count == 100


def test_workspace_metadata_accepts_provisional_attempt_without_trusted_offset() -> None:
    workspace = parse_alignment_review_workspace_metadata(
        (
            _reference_output(0),
            _comparison_output(1, 1, suggestion=None, audio_review=_provisional_review()),
        )
    )

    attempt = workspace.comparisons[0].audio_review.audio_attempt
    assert attempt is not None
    assert attempt.decision.state == "provisional"
    assert attempt.decision.candidate is not None


def test_workspace_metadata_accepts_observed_collection_facts() -> None:
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": _observed_attempt_dict(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    assert parsed.collection_observation == "observed"
    assert [fact.role for fact in parsed.collection] == ["reference", "comparison"]
    assert all(fact.cleanup_completed is True for fact in parsed.collection)
    assert parsed.collection_failure is None
    assert parsed.stability.classification == "stable"


def test_workspace_metadata_accepts_signed_chunk_evidence() -> None:
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(provisional_audio_attempt(frame_offset=-12)),
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    assert parsed.chunks.lags == (_frame_lag(-12),) * 4
    assert parsed.decision.candidate is not None
    assert parsed.decision.candidate.frame_offset == -12


def test_workspace_metadata_retains_authoritative_target_offset() -> None:
    target = VideoTargetEvidence(
        kind="chunk",
        first_chunk_index=0,
        last_chunk_index=0,
        credible=True,
        start_sample=0,
        end_sample=_CHUNK_SAMPLES,
        target_offset=246,
        alternative_offsets=(245, 246, 247),
        resolution="unresolved",
        positions=(VideoTargetPosition(0, 500, 1.0, 1.0, "neither"),),
    )
    attempt = replace(
        provisional_audio_attempt(chunk_count=1),
        video_check=VideoCheckObservation(
            observation="observed",
            scored_offsets=(144, 145, 146, 147, 148),
            confirmed_offset=146,
            index_build_seconds=0.0,
            positions=(),
            targets=(target,),
        ),
    )
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(attempt),
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    parsed_target = parsed.video_check.targets[0]
    assert parsed_target.target_offset == 246
    assert parsed_target.credible is True
    assert (parsed_target.start_sample, parsed_target.end_sample) == (0, _CHUNK_SAMPLES)
    contradictory = json.loads(review)
    contradictory["audio_attempt"]["video_check"]["targets"][0]["target_offset"] = 999999

    with pytest.raises(AlignmentReviewContractError, match="ordered target-offset neighbourhood"):
        parse_alignment_review_workspace_metadata(
            (
                _reference_output(0),
                _comparison_output(
                    1,
                    1,
                    suggestion=None,
                    audio_review=json.dumps(contradictory),
                ),
            )
        )


def test_workspace_metadata_rejects_unobserved_collection_payload() -> None:
    attempt = _observed_attempt_dict()
    attempt["collection_observation"] = "not_observed"
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="unobserved collection facts"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
        )


def test_workspace_metadata_rejects_provisional_attempt_as_trusted_hint() -> None:
    payload = {
        "current_authority": {"origin": "shared_computed_offsets", "frame_offset": 0},
        "evidence_availability": "current_attempt",
        "audio_attempt": asdict(provisional_audio_attempt(frame_offset=0)),
    }
    review = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    with pytest.raises(AlignmentReviewContractError, match="untrusted audio evidence"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=0, audio_review=review))
        )


@pytest.mark.parametrize("status", ["preanalysis_rejection", "aborted"])
def test_workspace_metadata_rejects_noncomplete_available_decision(status: str) -> None:
    attempt = cast(dict[str, object], asdict(provisional_audio_attempt()))
    attempt["status"] = status
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="non-complete audio attempts"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
        )

    decision = cast(dict[str, object], attempt["decision"])
    decision.update(state="unavailable", candidate=None)
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

    parsed_attempt = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed_attempt is not None
    assert parsed_attempt.status == status


def test_workspace_metadata_rejects_computed_authority_without_trusted_attempt() -> None:
    review = json.dumps(
        {
            "current_authority": {"origin": "computed_this_run", "frame_offset": 0},
            "evidence_availability": "historical_details_unavailable",
            "audio_attempt": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="requires its trusted attempt"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=0, audio_review=review))
        )


def test_workspace_metadata_rejects_unavailable_attempt_as_computed_authority() -> None:
    attempt = cast(dict[str, object], asdict(unavailable_audio_attempt()))
    decision = cast(dict[str, object], attempt["decision"])
    decision.update(
        state="unavailable",
        candidate=None,
        primary_reason="analysis_budget_exceeded",
        failed_gates=["analysis_budget_exceeded"],
    )
    review = json.dumps(
        {
            "current_authority": {"origin": "computed_this_run", "frame_offset": 0},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="untrusted audio evidence"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=0, audio_review=review))
        )


@pytest.mark.parametrize("old_version", [1, 2, 3, 4, 99])
def test_workspace_metadata_rejects_old_or_unknown_versions_with_regeneration(
    old_version: int,
) -> None:
    old_comparison = _comparison_output(1, 1)
    old_metadata = dict(old_comparison.metadata)
    old_metadata[ALIGNMENT_REVIEW_METADATA_VERSION_KEY] = old_version
    if old_version == 1:
        old_metadata.pop(ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY)
    old_comparison = AlignmentReviewOutputCandidate(
        output_id=1,
        source_frame_count=100,
        metadata=old_metadata,
    )

    with pytest.raises(
        AlignmentReviewContractError,
        match=rf"newly generated session.*metadata v{old_version}.*requires v5",
    ):
        parse_alignment_review_workspace_metadata((_reference_output(0), old_comparison))


def test_workspace_metadata_rejects_mixed_v1_v2_with_regeneration() -> None:
    old_reference = _reference_output(0)
    old_reference = AlignmentReviewOutputCandidate(
        output_id=0,
        source_frame_count=100,
        metadata=dict(old_reference.metadata) | {ALIGNMENT_REVIEW_METADATA_VERSION_KEY: 1},
    )

    with pytest.raises(AlignmentReviewContractError, match="metadata v1.*requires v5"):
        parse_alignment_review_workspace_metadata((_comparison_output(1, 1), old_reference))


@pytest.mark.parametrize(
    "audio_review",
    [
        '{"current_authority":{"origin":"none","origin":"none",'
        '"frame_offset":null},"evidence_availability":"not_computed",'
        '"audio_attempt":null}',
        "x" * (128 * 1024 + 1),
    ],
    ids=("duplicate-keys", "oversized"),
)
def test_workspace_metadata_rejects_duplicate_or_oversized_audio_review(
    audio_review: str,
) -> None:
    with pytest.raises(AlignmentReviewContractError):
        parse_alignment_review_workspace_metadata(
            (
                _reference_output(0),
                _comparison_output(1, 1, suggestion=None, audio_review=audio_review),
            )
        )


def test_workspace_metadata_rejects_nonfinite_or_inconsistent_attempt_evidence() -> None:
    payload = {
        "current_authority": {"origin": "none", "frame_offset": None},
        "evidence_availability": "current_attempt",
        "audio_attempt": asdict(provisional_audio_attempt()),
    }
    attempt = cast(dict[str, object], payload["audio_attempt"])
    cast(dict[str, object], attempt["audio"])["compensation_seconds"] = float("nan")

    with pytest.raises(AlignmentReviewContractError, match="compensation_seconds"):
        parse_alignment_review_workspace_metadata(
            (
                _reference_output(0),
                _comparison_output(
                    1,
                    1,
                    suggestion=None,
                    audio_review=json.dumps(payload),
                ),
            )
        )


def test_build_audio_review_map_bounds_empty_projection_for_many_chunks() -> None:
    attempt = provisional_audio_attempt(chunk_count=2160)
    reference = Path("ref.mp4")
    comparison = Path("a.mp4")
    result = AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=0.0,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        audio_attempt=attempt,
    )
    provenance = AlignmentProvenance(
        result=result,
        comparison_cache_key="ref:a",
        provenance="computed_this_run",
        evidence_availability="current_attempt",
    )
    payloads = _build_audio_review_map(
        reference=reference,
        comparisons=[comparison],
        results_map={"ref:a": result},
        provenances={"ref:a": provenance},
    )

    review = payloads["ref:a"]
    assert len(review.encode("utf-8")) <= 128 * 1024

    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )
    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    assert parsed.chunks.rows_omitted
    assert parsed.chunks.starts == ()
    assert len(parsed.runs) == 1
    assert parsed.audio.credible_chunks == 2160
    assert parsed.audio.compensation_seconds == attempt.audio.compensation_seconds
    assert parsed.audio.subframe_estimate == attempt.audio.subframe_estimate


def test_workspace_metadata_accepts_maximum_bounded_audio_projection() -> None:
    attempt = asdict(provisional_audio_attempt(chunk_count=512))
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    assert len(review.encode("utf-8")) < 128 * 1024

    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    assert len(parsed.chunks.starts) == 512
    assert parsed.audio.credible_chunks == 512


@pytest.mark.parametrize(
    ("tamper", "match"),
    [
        ("inactive_carries_lag", "inactive chunks cannot carry lag evidence"),
        ("starts_not_increasing", "chunk starts must increase"),
        ("agreeing_without_credible", "agreeing chunks must be credible"),
        ("lag_beyond_search_radius", "chunk lag exceeds the search radius"),
        ("run_exceeds_planned_chunks", "chunk run exceeds the planned chunks"),
        ("run_count_exceeds_span", "chunk run count exceeds its index span"),
        ("ragged_columns", "chunk columns must share one length"),
    ],
)
def test_workspace_metadata_rejects_inconsistent_chunk_evidence(
    tamper: str,
    match: str,
) -> None:
    attempt = _mutable_attempt_dict(provisional_audio_attempt())
    chunks = cast(dict[str, object], attempt["chunks"])
    if tamper == "inactive_carries_lag":
        cast(list[bool], chunks["active"])[0] = False
    elif tamper == "starts_not_increasing":
        cast(list[int], chunks["starts"])[1] = cast(list[int], chunks["starts"])[0]
    elif tamper == "agreeing_without_credible":
        cast(list[bool], chunks["credible"])[0] = False
        cast(list[bool], chunks["agrees"])[0] = True
    elif tamper == "lag_beyond_search_radius":
        cast(list[int], chunks["lags"])[0] = _LAG_SAMPLES + 8000
    elif tamper == "run_exceeds_planned_chunks":
        run = cast(list[dict[str, object]], attempt["runs"])[0]
        run["last_index"] = 9
        run["chunk_count"] = 10
    elif tamper == "run_count_exceeds_span":
        run = cast(list[dict[str, object]], attempt["runs"])[0]
        run["chunk_count"] = cast(int, run["last_index"]) - cast(int, run["first_index"]) + 2
    else:
        chunks["agrees"] = cast(list[bool], chunks["agrees"])[:-1]
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match=match):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
        )


@pytest.mark.parametrize(
    ("section", "field", "value", "match"),
    [
        ("analysis", "analysis_rate", 44100, "analysis rate must be 8000"),
        ("analysis", "max_offset_seconds", 0.5, "max_offset_seconds"),
        ("collection", "elapsed_seconds", -1.0, "elapsed"),
        ("collection_failure", "side", "bogus", "must be one of"),
        ("collection_failure", "category", "boom", "must be one of"),
        ("chunks", "counts", 0, "counts must be"),
        ("chunks", "psrs", float("nan"), "psrs"),
        ("audio", "compensation_seconds", float("nan"), "compensation_seconds"),
    ],
)
def test_workspace_metadata_rejects_malformed_audio_facts(
    section: str, field: str, value: object, match: str
) -> None:
    attempt = _observed_attempt_dict()
    attempt["collection_failure"] = {"category": "timeout", "side": None}
    if section == "analysis":
        cast(dict[str, object], attempt["analysis"])[field] = value
    elif section == "collection_failure":
        cast(dict[str, object], attempt["collection_failure"])[field] = value
    elif section == "collection":
        fact = cast(list[dict[str, object]], attempt["collection"])[0]
        fact[field] = value
    elif section == "chunks":
        column = cast(list[object], cast(dict[str, object], attempt["chunks"])[field])
        column[0] = value
    else:
        cast(dict[str, object], attempt["audio"])[field] = value

    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=True,
    )
    with pytest.raises(AlignmentReviewContractError, match=match):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
        )


def test_workspace_metadata_rejects_duplicate_collection_facts() -> None:
    attempt = _observed_attempt_dict()
    facts = cast(list[dict[str, object]], attempt["collection"])
    facts[1] = dict(facts[0])
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="paired sides"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
        )


def test_workspace_metadata_rejects_active_chunk_without_evidence() -> None:
    attempt = _mutable_attempt_dict(provisional_audio_attempt())
    chunks = cast(dict[str, object], attempt["chunks"])
    cast(list[object], chunks["lags"])[0] = None
    cast(list[object], chunks["psrs"])[0] = None
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="require a lag"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
        )


@pytest.mark.parametrize(
    "outputs",
    [
        (),
        (_reference_output(0),),
        (_comparison_output(1, 1),),
        (_reference_output(0), _reference_output(1), _comparison_output(2, 1)),
        (_reference_output(0), _comparison_output(1, 2)),
        (_reference_output(0), _comparison_output(1, 1), _comparison_output(2, 1)),
        (_reference_output(0), _comparison_output(0, 1)),
        (
            _reference_output(0),
            _comparison_output(1, 1),
            _comparison_output(2, 2, key="ref:a"),
        ),
        (
            _reference_output(0),
            _comparison_output(1, 1, session_id="87654321876543218765432187654321"),
        ),
    ],
)
def test_workspace_metadata_rejects_incomplete_duplicate_or_mixed_outputs(
    outputs: tuple[AlignmentReviewOutputCandidate, ...],
) -> None:
    with pytest.raises(AlignmentReviewContractError):
        parse_alignment_review_workspace_metadata(outputs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (ALIGNMENT_REVIEW_METADATA_VERSION_KEY, True),
        (ALIGNMENT_REVIEW_METADATA_VERSION_KEY, 1),
        (ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY, True),
        (ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY, True),
        (ALIGNMENT_REVIEW_METADATA_ROLE_KEY, "other"),
        (ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY, ""),
        (ALIGNMENT_REVIEW_METADATA_NAME_KEY, ""),
    ],
)
def test_workspace_metadata_rejects_malformed_values(field: str, value: object) -> None:
    comparison = _comparison_output(1, 1)
    malformed = AlignmentReviewOutputCandidate(
        output_id=comparison.output_id,
        source_frame_count=comparison.source_frame_count,
        metadata=dict(comparison.metadata) | {field: value},
    )

    with pytest.raises(AlignmentReviewContractError):
        parse_alignment_review_workspace_metadata((_reference_output(0), malformed))


@pytest.mark.parametrize(
    "candidate",
    [
        AlignmentReviewOutputCandidate(
            output_id=0,
            source_frame_count=0,
            metadata=_reference_output(0).metadata,
        ),
        AlignmentReviewOutputCandidate(
            output_id=1,
            source_frame_count=True,
            metadata=_comparison_output(1, 1).metadata,
        ),
        AlignmentReviewOutputCandidate(
            output_id=0,
            source_frame_count=100,
            metadata=dict(_reference_output(0).metadata)
            | {ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY: "ref:a"},
        ),
        AlignmentReviewOutputCandidate(
            output_id=1,
            source_frame_count=100,
            metadata={
                key: value
                for key, value in _comparison_output(1, 1).metadata.items()
                if key != ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY
            },
        ),
    ],
)
def test_workspace_metadata_rejects_invalid_bounds_and_role_specific_fields(
    candidate: AlignmentReviewOutputCandidate,
) -> None:
    other = _comparison_output(1, 1) if candidate.output_id == 0 else _reference_output(0)
    with pytest.raises(AlignmentReviewContractError):
        parse_alignment_review_workspace_metadata((other, candidate))


def _session(tmp_path: Path) -> AlignmentReviewSession:
    sessions_dir = tmp_path / "vsview_sessions"
    sessions_dir.mkdir()
    script_path = sessions_dir / f"vsview_ref_20260831T120000Z_{_SESSION_ID}.py"
    script_path.write_text("# session\n", encoding="utf-8")
    return alignment_review_session_from_script(
        script_path,
        sessions_dir=sessions_dir,
        require_result_absent=True,
    )


def _expected() -> tuple[AlignmentReviewExpectedComparison, ...]:
    return (
        AlignmentReviewExpectedComparison("ref:a", 100, 80),
        AlignmentReviewExpectedComparison("ref:b", 100, 120),
    )


def test_result_round_trip_accepts_confirmed_and_keep_current(tmp_path: Path) -> None:
    assert ALIGNMENT_REVIEW_RESULT_VERSION == 1
    session = _session(tmp_path)
    result = AlignmentReviewResult(
        session_id=session.session_id,
        decisions=(
            ConfirmedAlignmentReviewDecision("ref:a", 99, 79),
            KeepCurrentAlignmentReviewDecision("ref:b"),
        ),
    )

    write_alignment_review_result(session, result)

    assert read_alignment_review_result(session, _expected()) == result
    assert session.result_path.read_text(encoding="utf-8") == (
        "{\n"
        '  "schema_version": 1,\n'
        f'  "session_id": "{_SESSION_ID}",\n'
        '  "decisions": [\n'
        "    {\n"
        '      "comparison_key": "ref:a",\n'
        '      "action": "confirmed",\n'
        '      "reference_source_frame": 99,\n'
        '      "comparison_source_frame": 79\n'
        "    },\n"
        "    {\n"
        '      "comparison_key": "ref:b",\n'
        '      "action": "keep_current"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )


def test_result_write_is_atomic_and_propagates_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _session(tmp_path)
    result = AlignmentReviewResult(
        session_id=session.session_id,
        decisions=(KeepCurrentAlignmentReviewDecision("ref:a"),),
    )
    calls: list[Path] = []

    def fail_write(path: Path, _content: str, *, encoding: str) -> None:
        calls.append(path)
        assert encoding == "utf-8"
        raise OSError("disk full")

    monkeypatch.setattr(
        "frame_compare.vsview.alignment_review_contract.write_text_atomic", fail_write
    )

    with pytest.raises(OSError, match="disk full"):
        write_alignment_review_result(session, result)
    assert calls == [session.result_path]
    assert not session.result_path.exists()


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        '{"schema_version": 1, "schema_version": 1, '
        f'"session_id": "{_SESSION_ID}", "decisions": []}}',
        {"schema_version": 2, "session_id": _SESSION_ID, "decisions": []},
        {"schema_version": True, "session_id": _SESSION_ID, "decisions": []},
        {
            "schema_version": 1,
            "session_id": _SESSION_ID,
            "decisions": [],
            "unknown": 1,
        },
        {
            "schema_version": 1,
            "session_id": _SESSION_ID,
            "decisions": [{"comparison_key": "ref:a", "action": "other"}],
        },
        {
            "schema_version": 1,
            "session_id": _SESSION_ID,
            "decisions": [{"comparison_key": "", "action": "keep_current"}],
        },
        {
            "schema_version": 1,
            "session_id": _SESSION_ID,
            "decisions": [
                {
                    "comparison_key": "ref:a",
                    "action": "confirmed",
                    "reference_source_frame": True,
                    "comparison_source_frame": 0,
                }
            ],
        },
        {
            "schema_version": 1,
            "session_id": _SESSION_ID,
            "decisions": [
                {
                    "comparison_key": "ref:a",
                    "action": "keep_current",
                    "unexpected": 1,
                }
            ],
        },
    ],
)
def test_result_rejects_malformed_json_and_schema(tmp_path: Path, payload: object) -> None:
    session = _session(tmp_path)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    session.result_path.write_text(text, encoding="utf-8")

    with pytest.raises(AlignmentReviewContractError):
        read_alignment_review_result(session, _expected())


@pytest.mark.parametrize(
    "session_id,decisions",
    [
        ("87654321876543218765432187654321", [("ref:a", "keep"), ("ref:b", "keep")]),
        (_SESSION_ID, [("ref:a", "keep")]),
        (_SESSION_ID, [("ref:a", "keep"), ("ref:b", "keep"), ("ref:c", "keep")]),
        (_SESSION_ID, [("ref:b", "keep"), ("ref:a", "keep")]),
        (_SESSION_ID, [("ref:a", "keep"), ("ref:a", "keep")]),
    ],
)
def test_result_rejects_stale_incomplete_extra_reordered_or_duplicate_keys(
    tmp_path: Path,
    session_id: str,
    decisions: list[tuple[str, str]],
) -> None:
    session = _session(tmp_path)
    payload = {
        "schema_version": 1,
        "session_id": session_id,
        "decisions": [
            {"comparison_key": comparison_key, "action": "keep_current"}
            for comparison_key, _action in decisions
        ],
    }
    session.result_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AlignmentReviewContractError):
        read_alignment_review_result(session, _expected())


@pytest.mark.parametrize(
    "reference_frame,comparison_frame",
    [(-1, 0), (0, -1), (100, 0), (0, 80)],
)
def test_result_rejects_negative_or_out_of_bounds_frames(
    tmp_path: Path, reference_frame: int, comparison_frame: int
) -> None:
    session = _session(tmp_path)
    payload = {
        "schema_version": 1,
        "session_id": _SESSION_ID,
        "decisions": [
            {
                "comparison_key": "ref:a",
                "action": "confirmed",
                "reference_source_frame": reference_frame,
                "comparison_source_frame": comparison_frame,
            },
            {"comparison_key": "ref:b", "action": "keep_current"},
        ],
    }
    session.result_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AlignmentReviewContractError):
        read_alignment_review_result(session, _expected())


def test_result_requires_exact_regular_sibling(tmp_path: Path) -> None:
    session = _session(tmp_path)
    with pytest.raises(AlignmentReviewContractError, match="missing"):
        read_alignment_review_result(session, _expected())

    session.result_path.mkdir()
    with pytest.raises(AlignmentReviewContractError, match="regular file"):
        read_alignment_review_result(session, _expected())


def test_result_rejects_symlink_sibling(tmp_path: Path, symlinks_supported: None) -> None:
    session = _session(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    session.result_path.symlink_to(outside)

    with pytest.raises(AlignmentReviewContractError, match="regular file"):
        read_alignment_review_result(session, _expected())


def test_session_requires_owned_regular_uuid_named_script(tmp_path: Path) -> None:
    sessions_dir = tmp_path / "vsview_sessions"
    sessions_dir.mkdir()
    outside = tmp_path / f"vsview_ref_20260831T120000Z_{_SESSION_ID}.py"
    outside.write_text("# session", encoding="utf-8")

    with pytest.raises(AlignmentReviewContractError, match="outside"):
        alignment_review_session_from_script(outside, sessions_dir=sessions_dir)

    invalid = sessions_dir / "vsview_ref_without_uuid.py"
    invalid.write_text("# session", encoding="utf-8")
    with pytest.raises(AlignmentReviewContractError, match="identifier"):
        alignment_review_session_from_script(invalid, sessions_dir=sessions_dir)


def test_session_rejects_symlinked_script(tmp_path: Path, symlinks_supported: None) -> None:
    sessions_dir = tmp_path / "vsview_sessions"
    sessions_dir.mkdir()
    outside = tmp_path / f"vsview_ref_20260831T120000Z_{_SESSION_ID}.py"
    outside.write_text("# session", encoding="utf-8")
    linked = sessions_dir / f"vsview_ref_20260831T120000Z_{_SESSION_ID}.py"
    linked.symlink_to(outside)

    with pytest.raises(AlignmentReviewContractError, match="regular file"):
        alignment_review_session_from_script(linked, sessions_dir=sessions_dir)


def test_session_rejects_preexisting_result(tmp_path: Path) -> None:
    session = _session(tmp_path)
    session.result_path.write_text("{}", encoding="utf-8")

    with pytest.raises(AlignmentReviewContractError, match="already exists"):
        alignment_review_session_from_script(
            session.script_path,
            sessions_dir=session.sessions_dir,
            require_result_absent=True,
        )
