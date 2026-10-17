from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import TYPE_CHECKING

import structlog

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    compute_cache_key,
    keyed_metric_request,
    load_cached_metrics_for_request,
    save_metrics_cache,
)
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_strategies import (
    MetricComputationResult,
    calculate_metric_strategy,
)
from frame_compare.analysis.timing import AnalysisTimingRecorder, record_span
from frame_compare.analysis.types import (
    ClipIdentity,
    FrameMetrics,
    MetricCacheRequest,
    MetricFrameRange,
    MetricsAcquisition,
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
    reporter: ProgressReporter | None,
    request: MetricCacheRequest,
    timing_recorder: AnalysisTimingRecorder | None,
) -> FrameMetrics | None:
    with record_span(timing_recorder, "cache_lookup"):
        cache_result = load_cached_metrics_for_request(cache_dir, fingerprint, request)
    if not (cache_result.success and cache_result.metrics):
        if timing_recorder is not None:
            timing_recorder.cache_state = "miss"
        return None

    if reporter:
        reporter.set_description("Cache hit")
        reporter.advance(ANALYZE_PROGRESS_TOTAL - 1)
    if timing_recorder is not None:
        timing_recorder.cache_state = "hit"
    return cache_result.metrics


def _load_analysis_source(
    source_path: Path, vs_loader: VSLoader | None, memory_limit_mb: int | None
) -> SourceInfo:
    loader = vs_loader or DefaultVSLoader(memory_limit_mb=memory_limit_mb)
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
    request: MetricCacheRequest,
    metric_frame_range: MetricFrameRange,
) -> FrameMetrics:
    if (
        len(result.luminance) != len(result.motion)
        or (
            result.sampled_source_frames is None
            and len(result.luminance) != metric_frame_range.frame_count
        )
        or (
            result.sampled_source_frames is not None
            and len(result.luminance) != len(result.sampled_source_frames)
        )
    ):
        raise MetricsCalculationError(
            "Metric strategy returned arrays outside the requested frame range"
        )
    return FrameMetrics(
        luminance=result.luminance,
        motion=result.motion,
        metadata=MetricsMetadata(
            frame_count=len(result.luminance),
            fps=_resolved_fps(source, request),
            config_fingerprint=fingerprint,
            clips=clips,
            source_frame_count=metric_frame_range.source_frame_count,
            metric_source_start=metric_frame_range.start,
            metric_source_end_exclusive=metric_frame_range.end_exclusive,
            analysis_source_path=str(request.analysis_source_path),
            performance_mode=result.performance_mode,
            algorithm_id=result.algorithm_id,
            metric_backend=result.metric_backend,
            algorithm_identity_json=result.algorithm_identity_json,
            metric_active_rect=request.metric_active_rect,
            active_rect_source=request.active_rect_source,
            active_rect_detection_mode=request.active_rect_detection_mode,
            active_rect_algorithm_id=request.active_rect_algorithm_id,
            version=CACHE_VERSION,
        ),
        sampled_source_frames=result.sampled_source_frames,
    )


def _save_metrics_cache_best_effort(
    metrics: FrameMetrics,
    cache_dir: Path,
    reporter: ProgressReporter | None,
    timing_recorder: AnalysisTimingRecorder | None,
) -> None:
    with record_span(timing_recorder, "cache_write"):
        try:
            save_metrics_cache(metrics, cache_dir)
            if timing_recorder is not None:
                timing_recorder.cache_write_state = "written"
        except Exception as e:
            if timing_recorder is not None:
                timing_recorder.cache_write_state = "failed"
            if reporter:
                reporter.set_description(f"Cache save failed: {e}")
            log.warning("analysis_cache_save_failed", error=str(e), exc_info=True)


