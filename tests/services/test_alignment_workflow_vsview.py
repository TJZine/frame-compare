"""Audio-alignment workflow integration with native VSView review results."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.services.alignment import align_clips_from_request as _align_clips_from_request
from frame_compare.services.alignment_manual_overrides import load_manual_overrides
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.types import AlignmentRequest
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewResult,
    ConfirmedAlignmentReviewDecision,
    KeepCurrentAlignmentReviewDecision,
    write_alignment_review_result,
)
from tests.alignment_review_test_support import trusted_audio_attempt
from tests.services.alignment_request_test_support import (
    alignment_request,
)
from tests.services.alignment_request_test_support import (
    vsview_session as _session,
)
from tests.services.test_alignment_diagnostics import audio_attempt


def align_clips_from_request(
    request: AlignmentRequest,
    config: AlignmentConfig,
    **kwargs: Any,
) -> list[AlignmentResult]:
    return asyncio.run(_align_clips_from_request(request, config, **kwargs))


def _trusted_computed_result(
    reference: Path, comparison: Path, frame_offset: int
) -> AlignmentResult:
    return AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=frame_offset,
        time_offset_seconds=frame_offset / 24,
        correlation_score=0.99,
        algorithm="cross_correlation",
        source="computed",
        stability=audio_attempt().stability,
        audio_attempt=trusted_audio_attempt(frame_offset=frame_offset),
    )


def _configure_computed_alignment(monkeypatch: pytest.MonkeyPatch, frame_offset: int = 3) -> None:
    monkeypatch.setattr(
        "frame_compare.services.alignment_audio.probe_fps", lambda _path: Fraction(24, 1)
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda reference, comparison, **_kwargs: _trusted_computed_result(
            reference, comparison, frame_offset
        ),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        lambda: VSViewAvailability(
            status=VSViewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=True, stdout=True, stderr=True),
    )


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, config: AlignmentConfig):
    reference = tmp_path / "ref.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    _configure_computed_alignment(monkeypatch)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    return align_clips_from_request(request, config)


def test_confirmed_native_pair_replaces_computed_offset_and_persists_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def launch(*_args: object, **_kwargs: object):
        session = _session(tmp_path)
        write_alignment_review_result(
            session,
            AlignmentReviewResult(
                session_id=session.session_id,
                decisions=(
                    ConfirmedAlignmentReviewDecision(
                        comparison_key="ref:comparison",
                        reference_source_frame=80,
                        comparison_source_frame=68,
                    ),
                ),
            ),
        )
        return session, 0.0

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    results = _run(
        tmp_path,
        monkeypatch,
        config=AlignmentConfig(use_vsview=True, cache_results=False),
    )

    assert results[0].frame_offset == 12
    assert load_manual_overrides(tmp_path)["ref:comparison"].frame_offset == 12


def test_manual_zero_preserves_rejected_attempt_and_diagnostic_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    attempt = audio_attempt()
    unapplied = AlignmentResult(
        reference_clip="ref.mkv",
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
    initial_snapshot: dict[str, object] = {}
    monkeypatch.setattr(
        "frame_compare.services.alignment_audio.probe_fps",
        lambda _path: Fraction(24, 1),
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: unapplied,
    )
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        lambda: VSViewAvailability(
            status=VSViewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "_current_tty_status",
        lambda: SimpleNamespace(stdin=True, stdout=True, stderr=True),
    )

    def launch(*args: object, **_kwargs: object):
        prelaunch = capsys.readouterr().err
        assert "Provisional audio candidate: +0f - NOT APPLIED" in prelaunch
        initial_payload = json.loads(
            (tmp_path / "alignment_diagnostics" / "comparison-1.json").read_text(encoding="utf-8")
        )
        assert initial_payload["review_outcome"] == "pending"
        initial_snapshot["attempt"] = initial_payload["original_audio_attempt"]
        initial_snapshot["digest"] = initial_payload["original_attempt_digest"]
        session = _session(tmp_path)
        write_alignment_review_result(
            session,
            AlignmentReviewResult(
                session_id=session.session_id,
                decisions=(
                    ConfirmedAlignmentReviewDecision(
                        comparison_key="ref:comparison",
                        reference_source_frame=80,
                        comparison_source_frame=80,
                    ),
                ),
            ),
        )
        return session, 0.0

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)
    reference = tmp_path / "ref.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    config = AlignmentConfig(use_vsview=True, cache_results=False)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    request = replace(
        request,
        alignment_diagnostics_dir=tmp_path / "alignment_diagnostics",
        alignment_diagnostics_root=tmp_path.parent,
    )

    result = align_clips_from_request(request, config)[0]

    assert result.source == "manual"
    assert result.frame_offset == 0
    artifact = tmp_path / "alignment_diagnostics" / "comparison-1.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["review_outcome"] == "confirmed"
    assert payload["final_resolution"]["frame_offset"] == 0
    assert payload["final_resolution"]["reference_source_frame"] == 80
    assert payload["final_resolution"]["comparison_source_frame"] == 80
    assert payload["original_audio_attempt"] == initial_snapshot["attempt"]
    assert payload["original_attempt_digest"] == initial_snapshot["digest"]
    assert payload["original_audio_attempt"]["decision"]["state"] == "provisional"


@pytest.mark.parametrize("keep_current", [True, False], ids=["keep-current", "missing-result"])
def test_optional_native_review_retains_computed_offset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keep_current: bool
) -> None:
    def launch(*_args: object, **_kwargs: object):
        session = _session(tmp_path)
        if keep_current:
            write_alignment_review_result(
                session,
                AlignmentReviewResult(
                    session_id=session.session_id,
                    decisions=(KeepCurrentAlignmentReviewDecision("ref:comparison"),),
                ),
            )
        return session, 0.0

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)
    results = _run(
        tmp_path,
        monkeypatch,
        config=AlignmentConfig(use_vsview=True, cache_results=False),
    )
    assert results[0].frame_offset == 3
    assert load_manual_overrides(tmp_path) == {}


def test_forced_missing_result_stops_alignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        lambda *_args, **_kwargs: (_session(tmp_path), 0.0),
    )

    with pytest.raises(AudioAlignmentError, match="did not return a valid VSView review result"):
        _run(
            tmp_path,
            monkeypatch,
            config=AlignmentConfig(
                use_vsview=True,
                force_interactive=True,
                cache_results=False,
            ),
        )


def test_alignment_passes_complete_native_session_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launch = MagicMock(side_effect=lambda *_args, **_kwargs: (_session(tmp_path), 0.0))
    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    _run(
        tmp_path,
        monkeypatch,
        config=AlignmentConfig(use_vsview=True, cache_results=False),
    )

    request = launch.call_args.kwargs["request"]
    assert request.reference == tmp_path / "ref.mkv"
    assert request.comparisons == [tmp_path / "comparison.mkv"]
    assert request.suggested_offsets_by_key == {"ref:comparison": 3}
    assert request.presentation_names_by_stem == {
        "ref": "ref",
        "comparison": "comparison",
    }
    review = json.loads(request.audio_review_by_key["ref:comparison"])
    assert review["current_authority"] == {
        "origin": "computed_this_run",
        "frame_offset": 3,
    }
    assert review["evidence_availability"] == "current_attempt"
    assert review["audio_attempt"]["decision"]["candidate"]["frame_offset"] == 3
