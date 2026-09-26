"""Exact-match tests for frozen audio-alignment terminal strings.

The Align summary fragments, the VSView review-result message, the
manual-review invitation lines, and the provisional/unavailable evidence copy
are user-visible contracts: they must be reproduced verbatim. These tests
assert the exact text through the real render paths (not copies of the
literals).
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.services.alignment import align_clips_from_request as _align_async
from frame_compare.services.alignment_presentation import (
    present_alignment_evidence,
    print_pre_review_summary,
)
from frame_compare.services.alignment_vsview import format_vsview_review_message
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentProvenance,
    AlignmentResult,
)
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from tests.services.alignment_request_test_support import alignment_request
from tests.services.test_alignment_evidence import attempt_with_chunks


def _provisional_result(reference: Path, comparison: Path) -> AlignmentResult:
    attempt = attempt_with_chunks(2)
    return AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=1.0,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic="video_check_pending",
        stability=attempt.stability,
        audio_attempt=attempt,
    )


def _unavailable_result(
    reference: Path, comparison: Path, *, reason: str = "no_single_offset"
) -> AlignmentResult:
    attempt = replace(
        attempt_with_chunks(0),
        status="complete",
        audio=replace(
            attempt_with_chunks(0).audio,
            status="no_single_offset",  # type: ignore[arg-type]
        ),
        decision=replace(
            attempt_with_chunks(0).decision,
            state="unavailable",
            candidate=None,
            primary_reason=reason,
            failed_gates=(reason,),
        ),
    )
    return AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=0.0,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic=reason,
        stability=attempt.stability,
        audio_attempt=attempt,
    )


def _present(
    request: object,
    result: AlignmentResult,
    config: AlignmentConfig,
    *,
    verbose: bool = False,
    quiet: bool = False,
    json_output: bool = False,
) -> None:
    from frame_compare.services.alignment_keys import alignment_key

    key = alignment_key(request.reference.path, request.comparisons[0].path)  # type: ignore[union-attr]
    present_alignment_evidence(
        request=request,  # type: ignore[arg-type]
        results_map={key: result},
        provenances={
            key: AlignmentProvenance(
                result=result,
                comparison_cache_key="key",
                provenance="computed_this_run",
                evidence_availability="current_attempt",
            )
        },
        config=config,
        progress=None,
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
        diagnostics_written=False,
    )


def test_align_pre_review_summary_uses_frozen_fragments(tmp_path: Path, capsys) -> None:
    from frame_compare.utils.progress import RichProgressReporter

    reference, alpha, beta = (tmp_path / name for name in ("ref.mkv", "alpha.mkv", "beta.mkv"))
    for path in (reference, alpha, beta):
        path.touch()
    request = alignment_request(
        reference=reference,
        comparisons=[alpha, beta],
        config=AlignmentConfig(),
        generated_dir=tmp_path,
    )
    request = replace(
        request,
        comparisons=[
            replace(comparison, short_name=short_name)
            for comparison, short_name in zip(request.comparisons, ("Alpha", "Beta"), strict=True)
        ],
    )
    results_map = {
        f"{reference.stem}:{comparison.stem}": AlignmentResult(
            reference.name,
            comparison.name,
            None,
            None,
            0.0,
            None,
            "computed",
            applied=applied,
        )
        for comparison, applied in ((alpha, True), (beta, False))
    }

    print_pre_review_summary(
        request=request,
        results_map=results_map,
        progress=RichProgressReporter(no_color=True),
        no_color=True,
    )

    err = capsys.readouterr().err
    assert "Align" in err
    assert "Alpha audio applied · Beta needs visual confirmation" in err


def test_vsview_review_message_singular_pair_and_kept() -> None:
    assert (
        format_vsview_review_message(1, 1)
        == "Accepted 1 confirmed pair; 1 comparison kept its current offset."
    )


def test_vsview_review_message_plural_pairs_and_kept() -> None:
    assert (
        format_vsview_review_message(2, 1)
        == "Accepted 2 confirmed pairs; 1 comparison kept its current offset."
    )


def test_vsview_review_message_plural_kept() -> None:
    assert (
        format_vsview_review_message(2, 3)
        == "Accepted 2 confirmed pairs; 3 comparisons kept their current offset."
    )


def test_vsview_review_message_omits_kept_clause_when_zero() -> None:
    assert format_vsview_review_message(2, 0) == "Accepted 2 confirmed pairs."


@pytest.mark.parametrize(
    ("has_candidate", "expected"),
    [
        (
            True,
            "Opening VSView for manual review. The candidate is a hint, not a confirmed alignment.",
        ),
        (
            False,
            "Opening VSView for manual review. No automatic candidate is available; "
            "align the sources manually.",
        ),
    ],
)
def test_opening_vsview_review_lines_frozen_verbatim(
    has_candidate: bool,
    expected: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True, use_vsview=True)
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
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    if has_candidate:
        result = _provisional_result(reference, comparison)
    else:
        result = _unavailable_result(reference, comparison)
    monkeypatch.setattr(
        "frame_compare.services.alignment._estimate_audio_pair",
        lambda *_args, **_kwargs: result,
    )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    asyncio.run(
        _align_async(
            request,
            config,
            reference_fps=Fraction(24),
        )
    )

    err = capsys.readouterr().err
    assert expected in err


def _request_for(tmp_path: Path, config: AlignmentConfig) -> tuple[Path, Path, object]:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    return (
        reference,
        comparison,
        alignment_request(
            reference=reference,
            comparisons=[comparison],
            config=config,
            generated_dir=tmp_path,
        ),
    )


def test_normal_provisional_copy_is_frozen(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    _present(request, _provisional_result(reference, comparison), config)

    err = capsys.readouterr().err
    assert "Comparison 1 - Provisional audio candidate: +146f - NOT APPLIED" in err
    assert (
        "Visual confirmation required to use this hint. Align manually or keep the current alignment."
        not in err
    )
    assert "Video confirmation pending; not applied." in err


@pytest.mark.parametrize(
    ("reason", "phrase"),
    [
        ("no_single_offset", "no single offset across the track"),
        ("search_edge", "best offset at the search edge"),
        ("no_usable_audio", "no usable audio signal"),
        ("selected_audio_timeline_unavailable", "selected audio timeline unavailable"),
        ("analysis_budget_exceeded", "analysis budget exceeded"),
        ("source_identity_changed", "source changed during analysis"),
        ("timeout", "audio collection failed"),
    ],
)
def test_normal_unavailable_copy_is_frozen(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    reason: str,
    phrase: str,
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    _present(request, _unavailable_result(reference, comparison, reason=reason), config)

    err = capsys.readouterr().err
    assert f"Comparison 1 - No usable audio candidate ({phrase}) - NOT APPLIED" in err
    assert "Align manually or keep the current alignment." in err


def test_verbose_provisional_shows_chunk_facts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    _present(request, _provisional_result(reference, comparison), config, verbose=True)

    err = capsys.readouterr().err
    assert "active=2; credible=2; agreeing=2" in err
    assert "lag=+1177 samples" in err
    assert "compensation=+0.000s" in err
    assert "sub-frame=audio +146.23f" in err
    assert "planned=2" in err
    assert "whole-track-chunked-phat-video-check-20260925" in err


def test_verbose_unavailable_shows_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from frame_compare.utils.alignment_evidence import AudioChunkRun

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    base = attempt_with_chunks(2)
    attempt = replace(
        base,
        runs=(
            AudioChunkRun(first_index=0, last_index=0, lag=100, chunk_count=1),
            AudioChunkRun(first_index=1, last_index=1, lag=-200, chunk_count=1),
        ),
        audio=replace(base.audio, status="no_single_offset"),  # type: ignore[arg-type]
        decision=replace(
            base.decision,
            state="unavailable",
            candidate=None,
            primary_reason="no_single_offset",
            failed_gates=("no_single_offset",),
        ),
    )
    result = AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=0.5,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic="no_single_offset",
        stability=attempt.stability,
        audio_attempt=attempt,
    )
    _present(request, result, config, verbose=True)

    err = capsys.readouterr().err
    assert "Run 0-0: lag=+100 x1 chunks" in err
    assert "Run 1-1: lag=-200 x1 chunks" in err
    assert "No usable audio candidate (no single offset across the track) - NOT APPLIED" in err


def test_verbose_stability_scope_names_unassessed_chunks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from frame_compare.utils.alignment_evidence import AlignmentStabilitySummary

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    base = attempt_with_chunks(2)
    attempt = replace(
        base,
        stability=AlignmentStabilitySummary(
            classification="possible_discontinuity",
            valid_windows=1,
            offset_min_frames=146,
            offset_max_frames=146,
            first_offset_frames=146,
            last_offset_frames=146,
            largest_adjacent_jump_frames=0,
            change_position_seconds=None,
        ),
    )
    result = AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=0.5,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic="no_single_offset",
        stability=attempt.stability,
        audio_attempt=attempt,
    )
    _present(request, result, config, verbose=True)

    err = capsys.readouterr().err
    assert "chunks without credible evidence are not assessed" in err
    assert "unobserved planned chunks remain unassessed" not in err


def test_quiet_keeps_only_actionable_notices(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    _present(request, _provisional_result(reference, comparison), config, quiet=True)

    err = capsys.readouterr().err
    assert "Provisional audio candidate" in err

    applied = AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=3,
        time_offset_seconds=0.125,
        correlation_score=1.0,
        algorithm=None,
        source="manual",
        applied=True,
    )
    _present(request, applied, config, quiet=True)
    assert capsys.readouterr().err == ""


def test_json_mode_logs_review_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    _present(request, _provisional_result(reference, comparison), config, json_output=True)

    out = capsys.readouterr().out
    assert "audio_alignment_requires_review" in out
    assert "decision_state=provisional" in out
    assert "candidate_frame=146" in out
    assert "reason=video_check_pending" in out
