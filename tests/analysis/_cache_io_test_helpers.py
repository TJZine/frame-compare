"""Shared builders for cache contract tests."""

import os
from fractions import Fraction
from pathlib import Path

from frame_compare.analysis.cache_io import CACHE_VERSION, metrics_cache_filename
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.analysis.types import ClipIdentity, MetricActiveRect, MetricsMetadata
from frame_compare.config.schema import AnalysisConfig

FIXED_MTIME = 1704067200.0  # 2024-01-01 00:00:00 UTC


def valid_cache_metadata_payload(
    config: AnalysisConfig,
    *,
    frame_count: int = 0,
    metric_active_rect: dict[str, int] | None = None,
    active_rect_source: str = "full-frame",
    active_rect_detection_mode: str = "aspect_ratio",
) -> dict[str, object]:
    return {
        "frame_count": frame_count,
        "fps": "24/1",
        "config_fingerprint": "fp",
        "analysis_source_path": "",
        "clips": [],
        "performance_mode": config.performance_mode.value,
        "algorithm_id": metric_algorithm_id(config),
        "metric_backend": metric_backend(config),
        "algorithm_identity_json": stable_metric_algorithm_identity_json(config),
        "metric_active_rect": metric_active_rect,
        "active_rect_source": active_rect_source,
        "active_rect_detection_mode": active_rect_detection_mode,
        "active_rect_algorithm_id": "active_rect_resolution_v2",
        "version": CACHE_VERSION,
    }


def create_video_file(tmp_path: Path, name: str = "video.mkv", content: bytes = b"test") -> Path:
    """Create a dummy video file with fixed mtime."""
    f = tmp_path / name
    f.write_bytes(content)
    os.utime(f, (FIXED_MTIME, FIXED_MTIME))
    return f


def cache_file(cache_dir: Path, fingerprint: str, *video_paths: Path) -> Path:
    return cache_dir / metrics_cache_filename(list(video_paths), fingerprint)


def metrics_metadata(
    *,
    frame_count: int,
    fps: Fraction,
    config_fingerprint: str,
    clips: list[ClipIdentity],
    config: AnalysisConfig,
    analysis_source_path: str = "",
    metric_active_rect: MetricActiveRect | None = None,
) -> MetricsMetadata:
    return MetricsMetadata(
        frame_count=frame_count,
        fps=fps,
        config_fingerprint=config_fingerprint,
        clips=clips,
        analysis_source_path=analysis_source_path,
        performance_mode=config.performance_mode.value,
        algorithm_id=metric_algorithm_id(config),
        metric_backend=metric_backend(config),
        algorithm_identity_json=stable_metric_algorithm_identity_json(config),
        metric_active_rect=metric_active_rect,
        version=CACHE_VERSION,
    )
