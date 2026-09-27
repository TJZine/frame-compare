"""Focused V1-V7 tests using generated VapourSynth clips."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from threading import Event

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
    assert result.observation.targets[0].alternative_offsets == (1, 2)
    assert 0 not in result.observation.targets[0].alternative_offsets


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
        target(2, (500, 501, 502, 503)),
    )

    points = alignment_video._check_points(
        base_positions,
        targets,
        confirmed=0,
        fps_reference=FPS,
    )

    assert [point.reference_frame for point in points] == [110, 500, 900, 111, 112]
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
