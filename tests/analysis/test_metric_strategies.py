"""Tests for metric computation strategies."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_identity import stable_metric_algorithm_identity_json
from frame_compare.analysis.metric_strategies import (
    calculate_metric_strategy,
    calculate_performance_planestats_metrics,
    calculate_quality_planestats_metrics,
)
from frame_compare.analysis.timing import AnalysisTimingRecorder
from frame_compare.analysis.types import MetricActiveRect, MetricFrameRange
from frame_compare.config.schema import AnalysisConfig
from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter

type FakeClipOp = tuple[str, int | None, int | None] | tuple[str, int, int, int, int]


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
        self._clip.planestats_clipb_flags.append(clipb is not None)
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
            planestats_clipb_flags=self._clip.planestats_clipb_flags,
            slice_calls=self._clip.slice_calls,
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
            planestats_clipb_flags=self._clip.planestats_clipb_flags,
            slice_calls=self._clip.slice_calls,
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
            planestats_clipb_flags=self._clip.planestats_clipb_flags,
            slice_calls=self._clip.slice_calls,
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
        planestats_clipb_flags: list[bool] | None = None,
        slice_calls: list[tuple[int | None, int | None, int | None]] | None = None,
    ):
        self.values = values
        self.num_frames = len(values)
        self.width = width
        self.height = height
        self.format = SimpleNamespace(color_family=color_family)
        self.resize_calls = [] if resize_calls is None else resize_calls
        self.crop_calls = [] if crop_calls is None else crop_calls
        self.ops = [] if ops is None else ops
        self.planestats_clipb_flags = (
            [] if planestats_clipb_flags is None else planestats_clipb_flags
        )
        self.slice_calls = [] if slice_calls is None else slice_calls
        self.resize = FakeResize(self)
        self.std = FakeStd(self)

    def __getitem__(self, item: slice) -> FakeBalancedClip:
        self.slice_calls.append((item.start, item.stop, item.step))
        return FakeBalancedClip(
            self.values[item],
            width=self.width,
            height=self.height,
            color_family=self.format.color_family,
            resize_calls=self.resize_calls,
            crop_calls=self.crop_calls,
            ops=self.ops,
            planestats_clipb_flags=self.planestats_clipb_flags,
            slice_calls=self.slice_calls,
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
            planestats_clipb_flags=self.planestats_clipb_flags,
            slice_calls=self.slice_calls,
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
            planestats_clipb_flags=clips.planestats_clipb_flags,
            slice_calls=clips.slice_calls,
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
            planestats_clipb_flags=first.planestats_clipb_flags,
            slice_calls=first.slice_calls,
        )


FAKE_VS = SimpleNamespace(
    YUV=1,
    YUV420P8=2,
    GRAY=3,
    FLOAT=1,
    core=SimpleNamespace(std=FakeCoreStd()),
)


def test_quality_strategy_dispatch_matches_full_resolution_planestats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    clip = FakeBalancedClip([0.0, 0.25, 1.0], width=3840, height=2160)
    source = MagicMock()
    source.clip = clip

    direct_luminance, direct_motion = calculate_quality_planestats_metrics(clip)
    result = calculate_metric_strategy(source, AnalysisConfig(), reporter=None)

    assert result.luminance == direct_luminance
    assert result.motion == direct_motion
    assert len(result.luminance) == clip.num_frames
    assert len(result.motion) == clip.num_frames
    assert result.motion[0] == 0.0
    assert result.performance_mode == "quality"
    assert result.metric_backend == "vapoursynth_planestats"
    assert clip.resize_calls == []


def test_quality_strategy_applies_active_rect_without_resize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    clip = FakeBalancedClip([0.0], width=640, height=360)
    source = MagicMock()
    source.clip = clip

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(),
        reporter=None,
        metric_active_rect=MetricActiveRect(x=10, y=20, width=400, height=200),
    )

    assert result.luminance == [0.0]
    assert result.motion == [0.0]
    assert clip.crop_calls == [("CropAbs", 10, 20, 400, 200)]
    assert clip.resize_calls == []


def test_quality_default_strategy_uses_one_combined_planestats_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    clip = FakeBalancedClip([0.0, 0.25, 1.0])
    source = MagicMock()
    source.clip = clip

    result = calculate_metric_strategy(source, AnalysisConfig(), reporter=None)

    assert result.motion[0] == 0.0
    assert clip.planestats_clipb_flags == [True]


def test_invalid_active_rect_raises_metrics_calculation_error() -> None:
    clip = FakeBalancedClip([0.0], width=4, height=4)
    source = MagicMock()
    source.clip = clip

    with pytest.raises(MetricsCalculationError, match="active_rect is outside"):
        calculate_metric_strategy(
            source,
            AnalysisConfig(),
            reporter=None,
            metric_active_rect=MetricActiveRect(x=3, y=0, width=2, height=4),
        )


def test_quality_planestats_is_full_resolution_combined_and_dense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    clip = FakeBalancedClip([0.0, 0.25, 0.75, 1.0], width=3840, height=2160)
    recorder = AnalysisTimingRecorder()

    luminance, motion = calculate_quality_planestats_metrics(
        clip,
        timing_recorder=recorder,
    )

    assert luminance == [0.0, 0.25, 0.75, 1.0]
    assert motion == [0.0, 0.25, 0.5, 0.25]
    assert len(luminance) == clip.num_frames
    assert len(motion) == clip.num_frames
    assert clip.resize_calls == []
    assert clip.planestats_clipb_flags == [True]
    assert set(recorder.as_dict()) == {
        "metric_graph_build",
        "quality_frame_render",
        "quality_graph_build",
        "quality_metric_read",
    }


def test_quality_planestats_converts_non_yuv_like_quality_without_downscaling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    clip = FakeBalancedClip([0.2, 0.4], width=1920, height=1080, color_family=99)

    luminance, motion = calculate_quality_planestats_metrics(clip)

    assert luminance == [0.2, 0.4]
    assert motion == [0.0, 0.2]
    assert clip.resize_calls == [("Bicubic", None, None)]
    assert clip.ops == [("Bicubic", None, None)]


def test_quality_planestats_applies_active_rect_without_resize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    clip = FakeBalancedClip([0.1, 0.6], width=640, height=360)

    luminance, motion = calculate_quality_planestats_metrics(
        clip,
        metric_active_rect=MetricActiveRect(x=10, y=20, width=400, height=200),
    )

    assert luminance == [0.1, 0.6]
    assert motion == [0.0, 0.5]
    assert clip.crop_calls == [("CropAbs", 10, 20, 400, 200)]
    assert clip.resize_calls == []
    assert clip.ops == [("CropAbs", 10, 20, 400, 200)]


def test_quality_planestats_rejects_empty_clip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)

    with pytest.raises(MetricsCalculationError, match="Analysis clip has 0 frames"):
        calculate_quality_planestats_metrics(FakeBalancedClip([]))


def test_quality_planestats_reports_missing_frame_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    monkeypatch.setattr(
        FakePlaneStatsClip,
        "get_frame",
        lambda _self, _n: FakePlaneStatsFrame({"PlaneStatsAverage": 0.5}),
    )

    with pytest.raises(
        MetricsCalculationError,
        match="quality metric analysis",
    ):
        calculate_quality_planestats_metrics(FakeBalancedClip([0.0, 1.0]))


def test_quality_planestats_wraps_graph_failure_and_completes_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failing_vs = SimpleNamespace(
        YUV=FAKE_VS.YUV,
        YUV420P8=FAKE_VS.YUV420P8,
        GRAY=FAKE_VS.GRAY,
        core=SimpleNamespace(
            std=SimpleNamespace(ShufflePlanes=FakeCoreStd().ShufflePlanes),
        ),
    )
    monkeypatch.setitem(sys.modules, "vapoursynth", failing_vs)
    reporter = MagicMock(spec=ProgressReporter)

    with pytest.raises(MetricsCalculationError, match="graph construction"):
        calculate_quality_planestats_metrics(
            FakeBalancedClip([0.0, 1.0]),
            reporter=reporter,
        )

    reporter.complete_phase.assert_called_once_with(ProgressPhaseStatus.FAILED)


def test_quality_planestats_is_used_by_normal_quality_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality = MagicMock(return_value=([0.5], [0.0]))
    monkeypatch.setattr(
        "frame_compare.analysis.metric_strategies.calculate_quality_planestats_metrics",
        quality,
    )
    source = MagicMock()
    source.clip = FakeBalancedClip([0.0], width=4, height=4)

    result = calculate_metric_strategy(source, AnalysisConfig(), reporter=None)

    assert result.performance_mode == "quality"
    quality.assert_called_once()
    with pytest.raises(ValueError):
        AnalysisConfig(performance_mode="quality-planestats-candidate")


def test_quality_strategy_bounds_range_and_preserves_motion_lookbehind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    clip = FakeBalancedClip([0.0, 0.1, 0.4, 0.9, 0.9, 1.0])
    source = MagicMock()
    source.clip = clip

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(),
        reporter=None,
        metric_frame_range=MetricFrameRange(
            source_frame_count=6,
            start=2,
            end_exclusive=5,
        ),
    )

    assert result.luminance == [0.4, 0.9, 0.9]
    assert result.motion == pytest.approx([0.3, 0.5, 0.0])
    assert clip.slice_calls == [(1, 5, None), (0, 1, None), (0, -1, None)]


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


def test_performance_strategy_returns_exact_quarter_sparse_arrays(
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

    assert result.luminance == [0.25]
    assert result.motion == [0.25]
    assert result.sampled_source_frames == (1,)
    assert result.performance_mode == "performance"
    assert result.metric_backend == "vapoursynth_planestats"


def test_public_performance_planestats_callable_matches_production_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    clip = FakeBalancedClip([0.0, 0.25, 0.75, 1.0], width=640, height=360)

    luminance, motion, source_frames = calculate_performance_planestats_metrics(clip)

    assert luminance == [0.25]
    assert motion == [0.25]
    assert source_frames == (1,)
    assert clip.resize_calls == []
    assert clip.planestats_clipb_flags == [True]


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

    assert result.luminance == [0.25]
    assert result.motion == [0.25]
    assert set(recorder.as_dict()) == {
        "metric_graph_build",
        "performance_frame_render",
        "performance_graph_build",
        "performance_metric_read",
    }


def test_performance_strategy_crops_without_spatial_resize(
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
    assert source.clip.resize_calls == []
    assert source.clip.ops == [("CropAbs", 10, 20, 400, 200)]
    assert result.luminance == [0.25]
    assert result.motion == [0.25]
    assert result.sampled_source_frames == (1,)


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

    assert first.luminance == [0.25]
    assert first.motion == [0.0]
    assert second.luminance == first.luminance
    assert second.motion == first.motion


def test_performance_strategy_preserves_motion_lookbehind_at_sampled_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", FAKE_VS)
    source = MagicMock()
    source.clip = FakeBalancedClip([0.0, 1.0, 1.0, 1.0], width=640, height=360)

    result = calculate_metric_strategy(
        source,
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.sampled_source_frames == (1,)
    assert result.motion == [1.0]


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
    assert '"target_max_width"' not in first_performance
    assert '"resize"' not in first_performance
    assert '"sampled_burst_pairs_with_per_burst_source_lookbehind"' in first_performance
    parsed_performance = json.loads(first_performance)
    assert parsed_performance["luminance"]["spatial"] == "active_rect_aware_full_resolution_luma"
    assert parsed_performance["motion"]["spatial"] == "active_rect_aware_full_resolution_luma"
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

    assert result.luminance == [0.25]
    assert result.motion == [0.0]
