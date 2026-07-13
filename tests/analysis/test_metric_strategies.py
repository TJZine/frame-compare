"""Tests for metric computation strategies."""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import numpy as np
import pytest
import vapoursynth as vs_module

from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_identity import stable_metric_algorithm_identity_json
from frame_compare.analysis.metric_strategies import (
    calculate_metric_strategy,
    calculate_quality_luminance,
    calculate_quality_motion,
)
from frame_compare.analysis.timing import AnalysisTimingRecorder
from frame_compare.analysis.types import MetricActiveRect
from frame_compare.config.schema import AnalysisConfig
from frame_compare.utils.progress_protocol import ProgressReporter

vs_mock = vs_module

type FakeClipOp = tuple[str, int | None, int | None] | tuple[str, int, int, int, int]


class MockFrame:
    """Mock VapourSynth frame."""

    def __init__(self, data: np.ndarray):
        self._data = data

    def __getitem__(self, index: int) -> np.ndarray:
        if index == 0:
            return self._data
        raise IndexError("Mock only supports Y plane (index 0)")

    @property
    def props(self) -> dict:
        return {}


class MockClip:
    """Mock VapourSynth clip."""

    def __init__(self, frames: list[np.ndarray], fps: Fraction = Fraction(24, 1)):
        self._frames = [MockFrame(f) for f in frames]
        self.num_frames = len(frames)
        self.fps = MagicMock()
        self.fps.numerator = fps.numerator
        self.fps.denominator = fps.denominator
        self.width = frames[0].shape[1] if frames else 0
        self.height = frames[0].shape[0] if frames else 0
        self.format = MagicMock()
        self.format.color_family = vs_mock.YUV
        self.format.sample_type = vs_mock.INTEGER
        self.format.bits_per_sample = 8
        self.resize = MagicMock()

    def get_frame(self, n: int) -> MockFrame:
        if 0 <= n < self.num_frames:
            return self._frames[n]
        raise Exception(f"Frame {n} out of range")


class FakePlaneStatsFrame:
    def __init__(self, props: dict[str, float]):
        self.props = props


class FakePlaneStatsClip:
    def __init__(self, props_by_frame: list[dict[str, float]]):
        self._props_by_frame = props_by_frame
        self.num_frames = len(props_by_frame)

    def get_frame(self, n: int) -> FakePlaneStatsFrame:
        return FakePlaneStatsFrame(self._props_by_frame[n])


class FakeStd:
    def __init__(self, clip: FakeBalancedClip):
        self._clip = clip

    def PlaneStats(self, clipb: FakeBalancedClip | None = None) -> FakePlaneStatsClip:
        if clipb is None:
            return FakePlaneStatsClip([{"PlaneStatsAverage": value} for value in self._clip.values])
        return FakePlaneStatsClip(
            [
                {
                    "PlaneStatsAverage": current,
                    "PlaneStatsDiff": abs(current - previous),
                }
                for current, previous in zip(self._clip.values, clipb.values, strict=True)
            ]
        )

    def CropAbs(
        self,
        *,
        width: int,
        height: int,
        left: int,
        top: int,
    ) -> FakeBalancedClip:
        self._clip.crop_calls.append(("CropAbs", left, top, width, height))
        self._clip.ops.append(("CropAbs", left, top, width, height))
        return FakeBalancedClip(
            self._clip.values,
            width=width,
            height=height,
            color_family=self._clip.format.color_family,
            resize_calls=self._clip.resize_calls,
            crop_calls=self._clip.crop_calls,
            ops=self._clip.ops,
        )


class FakeResize:
    def __init__(self, clip: FakeBalancedClip):
        self._clip = clip

    def Bicubic(
        self,
        *,
        width: int | None = None,
        height: int | None = None,
        format: int | None = None,
    ) -> FakeBalancedClip:
        color_family = self._clip.format.color_family
        if format is not None:
            color_family = FAKE_VS.YUV if format == FAKE_VS.YUV420P8 else color_family
        self._clip.resize_calls.append(("Bicubic", width, height))
        self._clip.ops.append(("Bicubic", width, height))
        return FakeBalancedClip(
            self._clip.values,
            width=self._clip.width if width is None else width,
            height=self._clip.height if height is None else height,
            color_family=color_family,
            resize_calls=self._clip.resize_calls,
            crop_calls=self._clip.crop_calls,
            ops=self._clip.ops,
        )

    def Bilinear(
        self,
        *,
        width: int,
        height: int,
    ) -> FakeBalancedClip:
        self._clip.resize_calls.append(("Bilinear", width, height))
        self._clip.ops.append(("Bilinear", width, height))
        return FakeBalancedClip(
            self._clip.values,
            width=width,
            height=height,
            color_family=self._clip.format.color_family,
            resize_calls=self._clip.resize_calls,
            crop_calls=self._clip.crop_calls,
            ops=self._clip.ops,
        )


