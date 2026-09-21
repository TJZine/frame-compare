"""R0 automatic-authority hold tests through service and orchestration seams."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from frame_compare.services import alignment_audio, alignment_consensus, alignment_reuse_cache
from frame_compare.services.alignment import align_clips_from_request as _align_clips_from_request
from frame_compare.services.alignment_audio import AudioAnalysisPlan, AudioWindow, AudioWindowSpec
from frame_compare.services.alignment_correlation import CorrelationEstimate
from frame_compare.services.alignment_manual_overrides import ManualOverride, save_manual_override
from frame_compare.services.alignment_vsview import AlignmentVSViewOutcome
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
    AlignmentStabilitySummary,
    AudioAlignmentCollectionRecord,
)
from frame_compare.utils.types import AlignmentRequest
from tests.orchestration.phase_task_helpers import _clip, _context, _run_align_phase
from tests.services.alignment_request_test_support import alignment_request
from tests.services.test_alignment_diagnostics import audio_attempt


def align_clips_from_request(*args: object, **kwargs: object):
    return asyncio.run(_align_clips_from_request(*args, **kwargs))


@pytest.fixture(autouse=True)
def automatic_authority_hold_is_explicit_for_rollback_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the R0 rollback assertions held while R7 defaults to active authority."""
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", True)


def _held_candidate_consensus(offset: int = 0) -> alignment_consensus.AlignmentConsensus:
    attempt = audio_attempt()
    stability = AlignmentStabilitySummary("stable", 5, 0, 0, 0, 0, 0, None)
    attempt = replace(attempt, stability=stability)
    existing_candidate = attempt.decision.candidate
    assert existing_candidate is not None
    candidate = replace(
        existing_candidate,
        sample_offset=offset,
        frame_offset=offset,
    )
    decision = replace(
        attempt.decision,
        state="trusted_automatic",
        candidate=candidate,
        primary_reason="accepted",
        failed_gates=(),
    )
    attempt = replace(attempt, decision=decision)
    return alignment_consensus.AlignmentConsensus(
        sample_offset=offset,
        score=0.99,
        applied=True,
        diagnostic="accepted",
        valid_windows=5,
        consensus_windows=5,
        consensus_ratio=1.0,
        ambiguity_ratio=2.0,
        stability=stability,
        decision=decision,
        audio_attempt=attempt,
    )


def _request(tmp_path: Path, config: AlignmentConfig) -> AlignmentRequest:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    if not reference.exists():
        reference.touch()
    if not comparison.exists():
        comparison.touch()
    return alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )


def _one_success_four_failures(
    monkeypatch: pytest.MonkeyPatch,
    config: AlignmentConfig,
) -> alignment_consensus.AlignmentConsensus:
    plan = AudioAnalysisPlan(
        sample_rate=config.sample_rate,
        requested_sample_rate=config.sample_rate,
        windows=tuple(
            AudioWindowSpec(
                reference_start_sample=index * 8000,
                reference_sample_count=8000,
                comparison_start_sample=index * 8000,
                comparison_sample_count=8000,
            )
            for index in range(5)
        ),
        peak_fft_points=32768,
        total_fft_points=163840,
    )
    attempts = 0

    def estimate(*_args: Any, **_kwargs: Any) -> CorrelationEstimate:
        nonlocal attempts
        attempts += 1
        if attempts > 1:
            raise AudioAlignmentError(
                "recoverable test window failure",
                category="insufficient_signal",
                stage="correlation",
                role="comparison",
            )
        return CorrelationEstimate(sample_offset=24, score=0.99, peak_ratio=2.0)

    monkeypatch.setattr(alignment_consensus, "estimate_alignment_offset", estimate)
    summaries = tuple(
        AudioAlignmentCollectionRecord(
            phase="discovery",
            role=role,
            output_rate=config.sample_rate,
            requested_horizon=5 * 8000,
            emitted_sample_count=5 * 8000,
            emitted_byte_count=5 * 8000 * 4,
            retained_sample_count=5 * 8000,
            retained_byte_count=5 * 8000 * 4,
            status="complete",
            end_category="planned_end_reached",
            observed_eof_sample=None,
            elapsed_seconds=0.0,
            cleanup_failure_count=0,
            failure_count=0,
        )
        for role in ("reference", "comparison")
    )
    consensus = alignment_consensus.estimate_staged_consensus_offset(
        plan=plan,
        config=config,
        fps=Fraction(24),
        discovery_phase_loader=lambda: alignment_audio.CollectedAudioPhase(
            tuple(
                AudioWindow(
                    reference=np.ones(spec.reference_sample_count, dtype=np.float32),
                    comparison=np.ones(spec.comparison_sample_count, dtype=np.float32),
                    reference_start_sample=spec.reference_start_sample,
                    comparison_start_sample=spec.comparison_start_sample,
                )
                for spec in plan.windows
            ),
            summaries,
        ),
        verification_phase_loader=lambda _specs: pytest.fail(
            "same-rate test should not load scoring windows"
        ),
        verification_spec_builder=lambda _offsets: (),
    )
    attempt = replace(
        audio_attempt(),
        windows=consensus.window_records,
        decision=consensus.decision,
    )
    return replace(consensus, audio_attempt=attempt)


