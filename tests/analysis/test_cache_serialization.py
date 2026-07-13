"""Cache serialization and round-trip contract tests."""

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    compute_cache_key,
    load_cached_metrics,
    load_cached_metrics_for_request,
    save_metrics_cache,
)
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    MetricActiveRect,
    MetricCacheRequest,
    MetricFrameRange,
    MetricsMetadata,
)
from frame_compare.config.schema import AnalysisConfig
from tests.analysis._cache_io_test_helpers import (
    cache_file,
    create_video_file,
    metrics_metadata,
    valid_cache_metadata_payload,
)


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """Save → load → success=True, data matches, fps == Fraction(24)."""
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(random_frame_count=10)
    fingerprint = compute_cache_key([v1], config)

    clips = [ClipIdentity(path=str(v1), size=v1.stat().st_size, mtime=v1.stat().st_mtime)]
    metadata = metrics_metadata(
        frame_count=3,
        fps=Fraction(24, 1),
        config_fingerprint=fingerprint,
        clips=clips,
        config=config,
    )
    metrics = FrameMetrics(
        luminance=[0.1, 0.2, 0.3],
        motion=[0.0, 0.5, 0.1],
        metadata=metadata,
    )

    save_metrics_cache(metrics, tmp_path)
    result = load_cached_metrics(tmp_path, fingerprint, clips)

    assert (tmp_path / f"v1__{fingerprint}.compframes").exists()
    assert result.success is True
    assert result.metrics is not None
    assert result.metrics.luminance == [0.1, 0.2, 0.3]
    assert result.metrics.motion == [0.0, 0.5, 0.1]
    assert result.metrics.metadata.frame_count == 3
    assert result.metrics.metadata.fps == Fraction(24, 1)
    assert result.metrics.metadata.config_fingerprint == fingerprint
    assert result.metrics.metadata.analysis_source_path == ""
    assert result.metrics.metadata.performance_mode == "quality"
    assert result.metrics.metadata.metric_backend == "vapoursynth_planestats"
    assert result.metrics.metadata.algorithm_id == metric_algorithm_id(config)
    assert result.metrics.metadata.algorithm_identity_json == (
        stable_metric_algorithm_identity_json(config)
    )
    assert result.metrics.metadata.metric_active_rect is None
    assert result.metrics.metadata.active_rect_source == "full-frame"
    assert result.metrics.metadata.active_rect_detection_mode == "aspect_ratio"
    assert result.metrics.metadata.active_rect_algorithm_id == "active_rect_resolution_v2"


def test_save_rejects_stale_nested_metadata_version(tmp_path: Path) -> None:
    metadata = metrics_metadata(
        frame_count=1,
        fps=Fraction(24, 1),
        config_fingerprint="fingerprint",
        clips=[],
        config=AnalysisConfig(),
    )
    metrics = FrameMetrics(
        luminance=[0.1],
        motion=[0.0],
        metadata=replace(metadata, version=CACHE_VERSION - 1),
    )

    with pytest.raises(ValueError, match="does not match the current cache schema"):
        save_metrics_cache(metrics, tmp_path)


def test_request_aware_cache_load_rejects_mismatched_provenance(tmp_path: Path) -> None:
    video = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig()
    rect = MetricActiveRect(x=0, y=10, width=100, height=60)
    request = MetricCacheRequest(
        analysis_source_path=video,
        effective_fps=Fraction(24, 1),
        metric_active_rect=rect,
        active_rect_source="explicit",
        active_rect_detection_mode="provided",
    )
    fingerprint = compute_cache_key([video], config, metric_request=request)
    clips = [ClipIdentity(path=str(video), size=video.stat().st_size, mtime=video.stat().st_mtime)]
    metrics = FrameMetrics(
        luminance=[0.5],
        motion=[0.0],
        metadata=MetricsMetadata(
            frame_count=1,
            fps=Fraction(24, 1),
            config_fingerprint=fingerprint,
            clips=clips,
            analysis_source_path=str(video),
            performance_mode=config.performance_mode.value,
            algorithm_id=metric_algorithm_id(config),
            metric_backend=metric_backend(config),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config),
            metric_active_rect=rect,
            active_rect_source="metadata",
            active_rect_detection_mode="aspect_ratio",
        ),
    )
    save_metrics_cache(metrics, tmp_path)

    result = load_cached_metrics_for_request(tmp_path, fingerprint, clips, request)

    assert result.success is False
    assert result.reason == "mismatched_inputs"


