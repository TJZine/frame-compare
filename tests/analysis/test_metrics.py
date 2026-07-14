"""Tests for metrics orchestration and cache integration."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_strategies import MetricComputationResult
from frame_compare.analysis.metrics import calculate_metrics, slice_frame_metrics
from frame_compare.analysis.timing import AnalysisTimingRecorder
from frame_compare.analysis.types import (
    FrameMetrics,
    MetricActiveRect,
    MetricCacheRequest,
    MetricFrameRange,
    MetricsMetadata,
)
from frame_compare.config.schema import AnalysisConfig
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.types import SourceInfo


class _SliceClip:
    def __init__(self, frames: list[int]) -> None:
        self.frames = frames
        self.num_frames = len(frames)

    def __getitem__(self, frame_slice: slice) -> _SliceClip:
        return _SliceClip(self.frames[frame_slice])


def test_slice_sparse_metrics_filters_map_by_source_overlap() -> None:
    metrics = FrameMetrics(
        luminance=[0.1, 0.2, 0.3, 0.4],
        motion=[0.1, 0.2, 0.3, 0.4],
        metadata=MetricsMetadata(
            frame_count=4,
            fps=Fraction(24),
            config_fingerprint="fp",
            clips=[],
            source_frame_count=200,
            metric_source_start=100,
            metric_source_end_exclusive=140,
            performance_mode="performance",
        ),
        sampled_source_frames=(101, 110, 125, 138),
    )

    sliced = slice_frame_metrics(metrics, start_index=8, frame_count=20)

    assert sliced.metadata.metric_source_start == 108
    assert sliced.metadata.metric_source_end_exclusive == 128
    assert sliced.metadata.frame_count == 2
    assert sliced.sampled_source_frames == (110, 125)
    assert sliced.luminance == [0.2, 0.3]


@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_uses_cache_on_hit(mock_key, mock_load, tmp_path):
    mock_key.return_value = "fp"
    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()
    metrics = FrameMetrics(
        luminance=[0.5],
        motion=[0.0],
        metadata=MetricsMetadata(
            frame_count=1,
            fps=Fraction(24, 1),
            config_fingerprint="fp",
            clips=[],
            analysis_source_path=str(video_paths[0]),
        ),
    )
    mock_load.return_value = MagicMock(success=True, metrics=metrics)

    result = calculate_metrics(video_paths, config, tmp_path)
    assert result == metrics
    mock_load.assert_called_once()


@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_records_proven_cache_hit(mock_key, mock_load, tmp_path: Path) -> None:
    mock_key.return_value = "fp"
    video_path = tmp_path / "v1.mkv"
    video_path.write_bytes(b"")
    metrics = FrameMetrics(
        luminance=[0.5],
        motion=[0.0],
        metadata=MetricsMetadata(
            frame_count=1,
            fps=Fraction(24, 1),
            config_fingerprint="fp",
            clips=[],
            analysis_source_path=str(video_path),
        ),
    )
    mock_load.return_value = MagicMock(success=True, metrics=metrics)
    recorder = AnalysisTimingRecorder()

    result = calculate_metrics(
        [video_path],
        AnalysisConfig(),
        tmp_path,
        timing_recorder=recorder,
    )

    assert result == metrics
    assert recorder.cache_state == "hit"
    assert recorder.as_dict()["cache_lookup"] >= 0.0


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_recomputes_cache_with_mismatched_active_rect_provenance(
    mock_key,
    mock_load,
    mock_loader_cls,
    mock_strategy,
    mock_save,
    tmp_path: Path,
) -> None:
    mock_key.return_value = "fp"
    video_path = tmp_path / "v1.mkv"
    video_path.write_bytes(b"")
    rect = MetricActiveRect(x=10, y=20, width=300, height=200)
    mock_load.return_value = MagicMock(
        success=False,
        metrics=None,
        reason="mismatched_inputs",
    )
    mock_source = mock_loader_cls.return_value.load.return_value
    mock_source.clip.num_frames = 1
    mock_source.fps = Fraction(24, 1)
    mock_strategy.return_value = _quality_strategy_result(frame_count=1)
    config = AnalysisConfig()

    result = calculate_metrics(
        [video_path],
        config,
        tmp_path,
        metric_active_rect=rect,
        active_rect_source="explicit",
        active_rect_detection_mode="provided",
    )

    mock_strategy.assert_called_once_with(
        mock_source,
        config,
        None,
        rect,
        metric_frame_range=MetricFrameRange(1, 0, 1),
        timing_recorder=None,
    )
    assert mock_load.call_args.args[3] == MetricCacheRequest(
        analysis_source_path=video_path,
        effective_fps=None,
        metric_active_rect=rect,
        active_rect_source="explicit",
        active_rect_detection_mode="provided",
        active_rect_algorithm_id="active_rect_resolution_v2",
    )
    mock_save.assert_called_once()
    assert result.metadata.metric_active_rect == rect
    assert result.metadata.active_rect_source == "explicit"
    assert result.metadata.active_rect_detection_mode == "provided"
    assert result.metadata.active_rect_algorithm_id == "active_rect_resolution_v2"


def test_calculate_metrics_empty_video_paths_raises_fc4002(tmp_path: Path) -> None:
    from frame_compare.analysis.errors import MetricsCalculationError
    from frame_compare.config.schema import AnalysisConfig

    with pytest.raises(MetricsCalculationError, match="No input video paths provided"):
        calculate_metrics([], AnalysisConfig(), tmp_path)


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
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
        metric_backend="vapoursynth_planestats",
        algorithm_identity_json='{"backend":"vapoursynth_planestats"}',
    )

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()

    result = calculate_metrics(video_paths, config, tmp_path)

    assert len(result.luminance) == 10
    assert len(result.motion) == 10
    mock_strategy.assert_called_once_with(
        mock_source,
        config,
        None,
        None,
        metric_frame_range=MetricFrameRange(10, 0, 10),
        timing_recorder=None,
    )
    mock_save.assert_called_once()


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
@patch("frame_compare.analysis.metrics.compute_cache_key")
def test_calculate_metrics_records_cache_miss_compute_and_write(
    mock_key,
    mock_load,
    mock_loader_cls,
    mock_strategy,
    mock_save,
    tmp_path: Path,
) -> None:
    mock_key.return_value = "fp"
    mock_load.return_value = MagicMock(success=False)
    source = mock_loader_cls.return_value.load.return_value
    source.clip.num_frames = 1
    source.fps = Fraction(24, 1)
    mock_strategy.return_value = _quality_strategy_result(frame_count=1)
    video_path = tmp_path / "v1.mkv"
    video_path.write_bytes(b"")
    recorder = AnalysisTimingRecorder()

    calculate_metrics(
        [video_path],
        AnalysisConfig(),
        tmp_path,
        timing_recorder=recorder,
    )

    assert recorder.cache_state == "miss"
    assert recorder.cache_write_state == "written"
    assert set(recorder.as_dict()) >= {"cache_lookup", "source_load", "cache_write"}
    assert mock_strategy.call_args.kwargs["timing_recorder"] is recorder
    mock_save.assert_called_once()


def _quality_strategy_result(frame_count: int = 10) -> MetricComputationResult:
    return MetricComputationResult(
        luminance=[0.1] * frame_count,
        motion=[0.0] + [0.1] * max(0, frame_count - 1),
        performance_mode="quality",
        algorithm_id="algorithm-id",
        metric_backend="vapoursynth_planestats",
        algorithm_identity_json='{"backend":"vapoursynth_planestats"}',
    )


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
def test_calculate_metrics_forwards_metric_range_and_persists_range_metadata(
    mock_load,
    mock_loader_cls,
    mock_strategy,
    mock_save,
    tmp_path: Path,
) -> None:
    mock_load.return_value = MagicMock(success=False)
    clip = _SliceClip([0, 1, 2, 3, 4, 5])
    source = SourceInfo(
        clip=cast(Any, clip),
        width=1920,
        height=1080,
        num_frames=clip.num_frames,
        fps=Fraction(24, 1),
        format=cast(Any, object()),
        frame_props={},
        is_hdr=False,
        hdr_metadata=None,
    )
    mock_loader_cls.return_value.load.return_value = source
    mock_strategy.return_value = MetricComputationResult(
        luminance=[0.2, 0.3, 0.4],
        motion=[0.12, 0.23, 0.34],
        performance_mode="quality",
        algorithm_id="algorithm-id",
        metric_backend="vapoursynth_planestats",
        algorithm_identity_json='{"backend":"vapoursynth_planestats"}',
    )
    video_path = tmp_path / "v1.mkv"
    video_path.write_bytes(b"")
    requested_range = MetricFrameRange(source_frame_count=6, start=2, end_exclusive=5)

    result = calculate_metrics(
        [video_path],
        AnalysisConfig(),
        tmp_path,
        metric_frame_range=requested_range,
    )

    strategy_source = mock_strategy.call_args.args[0]
    assert strategy_source.clip.frames == [0, 1, 2, 3, 4, 5]
    assert mock_strategy.call_args.kwargs["metric_frame_range"] == requested_range
    assert result.luminance == [0.2, 0.3, 0.4]
    assert result.motion == [0.12, 0.23, 0.34]
    assert result.metadata.frame_count == 3
    assert result.metadata.source_frame_count == 6
    assert result.metadata.metric_source_start == 2
    assert result.metadata.metric_source_end_exclusive == 5
    mock_save.assert_called_once()


@pytest.mark.parametrize(
    ("requested_range", "strategy_values"),
    [
        (MetricFrameRange(6, 0, 3), [0.1, 0.2, 0.3]),
        (MetricFrameRange(6, 3, 6), [0.3, 0.4, 0.5]),
        (MetricFrameRange(6, 3, 4), [0.3]),
    ],
)
@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
def test_calculate_metrics_range_boundaries(
    mock_load,
    mock_loader_cls,
    mock_strategy,
    _mock_save,
    requested_range: MetricFrameRange,
    strategy_values: list[float],
    tmp_path: Path,
) -> None:
    mock_load.return_value = MagicMock(success=False)
    clip = _SliceClip([0, 1, 2, 3, 4, 5])
    mock_loader_cls.return_value.load.return_value = SourceInfo(
        clip=cast(Any, clip),
        width=1920,
        height=1080,
        num_frames=clip.num_frames,
        fps=Fraction(24, 1),
        format=cast(Any, object()),
        frame_props={},
        is_hdr=False,
        hdr_metadata=None,
    )
    mock_strategy.return_value = MetricComputationResult(
        luminance=strategy_values,
        motion=[0.0, *strategy_values[1:]],
        performance_mode="quality",
        algorithm_id="algorithm-id",
        metric_backend="vapoursynth_planestats",
        algorithm_identity_json='{"backend":"vapoursynth_planestats"}',
    )
    video_path = tmp_path / "v1.mkv"
    video_path.write_bytes(b"")

    result = calculate_metrics(
        [video_path],
        AnalysisConfig(),
        tmp_path,
        metric_frame_range=requested_range,
    )

    assert mock_strategy.call_args.args[0].clip.frames == [0, 1, 2, 3, 4, 5]
    assert mock_strategy.call_args.kwargs["metric_frame_range"] == requested_range
    assert result.luminance == strategy_values
    assert len(result.motion) == requested_range.frame_count
    assert result.metadata.frame_count == requested_range.frame_count


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
def test_calculate_metrics_forwards_active_rect_with_windowed_source(
    mock_load,
    mock_loader_cls,
    mock_strategy,
    _mock_save,
    tmp_path: Path,
) -> None:
    mock_load.return_value = MagicMock(success=False)
    clip = _SliceClip([0, 1, 2, 3])
    mock_loader_cls.return_value.load.return_value = SourceInfo(
        clip=cast(Any, clip),
        width=1920,
        height=1080,
        num_frames=clip.num_frames,
        fps=Fraction(24, 1),
        format=cast(Any, object()),
        frame_props={},
        is_hdr=False,
        hdr_metadata=None,
    )
    mock_strategy.return_value = MetricComputationResult(
        luminance=[0.1, 0.2],
        motion=[0.0, 0.2],
        performance_mode="quality",
        algorithm_id="algorithm-id",
        metric_backend="vapoursynth_planestats",
        algorithm_identity_json='{"backend":"vapoursynth_planestats"}',
    )
    video_path = tmp_path / "v1.mkv"
    video_path.write_bytes(b"")
    rect = MetricActiveRect(x=10, y=20, width=300, height=200)

    calculate_metrics(
        [video_path],
        AnalysisConfig(),
        tmp_path,
        metric_frame_range=MetricFrameRange(4, 1, 3),
        metric_active_rect=rect,
    )

    assert mock_strategy.call_args.args[0].clip.frames == [0, 1, 2, 3]
    assert mock_strategy.call_args.kwargs["metric_frame_range"] == MetricFrameRange(4, 1, 3)
    assert mock_strategy.call_args.args[3] == rect


@patch("frame_compare.analysis.metrics.save_metrics_cache")
@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
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
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
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

    mock_strategy.return_value = _quality_strategy_result()
    mock_save.side_effect = RuntimeError("disk full")

    video_paths = [tmp_path / "v1.mkv"]
    video_paths[0].write_bytes(b"")
    config = AnalysisConfig()
    recorder = AnalysisTimingRecorder()
    result = calculate_metrics(
        video_paths,
        config,
        tmp_path,
        timing_recorder=recorder,
    )

    assert isinstance(result, FrameMetrics)
    assert len(result.luminance) == 10
    assert len(result.motion) == 10
    assert recorder.cache_write_state == "failed"
    assert recorder.as_dict()["cache_write"] >= 0.0
    mock_save.assert_called_once()


@patch("frame_compare.analysis.metrics.calculate_metric_strategy")
@patch("frame_compare.analysis.metrics.DefaultVSLoader")
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
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
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
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
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
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
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
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
@patch("frame_compare.analysis.metrics.load_cached_metrics_for_request")
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
