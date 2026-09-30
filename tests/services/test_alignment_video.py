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
from frame_compare.services.alignment_correlation import (
    ChunkedAudioEstimate,
    ChunkObservation,
    ChunkPlan,
)
from frame_compare.services.alignment_decision import (
    DecidedAudioStage,
    decide_after_video,
    decide_completed_stage,
)
from frame_compare.services.alignment_video import VideoClipRequest
from frame_compare.utils.alignment_evidence import (
    AudioAlignmentAttempt,
    AudioChunkColumns,
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


def _remapped_clip(reference: vs.VideoNode, source_frame: Callable[[int], int]) -> vs.VideoNode:
    return vs.core.std.Splice(
        [
            reference[index : index + 1]
            for frame in range(reference.num_frames)
            for index in [source_frame(frame)]
        ]
    )


def _motion_ranges_clip(*ranges: range, frames: int = 180) -> vs.VideoNode:
    moving = _moving_clip(frames=frames)
    return vs.core.std.Splice(
        [
            moving[index : index + 1] if any(index in item for item in ranges) else moving[0:1]
            for index in range(frames)
        ]
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
    candidate = base.decision.candidate
    assert candidate is not None
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
                candidate,
                frame_offset=rounded,
                subframe_estimate=subframe,
            ),
        ),
    )


def _attempt_with_lags(
    lags: tuple[int, ...],
    *,
    global_lag: int = 0,
    chunk_samples: int = 16_000,
    reference_audio_start: Fraction = Fraction(0),
) -> AudioAlignmentAttempt:
    base = _attempt(rounded=0, lag=global_lag, planned=len(lags))
    compensation = reference_audio_start
    subframe = float((Fraction(global_lag, 8_000) + compensation) * FPS)
    rounded = int(np.floor(subframe + 0.5))
    agrees = tuple(abs(lag - global_lag) <= 16 for lag in lags)
    reference_stream, comparison_stream = base.selected_streams
    candidate = base.decision.candidate
    assert candidate is not None
    return replace(
        base,
        selected_streams=(
            replace(
                reference_stream,
                stream_start_num=reference_audio_start.numerator,
                stream_start_den=reference_audio_start.denominator,
                stream_start_basis="metadata",
            ),
            comparison_stream,
        ),
        analysis=replace(
            base.analysis,
            chunk_samples=chunk_samples,
            planned_chunk_count=len(lags),
        ),
        chunks=AudioChunkColumns(
            starts=tuple(index * chunk_samples for index in range(len(lags))),
            counts=(chunk_samples,) * len(lags),
            active=(True,) * len(lags),
            lags=lags,
            psrs=(100.0,) * len(lags),
            credible=(True,) * len(lags),
            agrees=agrees,
            total_samples=chunk_samples * len(lags),
        ),
        runs=(),
        audio=replace(
            base.audio,
            status="agreed",
            global_lag=global_lag,
            active_chunks=len(lags),
            credible_chunks=len(lags),
            agreeing_chunks=sum(agrees),
            compensation_seconds=float(compensation),
            subframe_estimate=subframe,
            rounded_frame=rounded,
        ),
        decision=replace(
            base.decision,
            candidate=replace(
                candidate,
                frame_offset=rounded,
                subframe_estimate=subframe,
            ),
        ),
    )