def test_save_and_load_round_trip_serializes_metric_active_rect(tmp_path: Path) -> None:
    v1 = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig(random_frame_count=10)
    rect = MetricActiveRect(x=4, y=8, width=320, height=180)
    request = MetricCacheRequest(
        analysis_source_path=v1,
        metric_active_rect=rect,
        active_rect_source="explicit",
        active_rect_detection_mode="provided",
        active_rect_algorithm_id="active_rect_resolution_v2",
    )
    fingerprint = compute_cache_key(
        [v1],
        config,
        metric_request=request,
    )

    clips = [ClipIdentity(path=str(v1), size=v1.stat().st_size, mtime=v1.stat().st_mtime)]
    metadata = metrics_metadata(
        frame_count=2,
        fps=Fraction(24, 1),
        config_fingerprint=fingerprint,
        clips=clips,
        config=config,
        analysis_source_path=str(v1),
        metric_active_rect=rect,
        active_rect_source="explicit",
        active_rect_detection_mode="provided",
    )
    metrics = FrameMetrics(
        luminance=[0.1, 0.2],
        motion=[0.0, 0.3],
        metadata=metadata,
    )

    save_metrics_cache(metrics, tmp_path)
    result = load_cached_metrics_for_request(tmp_path, fingerprint, clips, request)

    assert result.success is True
    assert result.metrics is not None
    assert result.metrics.metadata.metric_active_rect == rect
    assert result.metrics.metadata.active_rect_source == "explicit"
    assert result.metrics.metadata.active_rect_detection_mode == "provided"
    assert result.metrics.metadata.active_rect_algorithm_id == "active_rect_resolution_v2"


def test_windowed_cache_round_trip_preserves_range_and_first_motion(tmp_path: Path) -> None:
    video = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig()
    metric_range = MetricFrameRange(source_frame_count=100, start=20, end_exclusive=23)
    request = MetricCacheRequest(
        analysis_source_path=video,
        metric_frame_range=metric_range,
    )
    fingerprint = compute_cache_key([video], config, metric_request=request)
    metrics = FrameMetrics(
        luminance=[0.1, 0.2, 0.3],
        motion=[0.4, 0.5, 0.6],
        metadata=MetricsMetadata(
            frame_count=3,
            fps=Fraction(24, 1),
            config_fingerprint=fingerprint,
            clips=[
                ClipIdentity(
                    path=str(video),
                    size=video.stat().st_size,
                    mtime=video.stat().st_mtime,
                )
            ],
            source_frame_count=100,
            metric_source_start=20,
            metric_source_end_exclusive=23,
            analysis_source_path=str(video),
            performance_mode=config.performance_mode.value,
            algorithm_id=metric_algorithm_id(config),
            metric_backend=metric_backend(config),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config),
        ),
    )

    save_metrics_cache(metrics, tmp_path)
    result = load_cached_metrics_for_request(tmp_path, fingerprint, [], request)

    assert result.success is True
    assert result.metrics is not None
    assert result.metrics.motion[0] == 0.4
    assert result.metrics.metadata.metric_source_start == 20
    assert result.metrics.metadata.metric_source_end_exclusive == 23


