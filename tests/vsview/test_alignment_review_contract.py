from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

import pytest

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
from tests.services.test_alignment_diagnostics import audio_attempt, maximum_audio_attempt

_SESSION_ID = "12345678123456781234567812345678"


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
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": asdict(audio_attempt()),
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    workspace = parse_alignment_review_workspace_metadata(
        (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
    )

    decision = workspace.comparisons[0].audio_review.audio_attempt
    assert decision is not None
    assert cast(dict[str, object], decision["decision"])["state"] == "provisional"


def test_workspace_metadata_accepts_observed_collection_facts() -> None:
    attempt = asdict(audio_attempt())
    attempt["collection_observation"] = "observed"
    attempt["collection_summaries"] = [
        {
            "phase": phase,
            "role": role,
            "output_rate": 8000,
            "requested_horizon": 8000,
            "emitted_sample_count": 8000,
            "emitted_byte_count": 32000,
            "retained_sample_count": 8000,
            "retained_byte_count": 32000,
            "status": "complete",
            "end_category": "planned_end_reached",
            "observed_eof_sample": None,
            "elapsed_seconds": 0.25,
            "cleanup_failure_count": 0,
            "failure_count": 0,
        }
        for phase, role in (
            ("discovery", "reference"),
            ("discovery", "comparison"),
            ("verification", "reference"),
            ("verification", "comparison"),
        )
    ]
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

    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    assert parsed["collection_observation"] == "observed"
    assert len(cast(list[object], parsed["collection_summaries"])) == 4


def test_workspace_metadata_accepts_signed_window_evidence() -> None:
    attempt = cast(dict[str, object], asdict(maximum_audio_attempt()))
    window = cast(list[dict[str, object]], attempt["windows"])[0]
    window["requested_sample_lag"] = -1
    window["requested_frame_candidate"] = -2
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

    parsed = workspace.comparisons[0].audio_review.audio_attempt
    assert parsed is not None
    parsed_window = cast(list[dict[str, object]], parsed["windows"])[0]
    assert parsed_window["requested_sample_lag"] == -1
    assert parsed_window["requested_frame_candidate"] == -2


def test_workspace_metadata_rejects_unobserved_collection_payload() -> None:
    attempt = asdict(audio_attempt())
    attempt["collection_summaries"] = [
        {
            "phase": "discovery",
            "role": "reference",
            "output_rate": 8000,
            "requested_horizon": 8000,
            "emitted_sample_count": 8000,
            "emitted_byte_count": 32000,
            "retained_sample_count": 8000,
            "retained_byte_count": 32000,
            "status": "complete",
            "end_category": "planned_end_reached",
            "observed_eof_sample": None,
            "elapsed_seconds": 0.25,
            "cleanup_failure_count": 0,
            "failure_count": 0,
        }
    ]
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="unobserved alignment collection"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
        )


def test_workspace_metadata_rejects_provisional_attempt_as_trusted_hint() -> None:
    payload = {
        "current_authority": {"origin": "shared_computed_offsets", "frame_offset": 0},
        "evidence_availability": "current_attempt",
        "audio_attempt": asdict(audio_attempt()),
    }
    review = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    with pytest.raises(AlignmentReviewContractError, match="untrusted audio evidence"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=0, audio_review=review))
        )


@pytest.mark.parametrize("status", ["preanalysis_rejection", "aborted"])
def test_workspace_metadata_rejects_noncomplete_available_decision(status: str) -> None:
    attempt = asdict(audio_attempt())
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

    with pytest.raises(AlignmentReviewContractError, match="non-complete alignment attempts"):
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
    assert parsed_attempt["status"] == status


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
    attempt = asdict(audio_attempt())
    decision = cast(dict[str, object], attempt["decision"])
    decision.update(
        state="unavailable",
        candidate=None,
        primary_reason="analysis_budget_exceeded",
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


@pytest.mark.parametrize("old_version", [1, 2, 99])
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
        match=rf"newly generated session.*metadata v{old_version}.*requires v3",
    ):
        parse_alignment_review_workspace_metadata((_reference_output(0), old_comparison))


