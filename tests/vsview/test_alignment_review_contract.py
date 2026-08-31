from __future__ import annotations

import json
from pathlib import Path

import pytest

from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewContractError,
    AlignmentReviewExpectedComparison,
    AlignmentReviewResult,
    AlignmentReviewSession,
    ConfirmedAlignmentReviewDecision,
    KeepCurrentAlignmentReviewDecision,
    alignment_review_session_from_script,
    read_alignment_review_result,
    write_alignment_review_result,
)

_SESSION_ID = "12345678123456781234567812345678"


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
    assert json.loads(session.result_path.read_text(encoding="utf-8"))["schema_version"] == 1


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

    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    session.result_path.symlink_to(outside)
    with pytest.raises(AlignmentReviewContractError, match="regular file"):
        read_alignment_review_result(session, _expected())

    session.result_path.unlink()
    session.result_path.mkdir()
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