@pytest.mark.parametrize("offset", [0, 24, -24])
def test_service_hold_keeps_strong_computed_offsets_non_applied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offset: int,
) -> None:
    config = AlignmentConfig(sample_rate=24, cache_results=True)
    request = _request(tmp_path, config)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: _held_candidate_consensus(offset),
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert result.frame_offset is None
    assert result.time_offset_seconds is None
    assert result.applied is False
    assert result.diagnostic == alignment_consensus.AUTOMATIC_AUTHORITY_HOLD_REASON
    assert result.audio_attempt is not None
    assert result.audio_attempt.decision.state == "provisional"
    assert result.audio_attempt.decision.primary_reason == "automatic_authority_held"
    assert "automatic_authority_held" in result.audio_attempt.decision.failed_gates
    assert not (tmp_path / "shared-alignment" / "alignment_reuse.toml").exists()


@pytest.mark.parametrize("offset", [0, 24, -24])
def test_r7_qualified_mono_authority_reaches_application_and_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offset: int,
) -> None:
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    config = AlignmentConfig(sample_rate=24, cache_results=True)
    request = _request(tmp_path, config)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: _held_candidate_consensus(offset),
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert result.applied is True
    assert result.frame_offset == offset
    assert result.time_offset_seconds == offset / 24
    assert result.audio_attempt is not None
    assert result.audio_attempt.decision.state == "trusted_automatic"
    assert (tmp_path / "shared-alignment" / "alignment_reuse.toml").exists()


def test_r7_current_v12_cache_hit_is_authoritative_without_recompute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    config = AlignmentConfig(sample_rate=24, cache_results=True)
    request = _request(tmp_path, config)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: _held_candidate_consensus(24),
    )
    first = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]
    assert first.applied is True

    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: pytest.fail("current v12 cache hit must not recompute"),
    )
    second = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert second.source == "cached"
    assert second.applied is True
    assert second.frame_offset == 24


def test_r7_v11_cache_identity_misses_and_fresh_mono_result_applies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AlignmentConfig(sample_rate=24, cache_results=True)
    request = _request(tmp_path, config)
    comparison = request.comparisons[0]
    cached = AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=3,
        time_offset_seconds=0.125,
        correlation_score=0.99,
        algorithm="cross_correlation",
        source="computed",
        stability=AlignmentStabilitySummary("stable", 1, 1, 1, 1, 1, 0, None),
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    monkeypatch.setattr(
        alignment_reuse_cache,
        "ALIGNMENT_ESTIMATOR_POLICY",
        "continuous-origin-qualified-channel-corroboration-2097152-v11-held",
    )
    alignment_reuse_cache.save_reusable_offsets(
        request,
        [
            AlignmentProvenance(
                result=cached,
                comparison_cache_key=alignment_reuse_cache.comparison_cache_key(comparison),
                provenance="computed_this_run",
            )
        ],
    )
    monkeypatch.setattr(
        alignment_reuse_cache,
        "ALIGNMENT_ESTIMATOR_POLICY",
        "continuous-origin-qualified-channel-corroboration-2097152-v12",
    )
    calls = 0

    def estimate(*_args: object, **_kwargs: object) -> alignment_consensus.AlignmentConsensus:
        nonlocal calls
        calls += 1
        return _held_candidate_consensus(0)

    monkeypatch.setattr("frame_compare.services.alignment._estimate_audio_pair", estimate)

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert calls == 1
    assert result.source == "computed"
    assert result.applied is True
    assert result.frame_offset == 0


