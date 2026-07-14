"""Metric computation strategies for analysis performance modes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Protocol, cast

from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.analysis.metric_identity import (
    metric_algorithm_id,
    metric_backend,
    stable_metric_algorithm_identity_json,
)
from frame_compare.analysis.sampling import plan_performance_bursts
from frame_compare.analysis.timing import AnalysisTimingRecorder, record_span
from frame_compare.analysis.types import MetricActiveRect, MetricFrameRange
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
    sampled_source_frames: tuple[int, ...] | None = None


def calculate_metric_strategy(
    source: SourceInfo,
    config: AnalysisConfig,
    reporter: ProgressReporter | None,
    metric_active_rect: MetricActiveRect | None = None,
    *,
    metric_frame_range: MetricFrameRange | None = None,
    timing_recorder: AnalysisTimingRecorder | None = None,
) -> MetricComputationResult:
    """Dispatch metric computation for the configured analysis performance mode."""
    active_rect = _validated_active_rect(
        metric_active_rect,
        frame_width=source.clip.width,
        frame_height=source.clip.height,
    )
    if source.clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")
    frame_range = metric_frame_range or MetricFrameRange(
        source_frame_count=source.clip.num_frames,
        start=0,
        end_exclusive=source.clip.num_frames,
    )
    if frame_range.source_frame_count != source.clip.num_frames or frame_range.frame_count <= 0:
        raise MetricsCalculationError("Metric range does not match the loaded clip")
    if config.performance_mode == AnalysisPerformanceMode.QUALITY:
        decode_start = max(0, frame_range.start - 1)
        strategy_clip = source.clip[decode_start : frame_range.end_exclusive]
        luminance, motion = calculate_quality_planestats_metrics(
            strategy_clip,
            reporter,
            active_rect,
            timing_recorder=timing_recorder,
        )
        if decode_start < frame_range.start:
            luminance = luminance[1:]
            motion = motion[1:]
        return MetricComputationResult(
            luminance=luminance,
            motion=motion,
            performance_mode=config.performance_mode.value,
            algorithm_id=metric_algorithm_id(config),
            metric_backend=metric_backend(config),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config),
        )
    if config.performance_mode == AnalysisPerformanceMode.PERFORMANCE:
        luminance, motion, sampled_source_frames = calculate_performance_planestats_metrics(
            source.clip,
            reporter,
            active_rect,
            metric_frame_range=frame_range,
            timing_recorder=timing_recorder,
        )
        return MetricComputationResult(
            luminance=luminance,
            motion=motion,
            performance_mode=config.performance_mode.value,
            algorithm_id=metric_algorithm_id(config),
            metric_backend=metric_backend(config),
            algorithm_identity_json=stable_metric_algorithm_identity_json(config),
            sampled_source_frames=sampled_source_frames,
        )
    raise MetricsCalculationError(
        f"Unsupported analysis performance mode '{config.performance_mode.value}'."
    )


def calculate_performance_planestats_metrics(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None = None,
    metric_active_rect: MetricActiveRect | None = None,
    *,
    metric_frame_range: MetricFrameRange | None = None,
    timing_recorder: AnalysisTimingRecorder | None = None,
) -> tuple[list[float], list[float], tuple[int, ...]]:
    """Calculate sparse full-resolution PlaneStats metrics for performance mode."""
    if clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")

    active_rect = _validated_active_rect(
        metric_active_rect,
        frame_width=clip.width,
        frame_height=clip.height,
    )
    frame_range = metric_frame_range or MetricFrameRange(
        source_frame_count=clip.num_frames,
        start=0,
        end_exclusive=clip.num_frames,
    )
    if frame_range.source_frame_count != clip.num_frames or frame_range.frame_count <= 0:
        raise MetricsCalculationError("Performance metric range does not match the loaded clip")
    bursts = plan_performance_bursts(
        window_start=frame_range.start,
        window_end_exclusive=frame_range.end_exclusive,
    )
    total_samples = sum(burst.frame_count for burst in bursts)
    luminance: list[float] = []
    motion: list[float] = []
    sampled_source_frames: list[int] = []
    phase_status = ProgressPhaseStatus.COMPLETED
    if reporter:
        reporter.start_phase("Calculating metrics", total_samples)
    try:
        with perf_span("analysis.performance_metrics", frames=total_samples):
            for burst in bursts:
                burst_clip = clip[burst.decode_start : burst.end_exclusive]
                burst_luminance, burst_motion = _calculate_full_resolution_planestats_metrics(
                    burst_clip,
                    metric_active_rect=active_rect,
                    timing_recorder=timing_recorder,
                    timing_prefix="performance",
                )
                if burst.decode_start < burst.start:
                    burst_luminance = burst_luminance[1:]
                    burst_motion = burst_motion[1:]
                if (
                    len(burst_luminance) != burst.frame_count
                    or len(burst_motion) != burst.frame_count
                ):
                    raise MetricsCalculationError(
                        "Performance PlaneStats burst returned an unexpected metric count"
                    )
                luminance.extend(burst_luminance)
                motion.extend(burst_motion)
                sampled_source_frames.extend(range(burst.start, burst.end_exclusive))
                if reporter:
                    reporter.advance(burst.frame_count)
    except Exception:
        phase_status = ProgressPhaseStatus.FAILED
        raise
    finally:
        if reporter:
            reporter.complete_phase(phase_status)
    return luminance, motion, tuple(sampled_source_frames)


def calculate_quality_planestats_metrics(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None = None,
    metric_active_rect: MetricActiveRect | None = None,
    *,
    timing_recorder: AnalysisTimingRecorder | None = None,
) -> tuple[list[float], list[float]]:
    """Calculate full-resolution PlaneStats metrics used by quality mode."""
    return _calculate_full_resolution_planestats_metrics(
        clip,
        reporter,
        metric_active_rect,
        timing_recorder=timing_recorder,
        timing_prefix="quality",
    )


def _calculate_full_resolution_planestats_metrics(
    clip: vs.VideoNode,
    reporter: ProgressReporter | None = None,
    metric_active_rect: MetricActiveRect | None = None,
    *,
    timing_recorder: AnalysisTimingRecorder | None = None,
    timing_prefix: str,
) -> tuple[list[float], list[float]]:
    """Calculate full-resolution PlaneStats with caller-owned telemetry labels."""
    if clip.num_frames == 0:
        raise MetricsCalculationError("Analysis clip has 0 frames")

    active_rect = _validated_active_rect(
        metric_active_rect,
        frame_width=clip.width,
        frame_height=clip.height,
    )
    with perf_span(f"analysis.{timing_prefix}_planestats", frames=clip.num_frames):
        with record_span(timing_recorder, "metric_graph_build"):
            luma = _planestats_luma_clip(
                clip,
                active_rect=active_rect,
                mode_name=timing_prefix.capitalize(),
            )
        return _calculate_dense_planestats_metrics(
            luma,
            reporter,
            timing_recorder,
            timing_prefix=timing_prefix,
            error_label=timing_prefix,
            perf_label=f"analysis.{timing_prefix}_planestats_metrics",
        )


def _planestats_luma_clip(
    clip: vs.VideoNode,
    *,
    active_rect: MetricActiveRect | None,
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
        return luma
    except Exception as exc:
        raise MetricsCalculationError(f"{mode_name} luma preparation failed: {exc}") from exc


def _calculate_dense_planestats_metrics(
    luma: vs.VideoNode,
    reporter: ProgressReporter | None = None,
    timing_recorder: AnalysisTimingRecorder | None = None,
    *,
    timing_prefix: str = "performance",
    error_label: str = "performance",
    perf_label: str = "analysis.performance_metrics",
) -> tuple[list[float], list[float]]:
    if luma.num_frames == 0:
        raise MetricsCalculationError("Empty clip")

    with perf_span(perf_label, frames=luma.num_frames):
        if reporter:
            reporter.start_phase("Calculating metrics", luma.num_frames)

        luminance: list[float] = []
        motion = [0.0] * luma.num_frames
        phase_status = ProgressPhaseStatus.COMPLETED
        failure_stage = "graph construction"
        try:
            with record_span(timing_recorder, f"{timing_prefix}_graph_build"):
                import vapoursynth as vs

                core = _dynamic_attr(vs, "core")
                std = _dynamic_attr(core, "std")
                splice = cast(_SpliceFn, _dynamic_attr(std, "Splice"))
                previous = splice(clips=[luma[0:1], luma[0:-1]])
                plane_stats = cast(_PlaneStatsFn, _dynamic_attr(luma.std, "PlaneStats"))
                stats = cast(_FrameReadable, plane_stats(previous))
            failure_stage = "frame access"
            for n in range(luma.num_frames):
                frame_started = perf_counter() if timing_recorder is not None else 0.0
                frame = stats.get_frame(n)
                if timing_recorder is not None:
                    timing_recorder.add_seconds(
                        f"{timing_prefix}_frame_render", perf_counter() - frame_started
                    )
                metric_started = perf_counter() if timing_recorder is not None else 0.0
                luminance.append(_frame_prop_float(frame, "PlaneStatsAverage"))
                if n > 0:
                    motion[n] = _frame_prop_float(frame, "PlaneStatsDiff")
                if timing_recorder is not None:
                    timing_recorder.add_seconds(
                        f"{timing_prefix}_metric_read", perf_counter() - metric_started
                    )
                if reporter:
                    reporter.advance(1)
        except Exception as exc:
            phase_status = ProgressPhaseStatus.FAILED
            raise MetricsCalculationError(
                f"Failure during {error_label} metric analysis ({failure_stage}) "
                f"at frame {len(luminance)}: {exc}"
            ) from exc
        finally:
            if reporter:
                reporter.complete_phase(phase_status)

    return luminance, motion


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
    "calculate_performance_planestats_metrics",
    "calculate_quality_planestats_metrics",
]