class FakeBalancedClip:
    def __init__(
        self,
        values: list[float],
        *,
        width: int = 640,
        height: int = 360,
        color_family: int = 1,
        resize_calls: list[tuple[str, int | None, int | None]] | None = None,
        crop_calls: list[tuple[str, int, int, int, int]] | None = None,
        ops: list[FakeClipOp] | None = None,
    ):
        self.values = values
        self.num_frames = len(values)
        self.width = width
        self.height = height
        self.format = SimpleNamespace(color_family=color_family)
        self.resize_calls = [] if resize_calls is None else resize_calls
        self.crop_calls = [] if crop_calls is None else crop_calls
        self.ops = [] if ops is None else ops
        self.resize = FakeResize(self)
        self.std = FakeStd(self)

    def __getitem__(self, item: slice) -> FakeBalancedClip:
        return FakeBalancedClip(
            self.values[item],
            width=self.width,
            height=self.height,
            color_family=self.format.color_family,
            resize_calls=self.resize_calls,
            crop_calls=self.crop_calls,
            ops=self.ops,
        )

    def __add__(self, other: object) -> FakeBalancedClip:
        if not isinstance(other, FakeBalancedClip):
            return NotImplemented
        return FakeBalancedClip(
            [*self.values, *other.values],
            width=self.width,
            height=self.height,
            color_family=self.format.color_family,
            resize_calls=self.resize_calls,
            crop_calls=self.crop_calls,
            ops=self.ops,
        )


class FakeCoreStd:
    def ShufflePlanes(
        self,
        *,
        clips: FakeBalancedClip,
        planes: int,
        colorfamily: int,
    ) -> FakeBalancedClip:
        assert planes == 0
        return FakeBalancedClip(
            clips.values,
            width=clips.width,
            height=clips.height,
            color_family=colorfamily,
            resize_calls=clips.resize_calls,
            crop_calls=clips.crop_calls,
            ops=clips.ops,
        )

    def Splice(self, *, clips: list[object]) -> FakeBalancedClip:
        typed_clips = [clip for clip in clips if isinstance(clip, FakeBalancedClip)]
        assert len(typed_clips) == len(clips)
        first = typed_clips[0]
        return FakeBalancedClip(
            [value for clip in typed_clips for value in clip.values],
            width=first.width,
            height=first.height,
            color_family=first.format.color_family,
            resize_calls=first.resize_calls,
            crop_calls=first.crop_calls,
            ops=first.ops,
        )


FAKE_VS = SimpleNamespace(
    YUV=1,
    YUV420P8=2,
    GRAY=3,
    FLOAT=1,
    core=SimpleNamespace(std=FakeCoreStd()),
)


@pytest.fixture
def mock_reporter():
    return MagicMock(spec=ProgressReporter)


def test_calculate_luminance_black_frames_returns_zeros():
    frames = [np.zeros((10, 10), dtype=np.uint8) for _ in range(3)]
    clip = MockClip(frames)
    luminance = calculate_quality_luminance(clip)  # type: ignore
    assert luminance == [0.0, 0.0, 0.0]


def test_calculate_luminance_white_frames_returns_ones():
    frames = [np.full((10, 10), 255, dtype=np.uint8) for _ in range(3)]
    clip = MockClip(frames)
    luminance = calculate_quality_luminance(clip)  # type: ignore
    assert luminance == [1.0, 1.0, 1.0]


def test_calculate_luminance_single_frame():
    frames = [np.full((10, 10), 127, dtype=np.uint8)]
    clip = MockClip(frames)
    luminance = calculate_quality_luminance(clip)  # type: ignore
    assert len(luminance) == 1
    assert pytest.approx(luminance[0], abs=1e-2) == 127 / 255


def test_calculate_luminance_calls_progress_reporter(mock_reporter):
    frames = [np.zeros((10, 10), dtype=np.uint8) for _ in range(5)]
    clip = MockClip(frames)
    calculate_quality_luminance(clip, reporter=mock_reporter)  # type: ignore
    mock_reporter.start_phase.assert_called_once_with("Calculating luminance", 5)
    assert mock_reporter.advance.call_count == 5
    mock_reporter.complete_phase.assert_called_once()


def test_calculate_motion_static_clip_returns_zeros():
    frames = [np.full((10, 10), 100, dtype=np.uint8) for _ in range(3)]
    clip = MockClip(frames)
    motion = calculate_quality_motion(clip)  # type: ignore
    assert motion == [0.0, 0.0, 0.0]


def test_calculate_motion_first_frame_is_zero():
    frames = [
        np.zeros((10, 10), dtype=np.uint8),
        np.full((10, 10), 255, dtype=np.uint8),
    ]
    clip = MockClip(frames)
    motion = calculate_quality_motion(clip)  # type: ignore
    assert motion[0] == 0.0
    assert motion[1] == 1.0


