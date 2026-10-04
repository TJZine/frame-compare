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
    MAX_ALIGNMENT_EVIDENCE_BYTES,
    AlignmentStabilitySummary,
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioChunkColumns,
    AudioChunkRun,
    AudioCollectionFacts,
    AudioDecisionCandidate,
    AudioStageOutcome,
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
from tests.alignment_review_test_support import (
    agreed_audio as _agreed_audio,
)
from tests.alignment_review_test_support import (
    agreed_columns as _agreed_columns,
)
from tests.alignment_review_test_support import (
    analysis as _analysis,
)
from tests.alignment_review_test_support import (
    audio_review as _audio_review,
)
from tests.alignment_review_test_support import (
    frame_lag as _frame_lag,
)
from tests.alignment_review_test_support import (
    stable_summary as _stable_summary,
)
from tests.alignment_review_test_support import (
    stream as _stream,
)
from tests.alignment_review_test_support import (
    subframe_estimate as _subframe_estimate,
)

_SESSION_ID = "12345678123456781234567812345678"

_REFERENCE_DIGEST = "a" * 64
_COMPARISON_DIGEST = "b" * 64
_DIAGNOSTIC_POLICY = "retained-audio-evidence-v1"
_FPS_NUM = 24
_FPS_DEN = 1
_CHUNK_SAMPLES = 40000
_LAG_SAMPLES = 240000


def _single_run(*, lag: int, chunk_count: int) -> tuple[AudioChunkRun, ...]:
    return (
        AudioChunkRun(
            first_index=0,
            last_index=chunk_count - 1,
            lag=lag,
            chunk_count=chunk_count,
        ),
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
            primary_reason="audio_only",
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
        total_samples=0,
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
        provisional_audio_attempt(chunk_count=2),
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

    parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

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

    contradictory["audio_attempt"]["video_check"]["targets"][0]["target_offset"] = 246
    contradictory["audio_attempt"]["video_check"]["targets"][0]["end_sample"] = 1
    with pytest.raises(AlignmentReviewContractError, match="end does not match its last chunk"):
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


@pytest.mark.parametrize("status", ["preanalysis_rejection", "aborted"])
def test_workspace_metadata_rejects_available_and_accepts_unavailable_noncomplete_decision(
    status: str,
) -> None:
    attempt = cast(dict[str, object], asdict(provisional_audio_attempt()))
    attempt["status"] = status
    available_review = json.dumps(
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
            (
                _reference_output(0),
                _comparison_output(1, 1, suggestion=None, audio_review=available_review),
            )
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


@pytest.mark.parametrize("old_version", [1])
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


@pytest.mark.parametrize(
    "audio_review",
    [
        '{"current_authority":{"origin":"none","origin":"none",'
        '"frame_offset":null},"evidence_availability":"not_computed",'
        '"audio_attempt":null}',
        "x" * (MAX_ALIGNMENT_EVIDENCE_BYTES + 1),
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


def test_build_audio_review_map_bounds_native_projection_for_many_chunks() -> None:
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
    assert len(review.encode("utf-8")) <= MAX_ALIGNMENT_EVIDENCE_BYTES

    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    assert parsed.chunks.rows_omitted is True
    assert parsed.chunks.starts == ()
    assert parsed.chunks.total_samples == 2160 * _CHUNK_SAMPLES
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
    assert len(review.encode("utf-8")) < MAX_ALIGNMENT_EVIDENCE_BYTES

    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    assert len(parsed.chunks.starts) == 512
    assert parsed.audio.credible_chunks == 512


@pytest.mark.parametrize(
    "outputs",
    [
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
    session = _session(tmp_path)
    result = AlignmentReviewResult(
        session_id=session.session_id,
        decisions=(
            ConfirmedAlignmentReviewDecision("ref:a", 99, 79),
            KeepCurrentAlignmentReviewDecision("ref:b"),
        ),
    )

    write_alignment_review_result(session, result)

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

    assert read_alignment_review_result(session, _expected()) == result


def test_result_write_propagates_writer_failure_without_result(
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
        raise OSError("disk full")

    monkeypatch.setattr(
        "frame_compare.vsview.alignment_review_contract.write_text_atomic", fail_write
    )

    with pytest.raises(OSError, match="disk full"):
        write_alignment_review_result(session, result)
    assert not session.result_path.exists()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("not json", id="malformed-json"),
        pytest.param(
            '{"schema_version": 1, "schema_version": 1, '
            f'"session_id": "{_SESSION_ID}", "decisions": []}}',
            id="duplicate-root-key",
        ),
        *[
            pytest.param(
                {
                    "schema_version": 1,
                    "session_id": session_id,
                    "decisions": [
                        {"comparison_key": key, "action": "keep_current"} for key in keys
                    ],
                },
                id=case,
            )
            for case, session_id, keys in [
                ("stale-session", "87654321876543218765432187654321", ("ref:a", "ref:b")),
                ("reordered", _SESSION_ID, ("ref:b", "ref:a")),
                ("duplicate-comparison", _SESSION_ID, ("ref:a", "ref:a")),
            ]
        ],
    ],
)
def test_result_rejects_malformed_or_inconsistent_payload(tmp_path: Path, payload: object) -> None:
    session = _session(tmp_path)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    session.result_path.write_text(text, encoding="utf-8")
    with pytest.raises(AlignmentReviewContractError):
        read_alignment_review_result(session, _expected())


def test_result_rejects_missing_or_directory_sibling(tmp_path: Path) -> None:
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
