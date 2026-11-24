"""Field-level checks for the shared alignment review projection."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

import frame_compare.services.alignment_video as alignment_video
from frame_compare.services.alignment_evidence import (
    AudioChunkRun,
    VideoCheckPoint,
    VideoPositionDifference,
    VideoTargetEvidence,
    VideoTargetPosition,
)
from frame_compare.services.alignment_review_projection import (
    AudioReviewPresentation,
    AudioReviewRegion,
    _review_reason_region,
    build_audio_review_presentation,
)
from tests.alignment_review_scenarios import (
    boundary_video_inconclusive_attempt as _boundary_video_inconclusive_attempt,
)
from tests.alignment_review_scenarios import (
    review_attempt as _review_attempt,
)
from tests.alignment_review_scenarios import (
    singleton_chunk_target_attempt as _singleton_chunk_target_attempt,
)
from tests.services.alignment_projection_test_support import (
    producer_run_context_attempt,
    producer_target_context_attempt,
)


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


def _selected_reason_region(review: AudioReviewPresentation, reason: str) -> AudioReviewRegion:
    assert review.reasons[0] == reason
    region = _review_reason_region(review.regions, review.suggested_offset, reason)
    assert region is not None
    return region


def test_boundary_consensus_does_not_replace_audio_suggestion() -> None:
    review = build_audio_review_presentation(_boundary_video_inconclusive_attempt())

    assert review.suggested_offset == 146
    assert review.reasons == ("video_check_inconclusive",)


def test_early_competing_region_does_not_overlap_majority_region() -> None:
    review = build_audio_review_presentation(_early_competing_run_attempt())

    assert [(r.offset, r.start_seconds, r.end_seconds) for r in review.regions] == [
        (146, 60.0, 120.0),
        (243, 0.0, 60.0),
    ]
    region = _selected_reason_region(review, "competing_offset_confirmed_by_video")
    assert (region.offset, region.status) == (243, "confirmed by video")
    assert region.target_projections == ((("run", 0, 1), "alternative_confirmed"),)


def test_unresolved_reason_prefers_unsettled_region_over_confirmed_region() -> None:
    review = build_audio_review_presentation(_mixed_resolved_unresolved_attempt())

    region = _selected_reason_region(review, "unresolved_audio_disagreement")
    assert (region.offset, region.start_seconds, region.end_seconds) == (246, 60.0, 90.0)
    assert region.status == "not settled"
    assert region.target_projections == ((("chunk", 2, 2), "unresolved"),)


def test_unresolved_reason_skips_earlier_unexamined_region() -> None:
    review = build_audio_review_presentation(_unexamined_before_unresolved_attempt())

    region = _selected_reason_region(review, "unresolved_audio_disagreement")
    assert (region.offset, region.start_seconds, region.end_seconds) == (246, 60.0, 90.0)
    assert region.status == "not settled"
    assert region.target_projections == ((("chunk", 2, 2), "unresolved"),)


def test_chunk_target_identity_survives_singleton_run_projection() -> None:
    review = build_audio_review_presentation(_singleton_chunk_target_attempt())

    region = _selected_reason_region(review, "unresolved_audio_disagreement")
    assert (region.offset, region.start_seconds, region.end_seconds) == (246, 60.0, 90.0)
    assert region.status == "not settled"
    assert region.target_projections == ((("chunk", 2, 2), "unresolved"),)
    assert [r.target_projections for r in review.regions if r.status == "not checked"] == [
        ((("chunk", 0, 0), "unexamined"),)
    ]


def test_nested_alternative_confirmed_chunk_splits_wide_run() -> None:
    attempt = _nested_alternative_confirmed_chunk_attempt()
    review = build_audio_review_presentation(attempt)
    region = _selected_reason_region(review, "competing_offset_confirmed_by_video")

    assert [(r.offset, r.start_seconds, r.end_seconds) for r in review.regions] == [
        (243, 0.0, 60.0),
        (250, 60.0, 90.0),
        (243, 90.0, 120.0),
    ]
    assert (region.offset, region.status) == (250, "confirmed by video")
    assert region.target_projections == (
        (("chunk", 2, 2), "alternative_confirmed"),
        (("run", 0, 3), "unresolved"),
    )

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
        r
        for r in build_audio_review_presentation(resolved_attempt).regions
        if (("chunk", 2, 2), "resolved") in r.target_projections
    )
    assert resolved_region.offset == 146
    assert resolved_region.status == "confirmed by video"


def test_zero_is_retained_as_the_actual_alternative_winner() -> None:
    attempt = producer_target_context_attempt(credible=True, resolution="alternative_confirmed")
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
    region = _selected_reason_region(review, "competing_offset_confirmed_by_video")
    assert (region.offset, region.start_seconds, region.end_seconds) == (0, 60.0, 90.0)
    assert region.status == "confirmed by video"
    assert region.target_projections == ((("chunk", 2, 2), "alternative_confirmed"),)


def test_distinct_position_winners_use_the_selected_checkpoint_offset() -> None:
    attempt = producer_target_context_attempt(credible=True, resolution="alternative_confirmed")
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
    review = build_audio_review_presentation(
        replace(
            attempt,
            video_check=replace(attempt.video_check, targets=(target,), check_points=check_points),
        )
    )

    region = _selected_reason_region(review, "competing_offset_confirmed_by_video")
    assert (region.offset, region.start_seconds, region.end_seconds) == (1, 60.0, 90.0)
    assert region.status == "confirmed by video"
    assert region.target_projections == ((("chunk", 2, 2), "alternative_confirmed"),)
    assert review.check_points == (VideoCheckPoint(100 / 24, 100, 99),)


@pytest.mark.parametrize(
    ("resolution", "reason", "status"),
    [
        ("unresolved", "competing_offset", "not settled"),
        ("unexamined", "competing_offset", "not checked"),
        ("alternative_confirmed", "competing_offset_confirmed_by_video", "confirmed by video"),
    ],
)
def test_nonresolved_credible_runs_never_receive_resolved_context(
    resolution: str, reason: str, status: str
) -> None:
    attempt = producer_run_context_attempt(resolutions=(resolution,))
    review = build_audio_review_presentation(attempt)

    assert attempt.decision.state == "provisional"
    assert review.resolved_regions == ()
    region = _selected_reason_region(review, reason)
    assert (region.offset, region.start_seconds, region.end_seconds, region.status) == (
        2,
        60.0,
        120.0,
        status,
    )
    assert region.target_projections == ((("run", 2, 3), resolution),)


@pytest.mark.parametrize(
    ("shape", "second_bounds", "second_target"),
    [
        ("run_and_chunk", (210.0, 240.0), ("chunk", 7, 7)),
        ("two_runs", (300.0, 360.0), ("run", 10, 11)),
    ],
)
def test_resolved_targets_aggregate_bounds_counts_and_order(
    shape: str, second_bounds: tuple[float, float], second_target: tuple[str, int, int]
) -> None:
    attempt = producer_run_context_attempt(shape=shape, resolutions=("resolved", "resolved"))
    review = build_audio_review_presentation(attempt)

    assert attempt.decision.state == "trusted_automatic"
    assert review.resolved_regions == (
        AudioReviewRegion(0, 60.0, 120.0, "confirmed by video"),
        AudioReviewRegion(0, *second_bounds, "confirmed by video"),
    )
    assert [r.target_projections for r in review.regions if r.target_projections] == [
        ((("run", 2, 3), "resolved"),),
        ((second_target, "resolved"),),
    ]


def test_resolved_chunk_and_run_count_their_authoritative_members() -> None:
    chunk = build_audio_review_presentation(
        producer_target_context_attempt(credible=True, resolution="resolved")
    )
    run = build_audio_review_presentation(producer_run_context_attempt())

    assert chunk.resolved_regions == (AudioReviewRegion(0, 60.0, 90.0, "confirmed by video"),)
    assert [r.target_projections for r in chunk.regions if r.target_projections] == [
        ((("chunk", 2, 2), "resolved"),)
    ]
    assert run.resolved_regions == (AudioReviewRegion(0, 60.0, 120.0, "confirmed by video"),)
    assert [r.target_projections for r in run.regions if r.target_projections] == [
        ((("run", 2, 3), "resolved"),)
    ]


@pytest.mark.parametrize(
    ("reason", "expected_geometry", "expected_target"),
    [
        ("competing_offset", (243, 30.0, 90.0), ("run", 1, 2)),
        ("unresolved_audio_disagreement", (250, 90.0, 120.0), ("chunk", 3, 3)),
    ],
)
def test_reason_target_kind_selects_the_matching_region(
    reason: str, expected_geometry: tuple[int, float, float], expected_target: tuple[str, int, int]
) -> None:
    attempt = _unresolved_run_then_chunk_attempt()
    review = build_audio_review_presentation(
        replace(
            attempt,
            decision=replace(attempt.decision, primary_reason=reason, failed_gates=(reason,)),
        )
    )

    region = _selected_reason_region(review, reason)
    assert (region.offset, region.start_seconds, region.end_seconds) == expected_geometry
    assert region.status == "not settled"
    assert region.target_projections == ((expected_target, "unresolved"),)


def test_competing_reason_selects_the_unexamined_run() -> None:
    review = build_audio_review_presentation(_unexamined_competing_run_attempt())

    region = _selected_reason_region(review, "competing_offset")
    assert (region.offset, region.start_seconds, region.end_seconds) == (243, 60.0, 120.0)
    assert region.status == "not checked"
    assert region.target_projections == ((("run", 2, 3), "unexamined"),)


def test_confirmed_reason_skips_earlier_resolved_region() -> None:
    review = build_audio_review_presentation(_resolved_before_alternative_confirmed_attempt())

    region = _selected_reason_region(review, "competing_offset_confirmed_by_video")
    assert (region.offset, region.start_seconds, region.end_seconds) == (250, 90.0, 120.0)
    assert region.status == "confirmed by video"
    assert region.target_projections == ((("chunk", 3, 3), "alternative_confirmed"),)


def test_video_vote_uses_only_strict_informative_positions() -> None:
    review = build_audio_review_presentation(_strict_video_vote_attempt())

    assert review.suggested_offset == 146
    assert review.video_wins == 6
    assert review.video_informative == 6
    assert review.video_margin == pytest.approx(2.0)


def test_check_points_preserve_five_supplied_positions() -> None:
    attempt = _review_attempt("competing_offset_confirmed_by_video")
    points = tuple(VideoCheckPoint(float(index), 1_000 + index, 854 + index) for index in range(5))
    review = build_audio_review_presentation(
        replace(attempt, video_check=replace(attempt.video_check, check_points=points))
    )

    assert review.check_points == points
