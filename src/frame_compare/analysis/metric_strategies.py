"""Metric computation strategies for analysis performance modes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

import numpy as np
import numpy.typing as npt

from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.config.schema_enums import AnalysisPerformanceMode
from frame_compare.utils.perf import perf_span
from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.config.schema import AnalysisConfig
    from frame_compare.vs.types import SourceInfo


class _ShufflePlanesFn(Protocol):
    def __call__(self, *, clips: object, planes: int, colorfamily: int) -> object: ...


class _PlaneStatsFn(Protocol):
    def __call__(self, clipb: object | None = None) -> object: ...


class _FrameReadable(Protocol):
    def get_frame(self, n: int) -> object: ...


class _ResizeFn(Protocol):
    def __call__(self, *, width: int, height: int) -> object: ...


@dataclass(frozen=True, slots=True)
class MetricComputationResult:
    """Metric arrays and algorithm metadata produced by one strategy."""

    luminance: list[float]
    motion: list[float]
    performance_mode: str
    algorithm_id: str
    metric_backend: str
    algorithm_identity_json: str


def calculate_metric_strategy(
    source: SourceInfo,
    config: AnalysisConfig,
    reporter: ProgressReporter | None,
) -> MetricComputationResult:
    """Dispatch metric computation for the configured analysis performance mode."""
    if config.performance_mode == AnalysisPerformanceMode.QUALITY:
        luminance, motion = _calculate_quality_metrics(source.clip, reporter)
        return MetricComputationResult(
            luminance=luminance,
            motion=motion,
            performance_mode=config.performance_mode.value,
            algorithm_id=metric_algorithm_id(config),
            metric_backend=metric_backend(config),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config),
        )
    if config.performance_mode == AnalysisPerformanceMode.BALANCED:
        luminance, motion = _calculate_balanced_metrics(source.clip, reporter)
        return MetricComputationResult(
            luminance=luminance,
            motion=motion,
            performance_mode=config.performance_mode.value,
            algorithm_id=metric_algorithm_id(config),
            metric_backend=metric_backend(config),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config),
        )
    if config.performance_mode == AnalysisPerformanceMode.FAST:
        luminance, motion = _calculate_fast_metrics(source.clip, reporter)
        return MetricComputationResult(
            luminance=luminance,
            motion=motion,
            performance_mode=config.performance_mode.value,
            algorithm_id=metric_algorithm_id(config),
            metric_backend=metric_backend(config),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config),
        )
    raise MetricsCalculationError(
        f"Unsupported analysis performance mode '{config.performance_mode.value}'."
    )


def calculate_quality_luminance(
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
        phase_status = ProgressPhaseStatus.COMPLETED
        try:
            for n in range(clip.num_frames):
                frame = clip.get_frame(n)
                arr = _y_plane_array(frame)
                mean_val = float(arr.mean())
                luminance.append(mean_val / max_value)
                if reporter:
                    reporter.advance(1)
        except Exception as e:
            phase_status = ProgressPhaseStatus.FAILED
            raise MetricsCalculationError(
                f"Frame access failed at frame {len(luminance)}: {e}"
            ) from e
        finally:
            if reporter:
                reporter.complete_phase(phase_status)

        return luminance


def calculate_quality_motion(
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
        phase_status = ProgressPhaseStatus.COMPLETED
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
            phase_status = ProgressPhaseStatus.FAILED
            raise MetricsCalculationError(f"Frame access failed during motion analysis: {e}") from e
        finally:
            if reporter:
                reporter.complete_phase(phase_status)

        return motion


def _calculate_quality_metrics(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None,
) -> tuple[list[float], list[float]]:
    if clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")

    total_frames = clip.num_frames
    with perf_span("analysis.calculate_metrics", frames=total_frames):
        luminance = calculate_quality_luminance(clip, reporter)
        if reporter:
            reporter.advance(1)
        motion = calculate_quality_motion(clip, reporter=reporter)

    return luminance, motion


def _calculate_balanced_metrics(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None,
) -> tuple[list[float], list[float]]:
    if clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")

    total_frames = clip.num_frames
    with perf_span("analysis.calculate_metrics", frames=total_frames):
        luma = _balanced_luma_clip(clip)
        luminance = _calculate_balanced_luminance(luma, reporter)
        if reporter:
            reporter.advance(1)
        motion = _calculate_balanced_motion(luma, reporter)

    return luminance, motion


def _calculate_fast_metrics(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None,
) -> tuple[list[float], list[float]]:
    if clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")

    total_frames = clip.num_frames
    with perf_span("analysis.calculate_metrics", frames=total_frames):
        luma = _fast_luma_clip(clip)
        luminance = _calculate_fast_luminance(luma, reporter)
        if reporter:
            reporter.advance(1)
        motion = _calculate_fast_motion(luma, reporter)

    return luminance, motion


def _balanced_luma_clip(clip: vs.VideoNode) -> vs.VideoNode:
    return _planestats_luma_clip(
        clip,
        target_max_width=320,
        mode_name="Balanced",
        resize_filter="Bicubic",
    )


def _fast_luma_clip(clip: vs.VideoNode) -> vs.VideoNode:
    return _planestats_luma_clip(
        clip,
        target_max_width=160,
        mode_name="Fast",
        resize_filter="Bilinear",
    )


def _planestats_luma_clip(
    clip: vs.VideoNode,
    *,
    target_max_width: int,
    mode_name: str,
    resize_filter: str,
) -> vs.VideoNode:
    import vapoursynth as vs

    if clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")

    try:
        if clip.format.color_family != vs.YUV:
            clip = clip.resize.Bicubic(format=vs.YUV420P8)

        core = _dynamic_attr(vs, "core")
        std = _dynamic_attr(core, "std")
        shuffle_planes = cast(_ShufflePlanesFn, _dynamic_attr(std, "ShufflePlanes"))
        gray = cast(int, _dynamic_attr(vs, "GRAY"))
        luma = cast("vs.VideoNode", shuffle_planes(clips=clip, planes=0, colorfamily=gray))
        if luma.width <= target_max_width:
            return luma

        target_width = target_max_width
        target_height = max(1, round(luma.height * target_width / luma.width))
        resize = cast(_ResizeFn, _dynamic_attr(luma.resize, resize_filter))
        return cast("vs.VideoNode", resize(width=target_width, height=target_height))
    except Exception as exc:
        raise MetricsCalculationError(f"{mode_name} luma preparation failed: {exc}") from exc


def _calculate_fast_luminance(
    luma: vs.VideoNode,
    reporter: ProgressReporter | None = None,
) -> list[float]:
    if luma.num_frames == 0:
        raise MetricsCalculationError("Empty clip")

    with perf_span("analysis.fast_luminance", frames=luma.num_frames):
        if reporter:
            reporter.start_phase("Calculating luminance", luma.num_frames)

        plane_stats = cast(_PlaneStatsFn, _dynamic_attr(luma.std, "PlaneStats"))
        stats = cast(_FrameReadable, plane_stats())
        luminance: list[float] = []
        phase_status = ProgressPhaseStatus.COMPLETED
        try:
            for n in range(luma.num_frames):
                frame = stats.get_frame(n)
                luminance.append(_frame_prop_float(frame, "PlaneStatsAverage"))
                if reporter:
                    reporter.advance(1)
        except Exception as exc:
            phase_status = ProgressPhaseStatus.FAILED
            raise MetricsCalculationError(
                f"Frame access failed at frame {len(luminance)}: {exc}"
            ) from exc
        finally:
            if reporter:
                reporter.complete_phase(phase_status)

    return luminance


def _calculate_balanced_luminance(
    luma: vs.VideoNode,
    reporter: ProgressReporter | None = None,
) -> list[float]:
    if luma.num_frames == 0:
        raise MetricsCalculationError("Empty clip")

    with perf_span("analysis.balanced_luminance", frames=luma.num_frames):
        if reporter:
            reporter.start_phase("Calculating luminance", luma.num_frames)

        plane_stats = cast(_PlaneStatsFn, _dynamic_attr(luma.std, "PlaneStats"))
        stats = cast(_FrameReadable, plane_stats())
        luminance: list[float] = []
        phase_status = ProgressPhaseStatus.COMPLETED
        try:
            for n in range(luma.num_frames):
                frame = stats.get_frame(n)
                luminance.append(_frame_prop_float(frame, "PlaneStatsAverage"))
                if reporter:
                    reporter.advance(1)
        except Exception as exc:
            phase_status = ProgressPhaseStatus.FAILED
            raise MetricsCalculationError(
                f"Frame access failed at frame {len(luminance)}: {exc}"
            ) from exc
        finally:
            if reporter:
                reporter.complete_phase(phase_status)

    return luminance


def _calculate_balanced_motion(
    luma: vs.VideoNode,
    reporter: ProgressReporter | None = None,
) -> list[float]:
    return _calculate_dense_planestats_motion(
        luma,
        reporter,
        span_name="analysis.balanced_motion",
    )


def _calculate_dense_planestats_motion(
    luma: vs.VideoNode,
    reporter: ProgressReporter | None,
    *,
    span_name: str,
) -> list[float]:
    if luma.num_frames == 0:
        raise MetricsCalculationError("Empty clip")
    if luma.num_frames == 1:
        return [0.0]

    total_pairs = luma.num_frames - 1
    with perf_span(span_name, frames=luma.num_frames):
        if reporter:
            reporter.start_phase("Calculating motion", total_pairs)

        motion = [0.0] * luma.num_frames
        phase_status = ProgressPhaseStatus.COMPLETED
        try:
            previous = luma[0:total_pairs]
            current = luma[1 : luma.num_frames]
            plane_stats = cast(_PlaneStatsFn, _dynamic_attr(current.std, "PlaneStats"))
            stats = cast(_FrameReadable, plane_stats(previous))
            for result_index in range(total_pairs):
                frame = stats.get_frame(result_index)
                motion[result_index + 1] = _frame_prop_float(frame, "PlaneStatsDiff")
                if reporter:
                    reporter.advance(1)
        except Exception as exc:
            phase_status = ProgressPhaseStatus.FAILED
            raise MetricsCalculationError(
                f"Frame access failed during motion analysis: {exc}"
            ) from exc
        finally:
            if reporter:
                reporter.complete_phase(phase_status)

    return motion


def _calculate_fast_motion(
    luma: vs.VideoNode,
    reporter: ProgressReporter | None = None,
) -> list[float]:
    return _calculate_dense_planestats_motion(
        luma,
        reporter,
        span_name="analysis.fast_motion",
    )


def _y_plane_array(frame: vs.VideoFrame) -> npt.NDArray[np.generic]:
    return np.asarray(frame[0])


def _frame_prop_float(frame: object, key: str) -> float:
    props = getattr(frame, "props", None)
    if not isinstance(props, Mapping):
        raise MetricsCalculationError("VapourSynth frame props are unavailable")
    typed_props = cast(Mapping[str, object], props)
    value = typed_props[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise MetricsCalculationError(f"Expected numeric VapourSynth frame prop {key}")
    return float(value)


def _dynamic_attr(owner: object, name: str) -> object:
    return getattr(owner, name)


__all__ = [
    "MetricComputationResult",
    "calculate_metric_strategy",
    "calculate_quality_luminance",
    "calculate_quality_motion",
]
