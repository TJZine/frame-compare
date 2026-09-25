"""Native VSView alignment-review service contract tests."""

from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.alignment_manual_overrides import load_manual_overrides
from frame_compare.services.alignment_vsview import (
    AlignmentVSViewOutcome,
    maybe_launch_alignment_vsview,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentReviewSummary
from frame_compare.utils.types import AlignmentClipIdentity, AlignmentClipRequest
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewResult,
    ConfirmedAlignmentReviewDecision,
    KeepCurrentAlignmentReviewDecision,
    write_alignment_review_result,
)
from frame_compare.vsview.errors import VSViewError
from tests.services.alignment_request_test_support import (
    VSVIEW_SESSION_ID as _SESSION_ID,
)
from tests.services.alignment_request_test_support import alignment_request
from tests.services.alignment_request_test_support import (
    vsview_session as _session,
)
from tests.services.test_alignment_diagnostics import audio_attempt


def _clip(path: Path, *, frame_count: int = 200) -> AlignmentClipRequest:
    return AlignmentClipRequest(
        path=path,
        label=path.stem,
        identity=AlignmentClipIdentity(path=path, size_bytes=1, mtime_ns=1),
        trim_start_frames=0,
        trim_end_frame_inclusive=None,
        effective_fps_num=24,
        effective_fps_den=1,
        source_frame_count=frame_count,
        presentation_name=path.stem.title(),
    )


def _available() -> VSViewAvailability:
    return VSViewAvailability(
        status=VSViewAvailabilityStatus.AVAILABLE,
        message="available",
    )


def _set_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=True, stdout=True, stderr=True),
    )
    monkeypatch.setattr(alignment_vsview, "check_vsview_availability", _available)


def _call(
    tmp_path: Path,
    *,
    config: AlignmentConfig,
    comparisons: list[AlignmentClipRequest] | None = None,
    review_summary: AlignmentReviewSummary | None = None,
) -> AlignmentVSViewOutcome:
    reference = _clip(tmp_path / "ref.mkv")
    resolved_comparisons = comparisons or [_clip(tmp_path / "comparison.mkv", frame_count=150)]
    offsets = {f"ref:{comparison.path.stem}": 3 for comparison in resolved_comparisons}
    return maybe_launch_alignment_vsview(
        reference=reference,
        comparisons=resolved_comparisons,
        offsets_by_key=offsets,
        audio_review_by_key={
            key: json.dumps(
                {
                    "current_authority": {
                        "origin": "shared_computed_offsets",
                        "frame_offset": offset,
                    },
                    "evidence_availability": "historical_details_unavailable",
                    "audio_attempt": None,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            for key, offset in offsets.items()
        },
        cache_dir=tmp_path,
        config=config,
        progress=None,
        review_summary=review_summary,
    )


def test_disabled_review_has_no_runtime_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = MagicMock(side_effect=AssertionError("disabled review must not probe"))
    monkeypatch.setattr(alignment_vsview, "check_vsview_availability", probe)

    assert _call(tmp_path, config=AlignmentConfig()) == AlignmentVSViewOutcome(
        None, "not_requested"
    )


def test_native_result_confirms_and_keeps_in_request_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    comparisons = [
        _clip(tmp_path / "first.mkv", frame_count=150),
        _clip(tmp_path / "second.mkv", frame_count=120),
    ]

    def launch(*_args: object, **_kwargs: object):
        session = _session(tmp_path)
        write_alignment_review_result(
            session,
            AlignmentReviewResult(
                session_id=session.session_id,
                decisions=(
                    ConfirmedAlignmentReviewDecision("ref:first", 120, 108),
                    KeepCurrentAlignmentReviewDecision("ref:second"),
                ),
            ),
        )
        return session, 0.0

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    result = _call(
        tmp_path,
        config=AlignmentConfig(use_vsview=True),
        comparisons=comparisons,
    )

    assert result == AlignmentVSViewOutcome(
        {"ref:first": 12},
        "confirmed",
        (("ref:first", 120, 108),),
    )
    overrides = load_manual_overrides(tmp_path)
    assert set(overrides) == {"ref:first"}
    assert overrides["ref:first"].frame_offset == 12


def test_keep_current_only_is_a_successful_empty_override_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)

    def launch(*_args: object, **_kwargs: object):
        session = _session(tmp_path)
        write_alignment_review_result(
            session,
            AlignmentReviewResult(
                session_id=session.session_id,
                decisions=(KeepCurrentAlignmentReviewDecision("ref:comparison"),),
            ),
        )
        return session, 0.0

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    assert _call(tmp_path, config=AlignmentConfig(use_vsview=True)) == AlignmentVSViewOutcome(
        {}, "keep_current"
    )
    assert load_manual_overrides(tmp_path) == {}


@pytest.mark.parametrize("wait_seconds", [42.5, 0.0])
def test_launch_wait_seconds_reach_review_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wait_seconds: float
) -> None:
    _set_interactive(monkeypatch)

    def launch(*_args: object, **_kwargs: object):
        session = _session(tmp_path)
        write_alignment_review_result(
            session,
            AlignmentReviewResult(
                session_id=session.session_id,
                decisions=(KeepCurrentAlignmentReviewDecision("ref:comparison"),),
            ),
        )
        return session, wait_seconds

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)
    summary = AlignmentReviewSummary()

    assert _call(
        tmp_path, config=AlignmentConfig(use_vsview=True), review_summary=summary
    ) == AlignmentVSViewOutcome({}, "keep_current")
    assert summary.review_ran is True
    assert summary.review_seconds == pytest.approx(wait_seconds)


