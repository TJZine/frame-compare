"""Metric computation strategies for analysis performance modes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Protocol, cast

import numpy as np
import numpy.typing as npt

from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.analysis.timing import AnalysisTimingRecorder, record_span
from frame_compare.analysis.types import MetricActiveRect
from frame_compare.config.schema_enums import AnalysisPerformanceMode
from frame_compare.utils.perf import perf_span
from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.config.schema import AnalysisConfig
    from frame_compare.vs.types import SourceInfo


class _ShufflePlanesFn(Protocol):
    def __call__(self, *, clips: object, planes: int, colorfamily: int) -> object: ...


class _SpliceFn(Protocol):
    def __call__(self, *, clips: list[object]) -> object: ...


class _PlaneStatsFn(Protocol):
    def __call__(self, clipb: object | None = None) -> object: ...


class _CropAbsFn(Protocol):
    def __call__(self, *, width: int, height: int, left: int, top: int) -> object: ...


class _FrameReadable(Protocol):
    def get_frame(self, n: int) -> object: ...


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
    metric_active_rect: MetricActiveRect | None = None,
    *,
    timing_recorder: AnalysisTimingRecorder | None = None,
) -> MetricComputationResult:
    """Dispatch metric computation for the configured analysis performance mode."""
    active_rect = _validated_active_rect(
        metric_active_rect,
        frame_width=source.clip.width,
        frame_height=source.clip.height,
    )
    if config.performance_mode == AnalysisPerformanceMode.QUALITY:
        luminance, motion = _calculate_quality_metrics(
            source.clip,
            reporter,
            active_rect,
            timing_recorder,
        )
        return MetricComputationResult(
            luminance=luminance,
            motion=motion,
            performance_mode=config.performance_mode.value,
            algorithm_id=metric_algorithm_id(config),
            metric_backend=metric_backend(config),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config),
        )
    if config.performance_mode == AnalysisPerformanceMode.PERFORMANCE:
        luminance, motion = _calculate_performance_metrics(
            source.clip,
            reporter,
            active_rect,
            timing_recorder,
        )
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
    metric_active_rect: MetricActiveRect | None = None,
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
        active_rect = _validated_active_rect(
            metric_active_rect,
            frame_width=clip.width,
            frame_height=clip.height,
        )

        if reporter:
            reporter.start_phase("Calculating luminance", clip.num_frames)

        luminance: list[float] = []
        phase_status = ProgressPhaseStatus.COMPLETED
        try:
            for n in range(clip.num_frames):
                frame = clip.get_frame(n)
                arr = _cropped_y_plane_array(_y_plane_array(frame), active_rect)
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
    metric_active_rect: MetricActiveRect | None = None,
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

        active_rect = _validated_active_rect(
            metric_active_rect,
            frame_width=clip.width,
            frame_height=clip.height,
        )
        width = clip.width if active_rect is None else active_rect.width
        height = clip.height if active_rect is None else active_rect.height
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
                prev_arr = _cropped_y_plane_array(
                    _y_plane_array(prev_frame),
                    active_rect,
                ).astype(np.float32)
                curr_arr = _cropped_y_plane_array(
                    _y_plane_array(curr_frame),
                    active_rect,
                ).astype(np.float32)
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
    active_rect: MetricActiveRect | None,
    timing_recorder: AnalysisTimingRecorder | None,
) -> tuple[list[float], list[float]]:
    if clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")

    total_frames = clip.num_frames
    with perf_span("analysis.calculate_metrics", frames=total_frames):
        import vapoursynth as vs

        with record_span(timing_recorder, "metric_graph_build"):
            if clip.format.color_family != vs.YUV:
                clip = clip.resize.Bicubic(format=vs.YUV420P8)

        max_value: float = (
            1.0
            if clip.format.sample_type == vs.FLOAT
            else float((1 << clip.format.bits_per_sample) - 1)
        )
        width = clip.width if active_rect is None else active_rect.width
        height = clip.height if active_rect is None else active_rect.height
        norm_factor = float(width * height) * max_value

        if reporter:
            reporter.start_phase("Calculating metrics", total_frames)

        luminance: list[float] = []
        motion = [0.0] * total_frames
        previous_arr: npt.NDArray[np.float32] | None = None
        phase_status = ProgressPhaseStatus.COMPLETED
        try:
            for n in range(total_frames):
                frame_started = perf_counter() if timing_recorder is not None else 0.0
                frame = clip.get_frame(n)
                if timing_recorder is not None:
                    timing_recorder.add_seconds("frame_render", perf_counter() - frame_started)
                metric_started = perf_counter() if timing_recorder is not None else 0.0
                arr = _cropped_y_plane_array(_y_plane_array(frame), active_rect)
                luminance.append(float(arr.mean()) / max_value)
                current_arr = arr.astype(np.float32)
                if previous_arr is not None:
                    diff = np.abs(current_arr - previous_arr)
                    motion[n] = float(np.sum(diff)) / norm_factor
                previous_arr = current_arr
                if timing_recorder is not None:
                    timing_recorder.add_seconds("metric_compute", perf_counter() - metric_started)
                if reporter:
                    reporter.advance(1)
        except Exception as exc:
            phase_status = ProgressPhaseStatus.FAILED
            raise MetricsCalculationError(
                f"Frame access failed during metric analysis at frame {len(luminance)}: {exc}"
            ) from exc
        finally:
            if reporter:
                reporter.complete_phase(phase_status)

    return luminance, motion


def _calculate_performance_metrics(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None,
    active_rect: MetricActiveRect | None,
    timing_recorder: AnalysisTimingRecorder | None,
) -> tuple[list[float], list[float]]:
    if clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")

    total_frames = clip.num_frames
    with perf_span("analysis.calculate_metrics", frames=total_frames):
        with record_span(timing_recorder, "metric_graph_build"):
            luma = _performance_luma_clip(clip, active_rect)
        return _calculate_dense_planestats_metrics(luma, reporter, timing_recorder)


def _performance_luma_clip(
    clip: vs.VideoNode,
    active_rect: MetricActiveRect | None,
) -> vs.VideoNode:
    return _planestats_luma_clip(
        clip,
        active_rect=active_rect,
        target_max_width=320,
        mode_name="Performance",
    )


def _planestats_luma_clip(
    clip: vs.VideoNode,
    *,
    active_rect: MetricActiveRect | None,
    target_max_width: int,
    mode_name: str,
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
        if active_rect is not None:
            crop_abs = cast(_CropAbsFn, _dynamic_attr(luma.std, "CropAbs"))
            luma = cast(
                "vs.VideoNode",
                crop_abs(
                    width=active_rect.width,
                    height=active_rect.height,
                    left=active_rect.x,
                    top=active_rect.y,
                ),
            )
        if luma.width <= target_max_width:
            return luma

        target_width = target_max_width
        target_height = max(1, round(luma.height * target_width / luma.width))
        return luma.resize.Bicubic(width=target_width, height=target_height)
    except Exception as exc:
        raise MetricsCalculationError(f"{mode_name} luma preparation failed: {exc}") from exc


def _calculate_dense_planestats_metrics(
    luma: vs.VideoNode,
    reporter: ProgressReporter | None = None,
    timing_recorder: AnalysisTimingRecorder | None = None,
) -> tuple[list[float], list[float]]:
    if luma.num_frames == 0:
        raise MetricsCalculationError("Empty clip")

    with perf_span("analysis.performance_metrics", frames=luma.num_frames):
        if reporter:
            reporter.start_phase("Calculating metrics", luma.num_frames)

        with record_span(timing_recorder, "performance_graph_build"):
            import vapoursynth as vs

            core = _dynamic_attr(vs, "core")
            std = _dynamic_attr(core, "std")
            splice = cast(_SpliceFn, _dynamic_attr(std, "Splice"))
            previous = splice(clips=[luma[0:1], luma[0:-1]])
            plane_stats = cast(_PlaneStatsFn, _dynamic_attr(luma.std, "PlaneStats"))
            stats = cast(_FrameReadable, plane_stats(previous))
        luminance: list[float] = []
        motion = [0.0] * luma.num_frames
        phase_status = ProgressPhaseStatus.COMPLETED
        try:
            for n in range(luma.num_frames):
                frame_started = perf_counter() if timing_recorder is not None else 0.0
                frame = stats.get_frame(n)
                if timing_recorder is not None:
                    timing_recorder.add_seconds(
                        "performance_frame_render", perf_counter() - frame_started
                    )
                metric_started = perf_counter() if timing_recorder is not None else 0.0
                luminance.append(_frame_prop_float(frame, "PlaneStatsAverage"))
                if n > 0:
                    motion[n] = _frame_prop_float(frame, "PlaneStatsDiff")
                if timing_recorder is not None:
                    timing_recorder.add_seconds(
                        "performance_metric_read", perf_counter() - metric_started
                    )
                if reporter:
                    reporter.advance(1)
        except Exception as exc:
            phase_status = ProgressPhaseStatus.FAILED
            raise MetricsCalculationError(
                f"Frame access failed during performance metric analysis "
                f"at frame {len(luminance)}: {exc}"
            ) from exc
        finally:
            if reporter:
                reporter.complete_phase(phase_status)

    return luminance, motion


def _y_plane_array(frame: vs.VideoFrame) -> npt.NDArray[np.generic]:
    return np.asarray(frame[0])


def _cropped_y_plane_array(
    arr: npt.NDArray[np.generic],
    active_rect: MetricActiveRect | None,
) -> npt.NDArray[np.generic]:
    if active_rect is None:
        return arr
    return arr[
        active_rect.y : active_rect.y + active_rect.height,
        active_rect.x : active_rect.x + active_rect.width,
    ]


def _validated_active_rect(
    active_rect: MetricActiveRect | None,
    *,
    frame_width: int,
    frame_height: int,
) -> MetricActiveRect | None:
    if active_rect is None:
        return None
    if (
        active_rect.x < 0
        or active_rect.y < 0
        or active_rect.width <= 0
        or active_rect.height <= 0
        or active_rect.x + active_rect.width > frame_width
        or active_rect.y + active_rect.height > frame_height
    ):
        raise MetricsCalculationError(
            "Analysis active_rect is outside loaded clip dimensions "
            f"({frame_width}x{frame_height}): "
            f"x={active_rect.x}, y={active_rect.y}, "
            f"width={active_rect.width}, height={active_rect.height}"
        )
    return active_rect


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
