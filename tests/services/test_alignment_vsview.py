"""Native VSView alignment-review service contract tests."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.services.alignment import _build_audio_review_map, align_clips_from_request
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_vsview import (
    AlignmentVSViewOutcome,
    maybe_launch_alignment_vsview,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult, ComparisonResolution
from frame_compare.utils.types import AlignmentClipIdentity, AlignmentClipRequest
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewResult,
    ConfirmedAlignmentReviewDecision,
    KeepCurrentAlignmentReviewDecision,
    write_alignment_review_result,
)
from frame_compare.vsview.errors import VSViewError
from tests.alignment_review_test_support import trusted_audio_attempt
from tests.services.alignment_request_test_support import (
    VSVIEW_SESSION_ID as _SESSION_ID,
)
from tests.services.alignment_request_test_support import alignment_request
from tests.services.alignment_request_test_support import (
    vsview_session as _session,
)
from tests.services.test_alignment_diagnostics import audio_attempt


def _clip(path: Path, *, frame_count: int = 200) -> AlignmentClipRequest:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    stat = path.stat()
    return AlignmentClipRequest(
        path=path,
        label=path.stem,
        identity=AlignmentClipIdentity(
            path=path, size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns
        ),
        trim_start_frames=0,
        trim_end_frame_inclusive=None,
        effective_fps_num=24,
        effective_fps_den=1,
        source_fps_num=24,
        source_fps_den=1,
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


def _cached_resolution(reference: Path, comparison: Path) -> ComparisonResolution:
    return ComparisonResolution(
        AlignmentResult(
            reference.name, comparison.name, 3, 3 / 24, 1.0, "cross_correlation", "cached"
        ),
        "fixture",
        "shared_computed_offsets",
    )


def _call(
    tmp_path: Path,
    *,
    config: AlignmentConfig,
    comparisons: list[AlignmentClipRequest] | None = None,
) -> AlignmentVSViewOutcome:
    reference = _clip(tmp_path / "ref.mkv")
    resolved_comparisons = comparisons or [_clip(tmp_path / "comparison.mkv", frame_count=150)]
    paths = [comparison.path for comparison in resolved_comparisons]
    return maybe_launch_alignment_vsview(
        reference=reference,
        comparisons=resolved_comparisons,
        audio_review_by_key=_build_audio_review_map(
            reference=reference.path,
            comparisons=paths,
            resolutions={
                alignment_key(reference.path, path): _cached_resolution(reference.path, path)
                for path in paths
            },
        ),
        cache_dir=tmp_path,
        config=config,
        progress=None,
    )


def test_audio_review_envelopes_distinguish_current_attempt_and_reused_offset() -> None:
    reference = Path("ref")
    fresh = Path("fresh")
    reused = Path("reused")
    attempt = audio_attempt()
    fresh_result = AlignmentResult(
        reference.name,
        fresh.name,
        None,
        None,
        0.0,
        "cross_correlation",
        "computed",
        applied=False,
        audio_attempt=attempt,
    )
    fresh_key = alignment_key(reference, fresh)
    reused_key = alignment_key(reference, reused)
    reviews = _build_audio_review_map(
        reference=reference,
        comparisons=[fresh, reused],
        resolutions={
            fresh_key: ComparisonResolution(fresh_result, "fixture", "computed_this_run"),
            reused_key: _cached_resolution(reference, reused),
        },
    )

    assert set(reviews) == {fresh_key, reused_key}
    current = json.loads(reviews[fresh_key])
    historical = json.loads(reviews[reused_key])
    assert (
        set(current)
        == set(historical)
        == {
            "current_authority",
            "decision_state",
            "candidate_offset",
            "summary_lines",
            "detail_lines",
        }
    )
    assert current["current_authority"] == {"origin": "none", "frame_offset": None}
    assert current["decision_state"] == "provisional"
    assert current["candidate_offset"] == 0
    assert historical["current_authority"] == {
        "origin": "shared_computed_offsets",
        "frame_offset": 3,
    }
    assert historical["decision_state"] is None
    assert historical["candidate_offset"] is None
    assert historical["detail_lines"] == ["Historical audio details unavailable."]


def test_disabled_review_has_no_runtime_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    probe = MagicMock(side_effect=AssertionError("disabled review must not probe"))
    monkeypatch.setattr(alignment_vsview, "check_vsview_availability", probe)

    assert _call(tmp_path, config=AlignmentConfig()) == AlignmentVSViewOutcome(
        None, "not_requested"
    )


def test_native_result_applies_confirmed_pair_and_keeps_other_pair(
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

    reference = _clip(tmp_path / "ref.mkv")
    request = replace(
        alignment_request(
            reference=reference.path,
            comparisons=[comparison.path for comparison in comparisons],
            generated_dir=tmp_path,
        ),
        reference=reference,
        comparisons=comparisons,
    )
    attempt = trusted_audio_attempt(frame_offset=3)

    def compute(reference: Path, comparison: Path, **_kwargs: object) -> AlignmentResult:
        return AlignmentResult(
            reference.name,
            comparison.name,
            3,
            3 / 24,
            1.0,
            "cross_correlation",
            "computed",
            stability=attempt.stability,
            audio_attempt=attempt,
        )

    monkeypatch.setattr("frame_compare.services.alignment._estimate_audio_pair", compute)
    outcome = asyncio.run(
        align_clips_from_request(request, AlignmentConfig(use_vsview=True, cache_results=False))
    )

    assert outcome.review.review_ran is True
    assert outcome.review.pairs_confirmed == 1
    assert outcome.review.comparisons_kept == 1
    assert outcome.review.review_unresolved is False

    confirmed, kept = outcome.resolutions
    assert confirmed.origin == "interactive_confirmed_this_run"
    assert confirmed.accepted_offset == 12
    assert kept.origin == "computed_this_run"
    assert kept.accepted_offset == 3


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

    outcome = _call(tmp_path, config=AlignmentConfig(use_vsview=True))
    assert outcome.review_outcome == "keep_current"
    summary = outcome.summary
    assert summary.comparisons_kept == 1
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

    outcome = _call(tmp_path, config=AlignmentConfig(use_vsview=True))
    assert outcome.review_outcome == "rejected_result"
    summary = outcome.summary
    assert summary.review_unresolved is True
    assert summary.review_ran is False
    assert summary.review_seconds == pytest.approx(25.0)


def test_failed_launch_leaves_review_summary_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_interactive(monkeypatch)

    def launch(*_args: object, **_kwargs: object):
        raise VSViewError("launcher command was not found")

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    outcome = _call(tmp_path, config=AlignmentConfig(use_vsview=True))
    assert outcome.review_outcome == "no_result"
    summary = outcome.summary
    assert summary.review_unresolved is True
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

    outcome = _call(tmp_path, config=AlignmentConfig(use_vsview=True))
    assert outcome.review_outcome == "no_result"
    summary = outcome.summary
    assert summary.review_unresolved is True
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
    unapplied = AlignmentResult(
        reference_clip="reference.mkv",
        comparison_clip="comparison.mkv",
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=1.0,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic="audio_only",
        stability=attempt.stability,
        audio_attempt=attempt,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: unapplied,
    )
    config = AlignmentConfig(cache_results=False, no_color=True, use_vsview=True)
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        generated_dir=tmp_path,
    )

    outcome = asyncio.run(
        align_clips_from_request(
            request,
            config,
        )
    )

    assert outcome.review.review_ran is False
    assert outcome.review.review_unresolved is True


@pytest.mark.parametrize(
    "payload",
    [
        "{not json",
        "[" * 10000,
        "1" * 5000,
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
    ids=("malformed", "deep", "integer-limit", "stale-session", "partial", "out-of-bounds"),
)
def test_optional_invalid_result_is_rejected(
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
        {}, "keep_current", comparisons_kept=1
    )