def test_calculate_motion_changing_frames_returns_positive():
    frames = [
        np.zeros((10, 10), dtype=np.uint8),
        np.full((10, 10), 127, dtype=np.uint8),
    ]
    clip = MockClip(frames)
    motion = calculate_quality_motion(clip)  # type: ignore
    assert motion[0] == 0.0
    assert 0.0 < motion[1] < 1.0


def test_calculate_motion_single_frame_returns_single_zero():
    frames = [np.zeros((10, 10), dtype=np.uint8)]
    clip = MockClip(frames)
    motion = calculate_quality_motion(clip)  # type: ignore
    assert motion == [0.0]


def test_calculate_motion_output_length_equals_num_frames():
    frames = [np.zeros((10, 10), dtype=np.uint8) for _ in range(10)]
    clip = MockClip(frames)
    motion = calculate_quality_motion(clip)  # type: ignore
    assert len(motion) == 10


def test_calculate_motion_calls_progress_reporter(mock_reporter):
    frames = [np.zeros((10, 10), dtype=np.uint8) for _ in range(5)]
    clip = MockClip(frames)
    calculate_quality_motion(clip, reporter=mock_reporter)  # type: ignore
    mock_reporter.start_phase.assert_called_once_with("Calculating motion", 4)
    assert mock_reporter.advance.call_count == 4
    mock_reporter.complete_phase.assert_called_once()


def test_calculate_luminance_empty_clip_raises_error():
    clip = MockClip([])
    with pytest.raises(MetricsCalculationError, match="Empty clip"):
        calculate_quality_luminance(clip)  # type: ignore


def test_calculate_motion_empty_clip_raises_error():
    clip = MockClip([])
    with pytest.raises(MetricsCalculationError, match="Empty clip"):
        calculate_quality_motion(clip)  # type: ignore


def test_calculate_metrics_frame_access_failure_raises_fc4002():
    clip = MagicMock()
    clip.num_frames = 1
    clip.format.color_family = vs_mock.YUV
    clip.format.sample_type = vs_mock.INTEGER
    clip.format.bits_per_sample = 8
    clip.get_frame.side_effect = Exception("VS Error")

    with pytest.raises(MetricsCalculationError) as exc:
        calculate_quality_luminance(clip)  # type: ignore
    assert exc.value.code == "FC-4002"


def test_quality_strategy_dispatch_matches_direct_quality_helpers() -> None:
    frames = [
        np.zeros((4, 4), dtype=np.uint8),
        np.full((4, 4), 64, dtype=np.uint8),
        np.full((4, 4), 255, dtype=np.uint8),
    ]
    clip = MockClip(frames)
    source = MagicMock()
    source.clip = clip

    direct_luminance = calculate_quality_luminance(clip)
    direct_motion = calculate_quality_motion(clip)
    result = calculate_metric_strategy(source, AnalysisConfig(), reporter=None)

    assert result.luminance == direct_luminance
    assert result.motion == direct_motion
    assert len(result.luminance) == clip.num_frames
    assert len(result.motion) == clip.num_frames
    assert result.motion[0] == 0.0
    assert result.performance_mode == "quality"
    assert result.metric_backend == "python_numpy"


def test_quality_active_rect_ignores_border_pixels_for_luminance() -> None:
    frame = np.full((4, 4), 255, dtype=np.uint8)
    frame[1:3, 1:3] = 0
    clip = MockClip([frame])
    source = MagicMock()
    source.clip = clip

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(),
        reporter=None,
        metric_active_rect=MetricActiveRect(x=1, y=1, width=2, height=2),
    )

    assert result.luminance == [0.0]
    assert result.motion == [0.0]


def test_quality_active_rect_ignores_cropped_out_changes_for_motion() -> None:
    first = np.zeros((4, 4), dtype=np.uint8)
    second = np.zeros((4, 4), dtype=np.uint8)
    second[:, 0] = 255
    second[:, 3] = 255
    clip = MockClip([first, second])
    source = MagicMock()
    source.clip = clip

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(),
        reporter=None,
        metric_active_rect=MetricActiveRect(x=1, y=0, width=2, height=4),
    )

    assert result.motion == [0.0, 0.0]


def test_quality_default_strategy_reads_each_frame_once() -> None:
    frames = [
        np.zeros((4, 4), dtype=np.uint8),
        np.full((4, 4), 64, dtype=np.uint8),
        np.full((4, 4), 255, dtype=np.uint8),
    ]
    clip = MockClip(frames)
    clip.get_frame = MagicMock(side_effect=clip.get_frame)
    source = MagicMock()
    source.clip = clip

    result = calculate_metric_strategy(source, AnalysisConfig(), reporter=None)

    assert result.motion[0] == 0.0
    assert clip.get_frame.call_args_list == [call(0), call(1), call(2)]


