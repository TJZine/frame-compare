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
from frame_compare.services.alignment_diagnostics import original_attempt_digest
from frame_compare.services.alignment_manual_overrides import load_manual_overrides
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    AudioAlignmentDecision,
    AudioAnalysisFacts,
    AudioChunkColumns,
    AudioChunkRun,
    AudioDecisionCandidate,
    AudioStageOutcome,
    SelectedAudioStreamEvidence,
    VideoCheckObservation,
)
from frame_compare.utils.types import AlignmentRequest
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


def align_clips_from_request(
    request: AlignmentRequest,
    config: AlignmentConfig,
    **kwargs: Any,
) -> list[AlignmentResult]:
    return asyncio.run(_align_clips_from_request(request, config, **kwargs))


def _trusted_attempt(frame_offset: int) -> AudioAlignmentAttempt:
    """Hand-built trusted attempt so review tests stay isolated from the estimator.

    The whole-track audio stage never applies on its own in U3; these
    review-replacement tests stub the estimator with a trusted attempt to
    simulate confirmed authority flowing into the native session request.
    """
    return AudioAlignmentAttempt(
        reference_identity_digest="d" * 64,
        comparison_identity_digest="e" * 64,
        comparison_ordinal=1,
        status="complete",
        estimator_policy="whole-track-chunked-phat-video-check-motion-20260929",
        diagnostic_policy="retained-audio-evidence-v1",
        media_runtime_fingerprint="alignment-runtime",
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe="recipe",
        fps_num=24,
        fps_den=1,
        selected_streams=(
            SelectedAudioStreamEvidence(
                role="reference",
                source_identity_digest="d" * 64,
                audio_stream_index=0,
                absolute_stream_index=1,
                selection_method="automatic_metadata",
                selection_rank=(0, 0, 0, 0),
                codec_name="aac",
                sample_rate=48000,
                channels=2,
                channel_layout="stereo",
                language="eng",
                is_default=True,
                is_original=False,
                is_commentary=False,
                language_match="not_applicable",
                commentary_match="not_applicable",
                stream_start_num=0,
                stream_start_den=1,
                stream_start_basis="default_zero",
                input_start_num=0,
                input_start_den=1,
                input_start_basis="default_zero",
                time_base_num=1,
                time_base_den=48000,
                duration_num=120,
                duration_den=1,
                duration_basis="duration_ts",
                video_start_num=0,
                video_start_den=1,
                video_start_basis="default_zero",
                timeline_scale_num=1,
                timeline_scale_den=1,
            ),
            SelectedAudioStreamEvidence(
                role="comparison",
                source_identity_digest="e" * 64,
                audio_stream_index=0,
                absolute_stream_index=1,
                selection_method="automatic_metadata",
                selection_rank=(0, 0, 0, 0),
                codec_name="aac",
                sample_rate=48000,
                channels=2,
                channel_layout="stereo",
                language="eng",
                is_default=True,
                is_original=False,
                is_commentary=False,
                language_match="not_applicable",
                commentary_match="not_applicable",
                stream_start_num=0,
                stream_start_den=1,
                stream_start_basis="default_zero",
                input_start_num=0,
                input_start_den=1,
                input_start_basis="default_zero",
                time_base_num=1,
                time_base_den=48000,
                duration_num=120,
                duration_den=1,
                duration_basis="duration_ts",
                video_start_num=0,
                video_start_den=1,
                video_start_basis="default_zero",
                timeline_scale_num=1,
                timeline_scale_den=1,
            ),
        ),
        analysis=AudioAnalysisFacts(
            analysis_rate=8000,
            max_offset_seconds=30.0,
            chunk_samples=40000,
            lag_samples=240000,
            planned_chunk_count=5,
        ),
        chunks=AudioChunkColumns(
            starts=(0, 40000, 80000, 120000, 160000),
            counts=(40000,) * 5,
            active=(True,) * 5,
            lags=(0,) * 5,
            psrs=(88.5,) * 5,
            credible=(True,) * 5,
            agrees=(True,) * 5,
            total_samples=200000,
        ),
        runs=(AudioChunkRun(first_index=0, last_index=4, lag=0, chunk_count=5),),
        audio=AudioStageOutcome(
            status="agreed",
            global_lag=0,
            active_chunks=5,
            credible_chunks=5,
            agreeing_chunks=5,
            compensation_seconds=0.0,
            subframe_estimate=0.0,
            rounded_frame=0,
        ),
        collection_observation="not_observed",
        collection=(),
        video_check=VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        ),
        decision=AudioAlignmentDecision(
            state="trusted_automatic",
            candidate=AudioDecisionCandidate(
                frame_offset=frame_offset,
                time_offset_seconds=frame_offset / 24,
                subframe_estimate=float(frame_offset),
                basis="audio_only",
            ),
            primary_reason="audio_video_confirmed",
            failed_gates=(),
        ),
        stability=audio_attempt().stability,
    )


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
        audio_attempt=_trusted_attempt(frame_offset),
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
    assert results[0].source == "manual"
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
    review = json.loads(request.audio_review_by_key["ref:comparison"])
    assert review["current_authority"] == {
        "origin": "computed_this_run",
        "frame_offset": 3,
    }
    assert review["evidence_availability"] == "current_attempt"
    assert review["audio_attempt"]["decision"]["candidate"]["frame_offset"] == 3