def _decide_video(
    attempt: AudioAlignmentAttempt, video: VideoCheckObservation
) -> DecidedAudioStage:
    observations = tuple(
        ChunkObservation(
            index=index,
            reference_start=start,
            reference_count=count,
            active=active,
            lag=lag,
            psr=float(psr),
            credible=credible,
            agrees=agrees,
        )
        for index, (start, count, active, lag, psr, credible, agrees) in enumerate(
            zip(
                attempt.chunks.starts,
                attempt.chunks.counts,
                attempt.chunks.active,
                attempt.chunks.lags,
                attempt.chunks.psrs,
                attempt.chunks.credible,
                attempt.chunks.agrees,
                strict=True,
            )
        )
    )
    global_lag = attempt.audio.global_lag
    assert global_lag is not None
    estimate = ChunkedAudioEstimate(
        outcome=attempt.audio.status,
        global_lag=global_lag,
        observations=observations,
        runs=(),
        active_count=len(observations),
        credible_count=len(observations),
        agreeing_count=sum(item.agrees for item in observations),
    )
    plan = ChunkPlan(
        chunk_samples=attempt.analysis.chunk_samples,
        lag_samples=attempt.analysis.lag_samples,
        chunks=tuple((item.reference_start, item.reference_count) for item in observations),
    )
    reference_stream, comparison_stream = attempt.selected_streams
    stage = decide_completed_stage(
        estimate=estimate,
        plan=plan,
        max_offset_seconds=attempt.analysis.max_offset_seconds,
        reference_audio_start=Fraction(
            reference_stream.stream_start_num, reference_stream.stream_start_den
        ),
        reference_video_start=Fraction(
            reference_stream.video_start_num, reference_stream.video_start_den
        ),
        comparison_audio_start=Fraction(
            comparison_stream.stream_start_num, comparison_stream.stream_start_den
        ),
        comparison_video_start=Fraction(
            comparison_stream.video_start_num, comparison_stream.video_start_den
        ),
        fps_reference=FPS,
    )
    return decide_after_video(
        stage=stage,
        estimate=estimate,
        plan=plan,
        video=video,
        fps_reference=FPS,
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
) -> VideoCheckObservation:
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


def _assert_unobserved(observation: VideoCheckObservation) -> None:
    assert observation.observation == "not_observed"
    assert observation.positions == ()


def _force_target_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    base_positions = [
        alignment_video.VideoPositionDifference(
            position_index=index,
            reference_frame=20 + index,
            score_by_offset=(2.0, 1.0, 0.0, 1.0, 2.0),
        )
        for index in range(6)
    ]
    target = alignment_video._Target(
        kind="chunk",
        first_index=0,
        last_index=0,
        lag=333.0,
        credible=True,
        start_sample=0,
        end_sample=8_000,
        requested_positions=1,
    )
    monkeypatch.setattr(
        alignment_video,
        "_score_base_positions",
        lambda *_args, **_kwargs: (base_positions, [0] * 6, [float("inf")] * 6),
    )
    monkeypatch.setattr(
        alignment_video,
        "_build_targets",
        lambda *_args, **_kwargs: ((target,), ()),
    )
    monkeypatch.setattr(
        alignment_video,
        "_target_range",
        lambda *_args, **_kwargs: (10, 20),
    )
    monkeypatch.setattr(
        alignment_video,
        "_motion_positions",
        lambda *_args, **_kwargs: (20,),
    )


@pytest.mark.parametrize(
    ("truth", "expected"),
    [(-1, -1), (1, 1), (-2, None), (2, None), (-3, None), (3, None)],
)
def test_video_confirmation_only_accepts_neighbouring_truths(
    tmp_path: Path, truth: int, expected: int | None
) -> None:
    result = _run(tmp_path, truth=truth)
    assert result.observation == "observed"
    assert result.confirmed_offset == expected
    assert len(result.positions) == 12


def test_static_content_is_uninformative(tmp_path: Path) -> None:
    clip = vs.core.std.BlankClip(width=64, height=36, length=60, format=vs.GRAYS, color=0)
    result = _run(tmp_path, truth=0, reference_clip=clip, comparison_clip=clip)
    assert result.observation == "observed"
    assert result.confirmed_offset is None
    assert all(set(position.score_by_offset) == {0.0} for position in result.positions)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        pytest.param(
            [[0, 255], [0, 127]],
            [[0.375, 1.0], [0.375, 0.75]],
            id="uint8-values-with-tie",
        ),
        pytest.param(
            [[1023, 0], [511, 512]],
            [[1.0, 0.25], [0.5, 0.75]],
            id="uint10-values",
        ),
        pytest.param(
            [[-0.75, 0.25], [0.5, -0.25]],
            [[0.25, 0.75], [1.0, 0.5]],
            id="continuous-float32",
        ),
    ],
)
def test_average_ranks_match_hand_computed_oracle(
    values: list[list[float]], expected: list[list[float]]
) -> None:
    ranks = alignment_video._average_ranks(np.asarray(values, dtype=np.float32))

    assert ranks.dtype == np.float32
    np.testing.assert_array_equal(ranks, np.asarray(expected, dtype=np.float32))