def test_rejected_result_still_records_measured_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        lambda *_args, **_kwargs: (_session(tmp_path), 25.0),
    )
    summary = AlignmentReviewSummary()

    assert _call(
        tmp_path, config=AlignmentConfig(use_vsview=True), review_summary=summary
    ) == AlignmentVSViewOutcome(None, "rejected_result")
    assert summary.review_ran is False
    assert summary.review_seconds == pytest.approx(25.0)


def test_failed_launch_leaves_review_summary_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)

    def launch(*_args: object, **_kwargs: object):
        raise VSViewError("launcher command was not found")

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)
    summary = AlignmentReviewSummary()

    assert _call(
        tmp_path, config=AlignmentConfig(use_vsview=True), review_summary=summary
    ) == AlignmentVSViewOutcome(None, "no_result")
    assert summary.review_ran is False
    assert summary.review_seconds == 0.0


def test_disabled_launch_leaves_review_summary_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(alignment_vsview, "check_vsview_availability", _available)
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=False, stdout=True, stderr=False),
    )
    summary = AlignmentReviewSummary()

    assert _call(
        tmp_path, config=AlignmentConfig(use_vsview=True), review_summary=summary
    ) == AlignmentVSViewOutcome(None, "no_result")
    assert summary.review_ran is False
    assert summary.review_seconds == 0.0


def test_pending_review_without_launch_marks_review_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        lambda: VSViewAvailability(
            status=VSViewAvailabilityStatus.MISSING_RUNTIME, message="missing"
        ),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=False, stdout=True, stderr=False),
    )
    attempt = audio_attempt()
    consensus = AlignmentConsensus(
        None,
        0.99,
        False,
        "insufficient_consensus",
        5,
        4,
        0.8,
        2.0,
        window_records=attempt.windows,
        decision=attempt.decision,
        audio_attempt=attempt,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: consensus,
    )
    config = AlignmentConfig(cache_results=False, no_color=True, use_vsview=True)
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    summary = AlignmentReviewSummary()

    asyncio.run(
        align_clips_from_request(
            request,
            config,
            reference_fps=Fraction(24),
            review_summary=summary,
        )
    )

    assert summary.review_ran is False
    assert summary.review_unresolved is True


@pytest.mark.parametrize(
    "payload",
    [
        "{not json",
        json.dumps(
            {
                "schema_version": 1,
                "session_id": "f" * 32,
                "decisions": [{"comparison_key": "ref:comparison", "action": "keep_current"}],
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "session_id": _SESSION_ID,
                "decisions": [],
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "session_id": _SESSION_ID,
                "decisions": [
                    {
                        "comparison_key": "ref:comparison",
                        "action": "confirmed",
                        "reference_source_frame": 200,
                        "comparison_source_frame": 0,
                    }
                ],
            }
        ),
    ],
    ids=("malformed", "stale-session", "partial", "out-of-bounds"),
)
def test_optional_invalid_result_fails_closed_and_retains_offsets(
    payload: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_interactive(monkeypatch)

    def launch(*_args: object, **_kwargs: object):
        session = _session(tmp_path)
        session.result_path.write_text(payload, encoding="utf-8")
        return session, 0.0

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    assert _call(tmp_path, config=AlignmentConfig(use_vsview=True)) == AlignmentVSViewOutcome(
        None, "rejected_result"
    )
    assert load_manual_overrides(tmp_path) == {}


def test_close_without_finish_is_optional_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        lambda *_args, **_kwargs: (_session(tmp_path), 0.0),
    )

    assert _call(tmp_path, config=AlignmentConfig(use_vsview=True)) == AlignmentVSViewOutcome(
        None, "rejected_result"
    )


def test_forced_close_without_finish_is_typed_alignment_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        lambda *_args, **_kwargs: (_session(tmp_path), 0.0),
    )

    with pytest.raises(AudioAlignmentError, match="did not return a valid VSView review result"):
        _call(
            tmp_path,
            config=AlignmentConfig(use_vsview=True, force_interactive=True),
        )


