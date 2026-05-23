"""Metric calculation logic for frame analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import structlog

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    compute_cache_key,
    load_cached_metrics,
    save_metrics_cache,
)
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.errors import (
    MetricsCalculationError,
)
from frame_compare.utils.perf import perf_span
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.loader import DefaultVSLoader

if TYPE_CHECKING:
    from pathlib import Path

    import vapoursynth as vs  # type: ignore

    from frame_compare.config.schema import AnalysisConfig


log = structlog.get_logger()

# Orchestration "analyze" phase progress total.
# Contract:
# - `execute_phases()` advances the phase by 1 on successful completion.
# - `calculate_metrics()` advances the remaining steps (total - 1) on cache hit,
#   and advances twice (after luminance + after cache-save attempt) on cache miss.
ANALYZE_PROGRESS_TOTAL = 3


def calculate_metrics(
    video_paths: list[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    reporter: ProgressReporter | None = None,
) -> FrameMetrics:
    """
    Calculate frame metrics for the given clips.

    Uses cached values if valid cache exists and config matches.
    Only the reference clip (video_paths[0]) is analyzed.

    Args:
        video_paths: Video file paths (first entry is the reference clip)
        config: Analysis configuration
        cache_dir: Directory for cache files
        reporter: Optional progress reporter

    Returns:
        FrameMetrics with luminance and motion arrays

    Raises:
        MetricsCalculationError (FC-4002): If frame extraction or metric
            computation fails, OR if reference clip has 0 frames.
        PluginNotFoundError (FC-2003): If VapourSynth lsmas plugin unavailable.
        SourceLoadError (FC-4015): If video file cannot be loaded.
    """
    if not video_paths:
        raise MetricsCalculationError("No input video paths provided")

    fingerprint = compute_cache_key(video_paths, config)

    # Attempt to load from cache
    clips = [
        ClipIdentity(
            path=str(p),
            size=p.stat().st_size,
            mtime=p.stat().st_mtime,
        )
        for p in video_paths
    ]

    cache_result = load_cached_metrics(cache_dir, fingerprint, clips)
    if cache_result.success and cache_result.metrics:
        if reporter:
            reporter.set_description("Cache hit")
            reporter.advance(ANALYZE_PROGRESS_TOTAL - 1)
        return cache_result.metrics

    # Cache miss or invalid - compute metrics for reference clip only
    reference_path = video_paths[0]
    loader = DefaultVSLoader()
    try:
        source = loader.load(reference_path)
    except (PluginNotFoundError, SourceLoadError):
        raise
    except Exception as e:
        raise MetricsCalculationError(f"Failed to load reference video: {e}") from e

    clip = source.clip
    if clip.num_frames == 0:
        raise MetricsCalculationError("Reference clip has 0 frames")

    total_frames = int(clip.num_frames)  # type: ignore[arg-type]
    with perf_span("analysis.calculate_metrics", frames=total_frames):
        luminance = _calculate_luminance(clip, reporter)
        if reporter:
            reporter.advance(1)
        motion = _calculate_motion(clip, reporter=reporter)

    metrics = FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=clip.num_frames,
            fps=source.fps,
            config_fingerprint=fingerprint,
            clips=clips,
            version=CACHE_VERSION,
        ),
    )

    if reporter:
        reporter.start_phase("Saving analysis cache", total=1)
    try:
        save_metrics_cache(metrics, cache_dir)
    except Exception as e:
        if reporter:
            reporter.set_description(f"Cache save failed: {e}")
        log.warning("analysis_cache_save_failed", error=str(e), exc_info=True)
    finally:
        if reporter:
            reporter.advance(1)
            reporter.complete_phase()

    if reporter:
        reporter.advance(1)
    return metrics


def _calculate_luminance(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None = None,
) -> list[float]:
    """
    Calculate Y channel mean for each frame.

    Args:
        clip: VapourSynth clip to analyze
        reporter: Optional progress reporter

    Returns:
        List of per-frame luminance values (0.0-1.0)
    """
    import vapoursynth as vs  # type: ignore

    if clip.num_frames == 0:
        raise MetricsCalculationError("Empty clip")

    total_frames = int(clip.num_frames)  # type: ignore[arg-type]
    with perf_span("analysis.luminance", frames=total_frames):
        # Format handling: convert to YUV if needed
        if clip.format.color_family != vs.YUV:  # type: ignore
            clip = clip.resize.Bicubic(format=vs.YUV420P8)  # type: ignore

        max_value: float = (
            1.0
            if clip.format.sample_type == vs.FLOAT  # type: ignore
            else float((1 << clip.format.bits_per_sample) - 1)  # type: ignore
        )

        if reporter:
            reporter.start_phase("Calculating luminance", clip.num_frames)  # type: ignore

        luminance: list[float] = []
        try:
            for n in range(clip.num_frames):  # type: ignore
                frame = clip.get_frame(n)  # type: ignore
                arr = np.asarray(frame[0])  # type: ignore
                mean_val = float(np.mean(arr))  # type: ignore
                luminance.append(mean_val / max_value)
                if reporter:
                    reporter.advance(1)
        except Exception as e:
            # Re-raise with FC-4002 context
            raise MetricsCalculationError(
                f"Frame access failed at frame {len(luminance)}: {e}"
            ) from e
        finally:
            if reporter:
                reporter.complete_phase()

        return luminance


def _calculate_motion(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None = None,
) -> list[float]:
    """
    Calculate frame-to-frame difference scores.

    Args:
        clip: VapourSynth clip to analyze
        reporter: Optional progress reporter to receive progress updates during motion calculation.

    Returns:
        List of per-frame motion scores (0.0-1.0)
    """
    import vapoursynth as vs  # type: ignore

    if clip.num_frames == 0:
        raise MetricsCalculationError("Empty clip")

    total_frames = int(clip.num_frames)  # type: ignore[arg-type]
    with perf_span("analysis.motion", frames=total_frames):
        # Format handling: convert to YUV if needed
        if clip.format.color_family != vs.YUV:  # type: ignore
            clip = clip.resize.Bicubic(format=vs.YUV420P8)  # type: ignore

        width, height = clip.width, clip.height  # type: ignore
        max_value: float = (
            1.0
            if clip.format.sample_type == vs.FLOAT  # type: ignore
            else float((1 << clip.format.bits_per_sample) - 1)  # type: ignore
        )
        norm_factor = float(width * height) * max_value  # type: ignore

        if reporter:
            reporter.start_phase("Calculating motion", max(1, total_frames - 1))

        motion = [0.0] * clip.num_frames  # type: ignore
        try:
            for n in range(1, clip.num_frames):  # type: ignore
                prev_frame = clip.get_frame(n - 1)  # type: ignore
                curr_frame = clip.get_frame(n)  # type: ignore
                prev_arr = np.asarray(prev_frame[0]).astype(np.float32)  # type: ignore
                curr_arr = np.asarray(curr_frame[0]).astype(np.float32)  # type: ignore
                diff = np.abs(curr_arr - prev_arr)
                motion[n] = float(np.sum(diff)) / norm_factor  # type: ignore
                if reporter:
                    reporter.advance(1)
        except Exception as e:
            # Re-raise with FC-4002 context
            raise MetricsCalculationError(f"Frame access failed during motion analysis: {e}") from e
        finally:
            if reporter:
                reporter.complete_phase()

        return motion  # type: ignore