@pytest.mark.parametrize(
    ("ranges", "start", "end", "count", "expected"),
    [
        pytest.param((range(60, 70),), 40, 100, 1, (62,), id="moving-slot"),
        pytest.param((range(90, 100),), 40, 100, 1, (92,), id="fourth-candidate"),
        pytest.param((), 10, 70, 3, (12, 32, 52), id="static-ties-pick-first"),
        pytest.param((), 176, 180, 1, (176,), id="skip-candidates-past-end"),
        pytest.param((), 179, 179, 1, (179,), id="midpoint-fallback"),
        pytest.param((), 40, 100, 0, (), id="empty-count"),
    ],
)
def test_motion_positions_pick_the_moving_frame(
    ranges: tuple[range, ...],
    start: int,
    end: int,
    count: int,
    expected: tuple[int, ...],
) -> None:
    node = alignment_video._prepare_luma(_motion_ranges_clip(*ranges), None)

    positions = alignment_video._motion_positions(node, start, end, count, cancellation=None)

    assert positions == expected


def test_monotonic_tone_curve_preserves_confirmation(tmp_path: Path) -> None:
    reference = _moving_clip()
    comparison = _shifted_clip(_moving_clip(transform=lambda value: min(255, value * 2)), 1)
    result = _run(tmp_path, truth=1, reference_clip=reference, comparison_clip=comparison)
    assert result.confirmed_offset == 1


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
    _assert_unobserved(missing)

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
    _assert_unobserved(failed)

    class ValueErrorLoader(_Loader):
        def load(self, path: Path) -> SourceInfo:
            raise ValueError("synthetic native load failure")

    native_value_error = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=attempt,
        fps_reference=FPS,
        loader=ValueErrorLoader(loader.clips),
    )
    _assert_unobserved(native_value_error)


def test_non_finite_reference_luma_is_unavailable(tmp_path: Path) -> None:
    float_clip = vs.core.std.BlankClip(format=vs.YUV444PS, width=128, height=72, length=180)
    nan_clip = vs.core.std.Expr(float_clip, ["0 0 /", "", ""])

    result = _run(tmp_path, truth=0, reference_clip=nan_clip, comparison_clip=_moving_clip())

    _assert_unobserved(result)


def test_evidence_invariant_errors_are_not_mapped_to_native_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_video,
        "_build_targets",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("broken evidence")),
    )

    with pytest.raises(ValueError, match="broken evidence"):
        _run(tmp_path, truth=0)


@pytest.mark.parametrize("stage", ("base", "target"))
@pytest.mark.parametrize("error_type", (ValueError, TypeError))
def test_rank_programming_errors_propagate_from_checker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    error_type: type[Exception],
) -> None:
    if stage == "target":
        _force_target_scoring(monkeypatch)

    def fail_rank(_values: object) -> np.ndarray:
        raise error_type("broken rank logic")

    monkeypatch.setattr(alignment_video, "_average_ranks", fail_rank)

    with pytest.raises(error_type, match="broken rank logic"):
        _run(tmp_path, truth=0)


