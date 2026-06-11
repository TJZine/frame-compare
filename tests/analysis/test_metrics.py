"""Unit tests for metrics calculation."""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest


def _vs_spec_available() -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec("vapoursynth") is not None
    except ValueError:
        return False


# Create a mock vapoursynth module before importing metrics
if not _vs_spec_available() and "vapoursynth" not in sys.modules:
    vs_mock = MagicMock()
    vs_mock.YUV = 1
    vs_mock.GRAY = 2
    vs_mock.INTEGER = 0
    vs_mock.FLOAT = 1
    sys.modules["vapoursynth"] = vs_mock
else:
    import vapoursynth as vs_module  # type: ignore

    vs_mock = vs_module

from frame_compare.analysis.cache_io import compute_cache_key  # noqa: E402
from frame_compare.analysis.errors import MetricsCalculationError  # noqa: E402
from frame_compare.analysis.metric_identity import (  # noqa: E402
    stable_metric_algorithm_identity_json,
)
from frame_compare.analysis.metric_strategies import (  # noqa: E402
    MetricComputationResult,
    calculate_metric_strategy,
    calculate_quality_luminance,
    calculate_quality_motion,
)
from frame_compare.analysis.metrics import (  # noqa: E402
    ProgressReporter,
    calculate_metrics,
)
from frame_compare.analysis.types import FrameMetrics  # noqa: E402
from frame_compare.config.schema import AnalysisConfig  # noqa: E402
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError  # noqa: E402


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
                {"PlaneStatsDiff": abs(current - previous)}
                for current, previous in zip(self._clip.values, clipb.values, strict=True)
            ]
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
        return FakeBalancedClip(
            self._clip.values,
            width=self._clip.width if width is None else width,
            height=self._clip.height if height is None else height,
            color_family=color_family,
            resize_calls=self._clip.resize_calls,
        )

    def Bilinear(
        self,
        *,
        width: int,
        height: int,
    ) -> FakeBalancedClip:
        self._clip.resize_calls.append(("Bilinear", width, height))
        return FakeBalancedClip(
            self._clip.values,
            width=width,
            height=height,
            color_family=self._clip.format.color_family,
            resize_calls=self._clip.resize_calls,
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
    ):
        self.values = values
        self.num_frames = len(values)
        self.width = width
        self.height = height
        self.format = SimpleNamespace(color_family=color_family)
        self.resize_calls = [] if resize_calls is None else resize_calls
        self.resize = FakeResize(self)
        self.std = FakeStd(self)

    def __getitem__(self, item: slice) -> FakeBalancedClip:
        return FakeBalancedClip(
            self.values[item],
            width=self.width,
            height=self.height,
            color_family=self.format.color_family,
            resize_calls=self.resize_calls,
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


@patch("frame_compare.analysis.metrics.load_cached_metrics")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_uses_cache_on_hit(mock_key, mock_load, tmp_path):
    mock_key.return_value = "fp"
    metrics = MagicMock(spec=FrameMetrics)
    mock_load.return_value = MagicMock(success=True, metrics=metrics)

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()

    result = calculate_metrics(video_paths, config, tmp_path)
    assert result == metrics
    mock_load.assert_called_once()


def test_calculate_metrics_empty_video_paths_raises_fc4002(tmp_path: Path) -> None:
    from frame_compare.analysis.errors import MetricsCalculationError
    from frame_compare.config.schema import AnalysisConfig

    with pytest.raises(MetricsCalculationError, match="No input video paths provided"):
        calculate_metrics([], AnalysisConfig(), tmp_path)


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_computes_on_cache_miss(
    mock_key, mock_load, mock_loader_cls, mock_strategy, mock_save, tmp_path
):
    mock_key.return_value = "fp"
    mock_load.return_value = MagicMock(success=False)

    mock_loader = mock_loader_cls.return_value
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 10
    mock_source.clip = mock_clip
    mock_source.fps = Fraction(24, 1)
    mock_strategy.return_value = MetricComputationResult(
        luminance=[0.1] * 10,
        motion=[0.0] + [0.1] * 9,
        performance_mode="quality",
        algorithm_id="algorithm-id",
        metric_backend="python_numpy",
        algorithm_identity_json='{"backend":"python_numpy"}',
    )

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()

    result = calculate_metrics(video_paths, config, tmp_path)

    assert len(result.luminance) == 10
    assert len(result.motion) == 10
    mock_strategy.assert_called_once_with(mock_source, config, None)
    mock_save.assert_called_once()


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
    assert "coarse_to_refined" not in first_performance


def test_performance_cache_key_ignores_selection_counts_and_quantiles(tmp_path: Path) -> None:
    video_path = tmp_path / "v1.mkv"
    video_path.write_bytes(b"")

    base = AnalysisConfig(performance_mode="performance")
    changed_selection = AnalysisConfig(
        performance_mode="performance",
        random_seed=99,
        random_frame_count=23,
        dark_frame_count=17,
        bright_frame_count=19,
        motion_frame_count=29,
        user_frames=[3, 7],
    )
    changed_quantiles = AnalysisConfig(
        performance_mode="performance",
        dark_quantile=0.05,
        bright_quantile=0.95,
    )

    assert compute_cache_key([video_path], base) == compute_cache_key(
        [video_path], changed_selection
    )
    assert compute_cache_key([video_path], base) == compute_cache_key(
        [video_path], changed_quantiles
    )
    assert compute_cache_key([video_path], base) != compute_cache_key(
        [video_path],
        AnalysisConfig(performance_mode="quality"),
    )


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


def _quality_strategy_result(frame_count: int = 10) -> MetricComputationResult:
    return MetricComputationResult(
        luminance=[0.1] * frame_count,
        motion=[0.0] + [0.1] * max(0, frame_count - 1),
        performance_mode="quality",
        algorithm_id="algorithm-id",
        metric_backend="python_numpy",
        algorithm_identity_json='{"backend":"python_numpy"}',
    )


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_uses_effective_fps_in_metadata(
    mock_key, mock_load, mock_loader_cls, mock_strategy, mock_save, tmp_path
):
    mock_key.return_value = "fp"
    mock_load.return_value = MagicMock(success=False)
    mock_loader = mock_loader_cls.return_value
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 10
    mock_source.clip = mock_clip
    mock_source.fps = Fraction(30000, 1001)
    mock_strategy.return_value = _quality_strategy_result()

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")

    result = calculate_metrics(
        video_paths,
        AnalysisConfig(),
        tmp_path,
        effective_fps=Fraction(24000, 1001),
    )

    assert result.metadata.fps == Fraction(24000, 1001)
    mock_save.assert_called_once()


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_cache_save_is_best_effort(
    mock_key, mock_load, mock_loader_cls, mock_strategy, mock_save, tmp_path
):
    mock_key.return_value = "fp"
    mock_load.return_value = MagicMock(success=False)

    mock_loader = mock_loader_cls.return_value
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 10
    mock_source.clip = mock_clip
    mock_source.fps = Fraction(24, 1)

    def _strategy_side_effect(
        _source: object,
        _config: object,
        strategy_reporter: ProgressReporter | None,
    ) -> MetricComputationResult:
        if strategy_reporter:
            strategy_reporter.advance(1)
        return _quality_strategy_result()

    mock_strategy.side_effect = _strategy_side_effect
    mock_save.side_effect = RuntimeError("disk full")

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()
    reporter = MagicMock(spec=ProgressReporter)

    result = calculate_metrics(video_paths, config, tmp_path, reporter=reporter)

    assert isinstance(result, FrameMetrics)
    assert len(result.luminance) == 10
    assert len(result.motion) == 10
    reporter.start_phase.assert_not_called()
    reporter.complete_phase.assert_not_called()
    assert reporter.advance.call_args_list == [call(1), call(1)]
    reporter.set_description.assert_called()


@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
def test_calculate_metrics_analyzes_reference_by_default(
    mock_load, mock_loader_cls, mock_strategy, tmp_path
):
    mock_load.return_value = MagicMock(success=False)
    mock_strategy.return_value = _quality_strategy_result()
    mock_loader = mock_loader_cls.return_value
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 10
    mock_source.clip = mock_clip
    mock_source.fps = Fraction(24, 1)

    video_paths = [tmp_path / "ref.mkv", tmp_path / "comp.mkv"]
    for p in video_paths:
        p.write_bytes(b"")

    calculate_metrics(video_paths, AnalysisConfig(), tmp_path)

    # loader.load should only be called once with reference path
    mock_loader.load.assert_called_once_with(video_paths[0])


@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
def test_calculate_metrics_analyzes_selected_analysis_source(
    mock_load, mock_loader_cls, mock_strategy, tmp_path
):
    mock_load.return_value = MagicMock(success=False)
    mock_strategy.return_value = _quality_strategy_result()
    mock_loader = mock_loader_cls.return_value
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 10
    mock_source.clip = mock_clip
    mock_source.fps = Fraction(24, 1)

    video_paths = [tmp_path / "ref.mkv", tmp_path / "analysis.mkv"]
    for p in video_paths:
        p.write_bytes(b"")

    result = calculate_metrics(
        video_paths,
        AnalysisConfig(),
        tmp_path,
        analysis_source_path=video_paths[1],
    )

    mock_loader.load.assert_called_once_with(video_paths[1])
    assert result.metadata.analysis_source_path == str(video_paths[1])


@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
def test_calculate_metrics_zero_frame_analysis_source_error_is_not_reference_worded(
    mock_load, mock_loader_cls, tmp_path
):
    mock_load.return_value = MagicMock(success=False)
    mock_loader = mock_loader_cls.return_value
    mock_source = MagicMock()
    mock_loader.load.return_value = mock_source
    mock_clip = MagicMock()
    mock_clip.num_frames = 0
    mock_source.clip = mock_clip
    mock_source.fps = Fraction(24, 1)

    video_paths = [tmp_path / "ref.mkv", tmp_path / "analysis.mkv"]
    for p in video_paths:
        p.write_bytes(b"")

    with pytest.raises(MetricsCalculationError, match="Analysis clip has 0 frames"):
        calculate_metrics(
            video_paths,
            AnalysisConfig(),
            tmp_path,
            analysis_source_path=video_paths[1],
        )


@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
def test_calculate_metrics_propagates_plugin_not_found(mock_load, mock_loader_cls, tmp_path):
    """Verify PluginNotFoundError bubbles up unwrapped."""
    mock_load.return_value = MagicMock(success=False)
    mock_loader = mock_loader_cls.return_value
    mock_loader.load.side_effect = PluginNotFoundError("lsmas")

    video_paths = [tmp_path / "ref.mkv"]
    video_paths[0].write_bytes(b"")

    with pytest.raises(PluginNotFoundError) as exc:
        calculate_metrics(video_paths, AnalysisConfig(), tmp_path)
    assert exc.value.code == "FC-2003"


@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics")
def test_calculate_metrics_propagates_source_load_error(mock_load, mock_loader_cls, tmp_path):
    """Verify SourceLoadError bubbles up unwrapped."""
    mock_load.return_value = MagicMock(success=False)
    mock_loader = mock_loader_cls.return_value
    path = tmp_path / "ref.mkv"
    path.write_bytes(b"")
    mock_loader.load.side_effect = SourceLoadError(path, "Corrupt")

    video_paths = [path]

    with pytest.raises(SourceLoadError) as exc:
        calculate_metrics(video_paths, AnalysisConfig(), tmp_path)
    assert exc.value.code == "FC-4015"


def test_no_toplevel_vapoursynth_import() -> None:
    """Verify vapoursynth is only imported inside TYPE_CHECKING or functions.

    Per SSOT: Import-Time VapourSynth Dependency (SSOT)
    - No top-level 'import vapoursynth' outside TYPE_CHECKING blocks
    - TYPE_CHECKING blocks are explicitly allowed
    """
    import ast
    from pathlib import Path

    metrics_path = (
        Path(__file__).parent.parent.parent / "src" / "frame_compare" / "analysis" / "metrics.py"
    )
    source = metrics_path.read_text()
    tree = ast.parse(source)

    def is_type_checking_guard(node: ast.If) -> bool:
        """Check if an If node is 'if TYPE_CHECKING:' or 'if typing.TYPE_CHECKING:'."""
        test = node.test
        # Handle: if TYPE_CHECKING:
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        # Handle: if typing.TYPE_CHECKING:
        return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"

    def has_vapoursynth_import(nodes: list[ast.stmt]) -> tuple[bool, int]:
        """Check if any node is a vapoursynth import. Returns (found, lineno)."""
        for node in nodes:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "vapoursynth":
                        return (True, node.lineno)
            if isinstance(node, ast.ImportFrom) and node.module == "vapoursynth":
                return (True, node.lineno)
        return (False, 0)

    for node in ast.iter_child_nodes(tree):
        # Direct top-level import vapoursynth -> FAIL
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "vapoursynth", (
                    f"Top-level 'import vapoursynth' at line {node.lineno}"
                )
        # Direct top-level from vapoursynth import ... -> FAIL
        if isinstance(node, ast.ImportFrom) and node.module == "vapoursynth":
            raise AssertionError(f"Top-level 'from vapoursynth import' at line {node.lineno}")
        # Top-level If block
        if isinstance(node, ast.If):
            if is_type_checking_guard(node):
                # TYPE_CHECKING block: vapoursynth imports ALLOWED
                continue
            else:
                # Other if block: vapoursynth imports NOT allowed
                found, lineno = has_vapoursynth_import(node.body)
                if found:
                    raise AssertionError(
                        f"vapoursynth import in non-TYPE_CHECKING if block at line {lineno}"
                    )
