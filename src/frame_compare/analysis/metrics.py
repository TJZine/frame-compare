"""Metric calculation logic for frame analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
import structlog

from frame_compare.analysis.cache_io import (
    CACHE_VERSION,
    compute_cache_key,
    load_cached_metrics,
    save_metrics_cache,
)
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.utils.perf import perf_span
from frame_compare.utils.progress_protocol import ProgressReporter
from frame_compare.vs.errors import PluginNotFoundError, SourceLoadError
from frame_compare.vs.loader import DefaultVSLoader

if TYPE_CHECKING:
    from pathlib import Path

    import vapoursynth as vs

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


def _y_plane_array(frame: vs.VideoFrame) -> npt.NDArray[np.generic]:
    return np.asarray(frame[0])


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


def _load_reference_source(reference_path: Path, vs_loader: VSLoader | None) -> SourceInfo:
    loader = vs_loader or DefaultVSLoader()
    try:
        return loader.load(reference_path)
    except (PluginNotFoundError, SourceLoadError):
        raise
    except Exception as e:
        raise MetricsCalculationError(f"Failed to load reference video: {e}") from e


def _calculate_clip_metrics(
    source: SourceInfo, reporter: ProgressReporter | None
) -> tuple[list[float], list[float]]:
    clip = source.clip
    if clip.num_frames == 0:
        raise MetricsCalculationError("Reference clip has 0 frames")

    total_frames = clip.num_frames
    with perf_span("analysis.calculate_metrics", frames=total_frames):
        luminance = _calculate_luminance(clip, reporter)
        if reporter:
            reporter.advance(1)
        motion = _calculate_motion(clip, reporter=reporter)

    return luminance, motion


def _build_metrics(
    *,
    luminance: list[float],
    motion: list[float],
    source: SourceInfo,
    fingerprint: str,
    clips: list[ClipIdentity],
) -> FrameMetrics:
    return FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=source.clip.num_frames,
            fps=source.fps,
            config_fingerprint=fingerprint,
            clips=clips,
            version=CACHE_VERSION,
        ),
    )


def _save_metrics_cache_best_effort(
    metrics: FrameMetrics,
    cache_dir: Path,
    reporter: ProgressReporter | None,
) -> None:
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


def calculate_metrics(
    video_paths: list[Path],
    config: AnalysisConfig,
    cache_dir: Path,
    reporter: ProgressReporter | None = None,
    vs_loader: VSLoader | None = None,
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
        vs_loader: Optional VapourSynth clip loader seam

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
    clips = _clip_identities(video_paths)

    cached = _cached_metrics(cache_dir, fingerprint, clips, reporter)
    if cached:
        return cached

    # Cache miss or invalid - compute metrics for reference clip only
    source = _load_reference_source(video_paths[0], vs_loader)
    luminance, motion = _calculate_clip_metrics(source, reporter)
    metrics = _build_metrics(
        luminance=luminance,
        motion=motion,
        source=source,
        fingerprint=fingerprint,
        clips=clips,
    )

    _save_metrics_cache_best_effort(metrics, cache_dir, reporter)

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
    import vapoursynth as vs

    if clip.num_frames == 0:
        raise MetricsCalculationError("Empty clip")

    total_frames = clip.num_frames
    with perf_span("analysis.luminance", frames=total_frames):
        # Format handling: convert to YUV if needed
        if clip.format.color_family != vs.YUV:
            clip = clip.resize.Bicubic(format=vs.YUV420P8)

        max_value: float = (
            1.0
            if clip.format.sample_type == vs.FLOAT
            else float((1 << clip.format.bits_per_sample) - 1)
        )

        if reporter:
            reporter.start_phase("Calculating luminance", clip.num_frames)

        luminance: list[float] = []
        try:
            for n in range(clip.num_frames):
                frame = clip.get_frame(n)
                arr = _y_plane_array(frame)
                mean_val = float(arr.mean())
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
    import vapoursynth as vs

    if clip.num_frames == 0:
        raise MetricsCalculationError("Empty clip")

    total_frames = clip.num_frames
    with perf_span("analysis.motion", frames=total_frames):
        # Format handling: convert to YUV if needed
        if clip.format.color_family != vs.YUV:
            clip = clip.resize.Bicubic(format=vs.YUV420P8)

        width, height = clip.width, clip.height
        max_value: float = (
            1.0
            if clip.format.sample_type == vs.FLOAT
            else float((1 << clip.format.bits_per_sample) - 1)
        )
        norm_factor = float(width * height) * max_value

        if reporter:
            reporter.start_phase("Calculating motion", max(1, total_frames - 1))

        motion = [0.0] * clip.num_frames
        try:
            for n in range(1, clip.num_frames):
                prev_frame = clip.get_frame(n - 1)
                curr_frame = clip.get_frame(n)
                prev_arr = _y_plane_array(prev_frame).astype(np.float32)
                curr_arr = _y_plane_array(curr_frame).astype(np.float32)
                diff = np.abs(curr_arr - prev_arr)
                motion[n] = float(np.sum(diff)) / norm_factor
                if reporter:
                    reporter.advance(1)
        except Exception as e:
            # Re-raise with FC-4002 context
            raise MetricsCalculationError(f"Frame access failed during motion analysis: {e}") from e
        finally:
            if reporter:
                reporter.complete_phase()

        return motion
