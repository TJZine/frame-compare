from __future__ import annotations

import json
from pathlib import Path

import pytest

from frame_compare.vsview.alignment_review_contract import (
    ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
    ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY,
    ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
    ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
    ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
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
from tests.alignment_review_test_support import audio_review as _audio_review

_SESSION_ID = "12345678123456781234567812345678"


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
    authority_offset: int | None = 12,
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
            ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY: (
                _audio_review(authority_offset) if audio_review is None else audio_review
            ),
        },
    )


def test_workspace_metadata_accepts_one_reference_and_ordered_comparisons() -> None:
    workspace = parse_alignment_review_workspace_metadata(
        (
            _comparison_output(2, 2, key="ref:b", authority_offset=None),
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
        match=rf"newly generated session.*metadata v{old_version}.*requires v6",
    ):
        parse_alignment_review_workspace_metadata((_reference_output(0), old_comparison))


def test_workspace_metadata_rejects_malformed_audio_review_json() -> None:
    with pytest.raises(
        AlignmentReviewContractError, match="alignment review audio evidence is invalid"
    ) as exc_info:
        parse_alignment_review_workspace_metadata(
            (
                _reference_output(0),
                _comparison_output(1, 1, audio_review='{"current_authority":'),
            )
        )
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


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
    return alignment_review_session_from_script(script_path)


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
    with pytest.raises(AlignmentReviewContractError, match="unreadable"):
        read_alignment_review_result(session, _expected())


def test_session_rejects_script_filename_without_uuid(tmp_path: Path) -> None:
    invalid = tmp_path / "vsview_ref_without_uuid.py"
    invalid.write_text("# session", encoding="utf-8")
    with pytest.raises(AlignmentReviewContractError, match="identifier"):
        alignment_review_session_from_script(invalid)


@pytest.mark.parametrize(
    "content", [pytest.param("[" * 10000, id="deep"), pytest.param("1" * 5000, id="integer-limit")]
)
def test_result_decode_limits_are_unreadable(tmp_path: Path, content: str) -> None:
    session = _session(tmp_path)
    session.result_path.write_text(content, encoding="utf-8")
    with pytest.raises(AlignmentReviewContractError, match="result is unreadable"):
        read_alignment_review_result(session, _expected())