def test_r7_v11_embedded_computed_result_misses_before_mono_recompute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AlignmentConfig(cache_results=True, previous_offsets="disabled")
    request = _request(tmp_path, config)
    comparison = request.comparisons[0]
    manual = AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=0,
        time_offset_seconds=0.0,
        correlation_score=1.0,
        algorithm=None,
        source="manual",
    )
    computed = AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=3,
        time_offset_seconds=0.125,
        correlation_score=0.99,
        algorithm="cross_correlation",
        source="computed",
        stability=AlignmentStabilitySummary("stable", 1, 1, 1, 1, 1, 0, None),
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    monkeypatch.setattr(
        alignment_reuse_cache,
        "ALIGNMENT_ESTIMATOR_POLICY",
        "continuous-origin-qualified-channel-corroboration-2097152-v11-held",
    )
    alignment_reuse_cache.save_reusable_offsets(
        request,
        [
            AlignmentProvenance(
                result=manual,
                comparison_cache_key=alignment_reuse_cache.comparison_cache_key(comparison),
                provenance="interactive_confirmed_this_run",
                computed_result=computed,
            )
        ],
    )
    monkeypatch.setattr(
        alignment_reuse_cache,
        "ALIGNMENT_ESTIMATOR_POLICY",
        "continuous-origin-qualified-channel-corroboration-2097152-v12",
    )
    calls = 0

    def estimate(*_args: object, **_kwargs: object) -> alignment_consensus.AlignmentConsensus:
        nonlocal calls
        calls += 1
        return _held_candidate_consensus(0)

    monkeypatch.setattr("frame_compare.services.alignment._estimate_audio_pair", estimate)

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert calls == 1
    assert result.source == "computed"
    assert result.applied is True
    assert result.frame_offset == 0


def test_service_keeps_one_candidate_provisional_without_independent_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AlignmentConfig(
        sample_rate=8000,
        cache_results=False,
        minimum_valid_windows=1,
        consensus_minimum_ratio=1.0,
    )
    request = _request(tmp_path, config)
    consensus = _one_success_four_failures(monkeypatch, config)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: consensus,
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert result.applied is False
    assert result.frame_offset is None
    assert result.time_offset_seconds is None
    assert result.diagnostic == "insufficient_independent_support"
    assert result.audio_attempt is not None
    assert len(result.audio_attempt.windows) == 5
    assert (
        sum(
            window.terminal_category == "insufficient_signal"
            for window in result.audio_attempt.windows
        )
        == 4
    )
    candidate = result.audio_attempt.decision.candidate
    assert candidate is not None
    assert candidate.frame_offset == 0
    assert candidate.supporting_window_ids == ("primary-01",)
    assert result.audio_attempt.decision.primary_reason == "insufficient_independent_support"


def test_mixed_manual_and_held_computed_comparisons_keep_only_manual_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.mkv"
    manual_comparison = tmp_path / "manual.mkv"
    computed_comparison = tmp_path / "computed.mkv"
    for path in (reference, manual_comparison, computed_comparison):
        path.touch()
    config = AlignmentConfig(
        cache_results=True,
        previous_offsets="disabled",
        use_vsview=True,
    )
    save_manual_override(
        tmp_path,
        ManualOverride(
            reference_clip=reference.stem,
            comparison_clip=manual_comparison.stem,
            frame_offset=0,
            timestamp="2026-09-15T00:00:00Z",
        ),
    )
    request = alignment_request(
        reference=reference,
        comparisons=[manual_comparison, computed_comparison],
        config=config,
        generated_dir=tmp_path,
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: _held_candidate_consensus(24),
    )

    def no_review(**kwargs: Any) -> AlignmentVSViewOutcome:
        captured.update(kwargs)
        return AlignmentVSViewOutcome(None, "no_result")

    monkeypatch.setattr("frame_compare.services.alignment.maybe_launch_alignment_vsview", no_review)

    results = align_clips_from_request(request, config, reference_fps=Fraction(24))

    assert [(result.source, result.applied, result.frame_offset) for result in results] == [
        ("manual", True, 0),
        ("computed", False, None),
    ]
    assert captured["offsets_by_key"] == {
        "reference:manual": 0,
        "reference:computed": None,
    }
    assert not (tmp_path / "shared-alignment" / "alignment_reuse.toml").exists()


