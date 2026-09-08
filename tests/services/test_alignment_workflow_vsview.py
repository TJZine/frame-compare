"""Audio-alignment workflow integration with native VSView review results."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_consensus import AlignmentConsensus
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
        return session

    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", launch)

    results = _run(
        tmp_path,
        monkeypatch,
        config=AlignmentConfig(use_vsview=True, cache_results=False),
    )

    assert results[0].frame_offset == 12
    assert results[0].source == "manual"
    assert load_manual_overrides(tmp_path)["ref:comparison"].frame_offset == 12


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
        return session

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
        lambda *_args, **_kwargs: _session(tmp_path),
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
        lambda *_args, **_kwargs: _session(tmp_path),
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
    launch = MagicMock(side_effect=lambda *_args, **_kwargs: _session(tmp_path))
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