def test_invalid_active_rect_raises_metrics_calculation_error() -> None:
    clip = MockClip([np.zeros((4, 4), dtype=np.uint8)])
    source = MagicMock()
    source.clip = clip

    with pytest.raises(MetricsCalculationError, match="active_rect is outside"):
        calculate_metric_strategy(
            source,
            AnalysisConfig(),
            reporter=None,
            metric_active_rect=MetricActiveRect(x=3, y=0, width=2, height=4),
        )


def test_performance_strategy_rejects_empty_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([])

    with pytest.raises(MetricsCalculationError, match="Analysis clip has 0 frames"):
        calculate_metric_strategy(
            source,
            AnalysisConfig(performance_mode="performance"),
            reporter=None,
        )


def test_performance_strategy_returns_full_length_dense_arrays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([0.0, 0.25, 0.75, 1.0])

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.luminance == [0.0, 0.25, 0.75, 1.0]
    assert result.motion == [0.0, 0.25, 0.5, 0.25]
    assert len(result.luminance) == source.clip.num_frames
    assert len(result.motion) == source.clip.num_frames
    assert result.motion[0] == 0.0
    assert result.performance_mode == "performance"
    assert result.metric_backend == "vapoursynth_planestats"


def test_performance_strategy_records_one_combined_render_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([0.0, 0.25, 0.75, 1.0])
    recorder = AnalysisTimingRecorder()

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
        timing_recorder=recorder,
    )

    assert result.luminance == [0.0, 0.25, 0.75, 1.0]
    assert result.motion == [0.0, 0.25, 0.5, 0.25]
    assert set(recorder.as_dict()) == {
        "metric_graph_build",
        "performance_frame_render",
        "performance_graph_build",
        "performance_metric_read",
    }


def test_performance_strategy_crops_before_resize_and_remains_dense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([0.0, 0.25, 0.75], width=640, height=360)

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
        metric_active_rect=MetricActiveRect(x=10, y=20, width=400, height=200),
    )

    assert source.clip.crop_calls == [("CropAbs", 10, 20, 400, 200)]
    assert source.clip.resize_calls == [("Bicubic", 320, 160)]
    assert source.clip.ops == [("CropAbs", 10, 20, 400, 200), ("Bicubic", 320, 160)]
    assert result.luminance == [0.0, 0.25, 0.75]
    assert result.motion == [0.0, 0.25, 0.5]
    assert len(result.luminance) == 3
    assert len(result.motion) == 3
    assert result.motion[0] == 0.0


def test_performance_strategy_one_frame_motion_is_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([0.5])

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.luminance == [0.5]
    assert result.motion == [0.0]


def test_performance_strategy_constant_clip_is_deterministic_with_zero_motion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([0.25, 0.25, 0.25], width=160, height=90)
    config = AnalysisConfig(performance_mode="performance")

    first = calculate_metric_strategy(source, config, reporter=None)
    second = calculate_metric_strategy(source, config, reporter=None)

    assert first.luminance == [0.25, 0.25, 0.25]
    assert first.motion == [0.0, 0.0, 0.0]
    assert second.luminance == first.luminance
    assert second.motion == first.motion


def test_performance_strategy_simple_transition_has_motion_at_current_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([0.0, 1.0], width=640, height=360)

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.motion[0] == 0.0
    assert result.motion[1] > result.motion[0]


def test_performance_metric_identity_is_distinct_and_stable() -> None:
    quality = stable_metric_algorithm_identity_json(AnalysisConfig(performance_mode="quality"))
    first_performance = stable_metric_algorithm_identity_json(
        AnalysisConfig(performance_mode="performance")
    )
    second_performance = stable_metric_algorithm_identity_json(
        AnalysisConfig(performance_mode="performance")
    )

    assert first_performance == second_performance
    assert len({quality, first_performance}) == 2
    assert '"performance_mode":"performance"' in first_performance
    assert '"target_max_width":320' in first_performance
    assert '"resize":"bicubic"' in first_performance
    assert '"temporal":"all_adjacent_pairs"' in first_performance
    parsed_performance = json.loads(first_performance)
    assert parsed_performance["luminance"]["spatial"] == "active_rect_aware_luma_resize"
    assert parsed_performance["motion"]["spatial"] == "active_rect_aware_luma_resize"
    assert '"x"' not in first_performance
    assert "coarse_to_refined" not in first_performance


def test_performance_strategy_static_clip_has_zero_motion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([0.25, 0.25, 0.25], width=160)

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.luminance == [0.25, 0.25, 0.25]
    assert result.motion == [0.0, 0.0, 0.0]
