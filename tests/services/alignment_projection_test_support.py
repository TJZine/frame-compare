"""Producer-backed local target and run fixtures shared by alignment review tests."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import frame_compare.services.alignment_video as alignment_video
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
from frame_compare.services.alignment_evidence import (
    VideoCheckObservation,
    VideoPositionDifference,
    VideoTargetEvidence,
    VideoTargetPosition,
)
from tests.services.alignment_evidence_test_support import (
    attempt_with_chunks,
)


def producer_target_context_attempt(*, credible: bool, resolution: str, first_chunk_lag: int = 0):
    observations = tuple(
        ChunkObservation(
            index=index,
            reference_start=index * 240_000,
            reference_count=240_000,
            active=True,
            lag={0: first_chunk_lag, 2: 667}.get(index, 0),
            psr=30.0 if index != 2 or credible else 5.0,
            credible=index != 2 or credible,
            agrees=index != 2 and not (index == 0 and first_chunk_lag),
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
        agreeing_count=sum(item.agrees for item in observations),
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
    producer_targets, same_frame = alignment_video._build_targets(
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
        same_frame_context=same_frame,
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


def producer_run_context_attempt(
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