def test_native_keep_current_cannot_promote_held_computed_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AlignmentConfig(use_vsview=True, cache_results=False)
    request = _request(tmp_path, config)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: _held_candidate_consensus(24),
    )

    def keep_current(**kwargs: Any) -> AlignmentVSViewOutcome:
        captured.update(kwargs)
        return AlignmentVSViewOutcome(None, "keep_current")

    monkeypatch.setattr(
        "frame_compare.services.alignment.maybe_launch_alignment_vsview", keep_current
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]
    key = "reference:comparison"
    review = captured["audio_review_by_key"][key]

    assert captured["offsets_by_key"] == {key: None}
    assert '"current_authority":{"frame_offset":null,"origin":"none"}' in review
    assert result.applied is False
    assert result.frame_offset is None
    assert result.time_offset_seconds is None
    assert result.audio_attempt is not None
    assert result.audio_attempt.decision.state == "provisional"
    assert result.audio_attempt.decision.primary_reason == (
        alignment_consensus.AUTOMATIC_AUTHORITY_HOLD_REASON
    )


def test_orchestration_hold_reaches_trim_application_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _clip(tmp_path / "comparison.mkv", label="Comparison")
    ctx = _context(tmp_path, comparisons=[comparison])
    ctx.workspace = replace(
        ctx.workspace,
        run_dir=ctx.workspace.generated_root / "run",
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: _held_candidate_consensus(24),
    )

    output = _run_align_phase(ctx, selected_frames=[0, 1])

    assert output.reference.trim.trim_start_frames == 0
    assert output.comparisons[0].trim.trim_start_frames == 0
    assert output.comparisons[0].alignment is None
    assert "automatic_authority_held" in output.warnings[0]


def test_quiet_mode_explains_held_automatic_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = AlignmentConfig(cache_results=False)
    request = _request(tmp_path, config)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: _held_candidate_consensus(24),
    )

    align_clips_from_request(
        request,
        config,
        reference_fps=Fraction(24),
        quiet=True,
    )

    captured = capsys.readouterr()
    assert "automatic application is temporarily disabled" in captured.err
    assert "no computed correction was applied" in captured.err


def test_quiet_mode_discloses_unassessed_stability_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = AlignmentConfig(cache_results=False)
    request = _request(tmp_path, config)
    stability = AlignmentStabilitySummary("stable", 4, 0, 0, 0, 0, 0, None)
    consensus = _held_candidate_consensus()
    attempt = replace(consensus.audio_attempt, stability=stability)
    consensus = replace(consensus, stability=stability, audio_attempt=attempt)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: consensus,
    )

    align_clips_from_request(
        request,
        config,
        reference_fps=Fraction(24),
        quiet=True,
    )

    captured = capsys.readouterr()
    assert "4/5 qualified observed windows" in captured.err
    assert "rejected or unobserved planned intervals remain unassessed" in captured.err
    assert "diagnostic only" in captured.err


def test_current_identity_shared_computed_hit_cannot_bypass_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AlignmentConfig(cache_results=True)
    request = _request(tmp_path, config)
    comparison = request.comparisons[0]
    stability = AlignmentStabilitySummary("stable", 1, 1, 1, 1, 1, 0, None)
    cached = AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=3,
        time_offset_seconds=0.125,
        correlation_score=0.99,
        algorithm="cross_correlation",
        source="computed",
        stability=stability,
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    alignment_reuse_cache.save_reusable_offsets(
        request,
        [
            AlignmentProvenance(
                result=cached,
                comparison_cache_key=alignment_reuse_cache.comparison_cache_key(comparison),
                provenance="computed_this_run",
            )
        ],
        accepted_at="2026-09-15T00:00:00Z",
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", True)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: pytest.fail("held computed cache hit must not recompute"),
    )

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert result.frame_offset is None
    assert result.time_offset_seconds is None
    assert result.applied is False
    assert result.diagnostic == alignment_consensus.AUTOMATIC_AUTHORITY_HOLD_REASON