@pytest.mark.parametrize("stage", ("motion", "base", "target"))
def test_native_frame_read_value_error_is_unavailable_in_each_scoring_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    class NativeReadFailure:
        num_frames = 180

        def get_frame(self, _frame: int) -> None:
            raise ValueError("synthetic native read failure")

    monkeypatch.setattr(
        alignment_video,
        "_prepare_luma",
        lambda *_args, **_kwargs: NativeReadFailure(),
    )
    if stage == "base":
        monkeypatch.setattr(
            alignment_video,
            "_motion_positions",
            lambda *_args, **_kwargs: (20,),
        )
    elif stage == "target":
        _force_target_scoring(monkeypatch)

    result = _run(tmp_path, truth=0)

    _assert_unobserved(result)


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
    _assert_unobserved(result)
    assert cancellation.is_set()
    assert len(loader.calls) == 1


def test_index_build_timer_excludes_luma_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison, loader = _media(tmp_path, _moving_clip(), _moving_clip())
    clock = [0.0]
    loader.after_load = lambda _path: clock.__setitem__(0, clock[0] + 2.0)
    monkeypatch.setattr(alignment_video.time, "monotonic", lambda: clock[0])
    prepare_luma = alignment_video._prepare_luma

    def delayed_prepare_luma(
        clip: vs.VideoNode,
        active_rect: alignment_video.ActiveRect | None,
    ) -> vs.VideoNode:
        clock[0] += 100.0
        return prepare_luma(clip, active_rect)

    monkeypatch.setattr(alignment_video, "_prepare_luma", delayed_prepare_luma)

    result = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=_attempt(rounded=0),
        fps_reference=FPS,
        loader=loader,
    )

    assert result.index_build_seconds == 4.0


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
    _assert_unobserved(result)
    assert cancellation.is_set()
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
    _assert_unobserved(result)
    assert reference.path.stat().st_size != reference.identity.size_bytes


def test_out_of_range_overlap_is_unavailable(tmp_path: Path) -> None:
    reference, comparison, loader = _media(tmp_path, _moving_clip(frames=3), _moving_clip(frames=3))
    result = alignment_video.check_video_alignment(
        reference=reference,
        comparison=comparison,
        attempt=_attempt(rounded=10),
        fps_reference=FPS,
        loader=loader,
    )
    _assert_unobserved(result)


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


@pytest.mark.parametrize("alternative_source", (20, 4))
def test_tied_alternative_minima_choose_the_first_actual_winner(
    alternative_source: int,
) -> None:
    reference = _moving_clip(frames=30)
    remap = {17: alternative_source, 19: alternative_source, 20: 0}
    comparison = _remapped_clip(reference, lambda frame: remap.get(frame, frame))

    scored = alignment_video._score_hypotheses(reference, comparison, 20, 0, (1, 3))

    assert scored is not None
    confirmed_score, alternative_score, alternative_offset = scored
    assert alternative_offset == 1
    assert alignment_video._hypothesis_winner(confirmed_score, alternative_score) == "alternative"
    if alternative_source == 20:
        assert alternative_score == 0.0
    else:
        assert 0.0 < alternative_score < confirmed_score / 1.5


def test_tied_alternative_frames_block_through_video_and_decision(tmp_path: Path) -> None:
    reference = _moving_clip(frames=120)
    attempt = _attempt_with_lags(
        (333, -333, -333, -333, -333, -333, -333, -333, -333, -333),
        global_lag=-333,
        chunk_samples=8_000,
        reference_audio_start=Fraction(1, 24),
    )
    # Fixture-derived first-chunk motion winners; no production selector computes this oracle.
    target_frames = (6, 13, 15, 19)
    remap = {
        comparison_frame: reference_frame
        for reference_frame in target_frames
        for comparison_frame in (reference_frame - 1, reference_frame - 3)
    }
    remap.update(dict.fromkeys(target_frames, 0))
    comparison = _remapped_clip(reference, lambda frame: remap.get(frame, frame))

    result = _run(
        tmp_path,
        truth=0,
        reference_clip=reference,
        comparison_clip=comparison,
        attempt=attempt,
    )

    (target,) = result.targets
    assert target.resolution == "alternative_confirmed"
    expected_alternative_offsets = []
    for frame in target_frames:
        exact_1 = remap.get(frame - 1, frame - 1) == frame
        exact_3 = remap.get(frame - 3, frame - 3) == frame
        assert exact_3
        expected_alternative_offsets.append(1 if exact_1 else 3)
    assert [position.alternative_offset for position in target.positions] == (
        expected_alternative_offsets
    )
    assert result.check_points[0].suggested_comparison_frame == target_frames[0] - 1
    decided = _decide_video(attempt, result)
    assert decided.decision.state == "provisional"
    assert decided.decision.primary_reason == "competing_offset_confirmed_by_video"


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
    assert result.confirmed_offset == 0
    assert len(result.targets) == 1
    target = result.targets[0]
    assert target.alternative_offsets == (1, 2)
    assert target.credible is True
    assert (target.start_sample, target.end_sample) == (0, 8_000)
    assert 0 not in target.alternative_offsets


