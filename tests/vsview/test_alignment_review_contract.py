from __future__ import annotations

import json
from pathlib import Path

import pytest

from frame_compare.vsview.alignment_review_contract import (
    ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
    ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
    ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
    ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
    ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
    ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
    ALIGNMENT_REVIEW_SCHEMA_VERSION,
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
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_SCHEMA_VERSION,
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
) -> AlignmentReviewOutputCandidate:
    return AlignmentReviewOutputCandidate(
        output_id=output_id,
        source_frame_count=frame_count,
        metadata={
            ALIGNMENT_REVIEW_METADATA_VERSION_KEY: ALIGNMENT_REVIEW_SCHEMA_VERSION,
            ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY: session_id,
            ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY: key,
            ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY: ordinal,
            ALIGNMENT_REVIEW_METADATA_ROLE_KEY: "comparison",
            ALIGNMENT_REVIEW_METADATA_NAME_KEY: f"Comparison {ordinal}",
            ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY: suggestion,
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
        (ALIGNMENT_REVIEW_METADATA_VERSION_KEY, 2),
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
