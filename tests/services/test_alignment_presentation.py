"""User-visible terminal presentation contracts for audio alignment."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.cli.run_command import handle_json_output
from frame_compare.orchestration import RunResult
from frame_compare.services.alignment import align_clips_from_request as _align_async
from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkObservation,
    ChunkPlan,
)
from frame_compare.services.alignment_decision import (
    decide_completed_stage,
)
from frame_compare.services.alignment_evidence import (
    AudioChunkRun,
    AudioSameFrameContext,
    VideoCheckObservation,
    VideoTargetEvidence,
    audio_unavailable_phrase,
)
from frame_compare.services.alignment_keys import alignment_key
from frame_compare.services.alignment_presentation import (
    present_alignment_evidence,
)
from frame_compare.services.alignment_review_projection import build_audio_review_presentation
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    ComparisonResolution,
)
from frame_compare.utils.logging import configure_logging
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.utils.types import AlignmentRequest
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from tests.alignment_review_scenarios import (
    audio_failed_video_confirmed_attempt as _audio_failed_video_confirmed_attempt,
)
from tests.alignment_review_scenarios import (
    boundary_video_inconclusive_attempt as _boundary_video_inconclusive_attempt,
)
from tests.alignment_review_scenarios import (
    multi_context_attempt as _multi_context_attempt,
)
from tests.alignment_review_scenarios import (
    production_nested_targets_attempt as _production_nested_targets_attempt,
)
from tests.alignment_review_scenarios import (
    review_attempt as _review_attempt,
)
from tests.services.alignment_evidence_test_support import (
    attempt_with_chunks,
    retimed_comparison_stream,
    stream,
)
from tests.services.alignment_projection_test_support import (
    producer_run_context_attempt,
    producer_target_context_attempt,
)
from tests.services.alignment_request_test_support import alignment_request


def _provisional_result(reference: Path, comparison: Path) -> AlignmentResult:
    attempt = attempt_with_chunks(2)
    attempt = replace(
        attempt,
        decision=replace(
            attempt.decision,
            primary_reason="video_check_inconclusive",
            failed_gates=("video_check_inconclusive",),
        ),
        video_check=VideoCheckObservation(
            observation="observed",
            scored_offsets=(144, 145, 146, 147, 148),
            confirmed_offset=None,
            index_build_seconds=0.1,
            positions=(),
        ),
    )
    return AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=1.0,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic="video_check_inconclusive",
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
            status="no_single_offset",
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
    request: AlignmentRequest,
    result: AlignmentResult,
    config: AlignmentConfig,
    *,
    verbose: bool = False,
    quiet: bool = False,
    json_output: bool = False,
) -> None:
    key = alignment_key(request.reference.path, request.comparisons[0].path)
    present_alignment_evidence(
        request=request,
        resolutions={
            key: ComparisonResolution(
                result=result,
                comparison_cache_key="key",
                origin="computed_this_run",
            )
        },
        config=config,
        progress=None,
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
    )


def _four_region_attempt():
    attempt = _review_attempt("competing_offset")
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(1177, 81_000, 82_000, 83_000),
            agrees=(True, False, False, False),
        ),
        runs=tuple(
            AudioChunkRun(first_index=index, last_index=index, lag=lag, chunk_count=1)
            for index, lag in enumerate((1177, 81_000, 82_000, 83_000))
        ),
        video_check=replace(attempt.video_check, targets=()),
    )


def _unexamined_attempt():
    attempt = _review_attempt("unresolved_audio_disagreement")
    target = attempt.video_check.targets[0]
    targets = tuple(
        replace(
            target,
            kind="chunk",
            first_chunk_index=index,
            last_chunk_index=index,
            start_sample=index * 240_000,
            end_sample=(index + 1) * 240_000,
            resolution="unexamined",
            positions=(),
        )
        for index in (2, 3)
    )
    return replace(
        attempt,
        video_check=replace(attempt.video_check, targets=targets),
    )


def _mixed_unresolved_unexamined_attempt():
    attempt = _review_attempt("unresolved_audio_disagreement")
    unexamined = tuple(
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=index,
            last_chunk_index=index,
            credible=True,
            start_sample=index * 240_000,
            end_sample=(index + 1) * 240_000,
            target_offset=250,
            alternative_offsets=(249, 250, 251),
            resolution="unexamined",
            positions=(),
        )
        for index in (0, 1)
    )
    return replace(
        attempt,
        video_check=replace(
            attempt.video_check, targets=(*attempt.video_check.targets, *unexamined)
        ),
    )


def _producer_count_attempt(*, planned: int, active: int, credible: int, agreeing: int):
    observations = tuple(
        ChunkObservation(
            index=index,
            reference_start=index * 240_000,
            reference_count=240_000,
            active=index < active,
            lag=0 if index < active else None,
            psr=(30.0 if index < credible else 5.0) if index < active else None,
            credible=index < credible,
            agrees=index < agreeing,
        )
        for index in range(planned)
    )
    estimate = ChunkedAudioEstimate(
        outcome="agreed" if active else "no_usable_audio",
        global_lag=0 if active else None,
        observations=observations,
        runs=(),
        active_count=active,
        credible_count=credible,
        agreeing_count=agreeing,
    )
    plan = ChunkPlan(
        chunk_samples=240_000,
        lag_samples=8_000,
        chunks=tuple((index * 240_000, 240_000) for index in range(planned)),
    )
    stage = decide_completed_stage(
        estimate=estimate,
        plan=plan,
        max_offset_seconds=1.0,
        reference_audio_start=Fraction(0),
        reference_video_start=Fraction(0),
        comparison_audio_start=Fraction(0),
        comparison_video_start=Fraction(0),
        fps_reference=Fraction(24),
    )
    base = attempt_with_chunks(planned)
    return replace(
        base,
        fps_num=24,
        fps_den=1,
        analysis=stage.analysis,
        chunks=stage.chunks,
        runs=stage.runs,
        audio=stage.audio,
        video_check=base.video_check,
        decision=stage.decision,
        stability=stage.stability,
        authority_recount=stage.authority_recount,
    )


def _partial_final_target_attempt():
    attempt = _review_attempt("competing_offset")
    target = replace(attempt.video_check.targets[0], end_sample=840_000)
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            counts=(240_000, 240_000, 240_000, 120_000),
            total_samples=840_000,
        ),
        video_check=replace(attempt.video_check, targets=(target,)),
    )


def _applied_result(reference: Path, comparison: Path, attempt) -> AlignmentResult:
    assert attempt.decision.state == "trusted_automatic"
    candidate = attempt.decision.candidate
    assert candidate is not None
    return AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=candidate.frame_offset,
        time_offset_seconds=candidate.time_offset_seconds,
        correlation_score=1.0,
        algorithm="cross_correlation",
        source="computed",
        applied=True,
        diagnostic="audio_video_confirmed",
        stability=attempt.stability,
        audio_attempt=attempt,
    )


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
        generated_dir=tmp_path,
    )
    asyncio.run(
        _align_async(
            request,
            config,
        )
    )

    err = capsys.readouterr().err
    assert expected in err


def _request_for(tmp_path: Path, config: AlignmentConfig) -> tuple[Path, Path, AlignmentRequest]:
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
            generated_dir=tmp_path,
        ),
    )


def test_provisional_retimed_audio_shows_review_and_verbose_facts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    result = _provisional_result(reference, comparison)
    assert result.audio_attempt is not None
    result = replace(
        result,
        audio_attempt=replace(
            result.audio_attempt,
            selected_streams=(stream("reference"), retimed_comparison_stream()),
        ),
    )

    for verbose in (False, True):
        _present(request, result, config, verbose=verbose)
        err = capsys.readouterr().err
        assert "comparison: +146f · not applied" in err
        assert "could not confirm the exact frame" in err
        if verbose:
            assert "active=2; credible=2; agreeing=2" in err
            assert "lag=+1177 samples" in err
            assert "compensation=+0.000s" in err
            assert "sub-frame=audio +146.23f" in err
            assert "planned=2" in err
            assert "whole-track-chunked-phat-video-check-motion-20260929" in err
            assert "Context: Comparison audio retimed x1.0417 to its effective frame rate." in err
        else:
            assert "retimed" not in err
            assert (
                "Visual confirmation required to use this hint. Align manually or keep the current alignment."
                not in err
            )


def test_inconclusive_copy_does_not_report_boundary_hint_with_four_positions() -> None:
    review = build_audio_review_presentation(_boundary_video_inconclusive_attempt(position_count=4))

    assert review.reason_lines() == (
        "The audio points to +146f, but the video could not confirm the exact frame "
        "(little motion or different framing at the checked points).",
    )


@pytest.mark.parametrize(
    ("reason", "phrase"),
    [
        ("no_single_offset", "no single offset across the track"),
        ("search_edge", "best offset at the search edge"),
        ("no_usable_audio", "no usable audio signal"),
        ("selected_audio_timeline_unavailable", "selected audio timeline unavailable"),
        ("retime_rate_unsupported", "retimed audio rate unsupported"),
        ("analysis_budget_exceeded", "analysis budget exceeded"),
        ("source_identity_changed", "source changed during analysis"),
        ("timeout", "audio collection failed"),
        ("video_check_inconclusive", "video check was inconclusive"),
    ],
)
def test_audio_unavailable_phrase(reason: str, phrase: str) -> None:
    assert audio_unavailable_phrase(reason) == phrase


def test_verbose_unavailable_shows_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from frame_compare.services.alignment_evidence import AudioChunkRun

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    base = attempt_with_chunks(2)
    attempt = replace(
        base,
        runs=(
            AudioChunkRun(first_index=0, last_index=0, lag=100, chunk_count=1),
            AudioChunkRun(first_index=1, last_index=1, lag=-200, chunk_count=1),
        ),
        audio=replace(base.audio, status="no_single_offset"),
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
    _present(request, result, config)
    normal = capsys.readouterr().err
    assert "no audio match (no single offset across the track)" in normal
    assert "Align manually or keep the current alignment." in normal

    _present(request, result, config, verbose=True)

    err = capsys.readouterr().err
    assert "Run 0-0: lag=+100 x1 chunks" in err
    assert "Run 1-1: lag=-200 x1 chunks" in err
    assert "no audio match (no single offset across the track)" in err


def test_verbose_stability_scope_names_unassessed_chunks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from frame_compare.services.alignment_evidence import AlignmentStabilitySummary

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
    assert "· not applied" in err

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
    configure_logging("INFO", "json")
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    _present(request, _provisional_result(reference, comparison), config, json_output=True)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "audio_alignment_requires_review" in captured.err
    assert '"decision_state": "provisional"' in captured.err
    assert '"candidate_frame": 146' in captured.err
    assert '"reason": "video_check_inconclusive"' in captured.err


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (
            "competing_offset_confirmed_by_video",
            "The video confirms +243f in 1:00-2:00, so the sources likely differ by an edit there.",
        ),
        (
            "competing_offset",
            "Audio in 1:00-2:00 points to +243f, and the video could not settle which offset is right there.",
        ),
        (
            "unresolved_audio_disagreement",
            "Audio in 1:00-2:00 points to +243f, and the video could not rule that out.",
        ),
        (
            "video_check_inconclusive",
            "The audio points to +146f, but the video could not confirm the exact frame",
        ),
        (
            "video_check_unavailable",
            "The audio points to +146f, but the video could not be read to confirm the exact frame.",
        ),
    ],
)
def test_p4a_reason_copy_is_plain_and_shows_check_points(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    reason: str,
    expected: str,
) -> None:
    configure_logging("INFO", "json")
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _review_attempt(reason)
    result = AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=0.5,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic=reason,
        stability=attempt.stability,
        audio_attempt=attempt,
    )

    _present(request, result, config)

    err = capsys.readouterr().err
    assert "comparison: +146f · not applied" in err
    assert expected in err
    if reason != "video_check_unavailable":
        assert "Check 1:01:01  reference 13,123 <-> comparison 12,880 (+243f)" in err
    assert "Align manually or keep the current alignment." in err
    _present(request, result, config, verbose=True)
    assert f"Decision: state=provisional; reason={reason}" in capsys.readouterr().err
    _present(request, result, config, json_output=True)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "audio_alignment_requires_review" in captured.err
    assert f'"reason": "{reason}"' in captured.err
    assert expected not in captured.err


def test_combined_raw_audio_and_video_failures_both_render() -> None:
    attempt = _review_attempt("video_check_unavailable")
    attempt = replace(
        attempt,
        audio=replace(attempt.audio, status="no_single_offset"),
        decision=replace(
            attempt.decision,
            failed_gates=("video_check_unavailable", "no_single_offset"),
        ),
    )

    assert build_audio_review_presentation(attempt).reason_lines() == (
        "The audio points to +146f, but the video could not be read to confirm the exact frame.",
        "The audio does not agree on one offset across the track.",
    )


def test_audio_failed_but_video_confirmed_gets_v6_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _audio_failed_video_confirmed_attempt()
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

    _present(request, result, config)
    err = capsys.readouterr().err
    assert (
        "The audio does not agree on one offset across the track; the video suggests +146f" in err
    )

    _present(request, result, config, verbose=True)
    verbose = capsys.readouterr().err
    assert "Decision: state=provisional; reason=no_single_offset" in verbose
    assert "Video: confirmed +146f" in verbose


def test_four_regions_truncate_after_three_and_keep_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _four_region_attempt()
    result = AlignmentResult(
        reference.name,
        comparison.name,
        None,
        None,
        0.5,
        "cross_correlation",
        "computed",
        applied=False,
        diagnostic="competing_offset",
        stability=attempt.stability,
        audio_attempt=attempt,
    )

    _present(request, result, config)
    err = capsys.readouterr().err
    review = build_audio_review_presentation(attempt)
    assert [region.offset for region in review.regions] == [146, 243, 246, 249]
    assert review.regions[0].end_seconds == review.regions[1].start_seconds
    assert "+249f" not in "\n".join(review.region_lines(limit=3))
    assert "and 1 more regions" in err
    assert "+249f" not in err


def test_unexamined_budget_add_on_is_plain_and_verbose(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _unexamined_attempt()
    result = AlignmentResult(
        reference.name,
        comparison.name,
        None,
        None,
        0.5,
        "cross_correlation",
        "computed",
        applied=False,
        diagnostic="unresolved_audio_disagreement",
        stability=attempt.stability,
        audio_attempt=attempt,
    )

    _present(request, result, config)
    assert (
        "Audio in 2 more sections points elsewhere; they were not checked"
        in capsys.readouterr().err
    )
    _present(request, result, config, verbose=True)
    assert (
        "Decision: state=provisional; reason=unresolved_audio_disagreement"
        in capsys.readouterr().err
    )


def test_unresolved_reason_lists_region_before_unexamined_add_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _mixed_unresolved_unexamined_attempt()
    result = AlignmentResult(
        reference.name,
        comparison.name,
        None,
        None,
        0.5,
        "cross_correlation",
        "computed",
        applied=False,
        diagnostic="unresolved_audio_disagreement",
        stability=attempt.stability,
        audio_attempt=attempt,
    )

    _present(request, result, config)

    err = capsys.readouterr().err
    region = "Audio in 1:00-2:00 points to +243f, and the video could not rule that out."
    add_on = "Audio in 2 more sections points elsewhere; they were not checked, so the offset is not applied."
    assert err.index(region) < err.index(add_on)


def test_nested_target_reasons_and_regions_appear_in_terminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    attempt = _production_nested_targets_attempt()
    full_review = build_audio_review_presentation(attempt)
    expected_reasons = (
        "Audio in 0:00-1:00 points to +250f, and the video could not settle which offset is right there.",
        "Audio in 1:00-1:30 points to +246f, and the video could not rule that out.",
    )
    expected_regions = (
        "+250f  0:00-1:00  not settled",
        "+246f  1:00-1:30  not settled",
        "+250f  1:30-2:00  confirmed by video",
    )

    assert full_review.suggested_offset == 146
    assert full_review.reason_lines() == expected_reasons
    assert full_review.region_lines() == expected_regions

    unexamined = _unexamined_attempt()
    unexamined_target = replace(
        unexamined.video_check.targets[0],
        target_offset=250,
        alternative_offsets=(249, 250, 251),
    )
    unexamined = replace(
        unexamined,
        video_check=replace(unexamined.video_check, targets=(unexamined_target,)),
    )

    assert (
        "+250f  1:00-1:30  not checked"
        in build_audio_review_presentation(unexamined).region_lines()
    )

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    result = AlignmentResult(
        reference.name,
        comparison.name,
        None,
        None,
        0.5,
        "cross_correlation",
        "computed",
        applied=False,
        diagnostic="competing_offset",
        stability=attempt.stability,
        audio_attempt=attempt,
    )
    _present(request, result, config)

    err = capsys.readouterr().err
    for line in (*expected_reasons, *expected_regions):
        assert line in err


@pytest.mark.parametrize(
    (
        "credible",
        "resolution",
        "expected_state",
        "expected_reason",
        "expected_context",
        "expected_noted",
    ),
    [
        (
            True,
            "unresolved",
            "provisional",
            "unresolved_audio_disagreement",
            ("Local video inconclusive in 1:00-1:30 (+0f scored 1.000, +2f scored 1.000).",),
            None,
        ),
        (
            True,
            "resolved",
            "trusted_automatic",
            "audio_video_confirmed",
            ("Audio differed in 1:00-1:30; the video confirmed the offset there.",),
            "Noted: audio differed in 1 section (1:00-1:30); the video confirmed +0f there.",
        ),
        (False, "resolved", "trusted_automatic", "audio_video_confirmed", (), None),
        (
            False,
            "unresolved",
            "trusted_automatic",
            "audio_video_confirmed",
            (
                "Weak audio in 1:00-1:30 pointed to +2f; video inconclusive there "
                "(+0f scored 1.000, +2f scored 1.000); not counted.",
            ),
            (
                "Noted: weak audio in 1:00-1:30 pointed elsewhere; the video could "
                "not settle it, so it was not counted."
            ),
        ),
        (True, "unexamined", "provisional", "unresolved_audio_disagreement", (), None),
        (False, "unexamined", "trusted_automatic", "audio_video_confirmed", (), None),
        (
            True,
            "alternative_confirmed",
            "provisional",
            "competing_offset_confirmed_by_video",
            (),
            None,
        ),
        (
            False,
            "alternative_confirmed",
            "provisional",
            "competing_offset_confirmed_by_video",
            (),
            None,
        ),
    ],
)
def test_target_context_drives_terminal_and_json_review_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    credible: bool,
    resolution: str,
    expected_state: str,
    expected_reason: str,
    expected_context: tuple[str, ...],
    expected_noted: str | None,
) -> None:
    attempt = producer_target_context_attempt(credible=credible, resolution=resolution)
    full_review = build_audio_review_presentation(attempt)

    assert attempt.decision.state == expected_state
    assert attempt.decision.primary_reason == expected_reason

    assert full_review.context_lines() == expected_context
    assert full_review.noted_line() == expected_noted
    expected_offset = 0 if resolution == "resolved" else 2
    expected_status = {
        "resolved": "confirmed by video",
        "alternative_confirmed": "confirmed by video",
        "unresolved": "not settled",
        "unexamined": "not checked",
    }[resolution]
    target_region = f"{expected_offset:+d}f  1:00-1:30  {expected_status}"
    panel_target_region = f"{expected_offset:+d}f  1:00–1:30  {expected_status}"
    assert target_region in full_review.region_lines()
    assert panel_target_region in full_review.region_lines(panel=True)
    expected_check_offset = 0 if resolution in {"resolved", "unexamined"} else 2
    expected_check = (
        "1:15  reference 1,800 <-> comparison "
        f"{1_800 - expected_check_offset:,} ({expected_check_offset:+d}f)"
        if resolution != "unexamined"
        else "0:50  reference 1,200 <-> comparison 1,200 (+0f)"
    )
    assert expected_check in full_review.check_point_lines(include_label=False)
    if resolution == "resolved":
        assert "+2f  1:00-1:30  confirmed by video" not in full_review.region_lines()
        assert "comparison 1,798 (+2f)" not in full_review.check_point_lines()

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    applied = expected_state == "trusted_automatic"
    result = AlignmentResult(
        reference.name,
        comparison.name,
        0 if applied else None,
        0.0 if applied else None,
        0.5,
        "cross_correlation",
        "computed",
        applied=applied,
        diagnostic=attempt.decision.primary_reason,
        stability=attempt.stability,
        audio_attempt=attempt,
    )

    _present(request, result, config)
    full_terminal = capsys.readouterr().err

    assert "Picture differs" not in full_terminal
    assert "the picture differs" not in full_terminal
    assert (" · applied" in full_terminal) is applied
    assert (" · not applied" in full_terminal) is (not applied)

    _present(request, result, config, verbose=True)
    verbose_terminal = capsys.readouterr().err
    assert f"Decision: state={expected_state}; reason={expected_reason}" in verbose_terminal
    assert target_region in verbose_terminal
    assert expected_check in verbose_terminal
    assert "Picture differs" not in verbose_terminal
    if expected_noted is None:
        assert "Noted:" not in full_terminal
    else:
        assert expected_noted in full_terminal

    configure_logging("INFO", "json")
    _present(request, result, config, json_output=True)
    json_streams = capsys.readouterr()
    assert json_streams.out == ""
    assert ("audio_alignment_requires_review" in json_streams.err) is (not applied)
    if applied:
        assert json_streams.err == ""
    else:
        assert json.loads(json_streams.err)["reason"] == expected_reason


def test_nonzero_reference_start_shifts_region_times() -> None:
    attempt = producer_target_context_attempt(credible=True, resolution="unresolved")
    reference, comparison = attempt.selected_streams
    attempt = replace(
        attempt,
        selected_streams=(
            replace(reference, stream_start_num=10, stream_start_den=1),
            comparison,
        ),
    )

    review = build_audio_review_presentation(attempt)
    assert "+2f  1:10-1:40  not settled" in review.region_lines()
    assert "+2f  1:10–1:40  not settled" in review.region_lines(panel=True)


def test_resolved_credible_run_context_appears_in_terminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    attempt = producer_run_context_attempt()
    full_review = build_audio_review_presentation(attempt)
    expected_context = ("Audio differed in 1:00-2:00; the video confirmed the offset there.",)
    expected_noted = (
        "Noted: audio differed in 2 sections (1:00-2:00); the video confirmed +0f there."
    )

    assert attempt.decision.state == "trusted_automatic"
    assert attempt.video_check.targets[0].kind == "run"
    assert (
        attempt.video_check.targets[0].first_chunk_index,
        attempt.video_check.targets[0].last_chunk_index,
    ) == (2, 3)
    assert full_review.context_lines() == expected_context
    assert full_review.noted_line() == expected_noted
    assert full_review.noted_line(panel=True) == (
        "Noted: audio differed in 2 sections (1:00–2:00); the video confirmed +0f there."
    )

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    result = _applied_result(reference, comparison, attempt)

    _present(request, result, config)
    full_terminal = capsys.readouterr().err

    assert full_terminal == (
        "comparison: +0f · applied\n"
        "  8 of 10 sections agree · video check +0f · stable\n"
        f"  {expected_noted}\n"
    )

    _present(request, result, config, verbose=True)
    full_verbose = capsys.readouterr().err

    assert f"Context: {expected_context[0]}" in full_verbose
    assert (
        "Decision: state=trusted_automatic; reason=audio_video_confirmed; also=none" in full_verbose
    )


def test_partial_final_target_ends_at_last_sample() -> None:
    attempt = _partial_final_target_attempt()
    full_review = build_audio_review_presentation(attempt)

    assert full_review.reason_lines() == (
        "Audio in 1:00-1:45 points to +243f, and the video could not settle which offset is right there.",
    )
    assert "+243f  1:00-1:45  not settled" in full_review.region_lines()
    assert all("1:00-2:00" not in line for line in full_review.region_lines())


def test_partial_final_run_and_full_track_regions_end_at_last_sample() -> None:
    partial = _partial_final_target_attempt()
    run_attempt = replace(partial, video_check=replace(partial.video_check, targets=()))
    full_attempt = replace(run_attempt, runs=())

    for attempt, expected in (
        (run_attempt, "+243f  1:00-1:45  not settled"),
        (full_attempt, "+146f  0:00-1:45  confirmed by video"),
    ):
        full_regions = build_audio_review_presentation(attempt).region_lines()

        assert expected in full_regions
        assert all("2:00" not in line for line in full_regions)


def test_partial_final_same_frame_region_ends_at_last_sample() -> None:
    partial = _partial_final_target_attempt()
    attempt = replace(
        partial,
        video_check=replace(
            partial.video_check,
            same_frame_context=(AudioSameFrameContext(3, 1177, 146.23, 146),),
        ),
    )

    full_review = build_audio_review_presentation(attempt)

    assert tuple(
        (region.start_seconds, region.end_seconds) for region in full_review.same_frame_regions
    ) == ((90.0, 105.0),)


def test_json_review_diagnostics_stay_on_stderr_and_run_stdout_is_pinned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from frame_compare.utils.progress_protocol import AlignmentSummary, AlignmentSummaryEntry

    configure_logging("INFO", "json")
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    serialized_outputs: list[bytes] = []
    expected_stdout = (
        b'{"cache_hit":false,"clips_processed":0,"duration_seconds":0.0,"errors":[],'
        b'"frame_count":0,"report_path":null,"screenshots_dir":null,"slowpics_url":null,'
        b'"success":true}\n'
    )
    for reason in ("competing_offset", "video_check_inconclusive"):
        attempt = _review_attempt(reason)
        result = AlignmentResult(
            reference_clip=reference.name,
            comparison_clip=comparison.name,
            frame_offset=None,
            time_offset_seconds=None,
            correlation_score=0.5,
            algorithm="cross_correlation",
            source="computed",
            applied=False,
            diagnostic=reason,
            stability=attempt.stability,
            audio_attempt=attempt,
        )

        _present(request, result, config, json_output=True)
        diagnostic = capsys.readouterr()
        assert diagnostic.out == ""
        assert "audio_alignment_requires_review" in diagnostic.err
        assert f'"reason": "{reason}"' in diagnostic.err
        assert reason not in diagnostic.out

        handle_json_output(
            RunResult(
                success=True,
                alignment_summary=AlignmentSummary((AlignmentSummaryEntry("Encode", 0, "audio"),)),
                alignment_diagnostics_dir=tmp_path / "diagnostics",
                warnings=[RunWarning("alignment", "warning", reason)],
            )
        )
        serialized = capsys.readouterr()
        serialized_outputs.append(serialized.out.encode("utf-8"))
        assert serialized.out.encode("utf-8") == expected_stdout
        assert serialized.err == ""

    assert serialized_outputs[0] == serialized_outputs[1]


def test_applied_noted_line_prefers_same_frame_context_over_weak_audio_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    plain = producer_target_context_attempt(credible=False, resolution="unresolved")
    _present(request, _applied_result(reference, comparison, plain), config)
    assert (
        "Noted: weak audio in 1:00-1:30 pointed elsewhere; the video could not settle it, "
        "so it was not counted."
    ) in capsys.readouterr().err

    contextual = producer_target_context_attempt(
        credible=False, resolution="unresolved", first_chunk_lag=80
    )
    assert contextual.video_check.same_frame_context == (AudioSameFrameContext(0, 80, 0.24, 0),)
    assert all(point.reference_frame >= 30 * 24 for point in contextual.video_check.check_points)
    result = _applied_result(reference, comparison, contextual)
    _present(request, result, config)
    err = capsys.readouterr().err
    assert (
        "Noted: audio differed in 1 section (0:00-0:30) by less than a frame (sub-frame); "
        "not a disagreement."
    ) in err
    assert "the video confirmed +0f there" not in err
    assert "Noted: weak audio" not in err

    _present(request, result, config, verbose=True)
    err = capsys.readouterr().err
    assert "1 section differ by less than a frame (sub-frame); not a disagreement." in err
    assert err.count("by less than a frame (sub-frame); not a disagreement.") == 1


def test_p4a_verbose_rows_include_established_context_and_all_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _review_attempt("competing_offset_confirmed_by_video")
    result = AlignmentResult(
        reference_clip=reference.name,
        comparison_clip=comparison.name,
        frame_offset=None,
        time_offset_seconds=None,
        correlation_score=0.5,
        algorithm="cross_correlation",
        source="computed",
        applied=False,
        diagnostic="competing_offset_confirmed_by_video",
        stability=attempt.stability,
        audio_attempt=attempt,
    )

    _present(request, result, config, verbose=True)

    err = capsys.readouterr().err
    assert "Established: Audio: 4 of 4 clear sections agree on +146f" in err
    assert "Video: confirmed +146f at 1 of 1 check points" in err
    assert "Regions: +146f" in err
    assert "Decision: state=provisional; reason=competing_offset_confirmed_by_video" in err
    assert "Check 4:30  reference 6,474 <-> comparison 6,328 (+146f)" in err
    assert "             Video: confirmed +146f" in err
    assert "         +243f" in err
    assert ": Video: confirmed" not in err
    assert ": +243f" not in err
    assert "Check points: Check" not in err


@pytest.mark.parametrize(
    ("planned", "active", "credible", "agreeing", "expected"),
    [
        (
            4,
            4,
            3,
            3,
            "Audio: 3 of 3 clear sections agree on +0f (0 differ; 1 weak, 0 quiet not counted).",
        ),
        (
            4,
            3,
            3,
            3,
            "Audio: 3 of 3 clear sections agree on +0f (0 differ; 0 weak, 1 quiet not counted).",
        ),
        (
            5,
            4,
            3,
            3,
            "Audio: 3 of 3 clear sections agree on +0f (0 differ; 1 weak, 1 quiet not counted).",
        ),
        pytest.param(
            4,
            0,
            0,
            0,
            "Audio: 0 of 0 clear sections agree (0 differ; 0 weak, 4 quiet not counted).",
            id="all-quiet-no-offset",
        ),
    ],
)
def test_established_audio_counts_distinguish_weak_active_from_inactive(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    planned: int,
    active: int,
    credible: int,
    agreeing: int,
    expected: str,
) -> None:
    attempt = _producer_count_attempt(
        planned=planned,
        active=active,
        credible=credible,
        agreeing=agreeing,
    )

    full_review = build_audio_review_presentation(attempt)

    assert full_review.established_audio_line() == expected

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    result = AlignmentResult(
        reference.name,
        comparison.name,
        None,
        None,
        0.5,
        "cross_correlation",
        "computed",
        applied=False,
        diagnostic=attempt.decision.primary_reason,
        stability=attempt.stability,
        audio_attempt=attempt,
    )
    _present(request, result, config, verbose=True)
    full_terminal = capsys.readouterr().err

    assert f"Established: {expected}" in full_terminal
    assert " quiet)." not in full_terminal


def test_verbose_context_rows_use_one_key_and_continuations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _multi_context_attempt()
    result = AlignmentResult(
        reference.name,
        comparison.name,
        None,
        None,
        0.5,
        "cross_correlation",
        "computed",
        applied=False,
        diagnostic="competing_offset_confirmed_by_video",
        stability=attempt.stability,
        audio_attempt=attempt,
    )

    _present(request, result, config, verbose=True)

    err = capsys.readouterr().err
    assert "Context: Audio (raw): 2 of 4 sections agree; 2 more are within the same frame" in err
    assert "         2 sections differ by less than a frame (sub-frame); not a disagreement." in err
    assert err.count("Context:") == 1
    assert ": 2 sections differ by less than a frame" not in err


@pytest.mark.parametrize(
    ("observed", "confirmed", "classification", "video_segment"),
    [
        (True, 146, "stable", " · video check +146f"),
        (True, None, "possible_drift", " · video check inconclusive"),
        (False, None, "insufficient_evidence", ""),
        (False, None, "variable", ""),
    ],
)
def test_normal_audio_evidence_reports_observation_and_stability(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    observed: bool,
    confirmed: int | None,
    classification: str,
    video_segment: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import cast

    from frame_compare.services.alignment_evidence import (
        AlignmentStabilityClassification,
        AudioAuthorityRecount,
    )

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = attempt_with_chunks(2)
    attempt = replace(
        attempt,
        video_check=VideoCheckObservation(
            observation="observed" if observed else "not_observed",
            scored_offsets=(144, 145, 146, 147, 148) if observed else (),
            confirmed_offset=confirmed,
            index_build_seconds=0.0 if observed else None,
            positions=(),
        ),
        stability=replace(
            attempt.stability, classification=cast(AlignmentStabilityClassification, classification)
        ),
    )
    if confirmed is not None:
        attempt = replace(
            attempt,
            chunks=replace(attempt.chunks, agrees=(True, False)),
            audio=replace(attempt.audio, agreeing_chunks=1),
            authority_recount=AudioAuthorityRecount("agreed", 1, "agreed", 2, True),
        )
    result = replace(_provisional_result(reference, comparison), audio_attempt=attempt)
    _present(request, result, config)
    output = capsys.readouterr().err
    assert f"  2 of 2 sections agree{video_segment} · {classification.replace('_', ' ')}" in output
    if not observed:
        assert "video check" not in output

    from io import StringIO

    from rich.console import Console
    from rich.text import Text

    from frame_compare.utils.progress import RichProgressReporter

    rendered = StringIO()
    console = Console(
        file=rendered, width=120, force_terminal=True, color_system="standard", no_color=False
    )
    monkeypatch.setattr(
        "frame_compare.services.alignment_presentation.human_console", lambda **_kwargs: console
    )
    present_alignment_evidence(
        request=request,
        resolutions={
            alignment_key(reference, comparison): ComparisonResolution(
                result, "key", "computed_this_run"
            )
        },
        config=replace(config, no_color=False),
        progress=RichProgressReporter(no_color=True),
        verbose=False,
        quiet=False,
        json_output=False,
        review_pending=True,
    )
    rich_text = rendered.getvalue()
    plain = Text.from_ansi(rich_text).plain
    assert "comparison  +146f · not applied · confirm in VSView" in plain
    assert f"2 of 2 sections agree{video_segment} · {classification.replace('_', ' ')}" in plain
    assert "Align manually or keep the current alignment." not in plain
    evidence_style = Text.from_ansi(rich_text).get_style_at_offset(
        console, plain.index(classification.replace("_", " "))
    )
    assert (evidence_style.color is not None and evidence_style.color.number == 3) is (
        classification in {"possible_drift", "possible_discontinuity", "variable"}
    )


@pytest.mark.parametrize("verbose", [False, True])
def test_audio_evidence_does_not_repeat_completion_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verbose: bool
) -> None:
    from io import StringIO

    from rich.console import Console
    from rich.text import Text

    from frame_compare.utils.progress import RichProgressReporter

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    diagnostics = tmp_path / "generated" / "run" / "alignment_diagnostics"
    request = replace(request, workspace_root=tmp_path, alignment_diagnostics_dir=diagnostics)
    output = StringIO()
    console = Console(file=output, width=120, record=True, no_color=True)
    monkeypatch.setattr(
        "frame_compare.services.alignment_presentation.human_console", lambda **_kwargs: console
    )
    present_alignment_evidence(
        request=request,
        resolutions={
            alignment_key(reference, comparison): ComparisonResolution(
                _provisional_result(reference, comparison), "key", "computed_this_run"
            )
        },
        config=config,
        progress=RichProgressReporter(no_color=True),
        verbose=verbose,
        quiet=False,
        json_output=False,
    )
    plain = Text.from_ansi(output.getvalue()).plain
    assert "Audio alignment" in plain
    assert "alignment_diagnostics" not in plain
