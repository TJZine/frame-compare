"""Tests for content-sampled active-picture rectangle detection."""

from __future__ import annotations

import gc
import sys
import weakref
from collections.abc import Iterator, Sequence
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import GeneratorType, SimpleNamespace
from typing import TYPE_CHECKING, cast

import numpy as np
import numpy.typing as npt
import pytest

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection
from frame_compare.orchestration.active_rect_content import (
    ActiveRectContentDetectionError,
    ContentActiveRect,
    VSActiveRectFrameSampler,
    detect_content_active_rect,
    refine_auto_content_active_rects_for_clips,
    sample_source_frame_indices,
)
from frame_compare.orchestration.context import (
    ClipActiveRect,
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
)

if TYPE_CHECKING:
    from frame_compare.vs.loader import VSLoader


def _clip(
    *,
    name: str = "source.mkv",
    num_frames: int = 100,
    trim_start_frames: int = 0,
) -> ClipState:
    path = Path(name)
    return ClipState(
        path=path,
        label="source",
        probe=ClipProbeSnapshot(
            fingerprint=ClipFingerprint(path=path, size_bytes=100, mtime_ns=1),
            width=100,
            height=80,
            num_frames=num_frames,
            fps=Fraction(24, 1),
            is_hdr=False,
        ),
        source_fps=Fraction(24, 1),
        effective_fps=Fraction(24, 1),
    ).with_trim(
        trim_start_frames=trim_start_frames,
        trim_end_frame_inclusive=None,
    )


def _content_pattern(height: int, width: int) -> npt.NDArray[np.float32]:
    y = np.linspace(0.20, 0.80, height, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 0.20, width, dtype=np.float32)[None, :]
    return (y + x).astype(np.float32)


def _letterbox_frame(
    *,
    width: int = 100,
    height: int = 80,
    top: int = 10,
    bottom: int = 10,
    bar_value: float = 0.065,
) -> npt.NDArray[np.float32]:
    frame = np.full((height, width), bar_value, dtype=np.float32)
    frame[top : height - bottom, :] = _content_pattern(height - top - bottom, width)
    return frame


def _pillarbox_frame(
    *,
    width: int = 100,
    height: int = 80,
    left: int = 12,
    right: int = 12,
    bar_value: float = 0.065,
) -> npt.NDArray[np.float32]:
    frame = np.full((height, width), bar_value, dtype=np.float32)
    frame[:, left : width - right] = _content_pattern(height, width - left - right)
    return frame


def test_stable_top_bottom_letterbox_bars_produce_content_rect() -> None:
    frames = [_letterbox_frame(top=10, bottom=10) for _index in range(8)]

    rect = detect_content_active_rect(frames)

    assert rect == ContentActiveRect(x=0, y=10, width=100, height=60)


def test_detector_streams_frames_without_retaining_previous_arrays() -> None:
    def stream_frames() -> Iterator[npt.NDArray[np.float32]]:
        for _index in range(8):
            frame = _letterbox_frame(top=10, bottom=10)
            reference = weakref.ref(frame)
            yield frame
            del frame
            gc.collect()
            assert reference() is None

    rect = detect_content_active_rect(stream_frames())

    assert rect == ContentActiveRect(x=0, y=10, width=100, height=60)


def test_vs_sampler_fetches_frames_lazily_and_releases_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    source_references: list[weakref.ReferenceType[FakeSource]] = []

    class FakeFrame:
        def __getitem__(self, plane: int) -> npt.NDArray[np.float32]:
            assert plane == 0
            return _letterbox_frame(top=10, bottom=10)

    class FakeNode:
        format = SimpleNamespace(color_family=1, sample_type=2, bits_per_sample=32)

        def get_frame(self, index: int) -> FakeFrame:
            events.append(f"frame:{index}")
            return FakeFrame()

    class FakeSource:
        def __init__(self) -> None:
            self.clip = FakeNode()

    class FakeLoader:
        def load(self, _path: Path) -> FakeSource:
            events.append("load")
            source = FakeSource()
            source_references.append(weakref.ref(source))
            return source

    fake_vs = SimpleNamespace(YUV=1, FLOAT=2, YUV420P8=3)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)
    sampler = VSActiveRectFrameSampler(cast("VSLoader", FakeLoader()))

    frames = sampler.sample_luma_frames(_clip(), (3, 7, 11))

    assert isinstance(frames, GeneratorType)
    assert events == []
    sampled = next(frames)
    assert sampled.shape == (80, 100)
    assert events == ["load", "frame:3"]

    del sampled
    frames.close()
    gc.collect()
    assert source_references[0]() is None