def test_old_policy_cache_identity_misses_and_fresh_result_stays_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AlignmentConfig(cache_results=True)
    request = _request(tmp_path, config)
    comparison = request.comparisons[0]
    stability = AlignmentStabilitySummary("stable", 1, 1, 1, 1, 1, 0, None)
    cached = AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=3,
        time_offset_seconds=0.125,
        correlation_score=0.99,
        algorithm="cross_correlation",
        source="computed",
        stability=stability,
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    monkeypatch.setattr(alignment_reuse_cache, "ALIGNMENT_ESTIMATOR_POLICY", "old-policy-v5")
    alignment_reuse_cache.save_reusable_offsets(
        request,
        [
            AlignmentProvenance(
                result=cached,
                comparison_cache_key=alignment_reuse_cache.comparison_cache_key(comparison),
                provenance="computed_this_run",
            )
        ],
        accepted_at="2026-09-15T00:00:00Z",
    )
    monkeypatch.setattr(
        alignment_reuse_cache,
        "ALIGNMENT_ESTIMATOR_POLICY",
        "audio-authority-hold-2097152-v6",
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", True)
    calls = 0

    def estimate(*_args: object, **_kwargs: object) -> alignment_consensus.AlignmentConsensus:
        nonlocal calls
        calls += 1
        return _held_candidate_consensus(0)

    monkeypatch.setattr("frame_compare.services.alignment._estimate_audio_pair", estimate)

    result = align_clips_from_request(request, config, reference_fps=Fraction(24))[0]

    assert calls == 1
    assert result.applied is False
    assert result.frame_offset is None


def test_manual_authority_can_be_cached_without_embedded_computed_result(
    tmp_path: Path,
) -> None:
    config = AlignmentConfig(cache_results=True)
    request = _request(tmp_path, config)
    comparison = request.comparisons[0]
    manual = AlignmentResult(
        reference_clip=request.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=0,
        time_offset_seconds=0.0,
        correlation_score=1.0,
        algorithm=None,
        source="manual",
    )
    rejected_computed = replace(
        manual,
        frame_offset=3,
        time_offset_seconds=0.125,
        correlation_score=0.99,
        algorithm="cross_correlation",
        source="computed",
        stability=AlignmentStabilitySummary("stable", 1, 1, 1, 1, 1, 0, None),
    )
    alignment_reuse_cache.save_reusable_offsets(
        request,
        [
            AlignmentProvenance(
                result=manual,
                comparison_cache_key=alignment_reuse_cache.comparison_cache_key(comparison),
                provenance="interactive_confirmed_this_run",
                computed_result=rejected_computed,
            )
        ],
        accepted_at="2026-09-15T00:00:00Z",
    )

    entries = alignment_reuse_cache.load_reusable_offset_entries(request)
    assert entries is not None
    entry = entries[alignment_reuse_cache.comparison_cache_key(comparison)]
    assert entry.result.frame_offset == 0
    assert entry.origin == "interactive_confirmed"
    assert entry.computed_result is None


def test_embedded_computed_fallback_is_held_but_confirmed_manual_authority_survives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disabled_config = AlignmentConfig(cache_results=True, previous_offsets="disabled")
    disabled_request = _request(tmp_path, disabled_config)
    comparison = disabled_request.comparisons[0]
    manual = AlignmentResult(
        reference_clip=disabled_request.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=0,
        time_offset_seconds=0.0,
        correlation_score=1.0,
        algorithm=None,
        source="manual",
    )
    computed = AlignmentResult(
        reference_clip=disabled_request.reference.path.name,
        comparison_clip=comparison.path.name,
        frame_offset=3,
        time_offset_seconds=0.125,
        correlation_score=0.99,
        algorithm="cross_correlation",
        source="computed",
        stability=AlignmentStabilitySummary("stable", 1, 1, 1, 1, 1, 0, None),
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    alignment_reuse_cache.save_reusable_offsets(
        disabled_request,
        [
            AlignmentProvenance(
                result=manual,
                comparison_cache_key=alignment_reuse_cache.comparison_cache_key(comparison),
                provenance="interactive_confirmed_this_run",
                computed_result=computed,
            )
        ],
        accepted_at="2026-09-15T00:00:00Z",
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", True)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: pytest.fail("embedded computed evidence must not recompute"),
    )

    held = align_clips_from_request(
        disabled_request,
        disabled_config,
        reference_fps=Fraction(24),
    )[0]
    confirmed_config = AlignmentConfig(cache_results=True, previous_offsets="always")
    confirmed_request = _request(tmp_path, confirmed_config)
    confirmed = align_clips_from_request(
        confirmed_request,
        confirmed_config,
        reference_fps=Fraction(24),
    )[0]

    assert held.applied is False
    assert held.frame_offset is None
    assert held.diagnostic == alignment_consensus.AUTOMATIC_AUTHORITY_HOLD_REASON
    assert confirmed.applied is True
    assert confirmed.frame_offset == 0
    assert confirmed.source == "cached"