def test_v3a_nonzero_reference_start_targets_the_exact_disagreement(
    tmp_path: Path,
) -> None:
    reference = _moving_clip(frames=120)
    comparison = _remapped_clip(reference, lambda frame: frame + 2 if frame <= 24 else frame)
    attempt = _attempt_with_lags(
        (333, -333, -333, -333, -333, -333, -333, -333, -333, -333),
        global_lag=-333,
        chunk_samples=8_000,
        reference_audio_start=Fraction(1, 24),
    )

    result = _run(
        tmp_path,
        truth=0,
        reference_clip=reference,
        comparison_clip=comparison,
        attempt=attempt,
    )

    assert result.confirmed_offset == 0
    assert len(result.targets) == 1
    target = result.targets[0]
    assert (target.kind, target.first_chunk_index, target.last_chunk_index) == ("chunk", 0, 0)
    assert (target.start_sample, target.end_sample, target.target_offset) == (0, 8_000, 2)
    assert target.alternative_offsets == (1, 2, 3)
    target_frames = [position.reference_frame for position in target.positions]
    assert len(target_frames) == 4
    assert target_frames == sorted(target_frames)
    assert all(1 <= frame <= 24 for frame in target_frames)
    assert [position.winner for position in target.positions] == ["alternative"] * 4
    assert all(position.confirmed_score > 0.0 for position in target.positions)
    assert all(position.alternative_score == 0.0 for position in target.positions)
    assert target.resolution == "alternative_confirmed"
    winners = {
        position.reference_frame: alignment_video._position_winner(
            position.score_by_offset, result.scored_offsets
        )[0]
        for position in result.positions
    }
    contrast = next(frame for frame, winner in winners.items() if winner == 0)
    assert [
        (point.reference_frame, point.suggested_comparison_frame) for point in result.check_points
    ] == [(target_frames[0], target_frames[0] - target.target_offset), (contrast, contrast)]
    decided = _decide_video(attempt, result)
    assert decided.decision.state == "provisional"
    assert decided.decision.primary_reason == "competing_offset_confirmed_by_video"
    assert decided.decision.candidate is not None
    assert decided.decision.candidate.frame_offset == 0


