"""Run-local audio alignment diagnostic persistence tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from frame_compare.errors import PathEscapesRootError
from frame_compare.services import alignment_diagnostics
from frame_compare.services.types import (
    AlignmentResult,
    AudioAlignmentAttempt,
    AudioAlignmentCandidate,
    AudioAlignmentCollectionRecord,
    AudioAlignmentDecision,
    AudioAlignmentWindowRecord,
    AudioAttemptStatus,
    AudioDecisionState,
    SelectedAudioStreamEvidence,
)


def _stream(role: str, digest: str) -> SelectedAudioStreamEvidence:
    return SelectedAudioStreamEvidence(
        role="reference" if role == "reference" else "comparison",
        source_identity_digest=digest,
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
        language_match="not_applicable" if role == "reference" else "match",
        commentary_match="not_applicable" if role == "reference" else "match",
        stream_start_num=0,
        stream_start_den=1,
        stream_start_basis="metadata",
        input_start_num=0,
        input_start_den=1,
        input_start_basis="metadata",
        time_base_num=1,
        time_base_den=48000,
        duration_num=120,
        duration_den=1,
        duration_basis="duration_ts",
    )


def audio_attempt() -> AudioAlignmentAttempt:
    windows = tuple(
        AudioAlignmentWindowRecord(
            logical_id=f"primary-{index:02d}",
            purpose="primary",
            attempt_number=1,
            parent_id=None,
            planned_reference_start=index * 8000,
            planned_reference_count=8000,
            planned_comparison_start=index * 8000,
            planned_comparison_count=8000,
            analysis_rate=8000,
            requested_rate=8000,
            actual_reference_count=8000,
            actual_comparison_count=8000,
            effective_aligned_overlap=8000,
            requested_sample_lag=0 if index < 4 else 400,
            requested_frame_candidate=0 if index < 4 else 1,
            requested_score=0.99 if index < 4 else 0.4,
            score_stage="analysis_rate",
            peak_ratio=2.0 if index < 4 else 1.1,
            peak_stage="analysis_rate",
            peak_rate=8000,
            review_qualified=index < 4,
            configured_quality=True,
            vote_disposition="voted",
            terminal_stage="decision",
            terminal_category="correlated",
        )
        for index in range(5)
    )
    candidate = AudioAlignmentCandidate(
        sample_offset=0,
        sample_rate=8000,
        frame_offset=0,
        supporting_window_ids=tuple(window.logical_id for window in windows[:4]),
        median_score=0.99,
        minimum_peak_ratio=2.0,
    )
    return AudioAlignmentAttempt(
        reference_identity_digest="a" * 64,
        comparison_identity_digest="b" * 64,
        comparison_ordinal=1,
        status="complete",
        estimator_policy="stream-timeline-distributed-2097152-v5",
        diagnostic_policy="retained-audio-evidence-v1",
        media_runtime_fingerprint="alignment-runtime",
        ffmpeg_version="not_observed",
        ffprobe_version="not_observed",
        extraction_recipe=(
            "ffmpeg [seek] -i <role_input> -map 0:a:<selected_ordinal> -vn "
            "[channel] -af <bounded_filters> -fs <planned_pcm_bytes> -f f32le -"
        ),
        sample_rate=8000,
        fps_num=24,
        fps_den=1,
        confidence_threshold=0.0,
        ambiguity_peak_ratio=1.0,
        minimum_valid_windows=1,
        consensus_minimum_ratio=1.0,
        selected_streams=(
            _stream("reference", "a" * 64),
            _stream("comparison", "b" * 64),
        ),
        analysis_rate=8000,
        planned_window_count=5,
        peak_fft_points=32768,
        total_fft_points=163840,
        planning_reason=None,
        windows=windows,
        decision=AudioAlignmentDecision(
            state="provisional",
            candidate=candidate,
            primary_reason="insufficient_consensus",
            raw_correlated_windows=5,
            consensus_windows=4,
            consensus_ratio=0.8,
            aggregate_score=0.98,
            minimum_peak_ratio=2.0,
            failed_gates=("insufficient_consensus",),
        ),
    )


def maximum_audio_attempt() -> AudioAlignmentAttempt:
    base = audio_attempt()
    template = base.windows[0]
    windows = tuple(
        replace(
            template,
            logical_id=f"primary-{index:02d}",
            planned_reference_start=index * 8000,
            planned_comparison_start=index * 8000,
        )
        for index in range(16)
    )
    collections = tuple(
        AudioAlignmentCollectionRecord(
            phase=phase,
            role=role,
            output_rate=8000,
            requested_horizon=8000,
            emitted_sample_count=8000,
            emitted_byte_count=32000,
            retained_sample_count=8000,
            retained_byte_count=32000,
            status="complete",
            end_category="planned_end_reached",
            observed_eof_sample=None,
            elapsed_seconds=0.25,
            cleanup_failure_count=0,
            failure_count=0,
        )
        for phase, role in (
            ("discovery", "reference"),
            ("discovery", "comparison"),
            ("verification", "reference"),
            ("verification", "comparison"),
        )
    )
    return replace(
        base,
        planned_window_count=16,
        windows=windows,
        decision=replace(base.decision, raw_correlated_windows=16),
        collection_observation="observed",
        collection_summaries=collections,
    )


def test_audio_attempt_rejects_invalid_or_contradictory_states() -> None:
    attempt = audio_attempt()

    with pytest.raises(ValueError, match="decision state"):
        replace(attempt.decision, state=cast(AudioDecisionState, "invalid"))
    with pytest.raises(ValueError, match="attempt status"):
        replace(attempt, status=cast(AudioAttemptStatus, "invalid"))
    with pytest.raises(ValueError, match="consensus window count"):
        replace(
            attempt.decision,
            consensus_windows=attempt.decision.raw_correlated_windows + 1,
        )
    for ratio in (-0.1, 1.1):
        with pytest.raises(ValueError, match="consensus ratio"):
            replace(attempt.decision, consensus_ratio=ratio)
    for status in ("preanalysis_rejection", "aborted"):
        with pytest.raises(ValueError, match="non-complete audio attempts"):
            replace(attempt, status=status)

    unavailable = replace(attempt.decision, state="unavailable", candidate=None)
    for status in ("preanalysis_rejection", "aborted"):
        assert replace(attempt, status=status, decision=unavailable).status == status


def test_collection_record_rejects_invalid_counts_and_failure_topology() -> None:
    base = AudioAlignmentCollectionRecord(
        phase="discovery",
        role="reference",
        output_rate=8000,
        requested_horizon=8000,
        emitted_sample_count=8000,
        emitted_byte_count=32000,
        retained_sample_count=8000,
        retained_byte_count=32000,
        status="complete",
        end_category="planned_end_reached",
        observed_eof_sample=None,
        elapsed_seconds=0.25,
        cleanup_failure_count=0,
        failure_count=0,
    )

    with pytest.raises(ValueError):
        replace(base, requested_horizon=0)
    with pytest.raises(ValueError):
        replace(base, output_rate=0)
    with pytest.raises(ValueError):
        replace(base, elapsed_seconds=True)
    overlapping = replace(base, retained_sample_count=8001, retained_byte_count=32004)
    assert overlapping.retained_sample_count == 8001
    with pytest.raises(ValueError, match="complete collection"):
        replace(base, failure_count=1)
    with pytest.raises(ValueError, match="failed collection"):
        replace(base, status="failed", end_category="not_observed")
    with pytest.raises(ValueError, match="cleanup failures"):
        replace(
            base,
            status="failed",
            end_category="not_observed",
            cleanup_failure_count=2,
            failure_count=1,
        )
    with pytest.raises(ValueError, match="actual coverage"):
        replace(audio_attempt().windows[0], actual_coverage=True)
    with pytest.raises(ValueError, match="observed facts"):
        replace(
            audio_attempt().windows[0],
            actual_coverage=0.5,
            actual_useful_reference_start=1,
            actual_useful_reference_end=2,
            pre_eof_expected_overlap=1,
        )


def _result(attempt: AudioAlignmentAttempt, *, manual: bool = False) -> AlignmentResult:
    return AlignmentResult(
        reference_clip="reference.mkv",
        comparison_clip="comparison.mkv",
        frame_offset=0 if manual else None,
        time_offset_seconds=0.0 if manual else None,
        correlation_score=1.0 if manual else 0.99,
        algorithm=None if manual else "cross_correlation",
        source="manual" if manual else "computed",
        applied=manual,
        diagnostic=None if manual else "insufficient_consensus",
        audio_attempt=attempt,
    )


def test_diagnostic_is_bounded_pathless_and_preserves_original_digest(tmp_path: Path) -> None:
    attempt = audio_attempt()
    diagnostics_dir = tmp_path / "alignment_diagnostics"
    path, before_digest, before_size = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=diagnostics_dir,
        comparison_ordinal=1,
        reference_label="Reference",
        comparison_label="Comparison 1",
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="pending",
        final_result=_result(attempt),
        final_origin="none",
    )
    _, after_digest, after_size = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=diagnostics_dir,
        comparison_ordinal=1,
        reference_label="Reference",
        comparison_label="Comparison 1",
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="confirmed",
        final_result=_result(attempt, manual=True),
        final_origin="interactive_confirmed_this_run",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert before_digest == after_digest == payload["original_attempt_digest"]
    assert before_size < 128 * 1024
    assert after_size < 128 * 1024
    assert payload["review_outcome"] == "confirmed"
    assert payload["final_resolution"]["frame_offset"] == 0
    serialized = path.read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized
    assert "ffmpeg -i" not in serialized
    assert payload["original_audio_attempt"]["ffmpeg_version"] == "not_observed"
    assert payload["original_audio_attempt"]["ffprobe_version"] == "not_observed"
    assert payload["original_audio_attempt"]["collection_observation"] == "not_observed"
    assert payload["original_audio_attempt"]["collection_summaries"] == []
    assert payload["original_audio_attempt"]["extraction_recipe"] == (
        "ffmpeg [seek] -i <role_input> -map 0:a:<selected_ordinal> -vn "
        "[channel] -af <bounded_filters> -fs <planned_pcm_bytes> -f f32le -"
    )


def test_failed_final_replacement_preserves_last_valid_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt = audio_attempt()
    diagnostics_dir = tmp_path / "alignment_diagnostics"
    path, _, _ = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=diagnostics_dir,
        comparison_ordinal=1,
        reference_label="Reference",
        comparison_label="Comparison 1",
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="pending",
        final_result=_result(attempt),
        final_origin="none",
    )
    original = path.read_bytes()
    monkeypatch.setattr(
        alignment_diagnostics,
        "write_text_atomic",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError, match="disk full"):
        alignment_diagnostics.write_alignment_diagnostic(
            generated_root=tmp_path.parent,
            diagnostics_dir=diagnostics_dir,
            comparison_ordinal=1,
            reference_label="Reference",
            comparison_label="Comparison 1",
            attempt=attempt,
            evidence_availability="current_attempt",
            review_outcome="confirmed",
            final_result=_result(attempt, manual=True),
            final_origin="interactive_confirmed_this_run",
        )

    assert path.read_bytes() == original


def test_maximum_primary_window_artifact_fits_the_fixed_byte_bound(tmp_path: Path) -> None:
    attempt = maximum_audio_attempt()

    path, _, size = alignment_diagnostics.write_alignment_diagnostic(
        generated_root=tmp_path.parent,
        diagnostics_dir=tmp_path / "alignment_diagnostics",
        comparison_ordinal=1,
        reference_label="R" * 512,
        comparison_label="C" * 512,
        attempt=attempt,
        evidence_availability="current_attempt",
        review_outcome="not_requested",
        final_result=_result(attempt),
        final_origin="none",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert size < 128 * 1024
    assert len(payload["original_audio_attempt"]["windows"]) == 16
    assert len(payload["original_audio_attempt"]["collection_summaries"]) == 4
    assert len(payload["pair"]["reference_label"]) == 256
    assert len(payload["pair"]["comparison_label"]) == 256
    serialized = path.read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized
    assert "ffmpeg -i" not in serialized


def test_symlinked_diagnostic_directory_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    diagnostics_dir = tmp_path / "alignment_diagnostics"
    try:
        diagnostics_dir.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(PathEscapesRootError):
        alignment_diagnostics.diagnostic_path(tmp_path.parent, diagnostics_dir, 1)


def test_provisional_candidate_cannot_be_constructed_as_applied_authority() -> None:
    attempt = audio_attempt()

    with pytest.raises(ValueError, match="untrusted audio evidence"):
        AlignmentResult(
            reference_clip="reference.mkv",
            comparison_clip="comparison.mkv",
            frame_offset=0,
            time_offset_seconds=0.0,
            correlation_score=0.99,
            algorithm="cross_correlation",
            source="computed",
            applied=True,
            audio_attempt=attempt,
        )