def test_limited_range_off_black_bars_are_detected_when_stable() -> None:
    frames = [_letterbox_frame(top=10, bottom=10, bar_value=0.075) for _index in range(8)]

    rect = detect_content_active_rect(frames)

    assert rect == ContentActiveRect(x=0, y=10, width=100, height=60)


def test_stable_left_right_pillarbox_bars_produce_content_rect() -> None:
    frames = [_pillarbox_frame(left=12, right=12) for _index in range(8)]

    rect = detect_content_active_rect(frames)

    assert rect == ContentActiveRect(x=12, y=0, width=76, height=80)


def test_no_bars_returns_no_detection() -> None:
    frames = [_content_pattern(80, 100) for _index in range(8)]

    assert detect_content_active_rect(frames) is None


def test_inconsistent_margins_return_no_detection() -> None:
    frames = [
        *[_letterbox_frame(top=10, bottom=10) for _index in range(4)],
        *[_letterbox_frame(top=19, bottom=9) for _index in range(4)],
    ]

    assert detect_content_active_rect(frames) is None


def test_sparse_scene_specific_bars_do_not_meet_sample_agreement() -> None:
    frames = [
        *[_letterbox_frame(top=10, bottom=10) for _index in range(4)],
        *[_content_pattern(80, 100) for _index in range(12)],
    ]

    assert detect_content_active_rect(frames) is None


def test_all_dark_frames_return_no_detection() -> None:
    frames = [np.full((80, 100), 0.06, dtype=np.float32) for _index in range(8)]

    assert detect_content_active_rect(frames) is None


def test_fade_like_low_contrast_frames_return_no_detection() -> None:
    frame = np.full((80, 100), 0.065, dtype=np.float32)
    frame[10:70, :] = 0.085
    frames = [frame.copy() for _index in range(8)]

    assert detect_content_active_rect(frames) is None


def test_noisy_content_near_borders_does_not_overcrop() -> None:
    rng = np.random.default_rng(seed=1234)
    frames = [rng.uniform(0.05, 0.45, size=(80, 100)).astype(np.float32) for _index in range(8)]

    assert detect_content_active_rect(frames) is None


def test_crop_removing_more_than_max_axis_fraction_returns_no_detection() -> None:
    frames = [_letterbox_frame(top=20, bottom=20) for _index in range(8)]

    assert detect_content_active_rect(frames) is None


def test_tiny_margins_below_threshold_return_no_detection() -> None:
    frames = [_letterbox_frame(top=4, bottom=4) for _index in range(8)]

    assert detect_content_active_rect(frames) is None


def test_odd_detected_margins_preserve_source_frame_identity() -> None:
    frames = [_letterbox_frame(top=9, bottom=9) for _index in range(8)]

    rect = detect_content_active_rect(frames)

    assert rect == ContentActiveRect(x=0, y=9, width=100, height=62)


def test_one_frame_evidence_is_rejected() -> None:
    assert detect_content_active_rect([_letterbox_frame(top=10, bottom=10)]) is None


def test_sample_indices_use_trimmed_selection_window_source_domain() -> None:
    clip = _clip(num_frames=100, trim_start_frames=5)
    selection_window = SelectionWindow(start_frame=10, end_frame_exclusive=30)

    indices = sample_source_frame_indices(
        clip=clip,
        selection_window=selection_window,
        sample_count=4,
    )

    assert indices == (17, 22, 27, 32)


def test_auto_refinement_does_not_sample_static_non_full_frame_rects() -> None:
    clips = [
        _clip(num_frames=100),
        _clip(num_frames=100),
        _clip(num_frames=100),
        _clip(num_frames=100),
    ]
    clips = [
        replace(clips[0], active_rect=ClipActiveRect(0, 10, 100, 60, "explicit", "auto")),
        replace(clips[1], active_rect=ClipActiveRect(0, 10, 100, 60, "metadata", "auto")),
        replace(
            clips[2],
            active_rect=ClipActiveRect(0, 10, 100, 60, "dimension-derived", "auto"),
        ),
        replace(
            clips[3],
            active_rect=ClipActiveRect(0, 10, 100, 60, "aspect-ratio-derived", "auto"),
        ),
    ]

    class FailingSampler:
        def sample_luma_frames(self, _clip: ClipState, _indices: list[int]) -> list[object]:
            raise AssertionError("sampler should not be called")

    refined, warnings = refine_auto_content_active_rects_for_clips(
        clips=clips,
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
        detection=ScreenshotActiveRectDetection.AUTO,
        sampler=FailingSampler(),
        fail_closed=True,
    )

    assert refined == clips
    assert warnings == []


