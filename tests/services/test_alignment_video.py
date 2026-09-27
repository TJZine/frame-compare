"""Focused V1-V7 tests using generated VapourSynth clips."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from threading import Event
from typing import Literal

import numpy as np
import pytest
import vapoursynth as vs

from frame_compare.services import alignment_video
from frame_compare.services.alignment_video import VideoClipRequest
from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    AudioChunkColumns,
    AudioChunkRun,
    AudioStageOutcome,
    VideoCheckObservation,
)
from frame_compare.utils.types import AlignmentClipIdentity
from frame_compare.vs.types import SourceInfo
from tests.services.test_alignment_evidence import attempt_with_chunks

FPS = Fraction(24, 1)


def _moving_clip(
    *, frames: int = 60, transform: Callable[[int], int] | None = None
) -> vs.VideoNode:
    core = vs.core
    rows: list[vs.VideoNode] = []
    for row in range(4):
        tiles = []
        for column in range(8):
            value = ((column + row * 3) * 31) % 256
            tiles.append(
                core.std.BlankClip(
                    width=8,
                    height=9,
                    length=1,
                    format=vs.GRAYS,
                    color=(transform(value) if transform is not None else value),
                )
            )
        rows.append(core.std.StackHorizontal(tiles))
    pattern = core.std.StackVertical(rows)
    wide = core.std.StackHorizontal([pattern, pattern])
    return core.std.Splice(
        [wide.std.Crop(left=index % 7, right=64 - index % 7) for index in range(frames)]
    )


def _shifted_clip(reference: vs.VideoNode, offset: int) -> vs.VideoNode:
    if offset >= 0:
        return reference[offset:]
    return vs.core.std.Splice(
        [reference[0:1]] * -offset + [reference[: reference.num_frames + offset]]
    )


def _source(path: Path, clip: vs.VideoNode) -> SourceInfo:
    return SourceInfo(
        clip=clip,
        width=clip.width,
        height=clip.height,
        num_frames=clip.num_frames,
        fps=FPS,
        format=clip.format,
        frame_props={},
        is_hdr=False,
        hdr_metadata=None,
    )


class _Loader:
    def __init__(self, clips: dict[Path, vs.VideoNode]) -> None:
        self.clips = clips
        self.calls: list[Path] = []
        self.after_load: Callable[[Path], None] | None = None

    def load(self, path: Path) -> SourceInfo:
        self.calls.append(path)
        if self.after_load is not None:
            self.after_load(path)
        return _source(path, self.clips[path])

    def ensure_core(self) -> vs.Core:
        return vs.core


def _media(
    tmp_path: Path, reference_clip: vs.VideoNode, comparison_clip: vs.VideoNode
) -> tuple[VideoClipRequest, VideoClipRequest, _Loader]:
    reference_path = tmp_path / "reference.mkv"
    comparison_path = tmp_path / "comparison.mkv"
    reference_path.write_bytes(b"reference")
    comparison_path.write_bytes(b"comparison")

    def request(path: Path) -> VideoClipRequest:
        stat = path.stat()
        return VideoClipRequest(
            path=path,
            identity=AlignmentClipIdentity(path, stat.st_size, stat.st_mtime_ns),
        )

    return (
        request(reference_path),
        request(comparison_path),
        _Loader({reference_path: reference_clip, comparison_path: comparison_clip}),
    )


def _attempt(*, rounded: int, lag: int = 0, planned: int = 1) -> AudioAlignmentAttempt:
    base = attempt_with_chunks(planned, lag=lag)
    subframe = float(rounded)
    return replace(
        base,
        audio=replace(
            base.audio,
            global_lag=lag,
            subframe_estimate=subframe,
            rounded_frame=rounded,
        ),
        decision=replace(
            base.decision,
            candidate=replace(
                base.decision.candidate,
                frame_offset=rounded,
                subframe_estimate=subframe,
            ),
        ),
    )


def _run(
    tmp_path: Path,
    *,
    truth: int,
    audio_frame: int = 0,
    reference_clip: vs.VideoNode | None = None,
    comparison_clip: vs.VideoNode | None = None,
    loader: _Loader | None = None,
    attempt: AudioAlignmentAttempt | None = None,
    cancellation: Event | None = None,
) -> alignment_video.VideoCheckResult:
    reference_clip = reference_clip or _moving_clip()
    comparison_clip = comparison_clip or _shifted_clip(reference_clip, truth)
    if loader is None:
        reference, comparison, loader = _media(tmp_path, reference_clip, comparison_clip)
    else:
        reference, comparison, _unused = _media(tmp_path, reference_clip, comparison_clip)
        loader.clips = {reference.path: reference_clip, comparison.path: comparison_clip}
    current_attempt = attempt or _attempt(rounded=audio_frame)
    return alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=current_attempt,
        fps_reference=FPS,
        loader=loader,
        cancellation=cancellation,
    )


@pytest.mark.parametrize(
    ("truth", "expected"),
    [(-1, -1), (1, 1), (-2, None), (2, None), (-3, None), (3, None)],
)
def test_video_confirmation_only_accepts_neighbouring_truths(
    tmp_path: Path, truth: int, expected: int | None
) -> None:
    result = _run(tmp_path, truth=truth)
    assert result.reason is None
    assert result.observation.confirmed_offset == expected
    assert len(result.observation.positions) == 12


def test_static_content_is_uninformative(tmp_path: Path) -> None:
    clip = vs.core.std.BlankClip(width=64, height=36, length=60, format=vs.GRAYS, color=0)
    result = _run(tmp_path, truth=0, reference_clip=clip, comparison_clip=clip)
    assert result.reason is None
    assert result.observation.confirmed_offset is None
    assert all(set(position.score_by_offset) == {0.0} for position in result.observation.positions)


def test_monotonic_tone_curve_preserves_confirmation(tmp_path: Path) -> None:
    reference = _moving_clip()
    comparison = _shifted_clip(_moving_clip(transform=lambda value: min(255, value * 2)), 1)
    result = _run(tmp_path, truth=1, reference_clip=reference, comparison_clip=comparison)
    assert result.observation.confirmed_offset == 1


def test_missing_or_failing_loader_is_unavailable(tmp_path: Path) -> None:
    reference, comparison, loader = _media(tmp_path, _moving_clip(), _moving_clip())
    attempt = _attempt(rounded=0)
    missing = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=attempt,
        fps_reference=FPS,
        loader=None,
    )
    assert missing.reason == "video_check_unavailable"

    class FailingLoader(_Loader):
        def load(self, path: Path) -> SourceInfo:
            raise RuntimeError("synthetic load failure")

    failed = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=attempt,
        fps_reference=FPS,
        loader=FailingLoader(loader.clips),
    )
    assert failed.reason == "video_check_unavailable"


def test_cancellation_after_load_is_observed(tmp_path: Path) -> None:
    cancellation = Event()
    reference, comparison, loader = _media(tmp_path, _moving_clip(), _moving_clip())
    loader.after_load = lambda _path: cancellation.set()
    result = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=_attempt(rounded=0),
        fps_reference=FPS,
        loader=loader,
        cancellation=cancellation,
    )
    assert result.reason == "cancelled"
    assert len(loader.calls) == 1


def test_cancellation_between_positions_is_observed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cancellation = Event()
    original = alignment_video._read_frame
    reads = 0

    def read_frame(node: object, frame: int) -> np.ndarray:
        nonlocal reads
        reads += 1
        if reads >= 6:
            cancellation.set()
        return original(node, frame)  # type: ignore[arg-type]

    monkeypatch.setattr(alignment_video, "_read_frame", read_frame)
    result = _run(tmp_path, truth=0, cancellation=cancellation)
    assert result.reason == "cancelled"
    assert reads >= 6


def test_source_identity_change_after_load_is_unavailable(tmp_path: Path) -> None:
    reference, comparison, loader = _media(tmp_path, _moving_clip(), _moving_clip())
    loader.after_load = lambda path: path.write_bytes(path.read_bytes() + b"changed")
    result = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=_attempt(rounded=0),
        fps_reference=FPS,
        loader=loader,
    )
    assert result.reason == "source_identity_changed"


def test_out_of_range_overlap_is_unavailable(tmp_path: Path) -> None:
    reference, comparison, loader = _media(tmp_path, _moving_clip(frames=3), _moving_clip(frames=3))
    result = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=_attempt(rounded=10),
        fps_reference=FPS,
        loader=loader,
    )
    assert result.reason == "video_check_unavailable"


@pytest.mark.parametrize(
    ("confirmed", "alternative", "winner"),
    [
        (1.0, 1.0, "neither"),
        (0.0, 1.0, "confirmed"),
        (1.0, 0.0, "alternative"),
        (1.0, 1.5, "confirmed"),
        (1.5, 1.0, "alternative"),
        (1.0, 1.49, "neither"),
    ],
)
def test_v5a_relative_hypothesis_margin_rules(
    confirmed: float, alternative: float, winner: str
) -> None:
    assert alignment_video._hypothesis_winner(confirmed, alternative) == winner


def test_v3a_conversion_and_excluded_alternative(tmp_path: Path) -> None:
    assert (
        alignment_video.sample_to_reference_frame(
            0,
            fps_reference=FPS,
            audio_start_reference=Fraction(1, 24),
            video_start_reference=Fraction(0),
        )
        == 1
    )

    base = _attempt(rounded=0, planned=1)
    base = replace(
        base,
        chunks=AudioChunkColumns(
            starts=(0,),
            counts=(8000,),
            active=(True,),
            lags=(400,),
            psrs=(100.0,),
            credible=(True,),
            agrees=(False,),
            total_samples=8000,
        ),
        runs=(),
        audio=AudioStageOutcome(
            status="no_single_offset",
            global_lag=0,
            active_chunks=1,
            credible_chunks=1,
            agreeing_chunks=0,
            compensation_seconds=0.0,
            subframe_estimate=0.0,
            rounded_frame=0,
        ),
    )
    result = _run(tmp_path, truth=0, attempt=base)
    assert result.observation.confirmed_offset == 0
    assert len(result.observation.targets) == 1
    target = result.observation.targets[0]
    assert target.alternative_offsets == (1, 2)
    assert target.credible is True
    assert (target.start_sample, target.end_sample) == (0, 8_000)
    assert 0 not in target.alternative_offsets


def test_a4a_non_adjacent_same_lag_chunks_are_separate_targets() -> None:
    attempt = _attempt(rounded=0, planned=3)
    chunks = (
        alignment_video._Chunk(0, 0, 10, True, 400, 100.0, True, False),
        alignment_video._Chunk(1, 10, 10, True, 0, 100.0, True, True),
        alignment_video._Chunk(2, 20, 10, True, 400, 90.0, True, False),
    )
    attempt = replace(
        attempt,
        runs=(AudioChunkRun(first_index=0, last_index=2, lag=400, chunk_count=2),),
    )
    targets, _same_frame = alignment_video._build_targets(
        attempt,
        chunks,
        confirmed=0,
        fps_reference=FPS,
    )
    assert [(target.kind, target.first_index) for target in targets] == [
        ("chunk", 0),
        ("chunk", 2),
    ]


def test_a4b_boundary_regroups_frame_distinct_tail_as_one_run() -> None:
    attempt = _attempt(rounded=0, planned=4)
    chunks = (
        alignment_video._Chunk(0, 0, 10, True, 0, 100.0, True, True),
        alignment_video._Chunk(1, 10, 10, True, 166, 100.0, True, False),
        alignment_video._Chunk(2, 20, 10, True, 167, 99.0, True, False),
        alignment_video._Chunk(3, 30, 10, True, 168, 98.0, True, False),
    )

    targets, same_frame = alignment_video._build_targets(
        attempt,
        chunks,
        confirmed=0,
        fps_reference=FPS,
    )

    assert [(target.kind, target.first_index, target.last_index) for target in targets] == [
        ("run", 2, 3)
    ]
    assert targets[0].credible is True
    assert (targets[0].start_sample, targets[0].end_sample) == (20, 40)
    assert [item.chunk_index for item in same_frame] == [1]


def test_run_resolution_requires_two_confirmed_positions() -> None:
    one = alignment_video._target_resolution(
        "run",
        [alignment_video.VideoTargetPosition(0, 10, 0.1, 1.0, "confirmed")],
    )
    two = alignment_video._target_resolution(
        "run",
        [
            alignment_video.VideoTargetPosition(0, 10, 0.1, 1.0, "confirmed"),
            alignment_video.VideoTargetPosition(1, 20, 0.1, 1.0, "confirmed"),
        ],
    )
    alternative = alignment_video._target_resolution(
        "run",
        [alignment_video.VideoTargetPosition(0, 10, 1.0, 0.1, "alternative")],
    )
    assert one == "unresolved"
    assert two == "resolved"
    assert alternative == "alternative_confirmed"


def test_position_ties_and_periodic_aliases_are_not_informative() -> None:
    offsets = (-2, -1, 0, 1, 2)
    assert alignment_video._position_winner((1.0, 0.0, 0.0, 1.0, 2.0), offsets)[0] is None
    assert alignment_video._position_winner((1.0, 0.9, 0.5, 0.9, 0.5), offsets)[0] is None


def test_minority_position_edit_cannot_overrule_the_consensus() -> None:
    assert (
        alignment_video._confirmed_offset(
            0,
            [0] * 9 + [1] * 3,
            [2.0] * 12,
        )
        == 0
    )


def test_inconclusive_video_still_has_review_check_points(tmp_path: Path) -> None:
    clip = vs.core.std.BlankClip(width=64, height=36, length=60, format=vs.GRAYS, color=0)
    result = _run(tmp_path, truth=0, reference_clip=clip, comparison_clip=clip)
    assert result.observation.confirmed_offset is None
    assert len(result.observation.check_points) == 5


def test_check_points_cover_each_target_before_filling_the_five_point_cap() -> None:
    def target(first_index: int, frames: tuple[int, ...]) -> alignment_video.VideoTargetEvidence:
        return alignment_video.VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=first_index,
            last_chunk_index=first_index,
            credible=True,
            start_sample=(first_index) * 240_000,
            end_sample=((first_index) + 1) * 240_000,
            target_offset=1,
            alternative_offsets=(1,),
            resolution="unresolved",
            positions=tuple(
                alignment_video.VideoTargetPosition(
                    position_index=first_index * 4 + offset,
                    reference_frame=frame,
                    confirmed_score=1.0,
                    alternative_score=1.0,
                    winner="neither",
                )
                for offset, frame in enumerate(frames)
            ),
        )

    base_positions = (
        alignment_video.VideoPositionDifference(
            position_index=0,
            reference_frame=900,
            score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
        ),
    )
    targets = (
        target(1, (110, 111, 112, 113)),
        target(3, (500, 501, 502, 503)),
    )
    chunks = (
        alignment_video._Chunk(1, 0, 10, True, 0, 100.0, True, False),
        alignment_video._Chunk(3, 100, 10, True, 0, 90.0, True, False),
    )

    points = alignment_video._check_points(
        base_positions,
        targets,
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
        chunks=chunks,
    )

    assert [point.reference_frame for point in points] == [110, 500, 900, 111, 112]
    assert len(points) == 5


@pytest.mark.parametrize("confirmed", (-1, 0, 1))
def test_check_points_use_producer_scored_offsets_for_confirmed_contrast(
    confirmed: int,
) -> None:
    scored_offsets = (-2, -1, 0, 1, 2)
    scores = tuple(0.1 if offset == confirmed else 2.0 for offset in scored_offsets)
    position = alignment_video.VideoPositionDifference(
        position_index=0,
        reference_frame=900,
        score_by_offset=scores,
    )

    points = alignment_video._check_points(
        (position,),
        (),
        confirmed=confirmed,
        scored_offsets=scored_offsets,
        fps_reference=FPS,
    )
    winner, margin = alignment_video._position_winner(scores, scored_offsets)

    assert winner == confirmed
    assert margin == pytest.approx(20.0)
    assert [point.reference_frame for point in points] == [900]
    assert points[0].suggested_comparison_frame == 900 - confirmed


def test_check_points_use_authoritative_target_offset() -> None:
    target = alignment_video.VideoTargetEvidence(
        kind="chunk",
        first_chunk_index=1,
        last_chunk_index=1,
        credible=True,
        start_sample=(1) * 240_000,
        end_sample=((1) + 1) * 240_000,
        target_offset=246,
        alternative_offsets=(245, 246, 247),
        resolution="unresolved",
        positions=(alignment_video.VideoTargetPosition(12, 500, 1.0, 1.0, "neither"),),
    )

    points = alignment_video._check_points(
        (),
        (target,),
        confirmed=146,
        scored_offsets=(144, 145, 146, 147, 148),
        fps_reference=FPS,
    )

    assert points == (alignment_video.VideoCheckPoint(500 / float(FPS), 500, 254),)


def test_check_points_keep_adjacent_distinct_target_offsets_separate() -> None:
    def target(
        index: int, frame: int, offset: int, alternatives: tuple[int, ...]
    ) -> alignment_video.VideoTargetEvidence:
        return alignment_video.VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=index,
            last_chunk_index=index,
            credible=True,
            start_sample=(index) * 240_000,
            end_sample=((index) + 1) * 240_000,
            target_offset=offset,
            alternative_offsets=alternatives,
            resolution="unresolved",
            positions=(alignment_video.VideoTargetPosition(index, frame, 1.0, 1.0, "neither"),),
        )

    points = alignment_video._check_points(
        (
            alignment_video.VideoPositionDifference(
                position_index=0,
                reference_frame=900,
                score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
            ),
        ),
        (
            target(1, 500, 145, (145, 146)),
            target(2, 700, 146, (145, 146, 147)),
        ),
        confirmed=144,
        scored_offsets=(142, 143, 144, 145, 146),
        fps_reference=FPS,
        chunks=(
            alignment_video._Chunk(1, 0, 10, True, 0, 100.0, True, False),
            alignment_video._Chunk(2, 10, 10, True, 0, 90.0, True, False),
        ),
    )

    assert [(point.reference_frame, point.suggested_comparison_frame) for point in points] == [
        (500, 355),
        (700, 554),
        (900, 756),
    ]


@pytest.mark.parametrize("target_count", (5, 6))
def test_check_points_reserve_contrast_after_four_ordered_regions(target_count: int) -> None:
    if target_count == 5:
        specifications = (
            (1, 100, 1, 50.0),
            (2, 200, 1, 90.0),
            (3, 300, 2, 80.0),
            (4, 400, 3, 70.0),
            (5, 500, 4, 60.0),
        )
        expected = [200, 300, 400, 500, 900]
    else:
        specifications = (
            (1, 100, 1, 50.0),
            (2, 200, 1, 90.0),
            (3, 300, 2, 40.0),
            (4, 400, 2, 80.0),
            (5, 500, 3, 70.0),
            (6, 600, 4, 60.0),
        )
        expected = [200, 400, 500, 600, 900]

    def target(index: int, frame: int, alternative: int) -> alignment_video.VideoTargetEvidence:
        return alignment_video.VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=index,
            last_chunk_index=index,
            credible=True,
            start_sample=(index) * 240_000,
            end_sample=((index) + 1) * 240_000,
            target_offset=alternative,
            alternative_offsets=(alternative,),
            resolution="unresolved",
            positions=(
                alignment_video.VideoTargetPosition(
                    position_index=index,
                    reference_frame=frame,
                    confirmed_score=1.0,
                    alternative_score=1.0,
                    winner="neither",
                ),
            ),
        )

    targets = tuple(
        target(index, frame, alternative) for index, frame, alternative, _ in specifications
    )
    chunks = tuple(
        alignment_video._Chunk(
            index,
            (index - 1) * 10,
            10,
            True,
            0,
            psr,
            True,
            False,
        )
        for index, _frame, _alternative, psr in specifications
    )
    base_position = alignment_video.VideoPositionDifference(
        position_index=0,
        reference_frame=900,
        score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
    )
    points = alignment_video._check_points(
        (base_position,),
        targets,
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
        chunks=chunks,
    )

    assert [point.reference_frame for point in points] == expected
    assert len(points) == 5
    assert points == alignment_video._check_points(
        (base_position,),
        targets,
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
        chunks=chunks,
    )


def test_check_points_deduplicate_and_fill_in_deterministic_order() -> None:
    def target(index: int, frames: tuple[int, ...]) -> alignment_video.VideoTargetEvidence:
        return alignment_video.VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=index,
            last_chunk_index=index,
            credible=True,
            start_sample=(index) * 240_000,
            end_sample=((index) + 1) * 240_000,
            target_offset=1,
            alternative_offsets=(1,),
            resolution="unresolved",
            positions=tuple(
                alignment_video.VideoTargetPosition(
                    position_index=index * 2 + offset,
                    reference_frame=frame,
                    confirmed_score=1.0,
                    alternative_score=1.0,
                    winner="neither",
                )
                for offset, frame in enumerate(frames)
            ),
        )

    points = alignment_video._check_points(
        (
            alignment_video.VideoPositionDifference(
                position_index=0,
                reference_frame=900,
                score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
            ),
        ),
        (target(1, (100, 101)), target(3, (100,)), target(4, (201,))),
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
        chunks=(
            alignment_video._Chunk(1, 0, 10, True, 0, 100.0, True, False),
            alignment_video._Chunk(3, 20, 10, True, 0, 90.0, True, False),
            alignment_video._Chunk(4, 30, 10, True, 0, 80.0, True, False),
        ),
    )

    assert [(point.reference_frame, point.suggested_comparison_frame) for point in points] == [
        (100, 99),
        (201, 200),
        (900, 900),
        (101, 100),
    ]
    assert len(
        {(point.reference_frame, point.suggested_comparison_frame) for point in points}
    ) == len(points)


def test_check_points_follow_target_resolution_and_track_order() -> None:
    resolved = alignment_video.VideoTargetEvidence(
        kind="chunk",
        first_chunk_index=4,
        last_chunk_index=4,
        credible=True,
        start_sample=40,
        end_sample=50,
        target_offset=4,
        alternative_offsets=(3, 4, 5),
        resolution="resolved",
        positions=(
            alignment_video.VideoTargetPosition(0, 400, 1.0, 1.0, "neither"),
            alignment_video.VideoTargetPosition(1, 401, 0.1, 1.0, "confirmed"),
        ),
    )
    alternative = alignment_video.VideoTargetEvidence(
        kind="chunk",
        first_chunk_index=2,
        last_chunk_index=2,
        credible=True,
        start_sample=20,
        end_sample=30,
        target_offset=2,
        alternative_offsets=(1, 2, 3),
        resolution="alternative_confirmed",
        positions=(
            alignment_video.VideoTargetPosition(2, 200, 1.0, 1.0, "neither"),
            alignment_video.VideoTargetPosition(3, 201, 1.0, 0.1, "alternative"),
        ),
    )
    unresolved = alignment_video.VideoTargetEvidence(
        kind="run",
        first_chunk_index=0,
        last_chunk_index=1,
        credible=True,
        start_sample=0,
        end_sample=20,
        target_offset=1,
        alternative_offsets=(1,),
        resolution="unresolved",
        positions=(
            alignment_video.VideoTargetPosition(4, 100, 0.1, 1.0, "confirmed"),
            alignment_video.VideoTargetPosition(5, 101, 1.0, 1.0, "neither"),
        ),
    )

    points = alignment_video._check_points(
        (alignment_video.VideoPositionDifference(0, 900, (2.0, 1.0, 0.1, 1.0, 2.0)),),
        (resolved, alternative, unresolved),
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
        chunks=(
            alignment_video._Chunk(0, 0, 10, True, 0, 80.0, True, False),
            alignment_video._Chunk(1, 10, 10, True, 0, 80.0, True, False),
            alignment_video._Chunk(2, 20, 10, True, 0, 90.0, True, False),
            alignment_video._Chunk(4, 40, 10, True, 0, 100.0, True, False),
        ),
    )

    assert [(point.reference_frame, point.suggested_comparison_frame) for point in points] == [
        (101, 100),
        (201, 199),
        (401, 401),
        (900, 900),
        (100, 100),
    ]


@pytest.mark.parametrize(
    ("winner", "resolution", "comparison_frame"),
    [
        ("confirmed", "unresolved", 100),
        ("alternative", "alternative_confirmed", 99),
    ],
)
def test_single_winner_run_checkpoint_uses_its_winning_offset(
    winner: Literal["confirmed", "alternative"],
    resolution: str,
    comparison_frame: int,
) -> None:
    position = alignment_video.VideoTargetPosition(
        0,
        100,
        0.1 if winner == "confirmed" else 1.0,
        0.1 if winner == "alternative" else 1.0,
        winner,
    )
    actual_resolution = alignment_video._target_resolution("run", (position,))
    assert actual_resolution == resolution
    target = alignment_video.VideoTargetEvidence(
        kind="run",
        first_chunk_index=0,
        last_chunk_index=1,
        credible=True,
        start_sample=0,
        end_sample=20,
        target_offset=1,
        alternative_offsets=(1,),
        resolution=actual_resolution,
        positions=(position,),
    )

    points = alignment_video._check_points(
        (),
        (target,),
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
    )

    assert points == (alignment_video.VideoCheckPoint(100 / float(FPS), 100, comparison_frame),)


def test_mixed_run_checkpoint_pairing_is_truthful_ordered_and_capped() -> None:
    positions = (
        alignment_video.VideoTargetPosition(0, 100, 1.0, 1.0, "neither"),
        alignment_video.VideoTargetPosition(1, 101, 0.1, 1.0, "confirmed"),
        alignment_video.VideoTargetPosition(2, 102, 1.0, 0.1, "alternative"),
    )
    resolution = alignment_video._target_resolution("run", positions)
    assert resolution == "alternative_confirmed"
    target = alignment_video.VideoTargetEvidence(
        kind="run",
        first_chunk_index=0,
        last_chunk_index=1,
        credible=True,
        start_sample=0,
        end_sample=20,
        target_offset=1,
        alternative_offsets=(1,),
        resolution=resolution,
        positions=positions,
    )
    base_positions = tuple(
        alignment_video.VideoPositionDifference(
            index,
            frame,
            (2.0, 1.0, 0.1, 1.0, 2.0),
        )
        for index, frame in enumerate((900, 901))
    )

    points = alignment_video._check_points(
        base_positions,
        (target,),
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
    )

    assert [(point.reference_frame, point.suggested_comparison_frame) for point in points] == [
        (102, 101),
        (900, 900),
        (100, 99),
        (101, 101),
        (901, 901),
    ]
    assert points == alignment_video._check_points(
        base_positions,
        (target,),
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
    )


def test_unexamined_target_keeps_unscored_planned_review_point() -> None:
    target = alignment_video.VideoTargetEvidence(
        kind="chunk",
        first_chunk_index=1,
        last_chunk_index=1,
        credible=True,
        start_sample=10,
        end_sample=20,
        target_offset=3,
        alternative_offsets=(2, 3, 4),
        resolution="unexamined",
        positions=(),
    )

    points = alignment_video._check_points(
        (),
        (target,),
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
        chunks=(alignment_video._Chunk(1, 10, 10, True, 0, 100.0, True, False),),
        planned_target_frames={("chunk", 1, 1): (123,)},
    )

    assert points == (alignment_video.VideoCheckPoint(123 / float(FPS), 123, 120),)


def test_budget_exhaustion_keeps_planned_point_without_scoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = tuple(
        alignment_video._Target(
            kind="chunk",
            first_index=index,
            last_index=index,
            lag=400 * (index + 1),
            credible=True,
            start_sample=index * 240_000,
            end_sample=(index + 1) * 240_000,
            requested_positions=4,
        )
        for index in range(4)
    )
    scored_frames: list[int] = []

    monkeypatch.setattr(
        alignment_video,
        "_build_targets",
        lambda *_args, **_kwargs: (targets, ()),
    )
    monkeypatch.setattr(
        alignment_video,
        "_target_frames",
        lambda target, **_kwargs: tuple(target.first_index * 10 + offset for offset in range(1, 5)),
    )

    def score_hypotheses(
        _reference_node: object,
        _comparison_node: object,
        reference_frame: int,
        _confirmed: int,
        _alternative_offsets: object,
    ) -> tuple[float, float]:
        scored_frames.append(reference_frame)
        return 0.1, 1.0

    monkeypatch.setattr(alignment_video, "_score_hypotheses", score_hypotheses)

    result = _run(tmp_path, truth=0, attempt=_attempt(rounded=0, planned=4))

    assert len(scored_frames) == 12
    assert result.observation.targets[-1].resolution == "unexamined"
    assert result.observation.targets[-1].positions == ()
    assert any(
        point.reference_frame == 31 and point.suggested_comparison_frame == 26
        for point in result.observation.check_points
    )


def test_unbounded_psr_target_ranks_above_finite_target() -> None:
    attempt = _attempt(rounded=0, planned=2)
    attempt = replace(
        attempt,
        chunks=replace(
            attempt.chunks,
            lags=(400, 800),
            psrs=(100.0, "unbounded"),
            agrees=(False, False),
        ),
        runs=(),
    )

    chunks = alignment_video._chunks(attempt)
    targets, _same_frame = alignment_video._build_targets(
        attempt,
        chunks,
        confirmed=0,
        fps_reference=FPS,
    )

    assert [target.first_index for target in targets] == [1, 0]


def test_check_points_skip_colliding_base_before_confirmed_contrast() -> None:
    def target(index: int) -> alignment_video.VideoTargetEvidence:
        return alignment_video.VideoTargetEvidence(
            kind="chunk",
            first_chunk_index=index,
            last_chunk_index=index,
            credible=True,
            start_sample=(index) * 240_000,
            end_sample=((index) + 1) * 240_000,
            target_offset=index,
            alternative_offsets=(index,),
            resolution="resolved",
            positions=(
                alignment_video.VideoTargetPosition(
                    position_index=index,
                    reference_frame=100 * index,
                    confirmed_score=0.1,
                    alternative_score=1.0,
                    winner="confirmed",
                ),
            ),
        )

    base_positions = (
        alignment_video.VideoPositionDifference(
            position_index=0,
            reference_frame=100,
            score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
        ),
        alignment_video.VideoPositionDifference(
            position_index=1,
            reference_frame=900,
            score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
        ),
    )
    targets = tuple(target(index) for index in range(1, 5))
    chunks = tuple(
        alignment_video._Chunk(index, (index - 1) * 10, 10, True, 0, 100.0, True, False)
        for index in range(1, 5)
    )

    points = alignment_video._check_points(
        base_positions,
        targets,
        confirmed=0,
        scored_offsets=(-2, -1, 0, 1, 2),
        fps_reference=FPS,
        chunks=chunks,
    )

    assert [point.reference_frame for point in points] == [100, 900, 200, 300, 400]
    assert len(points) == 5


def test_evidence_failures_are_not_constructed_as_observed() -> None:
    with pytest.raises(ValueError, match="successful"):
        alignment_video.VideoCheckResult(
            observation=VideoCheckObservation(
                observation="not_observed",
                scored_offsets=(),
                confirmed_offset=None,
                index_build_seconds=None,
                positions=(),
            )
        )
