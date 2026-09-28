"""Exact-match tests for frozen audio-alignment terminal strings.

The Align summary fragments, the VSView review-result message, the
manual-review invitation lines, and the provisional/unavailable evidence copy
are user-visible contracts: they must be reproduced verbatim. These tests
assert the exact text through the real render paths (not copies of the
literals).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

import frame_compare.services.alignment_video as alignment_video
import frame_compare.services.alignment_vsview as alignment_vsview
from frame_compare.cli.run_command import handle_json_output
from frame_compare.orchestration import RunResult
from frame_compare.services.alignment import align_clips_from_request as _align_async
from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkObservation,
    ChunkPlan,
    ChunkRun,
)
from frame_compare.services.alignment_decision import (
    decide_after_video,
    decide_completed_stage,
)
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
from frame_compare.utils.alignment_evidence import (
    AudioAuthorityRecount,
    AudioChunkRun,
    AudioSameFrameContext,
    VideoCheckObservation,
    VideoCheckPoint,
    VideoPositionDifference,
    VideoTargetEvidence,
    VideoTargetPosition,
)
from frame_compare.utils.alignment_review_projection import build_audio_review_presentation
from frame_compare.utils.logging import configure_logging
from frame_compare.vsview.adapter import VSViewAvailability, VSViewAvailabilityStatus
from tests.services.alignment_request_test_support import alignment_request
from tests.services.test_alignment_evidence import (
    attempt_with_chunks,
    retimed_comparison_stream,
    stream,
)


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


def _review_attempt(reason: str):
    base = attempt_with_chunks(4)
    alternate_lag = 81_000
    target_resolution = {
        "competing_offset_confirmed_by_video": "alternative_confirmed",
        "competing_offset": "unresolved",
        "unresolved_audio_disagreement": "unresolved",
    }.get(reason)
    chunks = replace(
        base.chunks,
        lags=(1177, 1177, alternate_lag, alternate_lag),
        agrees=(True, True, False, False),
    )
    runs = (
        AudioChunkRun(first_index=0, last_index=1, lag=1177, chunk_count=2),
        AudioChunkRun(first_index=2, last_index=3, lag=alternate_lag, chunk_count=2),
    )
    target = (
        (
            VideoTargetEvidence(
                kind="run",
                first_chunk_index=2,
                last_chunk_index=3,
                credible=True,
                start_sample=(2) * 240_000,
                end_sample=((3) + 1) * 240_000,
                target_offset=243,
                alternative_offsets=(242, 243, 244),
                resolution=target_resolution,  # type: ignore[arg-type]
                positions=(
                    VideoTargetPosition(
                        position_index=1,
                        reference_frame=13_123,
                        confirmed_score=1.0,
                        alternative_score=0.1,
                        winner=(
                            "alternative"
                            if reason == "competing_offset_confirmed_by_video"
                            else "neither"
                        ),
                        alternative_offset=(
                            243 if reason == "competing_offset_confirmed_by_video" else None
                        ),
                    ),
                ),
            ),
        )
        if target_resolution is not None
        else ()
    )
    video = (
        VideoCheckObservation(
            observation="not_observed",
            scored_offsets=(),
            confirmed_offset=None,
            index_build_seconds=None,
            positions=(),
        )
        if reason == "video_check_unavailable"
        else VideoCheckObservation(
            observation="observed",
            scored_offsets=(144, 145, 146, 147, 148),
            confirmed_offset=(None if reason == "video_check_inconclusive" else 146),
            index_build_seconds=0.1,
            positions=(
                VideoPositionDifference(
                    position_index=0,
                    reference_frame=6_474,
                    score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
                ),
            ),
            targets=target,
            check_points=(
                VideoCheckPoint(3661.0, 13_123, 12_880),
                VideoCheckPoint(270.0, 6_474, 6_328),
            ),
        )
    )
    return replace(
        base,
        chunks=chunks,
        runs=runs,
        video_check=video,
        decision=replace(
            base.decision,
            state="provisional",
            primary_reason=reason,
            failed_gates=(reason,),
        ),
    )


def _boundary_video_inconclusive_attempt(*, position_count: int = 6):
    attempt = _review_attempt("video_check_inconclusive")
    positions = tuple(
        VideoPositionDifference(
            position_index=index,
            reference_frame=6_474 + index,
            score_by_offset=(2.0, 1.8, 1.4, 1.2, 0.1),
        )
        for index in range(position_count)
    )
    return replace(attempt, video_check=replace(attempt.video_check, positions=positions))


def _early_competing_run_attempt():
    attempt = _review_attempt("competing_offset_confirmed_by_video")
    target = replace(
        attempt.video_check.targets[0],
        first_chunk_index=0,
        last_chunk_index=1,
        start_sample=0,
        end_sample=480_000,
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(81_000, 81_000, 1177, 1177),
            agrees=(False, False, True, True),
        ),
        runs=(
            AudioChunkRun(first_index=0, last_index=1, lag=81_000, chunk_count=2),
            AudioChunkRun(first_index=2, last_index=3, lag=1177, chunk_count=2),
        ),
        video_check=replace(attempt.video_check, targets=(target,)),
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


def _mixed_resolved_unresolved_attempt():
    attempt = _review_attempt("unresolved_audio_disagreement")
    targets = (
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=1,
            last_chunk_index=1,
            credible=True,
            start_sample=(1) * 240_000,
            end_sample=((1) + 1) * 240_000,
            target_offset=243,
            alternative_offsets=(242, 243, 244),
            resolution="alternative_confirmed",
            positions=(VideoTargetPosition(1, 13_123, 1.0, 0.1, "alternative", 243),),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=2,
            last_chunk_index=2,
            credible=True,
            start_sample=(2) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=246,
            alternative_offsets=(245, 246, 247),
            resolution="unresolved",
            positions=(VideoTargetPosition(2, 9_000, 1.0, 1.0, "neither"),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(1177, 81_000, 82_000, 1177),
            agrees=(True, False, False, True),
        ),
        runs=(
            AudioChunkRun(first_index=0, last_index=0, lag=1177, chunk_count=1),
            AudioChunkRun(first_index=1, last_index=1, lag=81_000, chunk_count=1),
            AudioChunkRun(first_index=2, last_index=2, lag=82_000, chunk_count=1),
            AudioChunkRun(first_index=3, last_index=3, lag=1177, chunk_count=1),
        ),
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


def _unexamined_before_unresolved_attempt():
    attempt = _review_attempt("unresolved_audio_disagreement")
    targets = (
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=1,
            last_chunk_index=1,
            credible=True,
            start_sample=(1) * 240_000,
            end_sample=((1) + 1) * 240_000,
            target_offset=243,
            alternative_offsets=(242, 243, 244),
            resolution="unexamined",
            positions=(),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=2,
            last_chunk_index=2,
            credible=True,
            start_sample=(2) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=246,
            alternative_offsets=(245, 246, 247),
            resolution="unresolved",
            positions=(VideoTargetPosition(2, 9_000, 1.0, 1.0, "neither"),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(1177, 81_000, 82_000, 1177),
            agrees=(True, False, False, True),
        ),
        runs=tuple(
            AudioChunkRun(first_index=index, last_index=index, lag=lag, chunk_count=1)
            for index, lag in enumerate((1177, 81_000, 82_000, 1177))
        ),
        video_check=replace(attempt.video_check, targets=targets),
    )


def _singleton_chunk_target_attempt():
    attempt = _review_attempt("unresolved_audio_disagreement")
    targets = (
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=0,
            last_chunk_index=0,
            credible=True,
            start_sample=(0) * 240_000,
            end_sample=((0) + 1) * 240_000,
            target_offset=243,
            alternative_offsets=(242, 243, 244),
            resolution="unexamined",
            positions=(),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=2,
            last_chunk_index=2,
            credible=True,
            start_sample=(2) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=246,
            alternative_offsets=(245, 246, 247),
            resolution="unresolved",
            positions=(VideoTargetPosition(2, 9_000, 1.0, 1.0, "neither"),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(1177, 81_000, 82_000, 1177),
            agrees=(True, False, False, True),
        ),
        runs=tuple(
            AudioChunkRun(first_index=index, last_index=index, lag=lag, chunk_count=1)
            for index, lag in enumerate((1177, 81_000, 82_000, 1177))
        ),
        video_check=replace(attempt.video_check, targets=targets),
    )


def _nested_alternative_confirmed_chunk_attempt():
    attempt = _review_attempt("competing_offset_confirmed_by_video")
    targets = (
        VideoTargetEvidence(
            kind="run",
            first_chunk_index=0,
            last_chunk_index=3,
            credible=True,
            start_sample=(0) * 240_000,
            end_sample=((3) + 1) * 240_000,
            target_offset=243,
            alternative_offsets=(242, 243, 244),
            resolution="unresolved",
            positions=(VideoTargetPosition(1, 9_000, 1.0, 1.0, "neither"),),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=2,
            last_chunk_index=2,
            credible=True,
            start_sample=(2) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=250,
            alternative_offsets=(249, 250, 251),
            resolution="alternative_confirmed",
            positions=(VideoTargetPosition(2, 9_001, 1.0, 0.1, "alternative", 250),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(81_000, 81_000, 83_333, 81_000),
            credible=(True, True, True, True),
            agrees=(False, False, False, False),
        ),
        runs=(AudioChunkRun(first_index=0, last_index=3, lag=81_000, chunk_count=3),),
        audio=replace(
            attempt.audio,
            global_lag=81_000,
            credible_chunks=4,
            agreeing_chunks=0,
        ),
        video_check=replace(attempt.video_check, targets=targets),
    )


def _production_nested_targets_attempt():
    attempt = _review_attempt("competing_offset")
    targets = (
        VideoTargetEvidence(
            kind="run",
            first_chunk_index=0,
            last_chunk_index=1,
            credible=True,
            start_sample=(0) * 240_000,
            end_sample=((1) + 1) * 240_000,
            target_offset=250,
            alternative_offsets=(249, 250, 251),
            resolution="unresolved",
            positions=(VideoTargetPosition(1, 9_000, 1.0, 1.0, "neither"),),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=2,
            last_chunk_index=2,
            credible=False,
            start_sample=(2) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=246,
            alternative_offsets=(245, 246, 247),
            resolution="unresolved",
            positions=(VideoTargetPosition(2, 9_001, 1.0, 1.0, "neither"),),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=3,
            last_chunk_index=3,
            credible=True,
            start_sample=(3) * 240_000,
            end_sample=((3) + 1) * 240_000,
            target_offset=250,
            alternative_offsets=(249, 250, 251),
            resolution="alternative_confirmed",
            positions=(VideoTargetPosition(3, 9_002, 1.0, 0.1, "alternative", 250),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(81_000, 81_000, 82_000, 83_333),
            credible=(True, True, False, True),
            agrees=(False, False, False, False),
        ),
        runs=(AudioChunkRun(first_index=0, last_index=3, lag=81_000, chunk_count=3),),
        video_check=replace(attempt.video_check, targets=targets),
        decision=replace(
            attempt.decision,
            failed_gates=("competing_offset", "unresolved_audio_disagreement"),
        ),
    )


def _producer_target_context_attempt(*, credible: bool, resolution: str):
    observations = tuple(
        ChunkObservation(
            index=index,
            reference_start=index * 240_000,
            reference_count=240_000,
            active=True,
            lag=667 if index == 2 else 0,
            psr=30.0 if index != 2 or credible else 5.0,
            credible=index != 2 or credible,
            agrees=index != 2,
        )
        for index in range(5)
    )
    estimate = ChunkedAudioEstimate(
        outcome="agreed",
        global_lag=0,
        observations=observations,
        runs=(),
        active_count=5,
        credible_count=sum(item.credible for item in observations),
        agreeing_count=4,
    )
    plan = ChunkPlan(
        chunk_samples=240_000,
        lag_samples=8_000,
        chunks=tuple((index * 240_000, 240_000) for index in range(5)),
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
    base = attempt_with_chunks(5)
    producer_attempt = replace(
        base,
        fps_num=24,
        fps_den=1,
        analysis=stage.analysis,
        chunks=stage.chunks,
        runs=stage.runs,
        audio=stage.audio,
        decision=stage.decision,
        stability=stage.stability,
        authority_recount=stage.authority_recount,
    )
    chunks = alignment_video._chunks(producer_attempt)
    producer_targets, _same_frame = alignment_video._build_targets(
        producer_attempt,
        chunks,
        confirmed=0,
        fps_reference=Fraction(24),
    )
    assert len(producer_targets) == 1
    producer_target = producer_targets[0]
    target_offset = alignment_video._lag_to_frame(
        producer_target.lag,
        attempt=producer_attempt,
        fps_reference=Fraction(24),
    )
    assert target_offset == 2
    scores = {
        "resolved": (0.1, 1.0),
        "unresolved": (1.0, 1.0),
        "alternative_confirmed": (1.0, 0.1),
    }.get(resolution)
    positions = (
        ()
        if scores is None
        else (
            VideoTargetPosition(
                position_index=1,
                reference_frame=1_800,
                confirmed_score=scores[0],
                alternative_score=scores[1],
                winner=alignment_video._hypothesis_winner(*scores),
                alternative_offset=(
                    target_offset if resolution == "alternative_confirmed" else None
                ),
            ),
        )
    )
    target_resolution = (
        "unexamined"
        if resolution == "unexamined"
        else alignment_video._target_resolution(
            producer_target.kind,
            positions,
            credible=producer_target.credible,
        )
    )
    assert target_resolution == (
        "local_video_inconclusive" if not credible and resolution == "unresolved" else resolution
    )
    target = VideoTargetEvidence(
        kind=producer_target.kind,
        first_chunk_index=producer_target.first_index,
        last_chunk_index=producer_target.last_index,
        credible=producer_target.credible,
        start_sample=producer_target.start_sample,
        end_sample=producer_target.end_sample,
        target_offset=target_offset,
        alternative_offsets=(1, 2, 3),
        resolution=target_resolution,
        positions=positions,
    )
    base_positions = (VideoPositionDifference(0, 1_200, (2.0, 1.0, 0.1, 1.0, 2.0)),)
    video = VideoCheckObservation(
        observation="observed",
        scored_offsets=(-2, -1, 0, 1, 2),
        confirmed_offset=0,
        index_build_seconds=0.1,
        positions=base_positions,
        targets=(target,),
        check_points=alignment_video._check_points(
            base_positions,
            (target,),
            confirmed=0,
            scored_offsets=(-2, -1, 0, 1, 2),
            fps_reference=Fraction(24),
            chunks=chunks,
        ),
    )
    decided = decide_after_video(
        stage=stage,
        estimate=estimate,
        plan=plan,
        video=video,
        fps_reference=Fraction(24),
    )
    return replace(
        producer_attempt,
        analysis=decided.analysis,
        chunks=decided.chunks,
        runs=decided.runs,
        audio=decided.audio,
        video_check=decided.video_check,
        decision=decided.decision,
        stability=decided.stability,
        authority_recount=decided.authority_recount,
    )


def _producer_run_context_attempt(
    *, shape: str = "run", resolutions: tuple[str, ...] = ("resolved",)
):
    specs_by_shape = {
        "run": ((2, 3, 667),),
        "run_and_chunk": ((2, 3, 667), (7, 7, 1_000)),
        "two_runs": ((2, 3, 667), (10, 11, 1_000)),
    }
    totals = {"run": 10, "run_and_chunk": 15, "two_runs": 20}
    specs = specs_by_shape[shape]
    assert len(resolutions) == len(specs)
    resolution_by_bounds = {
        (first, last): resolution
        for (first, last, _lag), resolution in zip(specs, resolutions, strict=True)
    }
    lag_by_index = {index: lag for first, last, lag in specs for index in range(first, last + 1)}
    total = totals[shape]
    observations = tuple(
        ChunkObservation(
            index=index,
            reference_start=index * 240_000,
            reference_count=240_000,
            active=True,
            lag=lag_by_index.get(index, 0),
            psr=40.0 - index / 100,
            credible=True,
            agrees=index not in lag_by_index,
        )
        for index in range(total)
    )
    runs: list[ChunkRun] = []
    first = 0
    for index in range(1, total + 1):
        if index < total and observations[index].lag == observations[first].lag:
            continue
        lag = observations[first].lag
        assert lag is not None
        runs.append(ChunkRun(first, index - 1, lag, index - first))
        first = index
    agreeing = total - len(lag_by_index)
    estimate = ChunkedAudioEstimate(
        outcome="agreed",
        global_lag=0,
        observations=observations,
        runs=tuple(runs),
        active_count=total,
        credible_count=total,
        agreeing_count=agreeing,
    )
    plan = ChunkPlan(
        chunk_samples=240_000,
        lag_samples=8_000,
        chunks=tuple((index * 240_000, 240_000) for index in range(total)),
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
    base = attempt_with_chunks(total)
    producer_attempt = replace(
        base,
        fps_num=24,
        fps_den=1,
        analysis=stage.analysis,
        chunks=stage.chunks,
        runs=stage.runs,
        audio=stage.audio,
        decision=stage.decision,
        stability=stage.stability,
        authority_recount=stage.authority_recount,
    )
    chunks = alignment_video._chunks(producer_attempt)
    producer_targets, _same_frame = alignment_video._build_targets(
        producer_attempt,
        chunks,
        confirmed=0,
        fps_reference=Fraction(24),
    )
    assert [(target.first_index, target.last_index) for target in producer_targets] == [
        (first, last) for first, last, _lag in specs
    ]
    next_position = 1
    targets: list[VideoTargetEvidence] = []
    for producer_target in producer_targets:
        resolution = resolution_by_bounds[(producer_target.first_index, producer_target.last_index)]
        target_offset = alignment_video._lag_to_frame(
            producer_target.lag,
            attempt=producer_attempt,
            fps_reference=Fraction(24),
        )
        winner = {
            "resolved": "confirmed",
            "unresolved": "neither",
            "alternative_confirmed": "alternative",
        }.get(resolution)
        position_count = 2 if resolution == "resolved" and producer_target.kind == "run" else 1
        positions = (
            ()
            if winner is None
            else tuple(
                VideoTargetPosition(
                    next_position + offset,
                    2_000 + next_position + offset,
                    0.1 if winner == "confirmed" else 1.0,
                    0.1 if winner == "alternative" else 1.0,
                    winner,  # type: ignore[arg-type]
                    target_offset if winner == "alternative" else None,
                )
                for offset in range(position_count)
            )
        )
        next_position += len(positions)
        target_resolution = (
            "unexamined"
            if resolution == "unexamined"
            else alignment_video._target_resolution(
                producer_target.kind,
                positions,
                credible=producer_target.credible,
            )
        )
        assert target_resolution == resolution
        targets.append(
            VideoTargetEvidence(
                kind=producer_target.kind,
                first_chunk_index=producer_target.first_index,
                last_chunk_index=producer_target.last_index,
                credible=producer_target.credible,
                start_sample=producer_target.start_sample,
                end_sample=producer_target.end_sample,
                target_offset=target_offset,
                alternative_offsets=tuple(
                    offset for offset in range(target_offset - 1, target_offset + 2) if offset != 0
                ),
                resolution=target_resolution,
                positions=positions,
            )
        )
    base_positions = (VideoPositionDifference(0, 1_200, (2.0, 1.0, 0.1, 1.0, 2.0)),)
    video = VideoCheckObservation(
        observation="observed",
        scored_offsets=(-2, -1, 0, 1, 2),
        confirmed_offset=0,
        index_build_seconds=0.1,
        positions=base_positions,
        targets=tuple(targets),
        check_points=alignment_video._check_points(
            base_positions,
            tuple(targets),
            confirmed=0,
            scored_offsets=(-2, -1, 0, 1, 2),
            fps_reference=Fraction(24),
            chunks=chunks,
        ),
    )
    decided = decide_after_video(
        stage=stage,
        estimate=estimate,
        plan=plan,
        video=video,
        fps_reference=Fraction(24),
    )
    return replace(
        producer_attempt,
        analysis=decided.analysis,
        chunks=decided.chunks,
        runs=decided.runs,
        audio=decided.audio,
        video_check=decided.video_check,
        decision=decided.decision,
        stability=decided.stability,
        authority_recount=decided.authority_recount,
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


def _unresolved_run_then_chunk_attempt():
    attempt = _review_attempt("competing_offset")
    targets = (
        VideoTargetEvidence(
            kind="run",
            first_chunk_index=1,
            last_chunk_index=2,
            credible=True,
            start_sample=(1) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=243,
            alternative_offsets=(242, 243, 244),
            resolution="unresolved",
            positions=(VideoTargetPosition(1, 9_000, 1.0, 1.0, "neither"),),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=3,
            last_chunk_index=3,
            credible=True,
            start_sample=(3) * 240_000,
            end_sample=((3) + 1) * 240_000,
            target_offset=250,
            alternative_offsets=(249, 250, 251),
            resolution="unresolved",
            positions=(VideoTargetPosition(2, 9_001, 1.0, 1.0, "neither"),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(1177, 81_000, 81_000, 83_333),
            agrees=(True, False, False, False),
        ),
        runs=(
            AudioChunkRun(first_index=0, last_index=0, lag=1177, chunk_count=1),
            AudioChunkRun(first_index=1, last_index=2, lag=81_000, chunk_count=2),
            AudioChunkRun(first_index=3, last_index=3, lag=83_333, chunk_count=1),
        ),
        video_check=replace(attempt.video_check, targets=targets),
    )


def _unexamined_competing_run_attempt():
    attempt = _review_attempt("competing_offset")
    target = replace(attempt.video_check.targets[0], resolution="unexamined", positions=())
    return replace(attempt, video_check=replace(attempt.video_check, targets=(target,)))


def _resolved_before_alternative_confirmed_attempt():
    attempt = _review_attempt("competing_offset_confirmed_by_video")
    targets = (
        VideoTargetEvidence(
            kind="run",
            first_chunk_index=1,
            last_chunk_index=2,
            credible=True,
            start_sample=(1) * 240_000,
            end_sample=((2) + 1) * 240_000,
            target_offset=243,
            alternative_offsets=(242, 243, 244),
            resolution="resolved",
            positions=(
                VideoTargetPosition(1, 9_000, 0.1, 1.0, "confirmed"),
                VideoTargetPosition(2, 9_001, 0.1, 1.0, "confirmed"),
            ),
        ),
        VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=3,
            last_chunk_index=3,
            credible=True,
            start_sample=(3) * 240_000,
            end_sample=((3) + 1) * 240_000,
            target_offset=250,
            alternative_offsets=(249, 250, 251),
            resolution="alternative_confirmed",
            positions=(VideoTargetPosition(3, 9_002, 1.0, 0.1, "alternative", 250),),
        ),
    )
    return replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(1177, 81_000, 81_000, 83_333),
            agrees=(True, False, False, True),
        ),
        runs=(
            AudioChunkRun(first_index=0, last_index=0, lag=1177, chunk_count=1),
            AudioChunkRun(first_index=1, last_index=2, lag=81_000, chunk_count=2),
        ),
        video_check=replace(attempt.video_check, targets=targets),
    )


def _multi_context_attempt():
    attempt = _review_attempt("competing_offset_confirmed_by_video")
    return replace(
        attempt,
        audio=replace(attempt.audio, agreeing_chunks=2),
        authority_recount=AudioAuthorityRecount(
            raw_status="agreed",
            raw_agreeing_chunks=2,
            authority_status="agreed",
            authority_agreeing_chunks=4,
            passed=True,
        ),
        video_check=replace(
            attempt.video_check,
            same_frame_context=(
                AudioSameFrameContext(0, 1177, 146.23, 146),
                AudioSameFrameContext(1, 1177, 146.23, 146),
            ),
        ),
    )


def _audio_failed_video_confirmed_attempt():
    attempt = _review_attempt("video_check_inconclusive")
    return replace(
        attempt,
        audio=replace(attempt.audio, status="no_single_offset", agreeing_chunks=2),
        video_check=replace(attempt.video_check, confirmed_offset=146, targets=()),
        decision=replace(
            attempt.decision,
            primary_reason="no_single_offset",
            failed_gates=("no_single_offset",),
        ),
    )


def _strict_video_vote_attempt():
    attempt = _review_attempt("competing_offset_confirmed_by_video")
    positions = tuple(
        VideoPositionDifference(
            position_index=index,
            reference_frame=6_474 + index,
            score_by_offset=(2.0, 1.2, 0.5, 1.0, 2.0),
        )
        for index in range(6)
    ) + (
        VideoPositionDifference(
            position_index=6,
            reference_frame=6_480,
            score_by_offset=(0.0, 0.0, 0.0, 0.0, 0.0),
        ),
    )
    return replace(attempt, video_check=replace(attempt.video_check, positions=positions))


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
    assert (
        "Audio suggests +146 frames, but Frame Compare could not verify it against the pictures. "
        "No automatic change was made. Open VSView to check the lineup."
    ) in err


def test_inconclusive_copy_reports_a_strong_boundary_hint_without_confirming_it() -> None:
    review = build_audio_review_presentation(_boundary_video_inconclusive_attempt())

    assert review.reason_lines() == (
        "The sound and picture suggest different starting points. Audio suggests +146 frames; "
        "the checked scenes favor +148 frames. No automatic change was made. Open VSView to "
        "choose the frame where the pictures line up.",
    )


def test_inconclusive_copy_does_not_report_boundary_hint_with_four_positions() -> None:
    review = build_audio_review_presentation(_boundary_video_inconclusive_attempt(position_count=4))

    assert review.reason_lines() == (
        "Audio suggests +146 frames, but Frame Compare could not verify it against the pictures. "
        "No automatic change was made. Open VSView to check the lineup.",
    )


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
    assert "whole-track-chunked-phat-video-check-retimed-20260928" in err


def test_verbose_provisional_shows_retimed_context(
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
    _present(request, result, config, verbose=True)

    err = capsys.readouterr().err
    assert "Context: Comparison audio retimed x1.0417 to its effective frame rate." in err

    _present(request, result, config)
    assert "retimed" not in capsys.readouterr().err


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
            "Audio suggests +146 frames, but Frame Compare could not verify it against the pictures.",
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
    assert "Comparison 1 - Provisional audio candidate: +146f - NOT APPLIED" in err
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


def test_early_competing_region_does_not_overlap_majority_region(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _early_competing_run_attempt()
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

    _present(request, result, config)
    err = capsys.readouterr().err
    assert "+146f  1:00-2:00" in err
    assert "+243f  0:00-1:00" in err
    assert "+146f  0:00-2:00" not in err


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


def test_unresolved_reason_prefers_unsettled_region_over_confirmed_region(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _mixed_resolved_unresolved_attempt()
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
    assert "Audio in 1:00-1:30 points to +246f, and the video could not rule that out." in err
    assert "Audio in 0:30-1:00 points to +243f, and the video could not rule that out." not in err


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


def test_unresolved_reason_skips_earlier_unexamined_region(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _unexamined_before_unresolved_attempt()
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
    assert "Audio in 1:00-1:30 points to +246f, and the video could not rule that out." in err
    assert "Audio in 0:30-1:00 points to +243f, and the video could not rule that out." not in err


def test_chunk_target_identity_survives_singleton_run_projection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _singleton_chunk_target_attempt()
    review = build_audio_review_presentation(attempt)
    region = next(region for region in review.regions if region.offset == 246)

    assert region.target_projections == ((("chunk", 2, 2), "unresolved"),)

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
    assert "Audio in 1:00-1:30 points to +246f, and the video could not rule that out." in err
    assert "Audio in 1 more section points elsewhere; they were not checked" in err


def test_nested_alternative_confirmed_chunk_splits_wide_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _nested_alternative_confirmed_chunk_attempt()
    review = build_audio_review_presentation(attempt)
    region = next(region for region in review.regions if region.offset == 250)

    assert (region.start_seconds, region.end_seconds) == (60.0, 90.0)
    assert region.status == "confirmed by video"
    assert (("chunk", 2, 2), "alternative_confirmed") in region.target_projections

    resolved_target = replace(
        attempt.video_check.targets[1],
        resolution="resolved",
        positions=(VideoTargetPosition(2, 9_001, 0.1, 1.0, "confirmed"),),
    )
    resolved_attempt = replace(
        attempt,
        video_check=replace(
            attempt.video_check,
            targets=(attempt.video_check.targets[0], resolved_target),
        ),
    )
    resolved_region = next(
        region
        for region in build_audio_review_presentation(resolved_attempt).regions
        if (("chunk", 2, 2), "resolved") in region.target_projections
    )
    assert resolved_region.offset == 146
    assert resolved_region.status == "confirmed by video"

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
    _present(request, result, config)

    err = capsys.readouterr().err
    assert (
        "The video confirms +250f in 1:00-1:30, so the sources likely differ by an edit there."
        in err
    )
    assert "The video confirms +243f" not in err


def test_authoritative_nested_targets_match_compact_native_projection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    attempt = _production_nested_targets_attempt()
    compact = _project_audio_attempt_for_review(attempt)
    full_review = build_audio_review_presentation(attempt)
    compact_review = build_audio_review_presentation(compact)
    expected_reasons = (
        "Audio in 0:00-1:00 points to +250f, and the video could not settle which offset is right there.",
        "Audio in 1:00-1:30 points to +246f, and the video could not rule that out.",
    )
    expected_regions = (
        "+250f  0:00-1:00  not settled",
        "+246f  1:00-1:30  not settled",
        "+250f  1:30-2:00  confirmed by video",
    )

    assert compact.chunks.rows_omitted is True
    assert compact.chunks.total_samples == attempt.chunks.total_samples
    assert full_review.attempt.video_check.targets == compact_review.attempt.video_check.targets
    assert full_review.suggested_offset == compact_review.suggested_offset == 146
    assert full_review.reason_lines() == compact_review.reason_lines() == expected_reasons
    assert full_review.region_lines() == compact_review.region_lines() == expected_regions
    assert full_review.context_lines() == compact_review.context_lines()
    assert full_review.noted_line() == compact_review.noted_line()
    assert full_review.verbose_rows() == compact_review.verbose_rows()
    assert full_review.verbose_rows(panel=True) == compact_review.verbose_rows(panel=True)

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
    compact_unexamined = _project_audio_attempt_for_review(unexamined)
    assert build_audio_review_presentation(unexamined).region_lines() == (
        build_audio_review_presentation(compact_unexamined).region_lines()
    )
    assert (
        "+250f  1:00-1:30  not checked"
        in build_audio_review_presentation(compact_unexamined).region_lines()
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
def test_target_context_and_terminal_rows_match_compact_native_projection(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    credible: bool,
    resolution: str,
    expected_state: str,
    expected_reason: str,
    expected_context: tuple[str, ...],
    expected_noted: str | None,
) -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    attempt = _producer_target_context_attempt(credible=credible, resolution=resolution)
    compact = _project_audio_attempt_for_review(attempt)
    full_review = build_audio_review_presentation(attempt)
    compact_review = build_audio_review_presentation(compact)

    assert attempt.decision.state == expected_state
    assert attempt.decision.primary_reason == expected_reason
    assert compact.decision == attempt.decision
    assert compact.chunks.rows_omitted is True
    assert compact.chunks.total_samples == attempt.chunks.total_samples
    assert full_review.context_lines() == compact_review.context_lines() == expected_context
    assert full_review.context_lines(panel=True) == compact_review.context_lines(panel=True)
    assert full_review.noted_line() == compact_review.noted_line() == expected_noted
    assert full_review.noted_line(panel=True) == compact_review.noted_line(panel=True)
    assert full_review.normal_review_rows(
        panel=False, action_line="Align manually or keep the current alignment."
    ) == compact_review.normal_review_rows(
        panel=False, action_line="Align manually or keep the current alignment."
    )
    assert full_review.verbose_rows() == compact_review.verbose_rows()
    assert full_review.verbose_rows(panel=True) == compact_review.verbose_rows(panel=True)
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
    assert full_review.region_lines() == compact_review.region_lines()
    assert panel_target_region in full_review.region_lines(panel=True)
    assert full_review.region_lines(panel=True) == compact_review.region_lines(panel=True)
    expected_check_offset = 0 if resolution in {"resolved", "unexamined"} else 2
    expected_check = (
        "1:15  reference 1,800 <-> comparison "
        f"{1_800 - expected_check_offset:,} ({expected_check_offset:+d}f)"
        if resolution != "unexamined"
        else "0:50  reference 1,200 <-> comparison 1,200 (+0f)"
    )
    assert expected_check in full_review.check_point_lines(include_label=False)
    assert full_review.check_point_lines() == compact_review.check_point_lines()
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
    compact_result = replace(result, audio_attempt=compact)
    _present(request, result, config)
    full_terminal = capsys.readouterr().err
    _present(request, compact_result, config)
    assert capsys.readouterr().err == full_terminal
    assert "Picture differs" not in full_terminal
    assert "the picture differs" not in full_terminal
    assert (" - APPLIED" in full_terminal) is applied
    assert (" - NOT APPLIED" in full_terminal) is (not applied)

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


def test_nonzero_reference_start_shifts_full_and_compact_region_times() -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    attempt = _producer_target_context_attempt(credible=True, resolution="unresolved")
    reference, comparison = attempt.selected_streams
    attempt = replace(
        attempt,
        selected_streams=(
            replace(reference, stream_start_num=10, stream_start_den=1),
            comparison,
        ),
    )
    compact = _project_audio_attempt_for_review(attempt)

    for candidate in (attempt, compact):
        review = build_audio_review_presentation(candidate)
        assert "+2f  1:10-1:40  not settled" in review.region_lines()
        assert "+2f  1:10–1:40  not settled" in review.region_lines(panel=True)


def test_zero_is_retained_as_the_actual_alternative_winner() -> None:
    attempt = _producer_target_context_attempt(credible=True, resolution="alternative_confirmed")
    (target,) = attempt.video_check.targets
    (position,) = target.positions
    target = replace(
        target,
        target_offset=0,
        alternative_offsets=(-1, 0, 1),
        positions=(replace(position, alternative_offset=0),),
    )
    attempt = replace(
        attempt,
        video_check=replace(
            attempt.video_check,
            scored_offsets=(0, 1, 2, 3, 4),
            confirmed_offset=2,
            targets=(target,),
        ),
    )

    review = build_audio_review_presentation(attempt)
    assert any(region.offset == 0 for region in review.regions)
    assert review.reason_lines() == (
        "The video confirms +0f in 1:00-1:30, so the sources likely differ by an edit there.",
    )


def test_distinct_position_winners_use_the_selected_checkpoint_offset() -> None:
    attempt = _producer_target_context_attempt(credible=True, resolution="alternative_confirmed")
    (target,) = attempt.video_check.targets
    (position,) = target.positions
    target = replace(
        target,
        target_offset=2,
        alternative_offsets=(1, 2, 3),
        positions=(
            replace(position, reference_frame=100, alternative_offset=1),
            replace(position, position_index=13, reference_frame=120, alternative_offset=3),
        ),
    )
    check_points = alignment_video._check_points(
        (),
        (target,),
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=Fraction(24),
    )
    attempt = replace(
        attempt,
        video_check=replace(attempt.video_check, targets=(target,), check_points=check_points),
    )

    review = build_audio_review_presentation(attempt)
    assert review.reason_lines() == (
        "The video confirms +1f in 1:00-1:30, so the sources likely differ by an edit there.",
    )
    assert any(line.startswith("+1f") for line in review.region_lines())
    assert review.check_point_lines() == ("Check 0:04  reference 100 <-> comparison 99 (+1f)",)


def test_resolved_credible_run_context_matches_full_and_compact_terminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    attempt = _producer_run_context_attempt()
    compact = _project_audio_attempt_for_review(attempt)
    full_review = build_audio_review_presentation(attempt)
    compact_review = build_audio_review_presentation(compact)
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
    assert full_review.context_lines() == compact_review.context_lines() == expected_context
    assert full_review.noted_line() == compact_review.noted_line() == expected_noted
    assert full_review.noted_line(panel=True) == (
        "Noted: audio differed in 2 sections (1:00–2:00); the video confirmed +0f there."
    )

    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    result = _applied_result(reference, comparison, attempt)
    compact_result = replace(result, audio_attempt=compact)
    _present(request, result, config)
    full_terminal = capsys.readouterr().err
    _present(request, compact_result, config)
    assert capsys.readouterr().err == full_terminal
    assert full_terminal == (
        "Comparison 1 - Audio alignment accepted: +0f - APPLIED\n"
        "No additional confirmation needed.\n"
        f"{expected_noted}\n"
    )

    _present(request, result, config, verbose=True)
    full_verbose = capsys.readouterr().err
    _present(request, compact_result, config, verbose=True)
    assert capsys.readouterr().err == full_verbose
    assert f"Context: {expected_context[0]}" in full_verbose
    assert (
        "Decision: state=trusted_automatic; reason=audio_video_confirmed; also=none" in full_verbose
    )


@pytest.mark.parametrize(
    ("resolution", "state", "reason"),
    [
        ("unresolved", "provisional", "competing_offset"),
        ("unexamined", "provisional", "competing_offset"),
        (
            "alternative_confirmed",
            "provisional",
            "competing_offset_confirmed_by_video",
        ),
    ],
)
def test_nonresolved_credible_runs_never_receive_resolved_context(
    resolution: str, state: str, reason: str
) -> None:
    attempt = _producer_run_context_attempt(resolutions=(resolution,))
    review = build_audio_review_presentation(attempt)

    assert attempt.decision.state == state
    assert attempt.decision.primary_reason == reason
    expected = (
        ("Local video inconclusive in 1:00-2:00 (+0f scored 1.000, +2f scored 1.000).",)
        if resolution == "unresolved"
        else ()
    )
    assert review.context_lines() == expected
    assert review.noted_line() is None


@pytest.mark.parametrize(
    ("shape", "expected_context", "expected_noted"),
    [
        (
            "run_and_chunk",
            (
                "Audio differed in 1:00-2:00; the video confirmed the offset there.",
                "Audio differed in 3:30-4:00; the video confirmed the offset there.",
            ),
            "Noted: audio differed in 3 sections (1:00-2:00, 3:30-4:00); the video confirmed +0f there.",
        ),
        (
            "two_runs",
            (
                "Audio differed in 1:00-2:00; the video confirmed the offset there.",
                "Audio differed in 5:00-6:00; the video confirmed the offset there.",
            ),
            "Noted: audio differed in 4 sections (1:00-2:00, 5:00-6:00); the video confirmed +0f there.",
        ),
    ],
)
def test_resolved_targets_aggregate_bounds_counts_and_order(
    shape: str, expected_context: tuple[str, ...], expected_noted: str
) -> None:
    attempt = _producer_run_context_attempt(shape=shape, resolutions=("resolved", "resolved"))
    review = build_audio_review_presentation(attempt)

    assert attempt.decision.state == "trusted_automatic"
    assert review.context_lines() == expected_context
    assert review.noted_line() == expected_noted


def test_resolved_chunk_and_run_count_their_authoritative_members() -> None:
    chunk = build_audio_review_presentation(
        _producer_target_context_attempt(credible=True, resolution="resolved")
    )
    run = build_audio_review_presentation(_producer_run_context_attempt())

    assert chunk.noted_line() == (
        "Noted: audio differed in 1 section (1:00-1:30); the video confirmed +0f there."
    )
    assert run.noted_line() == (
        "Noted: audio differed in 2 sections (1:00-2:00); the video confirmed +0f there."
    )


def test_partial_final_target_bounds_match_compact_native_projection() -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    attempt = _partial_final_target_attempt()
    compact = _project_audio_attempt_for_review(attempt)
    full_review = build_audio_review_presentation(attempt)
    compact_review = build_audio_review_presentation(compact)

    assert (
        full_review.reason_lines()
        == compact_review.reason_lines()
        == (
            "Audio in 1:00-1:45 points to +243f, and the video could not settle which offset is right there.",
        )
    )
    assert full_review.region_lines() == compact_review.region_lines()
    assert "+243f  1:00-1:45  not settled" in compact_review.region_lines()
    assert all("1:00-2:00" not in line for line in compact_review.region_lines())


def test_partial_final_base_regions_match_compact_native_projection() -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    partial = _partial_final_target_attempt()
    run_attempt = replace(partial, video_check=replace(partial.video_check, targets=()))
    full_attempt = replace(run_attempt, runs=())

    for attempt, expected in (
        (run_attempt, "+243f  1:00-1:45  not settled"),
        (full_attempt, "+146f  0:00-1:45  confirmed by video"),
    ):
        compact = _project_audio_attempt_for_review(attempt)
        full_regions = build_audio_review_presentation(attempt).region_lines()
        compact_regions = build_audio_review_presentation(compact).region_lines()

        assert compact.chunks.rows_omitted is True
        assert compact.chunks.total_samples == attempt.chunks.total_samples
        assert full_regions == compact_regions
        assert expected in compact_regions
        assert all("2:00" not in line for line in compact_regions)


def test_partial_final_same_frame_context_matches_compact_native_projection() -> None:
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    partial = _partial_final_target_attempt()
    attempt = replace(
        partial,
        video_check=replace(
            partial.video_check,
            same_frame_context=(AudioSameFrameContext(3, 1177, 146.23, 146),),
        ),
    )
    compact = _project_audio_attempt_for_review(attempt)
    full_review = build_audio_review_presentation(attempt)
    compact_review = build_audio_review_presentation(compact)

    assert compact.chunks.rows_omitted is True
    assert compact.chunks.total_samples == attempt.chunks.total_samples
    assert full_review.same_frame_regions == compact_review.same_frame_regions
    assert tuple(
        (region.start_seconds, region.end_seconds) for region in compact_review.same_frame_regions
    ) == ((90.0, 105.0),)


@pytest.mark.parametrize(
    ("reason", "expected", "not_expected"),
    [
        (
            "competing_offset",
            "Audio in 0:30-1:30 points to +243f, and the video could not settle which offset is right there.",
            "Audio in 1:30-2:00 points to +250f, and the video could not settle which offset is right there.",
        ),
        (
            "unresolved_audio_disagreement",
            "Audio in 1:30-2:00 points to +250f, and the video could not rule that out.",
            "Audio in 0:30-1:30 points to +243f, and the video could not rule that out.",
        ),
    ],
)
def test_reason_target_kind_selects_the_matching_region(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    reason: str,
    expected: str,
    not_expected: str,
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _unresolved_run_then_chunk_attempt()
    attempt = replace(
        attempt,
        decision=replace(
            attempt.decision,
            primary_reason=reason,
            failed_gates=(reason,),
        ),
    )
    result = AlignmentResult(
        reference.name,
        comparison.name,
        None,
        None,
        0.5,
        "cross_correlation",
        "computed",
        applied=False,
        diagnostic=reason,
        stability=attempt.stability,
        audio_attempt=attempt,
    )

    _present(request, result, config)

    err = capsys.readouterr().err
    assert expected in err
    assert not_expected not in err


def test_unexamined_competing_run_has_the_competing_reason_sentence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _unexamined_competing_run_attempt()
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

    assert (
        "Audio in 1:00-2:00 points to +243f, and the video could not settle which offset is right there."
        in capsys.readouterr().err
    )


def test_confirmed_reason_skips_earlier_resolved_region(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    attempt = _resolved_before_alternative_confirmed_attempt()
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

    _present(request, result, config)

    err = capsys.readouterr().err
    assert (
        "The video confirms +250f in 1:30-2:00, so the sources likely differ by an edit there."
        in err
    )
    assert (
        "The video confirms +243f in 0:30-1:30, so the sources likely differ by an edit there."
        not in err
    )


def test_json_review_diagnostics_stay_on_stderr_and_run_stdout_is_pinned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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

        handle_json_output(RunResult(success=True, warnings=[reason]))
        serialized = capsys.readouterr()
        serialized_outputs.append(serialized.out.encode("utf-8"))
        assert serialized.out.encode("utf-8") == expected_stdout
        assert serialized.err == ""

    assert serialized_outputs[0] == serialized_outputs[1]


def test_video_vote_uses_only_strict_informative_positions() -> None:
    review = build_audio_review_presentation(_strict_video_vote_attempt())
    assert review.video_wins == 6
    assert review.video_informative == 6
    assert review.video_margin == pytest.approx(2.0)
    assert review.established_video_line() == (
        "Video: confirmed +146f at 6 of 7 check points (median margin 2.0x)."
    )


def test_check_points_preserve_order_and_cap_at_five() -> None:
    attempt = _review_attempt("competing_offset_confirmed_by_video")
    points = tuple(VideoCheckPoint(float(index), 1_000 + index, 854 + index) for index in range(5))
    review = build_audio_review_presentation(
        replace(attempt, video_check=replace(attempt.video_check, check_points=points))
    )
    assert len(review.check_points) == 5
    assert [point.reference_frame for point in review.check_points] == [
        1_000,
        1_001,
        1_002,
        1_003,
        1_004,
    ]


def test_applied_noted_line_only_exists_with_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = AlignmentConfig(cache_results=False, no_color=True)
    reference, comparison, request = _request_for(tmp_path, config)
    plain = _producer_target_context_attempt(credible=False, resolution="unresolved")
    _present(request, _applied_result(reference, comparison, plain), config)
    assert (
        "Noted: weak audio in 1:00-1:30 pointed elsewhere; the video could not settle it, "
        "so it was not counted."
    ) in capsys.readouterr().err

    contextual = replace(
        plain,
        video_check=replace(
            plain.video_check,
            same_frame_context=(
                AudioSameFrameContext(0, 0, 0.0, 0),
                AudioSameFrameContext(1, 0, 0.0, 0),
            ),
        ),
    )
    _present(request, _applied_result(reference, comparison, contextual), config)
    err = capsys.readouterr().err
    assert "Noted: audio differed in 2 sections (0:00-0:30, 0:30-1:00);" in err


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
        (
            4,
            0,
            0,
            0,
            "Audio: 0 of 0 clear sections agree on +0f (0 differ; 0 weak, 4 quiet not counted).",
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
    from frame_compare.services.alignment import _project_audio_attempt_for_review

    attempt = _producer_count_attempt(
        planned=planned,
        active=active,
        credible=credible,
        agreeing=agreeing,
    )
    compact = _project_audio_attempt_for_review(attempt)
    full_review = build_audio_review_presentation(attempt)
    compact_review = build_audio_review_presentation(compact)

    assert full_review.established_audio_line() == expected
    assert compact_review.established_audio_line() == expected
    assert full_review.verbose_rows() == compact_review.verbose_rows()

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
    _present(request, replace(result, audio_attempt=compact), config, verbose=True)
    assert capsys.readouterr().err == full_terminal
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