def test_normal_auto_refinement_keeps_successful_clip_when_later_clip_sampling_fails() -> None:
    clips = [
        replace(
            _clip(name="detected.mkv"),
            active_rect=ClipActiveRect(0, 0, 100, 80, "full-frame", "auto"),
        ),
        replace(
            _clip(name="failed.mkv"),
            active_rect=ClipActiveRect(0, 0, 100, 80, "full-frame", "auto"),
        ),
    ]

    class PartiallyFailingSampler:
        def sample_luma_frames(
            self,
            clip: ClipState,
            indices: list[int],
        ) -> list[np.ndarray[tuple[int, int], np.dtype[np.float32]]]:
            if clip.path.name == "failed.mkv":
                raise RuntimeError("sample boom")
            return [_letterbox_frame(top=10, bottom=10) for _index in indices]

    refined, warnings = refine_auto_content_active_rects_for_clips(
        clips=clips,
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
        detection=ScreenshotActiveRectDetection.AUTO,
        sampler=PartiallyFailingSampler(),
        fail_closed=False,
    )

    assert refined[0].active_rect == ClipActiveRect(0, 10, 100, 60, "content-derived", "auto")
    assert refined[1].active_rect == ClipActiveRect(0, 0, 100, 80, "full-frame", "auto")
    assert len(warnings) == 1
    assert "active-rect auto detection failed for failed.mkv" in warnings[0]


def test_full_window_retry_can_recompute_content_derived_rect() -> None:
    clip = replace(
        _clip(),
        active_rect=ClipActiveRect(0, 10, 100, 60, "content-derived", "auto"),
    )

    class FullWindowSampler:
        def sample_luma_frames(
            self,
            _clip: ClipState,
            indices: list[int],
        ) -> list[np.ndarray[tuple[int, int], np.dtype[np.float32]]]:
            return [_pillarbox_frame(left=12, right=12) for _index in indices]

    refined, warnings = refine_auto_content_active_rects_for_clips(
        clips=[clip],
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
        detection=ScreenshotActiveRectDetection.AUTO,
        sampler=FullWindowSampler(),
        fail_closed=False,
        recompute_content_derived=True,
    )

    assert refined[0].active_rect == ClipActiveRect(12, 0, 76, 80, "content-derived", "auto")
    assert warnings == []


def test_full_window_retry_clears_stale_content_rect_when_full_window_has_no_crop() -> None:
    clips = [
        replace(
            _clip(name="content-a.mkv"),
            active_rect=ClipActiveRect(0, 10, 100, 60, "content-derived", "auto"),
        ),
        replace(
            _clip(name="content-b.mkv"),
            active_rect=ClipActiveRect(0, 10, 100, 60, "content-derived", "auto"),
        ),
        replace(
            _clip(name="ratio-propagated.mkv"),
            active_rect=ClipActiveRect(0, 10, 100, 60, "aspect-ratio-derived", "auto"),
        ),
    ]

    class NoCropSampler:
        def sample_luma_frames(
            self,
            _clip: ClipState,
            indices: list[int],
        ) -> list[np.ndarray[tuple[int, int], np.dtype[np.float32]]]:
            return [_content_pattern(80, 100) for _index in indices]

    refined, warnings = refine_auto_content_active_rects_for_clips(
        clips=clips,
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
        detection=ScreenshotActiveRectDetection.AUTO,
        sampler=NoCropSampler(),
        fail_closed=True,
        recompute_content_derived=True,
    )

    assert [clip.active_rect for clip in refined] == [
        ClipActiveRect(0, 0, 100, 80, "full-frame", "auto"),
        ClipActiveRect(0, 0, 100, 80, "full-frame", "auto"),
        ClipActiveRect(0, 0, 100, 80, "full-frame", "auto"),
    ]
    assert warnings == []


def test_auto_refinement_maps_failure_raised_during_iterator_consumption() -> None:
    clip = replace(
        _clip(name="failed-during-iteration.mkv"),
        active_rect=ClipActiveRect(0, 0, 100, 80, "full-frame", "auto"),
    )

    class IterationFailingSampler:
        def sample_luma_frames(
            self,
            _clip: ClipState,
            _indices: Sequence[int],
        ) -> Iterator[npt.NDArray[np.float32]]:
            yield _letterbox_frame(top=10, bottom=10)
            raise RuntimeError("iteration boom")

    refined, warnings = refine_auto_content_active_rects_for_clips(
        clips=[clip],
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
        detection=ScreenshotActiveRectDetection.AUTO,
        sampler=IterationFailingSampler(),
        fail_closed=False,
    )

    assert refined == [clip]
    assert len(warnings) == 1
    assert "RuntimeError: iteration boom" in warnings[0]

    with pytest.raises(ActiveRectContentDetectionError, match="RuntimeError: iteration boom"):
        refine_auto_content_active_rects_for_clips(
            clips=[clip],
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
            detection=ScreenshotActiveRectDetection.AUTO,
            sampler=IterationFailingSampler(),
            fail_closed=True,
        )