def test_workspace_metadata_rejects_mixed_v1_v2_with_regeneration() -> None:
    old_reference = _reference_output(0)
    old_reference = AlignmentReviewOutputCandidate(
        output_id=0,
        source_frame_count=100,
        metadata=dict(old_reference.metadata) | {ALIGNMENT_REVIEW_METADATA_VERSION_KEY: 1},
    )

    with pytest.raises(AlignmentReviewContractError, match="metadata v1.*requires v3"):
        parse_alignment_review_workspace_metadata((_comparison_output(1, 1), old_reference))


@pytest.mark.parametrize(
    "audio_review",
    [
        '{"current_authority":{"origin":"none","origin":"none",'
        '"frame_offset":null},"evidence_availability":"not_computed",'
        '"audio_attempt":null}',
        "x" * (128 * 1024 + 1),
    ],
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
        "audio_attempt": asdict(audio_attempt()),
    }
    attempt = cast(dict[str, object], payload["audio_attempt"])
    attempt["confidence_threshold"] = float("nan")

    with pytest.raises(AlignmentReviewContractError, match="confidence_threshold"):
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


def test_workspace_metadata_accepts_maximum_bounded_audio_projection() -> None:
    attempt = asdict(maximum_audio_attempt())
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
    assert len(cast(list[object], parsed["windows"])) == 16
    assert len(cast(list[object], parsed["collection_summaries"])) == 4


@pytest.mark.parametrize(
    ("section", "field", "value", "match"),
    [
        ("attempt", "confidence_threshold", float("nan"), "confidence_threshold"),
        ("collection", "output_rate", True, "output_rate"),
        ("collection", "requested_horizon", 0, "collection bounds"),
        ("collection", "failure_count", 0, "failed collection"),
        ("collection", "cleanup_failure_count", 2, "cleanup failures"),
        ("collection", "elapsed_seconds", float("nan"), "elapsed_seconds"),
        ("window", "discovery_reference_count", -1, "discovery_reference_count"),
        ("window", "actual_coverage", True, "actual_coverage"),
        ("window", "actual_coverage", 0.5, "unobserved coverage"),
    ],
)
def test_workspace_metadata_rejects_malformed_retained_audio_facts(
    section: str, field: str, value: object, match: str
) -> None:
    attempt = cast(dict[str, object], asdict(maximum_audio_attempt()))
    if section == "attempt":
        attempt[field] = value
    elif section == "collection":
        collections = cast(list[dict[str, object]], attempt["collection_summaries"])
        collection = collections[0]
        if field == "failure_count":
            collection["status"] = "failed"
            collection["end_category"] = "not_observed"
        if field == "cleanup_failure_count":
            collection["status"] = "failed"
            collection["end_category"] = "not_observed"
            collection["failure_count"] = 1
        collection[field] = value
    else:
        windows = cast(list[dict[str, object]], attempt["windows"])
        window = windows[0]
        window[field] = value

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


def test_workspace_metadata_rejects_duplicate_collection_summaries() -> None:
    attempt = cast(dict[str, object], asdict(maximum_audio_attempt()))
    collections = cast(list[dict[str, object]], attempt["collection_summaries"])
    collections[1]["phase"] = collections[0]["phase"]
    collections[1]["role"] = collections[0]["role"]
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="duplicated"):
        parse_alignment_review_workspace_metadata(
            (_reference_output(0), _comparison_output(1, 1, suggestion=None, audio_review=review))
        )


def test_workspace_metadata_rejects_all_unobserved_coverage_facts() -> None:
    attempt = cast(dict[str, object], asdict(maximum_audio_attempt()))
    window = cast(list[dict[str, object]], attempt["windows"])[0]
    window.update(
        {
            "actual_coverage": 0.5,
            "actual_useful_reference_start": 1,
            "actual_useful_reference_end": 2,
            "pre_eof_expected_overlap": 1,
        }
    )
    review = json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "current_attempt",
            "audio_attempt": attempt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    with pytest.raises(AlignmentReviewContractError, match="unobserved coverage"):
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
