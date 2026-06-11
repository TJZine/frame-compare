"""Metric calculation logic for frame analysis."""

from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

import structlog

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    compute_cache_key,
    load_cached_metrics,
    save_metrics_cache,
)
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_strategies import (
    MetricComputationResult,
    calculate_metric_strategy,
)
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    MetricActiveRect,
    MetricsMetadata,
)
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.loader import DefaultVSLoader

if TYPE_CHECKING:
    from pathlib import Path

    from frame_compare.config.schema import AnalysisConfig
    from frame_compare.vs.loader import VSLoader
    from frame_compare.vs.types import SourceInfo


log = structlog.get_logger()

# Orchestration "analyze" phase progress total.
# Contract:
# - `execute_phases()` advances the phase by 1 on successful completion.
# - `calculate_metrics()` advances the remaining steps (total - 1) on cache hit,
#   and advances twice (after luminance + after cache-save attempt) on cache miss.
ANALYZE_PROGRESS_TOTAL = 3


def _clip_identities(video_paths: list[Path]) -> list[ClipIdentity]:
    return [
        ClipIdentity(
            path=str(path),
            size=path.stat().st_size,
            mtime=path.stat().st_mtime,
        )
        for path in video_paths
    ]


def _cached_metrics(
    cache_dir: Path,
    fingerprint: str,
    clips: list[ClipIdentity],
    reporter: ProgressReporter | None,
) -> FrameMetrics | None:
    cache_result = load_cached_metrics(cache_dir, fingerprint, clips)
    if not (cache_result.success and cache_result.metrics):
        return None

    if reporter:
        reporter.set_description("Cache hit")
        reporter.advance(ANALYZE_PROGRESS_TOTAL - 1)
    return cache_result.metrics


def _load_analysis_source(source_path: Path, vs_loader: VSLoader | None) -> SourceInfo:
    loader = vs_loader or DefaultVSLoader()
    try:
        return loader.load(source_path)
    except (PluginNotFoundError, SourceLoadError):
        raise
    except Exception as e:
        raise MetricsCalculationError(f"Failed to load analysis video: {e}") from e


def _build_metrics(
    *,
    result: MetricComputationResult,
    source: SourceInfo,
    fingerprint: str,
    clips: list[ClipIdentity],
    analysis_source_path: Path,
    effective_fps: Fraction | None,
    metric_active_rect: MetricActiveRect | None,
    active_rect_source: str,
    active_rect_detection_mode: str,
    active_rect_algorithm_id: str,
) -> FrameMetrics:
    return FrameMetrics(
        luminance=result.luminance,
        motion=result.motion,
        metadata=MetricsMetadata(
            frame_count=source.clip.num_frames,
            fps=effective_fps if effective_fps is not None else source.fps,
            config_fingerprint=fingerprint,
            clips=clips,
            analysis_source_path=str(analysis_source_path),
            performance_mode=result.performance_mode,
            algorithm_id=result.algorithm_id,
            metric_backend=result.metric_backend,
            algorithm_identity_json=result.algorithm_identity_json,
            metric_active_rect=metric_active_rect,
            active_rect_source=active_rect_source,
            active_rect_detection_mode=active_rect_detection_mode,
            active_rect_algorithm_id=active_rect_algorithm_id,
            version=CACHE_VERSION,
        ),
    )


def _save_metrics_cache_best_effort(
    metrics: FrameMetrics,
    cache_dir: Path,
    reporter: ProgressReporter | None,
) -> None:
    try:
        save_metrics_cache(metrics, cache_dir)
    except Exception as e:
        if reporter:
            reporter.set_description(f"Cache save failed: {e}")
        log.warning("analysis_cache_save_failed", error=str(e), exc_info=True)


def calculate_metrics(
    video_paths: list[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    reporter: ProgressReporter | None = None,
    vs_loader: VSLoader | None = None,
    selection_domain: str | None = None,
    analysis_source_path: Path | None = None,
    effective_fps: Fraction | None = None,
    metric_active_rect: MetricActiveRect | None = None,
    active_rect_source: str = "full-frame",
    active_rect_detection_mode: str = "aspect_ratio",
    active_rect_algorithm_id: str = "active_rect_resolution_v1",
) -> FrameMetrics:
    """
    Calculate frame metrics for the given clips.

    Uses cached values if valid cache exists and config matches.
    Only the selected analysis source is analyzed.

    Args:
        video_paths: Ordered video file paths (first entry is the selected reference clip)
        analysis_source_path: Video path to load for metric analysis. Defaults to
            the selected reference for compatibility with older callers.
        config: Analysis configuration
        cache_dir: Directory for cache files
        reporter: Optional progress reporter
        vs_loader: Optional VapourSynth clip loader seam
        selection_domain: Optional selection-domain token included in
            the analysis cache key when source overrides affect reference
            selection.
        effective_fps: Optional FPS value stored in metrics metadata for
            timing and selection-detail normalization.

    Returns:
        FrameMetrics with luminance and motion arrays

    Raises:
        MetricsCalculationError (FC-4002): If frame extraction or metric
            computation fails, OR if analysis clip has 0 frames.
        PluginNotFoundError (FC-2003): If VapourSynth lsmas plugin unavailable.
        SourceLoadError (FC-4015): If video file cannot be loaded.
    """
    if not video_paths:
        raise MetricsCalculationError("No input video paths provided")
    source_path = video_paths[0] if analysis_source_path is None else analysis_source_path

    fingerprint = compute_cache_key(
        video_paths,
        config,
        selection_domain=selection_domain,
        metric_active_rect=metric_active_rect,
    )
    clips = _clip_identities(video_paths)

    cached = _cached_metrics(cache_dir, fingerprint, clips, reporter)
    if cached:
        return cached

    # Cache miss or invalid - compute metrics for the selected analysis source only.
    source = _load_analysis_source(source_path, vs_loader)
    try:
        strategy_result = calculate_metric_strategy(source, config, reporter, metric_active_rect)
        metrics = _build_metrics(
            result=strategy_result,
            source=source,
            fingerprint=fingerprint,
            clips=clips,
            analysis_source_path=source_path,
            effective_fps=effective_fps,
            metric_active_rect=metric_active_rect,
            active_rect_source=active_rect_source,
            active_rect_detection_mode=active_rect_detection_mode,
            active_rect_algorithm_id=active_rect_algorithm_id,
        )
    finally:
        del source

    _save_metrics_cache_best_effort(metrics, cache_dir, reporter)

    if reporter:
        reporter.advance(1)
    return metrics