def test_windowed_cache_request_rejects_different_range(tmp_path: Path) -> None:
    video = create_video_file(tmp_path, "v1.mkv")
    config = AnalysisConfig()
    stored_range = MetricFrameRange(source_frame_count=100, start=20, end_exclusive=23)
    stored_request = MetricCacheRequest(
        analysis_source_path=video,
        metric_frame_range=stored_range,
    )
    fingerprint = compute_cache_key([video], config, metric_request=stored_request)
    metadata = MetricsMetadata(
        frame_count=3,
        fps=Fraction(24, 1),
        config_fingerprint=fingerprint,
        clips=[],
        source_frame_count=100,
        metric_source_start=20,
        metric_source_end_exclusive=23,
        analysis_source_path=str(video),
        performance_mode=config.performance_mode.value,
        algorithm_id=metric_algorithm_id(config),
        metric_backend=metric_backend(config),
        algorithm_identity_json=stable_metric_algorithm_identity_json(config),
    )
    save_metrics_cache(
        FrameMetrics(luminance=[0.1, 0.2, 0.3], motion=[0.4, 0.5, 0.6], metadata=metadata),
        tmp_path,
    )
    mismatched_request = MetricCacheRequest(
        analysis_source_path=video,
        metric_frame_range=MetricFrameRange(100, 21, 24),
    )

    result = load_cached_metrics_for_request(tmp_path, fingerprint, [], mismatched_request)

    assert result.success is False
    assert result.reason == "mismatched_inputs"


def test_load_cache_accepts_content_derived_auto_active_rect_metadata(tmp_path: Path) -> None:
    config = AnalysisConfig()
    metadata = valid_cache_metadata_payload(
        config,
        frame_count=1,
        metric_active_rect={"x": 0, "y": 10, "width": 100, "height": 60},
        active_rect_source="content-derived",
        active_rect_detection_mode="auto",
    )
    cache_file(tmp_path, "fp").write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "fingerprint": "fp",
                "luminance": [0.1],
                "motion": [0.0],
                "metadata": metadata,
            }
        ),
        encoding="utf-8",
    )

    result = load_cached_metrics(tmp_path, "fp", [])

    assert result.success is True
    assert result.metrics is not None
    assert result.metrics.metadata.metric_active_rect == MetricActiveRect(
        x=0,
        y=10,
        width=100,
        height=60,
    )
    assert result.metrics.metadata.active_rect_source == "content-derived"
    assert result.metrics.metadata.active_rect_detection_mode == "auto"


def test_save_writes_required_keys(tmp_path: Path) -> None:
    """Cache file JSON has all required keys + version == CACHE_VERSION."""
    config = AnalysisConfig()
    metadata = metrics_metadata(
        frame_count=10,
        fps=Fraction(24000, 1001),
        config_fingerprint="fp",
        clips=[],
        config=config,
    )
    metrics = FrameMetrics(luminance=[0.5], motion=[0.1], metadata=metadata)
    save_metrics_cache(metrics, tmp_path)

    with (tmp_path / "analysis__fp.compframes").open("r") as f:
        data = json.load(f)

    assert data["version"] == CACHE_VERSION
    assert "fingerprint" in data
    assert "luminance" in data
    assert "motion" in data
    assert "metadata" in data
    assert data["metadata"]["frame_count"] == 10
    assert data["metadata"]["fps"] == "24000/1001"
    assert data["metadata"]["analysis_source_path"] == ""
    assert data["metadata"]["performance_mode"] == "quality"
    assert data["metadata"]["algorithm_id"] == metric_algorithm_id(config)
    assert data["metadata"]["metric_backend"] == "vapoursynth_planestats"
    assert data["metadata"]["algorithm_identity_json"] == stable_metric_algorithm_identity_json(
        config
    )
    assert data["metadata"]["metric_active_rect"] is None
    assert data["metadata"]["active_rect_source"] == "full-frame"
    assert data["metadata"]["active_rect_detection_mode"] == "aspect_ratio"
    assert data["metadata"]["active_rect_algorithm_id"] == "active_rect_resolution_v2"