def test_result_bounds_come_from_typed_request_not_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    comparison = _clip(tmp_path / "comparison.mkv", frame_count=10)

    def launch(*_args: object, **_kwargs: object):
        session = _session(tmp_path)
        session.result_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "session_id": session.session_id,
                    "decisions": [
                        {
                            "comparison_key": "ref:comparison",
                            "action": "confirmed",
                            "reference_source_frame": 5,
                            "comparison_source_frame": 10,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return session, 0.0

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    assert _call(
        tmp_path,
        config=AlignmentConfig(use_vsview=True),
        comparisons=[comparison],
    ) == AlignmentVSViewOutcome(
        None,
        "rejected_result",
    )


def test_non_tty_optional_generates_but_does_not_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(alignment_vsview, "check_vsview_availability", _available)
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=False, stdout=True, stderr=False),
    )
    session = _session(tmp_path)
    launch = MagicMock(return_value=(session, 0.0))
    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    assert _call(tmp_path, config=AlignmentConfig(use_vsview=True)) == AlignmentVSViewOutcome(
        None, "no_result"
    )
    assert launch.call_args.kwargs["config"].enabled is False


def test_non_tty_forced_review_fails_before_session_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(alignment_vsview, "check_vsview_availability", _available)
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=False, stdout=True, stderr=False),
    )
    launch = MagicMock()
    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    with pytest.raises(AudioAlignmentError, match="no interactive terminal"):
        _call(
            tmp_path,
            config=AlignmentConfig(use_vsview=True, force_interactive=True),
        )
    launch.assert_not_called()


@pytest.mark.parametrize(
    "status",
    [VSViewAvailabilityStatus.MISSING_RUNTIME, VSViewAvailabilityStatus.MISSING_PLUGIN],
)
def test_forced_review_requires_complete_same_environment_runtime(
    status: VSViewAvailabilityStatus,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        lambda: VSViewAvailability(status=status, message="missing"),
    )

    with pytest.raises(AudioAlignmentError, match="this Python environment"):
        _call(
            tmp_path,
            config=AlignmentConfig(use_vsview=True, force_interactive=True),
        )


def test_optional_process_failure_retains_offsets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSViewError("launch exited with code 7")),
    )

    assert _call(tmp_path, config=AlignmentConfig(use_vsview=True)) == AlignmentVSViewOutcome(
        None, "no_result"
    )


def test_optional_session_setup_failure_retains_offsets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(
            side_effect=VSViewError("VSView session setup failed (AlignmentReviewContractError)")
        ),
    )

    assert _call(tmp_path, config=AlignmentConfig(use_vsview=True)) == AlignmentVSViewOutcome(
        None, "no_result"
    )
    assert load_manual_overrides(tmp_path) == {}


def test_forced_process_failure_propagates_typed_vsview_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSViewError("launch exited with code 7")),
    )

    with pytest.raises(VSViewError, match="launch exited with code 7"):
        _call(
            tmp_path,
            config=AlignmentConfig(use_vsview=True, force_interactive=True),
        )


def test_native_review_never_reads_terminal_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)

    class _NoRead:
        def readline(self) -> str:
            raise AssertionError("native review must not read stdin")

    monkeypatch.setattr(alignment_vsview.sys, "stdin", _NoRead())

    def launch(*_args: object, **_kwargs: object):
        session = _session(tmp_path)
        write_alignment_review_result(
            session,
            AlignmentReviewResult(
                session_id=session.session_id,
                decisions=(KeepCurrentAlignmentReviewDecision("ref:comparison"),),
            ),
        )
        return session, 0.0

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    assert _call(tmp_path, config=AlignmentConfig(use_vsview=True)) == AlignmentVSViewOutcome(
        {}, "keep_current"
    )


def test_progress_is_resumed_after_review_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)
    progress = MagicMock()
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSViewError("failed")),
    )
    reference = _clip(tmp_path / "ref.mkv")
    comparison = _clip(tmp_path / "comparison.mkv")

    maybe_launch_alignment_vsview(
        reference=reference,
        comparisons=[comparison],
        offsets_by_key={"ref:comparison": 0},
        audio_review_by_key={
            "ref:comparison": json.dumps(
                {
                    "current_authority": {
                        "origin": "shared_computed_offsets",
                        "frame_offset": 0,
                    },
                    "evidence_availability": "historical_details_unavailable",
                    "audio_attempt": None,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        },
        cache_dir=tmp_path,
        config=AlignmentConfig(use_vsview=True),
        progress=progress,
    )

    progress.suspend.assert_called_once_with()
    progress.resume.assert_called_once_with()