def test_a4b_boundary_regroups_frame_distinct_tail_as_one_run() -> None:
    attempt = _attempt(rounded=0, planned=4)
    chunks = (
        ChunkObservation(0, 0, 10, True, 0, 100.0, True, True),
        ChunkObservation(1, 10, 10, True, 166, 100.0, True, False),
        ChunkObservation(2, 20, 10, True, 167, 99.0, True, False),
        ChunkObservation(3, 30, 10, True, 168, 98.0, True, False),
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


def test_real_scoring_run_with_one_winning_position_stays_unresolved(
    tmp_path: Path,
) -> None:
    reference = _motion_ranges_clip(range(60, 70), range(96, 180))
    attempt = _attempt_with_lags((667, 667, 0, 0, 0, 0, 0, 0, 0, 0))
    result = _run(
        tmp_path,
        truth=0,
        reference_clip=reference,
        comparison_clip=reference,
        attempt=attempt,
    )

    assert result.confirmed_offset == 0
    assert len(result.targets) == 1
    target = result.targets[0]
    assert (target.kind, target.first_chunk_index, target.last_chunk_index) == ("run", 0, 1)
    assert len(target.positions) == 4
    assert all(0 <= position.reference_frame <= 95 for position in target.positions)
    (winner,) = [position for position in target.positions if position.winner == "confirmed"]
    assert winner.reference_frame in range(60, 70)
    assert winner.confirmed_score == 0.0 < winner.alternative_score
    neither = [position for position in target.positions if position.winner == "neither"]
    assert len(neither) == 3
    assert all(
        position.confirmed_score == position.alternative_score == 0.0 for position in neither
    )
    assert target.resolution == "unresolved"
    base_winners = [
        alignment_video._position_winner(position.score_by_offset, result.scored_offsets)
        for position in result.positions
    ]
    assert base_winners.count((0, float("inf"))) == 7
    assert base_winners.count((None, 0.0)) == 5
    decided = _decide_video(attempt, result)
    assert decided.decision.state == "provisional"
    assert decided.decision.primary_reason == "competing_offset"
    assert decided.decision.candidate is not None
    assert decided.decision.candidate.frame_offset == 0


def test_position_ties_and_periodic_aliases_are_not_informative() -> None:
    offsets = (-2, -1, 0, 1, 2)
    assert alignment_video._position_winner((1.0, 0.0, 0.0, 1.0, 2.0), offsets)[0] is None
    assert alignment_video._position_winner((1.0, 0.9, 0.5, 0.9, 0.5), offsets)[0] is None


@pytest.mark.parametrize("cadence", ["duplicated", "periodic"])
def test_real_cadence_aliases_do_not_confirm_a_wrong_offset(tmp_path: Path, cadence: str) -> None:
    moving = _moving_clip(frames=120)
    reference = _remapped_clip(
        moving,
        (lambda frame: frame // 2) if cadence == "duplicated" else (lambda frame: frame % 2),
    )
    attempt = _attempt_with_lags((333,) * 10, global_lag=333)
    result = _run(
        tmp_path,
        truth=0,
        reference_clip=reference,
        comparison_clip=reference,
        attempt=attempt,
    )

    assert result.scored_offsets == (-1, 0, 1, 2, 3)
    assert result.confirmed_offset is None
    assert len(result.positions) == 12
    winners = [
        alignment_video._position_winner(position.score_by_offset, result.scored_offsets)
        for position in result.positions
    ]
    assert winners == [(None, 0.0)] * 12
    assert all(position.score_by_offset.count(0.0) >= 2 for position in result.positions)
    decided = _decide_video(attempt, result)
    assert decided.decision.state == "provisional"
    assert decided.decision.primary_reason == "video_check_inconclusive"


def test_real_minority_position_edit_does_not_confirm_the_edit_offset(
    tmp_path: Path,
) -> None:
    reference = _moving_clip(frames=120)
    comparison = _remapped_clip(
        reference,
        lambda frame: frame + 1 if 5 <= frame <= 27 else frame,
    )
    result = _run(
        tmp_path,
        truth=0,
        reference_clip=reference,
        comparison_clip=comparison,
    )
    winners_and_margins = [
        alignment_video._position_winner(position.score_by_offset, result.scored_offsets)
        for position in result.positions
    ]

    assert len(result.positions) == 12
    assert winners_and_margins == [
        (1, float("inf")),
        (1, float("inf")),
        (1, float("inf")),
        *((0, float("inf")),) * 9,
    ]
    assert all(
        position.reference_frame in range(5, 28)
        for position, (winner, _margin) in zip(result.positions, winners_and_margins, strict=True)
        if winner == 1
    )
    assert all(
        position.reference_frame not in range(5, 28)
        for position, (winner, _margin) in zip(result.positions, winners_and_margins, strict=True)
        if winner == 0
    )
    assert result.confirmed_offset == 0
    decided = _decide_video(_attempt_with_lags((0,) * 10), result)
    assert decided.decision.state == "trusted_automatic"
    assert decided.decision.primary_reason == "audio_video_confirmed"
    assert decided.decision.candidate is not None
    assert decided.decision.candidate.frame_offset == 0


def test_inconclusive_video_still_has_review_check_points(tmp_path: Path) -> None:
    clip = vs.core.std.BlankClip(width=64, height=36, length=60, format=vs.GRAYS, color=0)
    result = _run(tmp_path, truth=0, reference_clip=clip, comparison_clip=clip)
    assert result.confirmed_offset is None
    assert len(result.check_points) == 5


def _checkpoint_target(
    index: int,
    frame: int,
    offset: int,
    alternatives: tuple[int, ...],
    *,
    resolution: str = "unresolved",
    winner: Literal["confirmed", "neither"] = "neither",
) -> alignment_video.VideoTargetEvidence:
    return alignment_video.VideoTargetEvidence(
        kind="chunk",
        first_chunk_index=index,
        last_chunk_index=index,
        credible=True,
        start_sample=index * 240_000,
        end_sample=(index + 1) * 240_000,
        target_offset=offset,
        alternative_offsets=alternatives,
        resolution=resolution,
        positions=(alignment_video.VideoTargetPosition(index, frame, 0.1, 1.0, winner),),
    )


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
    target = _checkpoint_target(1, 500, 246, (245, 246, 247))

    points = alignment_video._check_points(
        (),
        (target,),
        confirmed=146,
        scored_offsets=(144, 145, 146, 147, 148),
        fps_reference=FPS,
    )

    assert points == (alignment_video.VideoCheckPoint(500 / float(FPS), 500, 254),)


def test_check_points_keep_adjacent_distinct_target_offsets_separate() -> None:
    points = alignment_video._check_points(
        (
            alignment_video.VideoPositionDifference(
                position_index=0,
                reference_frame=900,
                score_by_offset=(2.0, 1.0, 0.1, 1.0, 2.0),
            ),
        ),
        (
            _checkpoint_target(1, 500, 145, (145, 146)),
            _checkpoint_target(2, 700, 146, (145, 146, 147)),
        ),
        confirmed=144,
        scored_offsets=(142, 143, 144, 145, 146),
        fps_reference=FPS,
        chunks=(
            ChunkObservation(1, 0, 10, True, 0, 100.0, True, False),
            ChunkObservation(2, 10, 10, True, 0, 90.0, True, False),
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

    targets = tuple(
        _checkpoint_target(index, frame, alternative, (alternative,))
        for index, frame, alternative, _ in specifications
    )
    chunks = tuple(
        ChunkObservation(
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
            alignment_video.VideoTargetPosition(3, 201, 1.0, 0.1, "alternative", 1),
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
            ChunkObservation(0, 0, 10, True, 0, 80.0, True, False),
            ChunkObservation(1, 10, 10, True, 0, 80.0, True, False),
            ChunkObservation(2, 20, 10, True, 0, 90.0, True, False),
            ChunkObservation(4, 40, 10, True, 0, 100.0, True, False),
        ),
    )

    assert [(point.reference_frame, point.suggested_comparison_frame) for point in points] == [
        (101, 100),
        (201, 200),
        (401, 401),
        (900, 900),
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
        1 if winner == "alternative" else None,
    )
    actual_resolution = alignment_video._target_resolution(
        "run",
        (position,),
        credible=True,
    )
    assert actual_resolution == resolution
    target = alignment_video.VideoTargetEvidence(
        kind="run",
        first_chunk_index=0,
        last_chunk_index=1,
        credible=True,
        start_sample=0,
        end_sample=20,
        target_offset=1,
        alternative_offsets=(1, 2),
        resolution=actual_resolution,
        positions=(position,),
    )
    observation = VideoCheckObservation(
        observation="observed",
        scored_offsets=(-2, -1, 0, 1, 2),
        confirmed_offset=0,
        index_build_seconds=0.0,
        positions=(),
        targets=(target,),
    )
    assert observation.targets == (target,)

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
        alignment_video.VideoTargetPosition(2, 102, 1.0, 0.1, "alternative", 1),
    )
    resolution = alignment_video._target_resolution("run", positions, credible=True)
    assert resolution == "alternative_confirmed"
    target = alignment_video.VideoTargetEvidence(
        kind="run",
        first_chunk_index=0,
        last_chunk_index=1,
        credible=True,
        start_sample=0,
        end_sample=20,
        target_offset=1,
        alternative_offsets=(1, 2),
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
        chunks=(ChunkObservation(1, 10, 10, True, 0, 100.0, True, False),),
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
        "_target_range",
        lambda target, **_kwargs: (
            target.first_index * 10 + 1,
            target.first_index * 10 + 40,
        ),
    )

    def score_hypotheses(
        _reference_node: object,
        _comparison_node: object,
        reference_frame: int,
        _confirmed: int,
        _alternative_offsets: object,
        **_kwargs: object,
    ) -> tuple[float, float, int]:
        scored_frames.append(reference_frame)
        return 0.1, 1.0, 1

    monkeypatch.setattr(alignment_video, "_score_hypotheses", score_hypotheses)

    result = _run(tmp_path, truth=0, attempt=_attempt(rounded=0, planned=4))

    assert len(scored_frames) == 12
    assert result.targets[-1].resolution == "unexamined"
    assert result.targets[-1].positions == ()
    assert any(
        point.reference_frame == 31 and point.suggested_comparison_frame == 26
        for point in result.check_points
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
    targets = tuple(
        _checkpoint_target(
            index,
            100 * index,
            index,
            (index,),
            resolution="resolved",
            winner="confirmed",
        )
        for index in range(1, 5)
    )
    chunks = tuple(
        ChunkObservation(index, (index - 1) * 10, 10, True, 0, 100.0, True, False)
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

    assert [point.reference_frame for point in points] == [100, 900]


def test_video_check_reuses_only_selected_luma_with_identical_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = _moving_clip(frames=180)
    attempt = _attempt_with_lags((333, 0, 0, 0, 0, 0, 0, 0, 0, 0), chunk_samples=8_000)
    select = alignment_video._motion_positions
    read = alignment_video._read_frame
    reuse = False
    retained_counts: list[int] = []
    retained_bytes: list[int] = []
    reads = 0

    def select_frames(
        node: vs.VideoNode,
        start: float | int,
        end: float | int,
        count: int,
        *,
        cancellation: Event | None,
        retained_frames: dict[int, alignment_video.FloatFrame] | None = None,
    ) -> tuple[int, ...] | None:
        if retained_frames is not None:
            assert not retained_frames
        selected = select(
            node,
            start,
            end,
            count,
            cancellation=cancellation,
            retained_frames=retained_frames if reuse else None,
        )
        if retained_frames is not None:
            retained_counts.append(len(retained_frames))
            retained_bytes.append(sum(image.nbytes for image in retained_frames.values()))
        return selected

    def read_frame(node: vs.VideoNode, frame: int) -> alignment_video.FloatFrame:
        nonlocal reads
        reads += 1
        return read(node, frame)

    monkeypatch.setattr(alignment_video, "_motion_positions", select_frames)
    monkeypatch.setattr(alignment_video, "_read_frame", read_frame)
    baseline = _run(tmp_path, truth=0, reference_clip=reference, attempt=attempt)
    baseline_reads = reads
    reads = 0
    reuse = True
    result = _run(tmp_path, truth=0, reference_clip=reference, attempt=attempt)

    assert result.targets and result.targets[0].positions
    assert replace(result, index_build_seconds=0.0) == replace(baseline, index_build_seconds=0.0)
    assert _decide_video(attempt, result).decision == _decide_video(attempt, baseline).decision
    selected_count = len(result.positions) + sum(len(target.positions) for target in result.targets)
    assert baseline_reads - reads == selected_count
    assert max(retained_counts) == 12
    assert max(retained_bytes) <= 12 * 320 * 180 * np.dtype(np.float32).itemsize