def calculate_metrics(
    request: MetricCacheRequest,
    *,
    video_paths: list[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    selection_domain: str | None = None,
    reporter: ProgressReporter | None = None,
    vs_loader: VSLoader | None = None,
    timing_recorder: AnalysisTimingRecorder | None = None,
    memory_limit_mb: int | None = None,
) -> MetricsAcquisition:
    if not video_paths:
        raise MetricsCalculationError("No input video paths provided")
    request = keyed_metric_request(request, video_paths)
    source_path = request.analysis_source_path
    assert source_path is not None

    fingerprint = compute_cache_key(
        video_paths,
        config,
        selection_domain=selection_domain,
        metric_request=request,
    )
    cached = _cached_metrics(
        cache_dir,
        fingerprint,
        reporter,
        request,
        timing_recorder,
    )
    if cached:
        return MetricsAcquisition(metrics=cached, disposition="hit")

    clips = _clip_identities(video_paths)

    with record_span(timing_recorder, "source_load"):
        source = _load_analysis_source(source_path, vs_loader, memory_limit_mb)
    try:
        resolved_range = _resolved_metric_frame_range(source, request.metric_frame_range)
        strategy_result = calculate_metric_strategy(
            source,
            config,
            reporter,
            request.metric_active_rect,
            metric_frame_range=resolved_range,
            timing_recorder=timing_recorder,
        )
        metrics = _build_metrics(
            result=strategy_result,
            source=source,
            fingerprint=fingerprint,
            clips=clips,
            request=request,
            metric_frame_range=resolved_range,
        )
    finally:
        del source

    _save_metrics_cache_best_effort(metrics, cache_dir, reporter, timing_recorder)

    if reporter:
        reporter.advance(1)
    return MetricsAcquisition(metrics=metrics, disposition="computed")


def _resolved_fps(source: SourceInfo, request: MetricCacheRequest) -> Fraction:
    return source.fps if request.effective_fps is None else request.effective_fps


def _resolved_metric_frame_range(
    source: SourceInfo,
    requested: MetricFrameRange | None,
) -> MetricFrameRange:
    source_frame_count = source.clip.num_frames
    if source_frame_count <= 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")
    if requested is None:
        return MetricFrameRange(
            source_frame_count=source_frame_count,
            start=0,
            end_exclusive=source_frame_count,
        )
    if requested.source_frame_count != source_frame_count:
        raise MetricsCalculationError(
            "Requested metric frame range does not match the loaded analysis source"
        )
    if requested.frame_count <= 0:
        raise MetricsCalculationError("Requested metric frame range is empty")
    return requested


def slice_frame_metrics(
    metrics: FrameMetrics,
    *,
    start_index: int,
    frame_count: int,
) -> FrameMetrics:
    if (
        start_index < 0
        or frame_count < 0
        or start_index + frame_count > metrics.eligible_frame_count
    ):
        raise MetricsCalculationError("Requested metric slice is outside cached metric range")
    source_start = metrics.metadata.metric_source_start + start_index
    source_end = source_start + frame_count
    if metrics.sampled_source_frames is None:
        end_index = start_index + frame_count
        return FrameMetrics(
            luminance=metrics.luminance[start_index:end_index],
            motion=metrics.motion[start_index:end_index],
            metadata=replace(
                metrics.metadata,
                frame_count=frame_count,
                metric_source_start=source_start,
                metric_source_end_exclusive=source_end,
            ),
        )

    source_frames = tuple(metrics.source_frames())
    retained_indices = [
        index
        for index, source_frame in enumerate(source_frames)
        if source_start <= source_frame < source_end
    ]
    sampled_source_frames = tuple(source_frames[index] for index in retained_indices)
    return FrameMetrics(
        luminance=[metrics.luminance[index] for index in retained_indices],
        motion=[metrics.motion[index] for index in retained_indices],
        metadata=replace(
            metrics.metadata,
            frame_count=len(retained_indices),
            metric_source_start=source_start,
            metric_source_end_exclusive=source_end,
        ),
        sampled_source_frames=sampled_source_frames,
    )
