"""Search-boundary rejection must not imply that a consistent offset varies."""

from __future__ import annotations

from fractions import Fraction

import pytest

from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkObservation,
    ChunkPlan,
    ChunkRun,
)
from frame_compare.services.alignment_decision import (
    decide_completed_stage,
    recount_audio_authority,
)


@pytest.mark.parametrize("lag", [-7990, 7990])
@pytest.mark.parametrize("chunk_count", [1, 2, 3])
def test_consistent_search_edge_is_stable_but_not_authoritative(
    lag: int, chunk_count: int
) -> None:
    chunk_samples = 40_000
    fps = Fraction(24)
    observations = tuple(
        ChunkObservation(
            index=index,
            reference_start=index * chunk_samples,
            reference_count=chunk_samples,
            active=True,
            lag=lag,
            psr=40.0,
            credible=True,
            agrees=True,
        )
        for index in range(chunk_count)
    )
    plan = ChunkPlan(
        chunk_samples=chunk_samples,
        lag_samples=8000,
        chunks=tuple((item.reference_start, item.reference_count) for item in observations),
    )
    estimate = ChunkedAudioEstimate(
        outcome="search_edge",
        global_lag=lag,
        observations=observations,
        runs=(ChunkRun(0, chunk_count - 1, lag, chunk_count),),
        active_count=chunk_count,
        credible_count=chunk_count,
        agreeing_count=chunk_count,
    )
    stage = decide_completed_stage(
        estimate=estimate,
        plan=plan,
        max_offset_seconds=1.0,
        reference_audio_start=Fraction(0),
        reference_video_start=Fraction(0),
        comparison_audio_start=Fraction(0),
        comparison_video_start=Fraction(0),
        fps_reference=fps,
    )
    expected_frame = -24 if lag < 0 else 24
    recount = recount_audio_authority(
        estimate=estimate,
        plan=plan,
        confirmed_offset=expected_frame,
        fps_reference=fps,
        compensation_seconds=0.0,
    )

    assert stage.audio.status == "search_edge"
    assert stage.decision.state == "unavailable"
    assert stage.decision.primary_reason == "search_edge"
    assert stage.decision.failed_gates == ("search_edge",)
    assert stage.decision.candidate is None
    assert recount.authority_status == "search_edge"
    assert recount.passed is False
    assert stage.stability.classification == "stable"
    assert stage.stability.valid_windows == chunk_count
    assert stage.stability.offset_min_frames == expected_frame
    assert stage.stability.offset_max_frames == expected_frame
    assert stage.stability.largest_adjacent_jump_frames == 0
