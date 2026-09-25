"""Audio-alignment workflow integration with native VSView review results."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.services.alignment import align_clips_from_request as _align_clips_from_request
from frame_compare.services.alignment_consensus import AlignmentConsensus
from frame_compare.services.alignment_diagnostics import original_attempt_digest
from frame_compare.services.alignment_manual_overrides import load_manual_overrides
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewResult,
    ConfirmedAlignmentReviewDecision,
    KeepCurrentAlignmentReviewDecision,
    write_alignment_review_result,
)
from tests.services.alignment_request_test_support import (
    alignment_request,
)
from tests.services.alignment_request_test_support import (
    vsview_session as _session,
)
from tests.services.test_alignment_diagnostics import audio_attempt


def align_clips_from_request(*args: object, **kwargs: object):
    return asyncio.run(_align_clips_from_request(*args, **kwargs))


@pytest.fixture(autouse=True)
def automatic_authority_is_disabled_for_native_workflow_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep native-review fixtures focused on review replacement semantics."""
    monkeypatch.setattr(
        "frame_compare.services.alignment_consensus.automatic_authority_is_held",
        lambda: False,
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment_reuse_cache.automatic_authority_is_held",
        lambda: False,
    )


def _configure_computed_alignment(monkeypatch: pytest.MonkeyPatch, offset: int = 1000) -> None:
    monkeypatch.setattr(
        "frame_compare.services.alignment_audio.probe_fps", lambda _path: Fraction(24, 1)
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: AlignmentConsensus(
            sample_offset=offset,
            score=0.99,
            applied=True,
            diagnostic="accepted",
            valid_windows=1,
            consensus_windows=1,
            consensus_ratio=1.0,
            ambiguity_ratio=2.0,
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
    assert results[0].source == "manual"
    assert load_manual_overrides(tmp_path)["ref:comparison"].frame_offset == 12


def test_manual_zero_preserves_rejected_attempt_and_diagnostic_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    attempt = audio_attempt()
    initial_snapshot: dict[str, object] = {}
    monkeypatch.setattr(
        "frame_compare.services.alignment_audio.probe_fps",
        lambda _path: Fraction(24, 1),
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: AlignmentConsensus(
            sample_offset=None,
            score=0.99,
            applied=False,
            diagnostic="insufficient_consensus",
            valid_windows=5,
            consensus_windows=4,
            consensus_ratio=0.8,
            ambiguity_ratio=2.0,
            window_records=attempt.windows,
            decision=attempt.decision,
            audio_attempt=attempt,
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

    def launch(*args: object, **_kwargs: object):
        prelaunch = capsys.readouterr().err
        assert "Provisional audio candidate: +0f - NOT APPLIED" in prelaunch
        native_request = cast(Any, _kwargs["request"])
        review = json.loads(native_request.audio_review_by_key["ref:comparison"])
        assert review["current_authority"] == {"origin": "none", "frame_offset": None}
        assert review["evidence_availability"] == "current_attempt"
        assert review["audio_attempt"]["decision"]["state"] == "provisional"
        assert native_request.suggested_offsets_by_key == {"ref:comparison": None}
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
    assert result.audio_attempt == attempt
    artifact = tmp_path / "alignment_diagnostics" / "comparison-1.json"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["review_outcome"] == "confirmed"
    assert payload["final_resolution"]["frame_offset"] == 0
    assert payload["final_resolution"]["reference_source_frame"] == 80
    assert payload["final_resolution"]["comparison_source_frame"] == 80
    assert payload["original_audio_attempt"] == initial_snapshot["attempt"]
    assert payload["original_attempt_digest"] == initial_snapshot["digest"]
    assert payload["original_attempt_digest"] == original_attempt_digest(attempt)
    assert payload["original_audio_attempt"]["decision"]["state"] == "provisional"


def test_keep_current_native_decision_retains_computed_offset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    results = _run(
        tmp_path,
        monkeypatch,
        config=AlignmentConfig(use_vsview=True, cache_results=False),
    )

    assert results[0].frame_offset == 3
    assert results[0].source == "computed"
    assert load_manual_overrides(tmp_path) == {}


def test_optional_missing_result_retains_computed_offset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        lambda *_args, **_kwargs: (_session(tmp_path), 0.0),
    )

    results = _run(
        tmp_path,
        monkeypatch,
        config=AlignmentConfig(use_vsview=True, cache_results=False),
    )

    assert results[0].frame_offset == 3
    assert results[0].source == "computed"


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
