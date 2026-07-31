"""Selection and analysis phase work plus shared frame-selection translations."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.errors import MetricsCalculationError, SelectionError
from frame_compare.analysis.frame_plan import create_frame_plan
from frame_compare.analysis.metrics import calculate_metrics
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.types import (
    CacheLoadResult,
    FrameMetrics,
    FrameSelection,
    SelectionBreakdown,
    SelectionDetail,
    SelectionDetailsByFrame,
)
from frame_compare.analysis.window import SelectionWindow
from frame_compare.orchestration.active_rect import metric_cache_request_for_clip
from frame_compare.orchestration.context import (
    ClipState,
    RunContext,
)
from frame_compare.orchestration.execution_types import AnalyzePhaseOutput, FramePlanPhaseOutput
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError
from frame_compare.utils.types import WorkspacePaths

if TYPE_CHECKING:
    from frame_compare.config.schema import AnalysisConfig
    from frame_compare.render.types import OverlaySelectionDetail
    from frame_compare.vs.loader import VSLoader

__all__ = [
    "build_initial_selection_details_by_source_frame",
    "generated_frame_count",
    "map_aligned_to_source_frame",
    "run_analyze_phase",
    "selection_breakdown_with_source_offset",
    "select_initial_frame_plan",
    "selection_detail_for_frame",
    "selection_details_with_source_offset",
    "selection_label_for_frame",
    "selection_timecode_for_frame",
    "source_frames_for_reference_base_domain",
    "to_overlay_selection_detail",
]


def select_initial_frame_plan(ctx: RunContext) -> FramePlanPhaseOutput:
    window_start, frame_count = _selection_window_for_context(ctx)
    user_frames = _user_frames_in_window(
        ctx.config.analysis, ctx.reference, window_start, frame_count
    )
    user_frame_set = set(user_frames)
    dropped_user_frames = sorted(set(ctx.config.analysis.user_frames) - set(user_frames))
    source_offset = ctx.reference.trim.trim_start_frames + window_start
    selectable_random_indices = [
        frame_index
        for frame_index in range(frame_count)
        if source_offset + frame_index not in user_frame_set
    ]
    random_count = ctx.config.analysis.random_frame_count
    if random_count > len(selectable_random_indices):
        raise SelectionError(
            "insufficient random candidates after user frames",
            requested=random_count,
            found=len(selectable_random_indices),
        )
    random_frames = [
        selectable_random_indices[frame] + window_start
        for frame in create_frame_plan(
            num_frames=len(selectable_random_indices),
            count=random_count,
            seed=ctx.config.analysis.random_seed,
        ).frames
    ]
    random_source_frames = [ctx.reference.trim.trim_start_frames + frame for frame in random_frames]
    selected_frames = sorted(
        {
            *(frame - ctx.reference.trim.trim_start_frames for frame in user_frames),
            *random_frames,
        }
    )
    requested_initial_count = len(ctx.config.analysis.user_frames) + (
        ctx.config.analysis.random_frame_count
    )
    if requested_initial_count > 0 and not selected_frames:
        raise SelectionError(
            "no selectable user or random frames remain after trims/windowing",
            requested=requested_initial_count,
            found=0,
        )
    warnings = (
        [
            "frame selection: dropped user frame(s) outside trims/windowing: "
            + ", ".join(str(frame) for frame in dropped_user_frames)
        ]
        if dropped_user_frames
        else []
    )
    return FramePlanPhaseOutput(
        selected_frames=selected_frames,
        selection_breakdown=SelectionBreakdown(user=user_frames, random=random_source_frames),
        selection_details_by_source_frame=build_initial_selection_details_by_source_frame(
            user_source_frames=user_frames,
            random_source_frames=random_source_frames,
            fps=ctx.reference.effective_fps,
        ),
        warnings=warnings,
    )


def build_initial_selection_details_by_source_frame(
    *,
    user_source_frames: list[int],
    random_source_frames: list[int],
    fps: Fraction,
) -> SelectionDetailsByFrame:
    details: SelectionDetailsByFrame = {}
    for frame in user_source_frames:
        details[frame] = SelectionDetail(
            frame_index=frame,
            label="User",
            source="frame_plan",
            timecode=selection_timecode_for_frame(frame, fps),
            clip_role="frame_plan",
            notes="user",
        )
    for frame in random_source_frames:
        details.setdefault(
            frame,
            SelectionDetail(
                frame_index=frame,
                label="Random",
                source="frame_plan",
                timecode=selection_timecode_for_frame(frame, fps),
                clip_role="frame_plan",
                notes="random",
            ),
        )
    return details


def _user_frames_in_window(
    config: AnalysisConfig,
    reference: ClipState,
    window_start: int,
    frame_count: int,
) -> list[int]:
    source_start = reference.trim.trim_start_frames + window_start
    source_end = source_start + frame_count
    return sorted({frame for frame in config.user_frames if source_start <= frame < source_end})


def _selection_window_for_context(ctx: RunContext) -> tuple[int, int]:
    window = ctx.selection_window
    if window.frame_count > 0:
        return window.start_frame, window.frame_count
    return 0, ctx.reference.effective_num_frames()


def generated_frame_count(config: AnalysisConfig) -> int:
    return (
        config.random_frame_count
        + config.dark_frame_count
        + config.bright_frame_count
        + config.motion_frame_count
    )


def _source_offset_for_reference_window(reference: ClipState, window_start: int) -> int:
    return reference.trim.trim_start_frames + window_start


def run_analyze_phase(
    ctx: RunContext,
    *,
    input_videos: list[Path],
    workspace: WorkspacePaths,
    require_cache_only: bool = False,
    vs_loader: VSLoader | None = None,
) -> AnalyzePhaseOutput:
    if ctx.analysis_clip is None:
        raise MetricsCalculationError("Analysis source was not resolved for metric analysis.")

    selection_domain = ctx.analysis_selection_domain
    metric_request = metric_cache_request_for_clip(
        ctx.analysis_clip,
        selection_window=ctx.selection_window,
        fallback_detection_mode=ctx.config.screenshots.active_rect_detection.value,
    )
    fingerprint = cache_io.compute_cache_key(
        input_videos,
        ctx.config.analysis,
        selection_domain=selection_domain,
        metric_request=metric_request,
    )
    cache_result = cache_io.load_cached_metrics_for_request(
        workspace.cache_dir,
        fingerprint,
        clips=[],
        request=metric_request,
    )
    metrics_cache_hit = cache_result.success and cache_result.metrics is not None
    if require_cache_only:
        metrics = _require_cached_metrics(
            cache_result=cache_result,
            cache_dir=workspace.cache_dir,
            input_videos=input_videos,
            fingerprint=fingerprint,
        )
    else:
        metrics = calculate_metrics(
            video_paths=input_videos,
            analysis_source_path=ctx.analysis_clip.path,
            config=ctx.config.analysis,
            cache_dir=workspace.cache_dir,
            reporter=ctx.reporter,
            vs_loader=vs_loader,
            selection_domain=selection_domain,
            effective_fps=ctx.analysis_clip.effective_fps,
            metric_frame_range=metric_request.metric_frame_range,
            metric_active_rect=metric_request.metric_active_rect,
            active_rect_source=metric_request.active_rect_source,
            active_rect_detection_mode=metric_request.active_rect_detection_mode,
            active_rect_algorithm_id=metric_request.active_rect_algorithm_id,
        )
    selection = _select_frames_for_selection_domain(
        metrics=metrics,
        reference=ctx.reference,
        analysis_clip=ctx.analysis_clip,
        selection_window=ctx.selection_window,
        config=ctx.config.analysis,
    )
    return AnalyzePhaseOutput(
        selected_frames=list(selection.frames),
        selection_breakdown=selection.breakdown,
        metrics_cache_hit=metrics_cache_hit,
        analysis_metrics=metrics,
        selection_details_by_source_frame=dict(selection.selection_details),
    )


def _require_cached_metrics(
    *,
    cache_result: CacheLoadResult,
    cache_dir: Path,
    input_videos: list[Path],
    fingerprint: str,
) -> FrameMetrics:
    if cache_result.success and cache_result.metrics is not None:
        return cache_result.metrics

    cache_path = cache_io.find_metrics_cache_file(cache_dir, fingerprint)
    expected_cache_path = cache_dir / cache_io.metrics_cache_filename(input_videos, fingerprint)
    error_cache_path = cache_path or expected_cache_path
    reason = cache_result.reason
    if reason == "corrupted":
        raise CacheCorruptionError(error_cache_path)
    if reason == "version_mismatch":
        found = cache_io.read_cache_version(error_cache_path) or "unknown"
        raise CacheVersionMismatchError(found, str(cache_io.CACHE_VERSION))
    raise MetricsCalculationError(f"Cached metrics missing or mismatched ({reason}).")


def _select_frames_for_selection_domain(
    *,
    metrics: FrameMetrics,
    reference: ClipState,
    analysis_clip: ClipState,
    selection_window: SelectionWindow,
    config: AnalysisConfig,
) -> FrameSelection:
    window_start, frame_count = (
        (selection_window.start_frame, selection_window.frame_count)
        if selection_window.frame_count > 0
        else (0, reference.effective_num_frames())
    )
    if frame_count <= 0:
        raise SelectionError("reference source trims leave no selectable frames", 0, 0)
    expected_metric_start = analysis_clip.trim.trim_start_frames + window_start
    if (
        metrics.metadata.metric_source_start != expected_metric_start
        or metrics.metadata.metric_source_end_exclusive != expected_metric_start + frame_count
        or len(metrics.luminance) != metrics.metadata.frame_count
        or len(metrics.motion) != metrics.metadata.frame_count
    ):
        raise MetricsCalculationError(
            "Analysis metrics do not match the requested selection window"
        )
    source_offset = _source_offset_for_reference_window(reference, window_start)
    selection = select_frames(
        metrics=metrics,
        config=_config_for_selection_window(
            config=config,
            reference=reference,
            window_start=window_start,
            frame_count=frame_count,
        ),
    )
    return FrameSelection(
        frames=[frame + window_start for frame in selection.frames],
        seed=selection.seed,
        breakdown=selection_breakdown_with_source_offset(
            selection.breakdown,
            source_offset=source_offset,
        ),
        selection_details=selection_details_with_source_offset(
            dict(selection.selection_details),
            source_offset=source_offset,
            source_fps=reference.effective_fps,
        ),
    )


def _config_for_selection_window(
    *,
    config: AnalysisConfig,
    reference: ClipState,
    window_start: int,
    frame_count: int,
) -> AnalysisConfig:
    source_start = reference.trim.trim_start_frames + window_start
    source_end = source_start + frame_count
    local_user_frames = [
        frame - source_start for frame in config.user_frames if source_start <= frame < source_end
    ]
    return config.model_copy(
        update={
            "user_frames": local_user_frames,
        }
    )


def selection_label_for_frame(frame: int, breakdown: SelectionBreakdown | None) -> str | None:
    if breakdown is None:
        return None
    if frame in breakdown.user:
        return "User"
    if frame in breakdown.quantile_dark:
        return "Dark"
    if frame in breakdown.quantile_bright:
        return "Bright"
    if frame in breakdown.motion:
        return "Motion"
    if frame in breakdown.random:
        return "Random"
    return None


def selection_detail_for_frame(
    frame: int,
    details_by_source_frame: dict[int, SelectionDetail] | None,
) -> SelectionDetail | None:
    if details_by_source_frame is None:
        return None
    return details_by_source_frame.get(frame)


def selection_breakdown_with_source_offset(
    breakdown: SelectionBreakdown,
    *,
    source_offset: int,
) -> SelectionBreakdown:
    return SelectionBreakdown(
        user=[frame + source_offset for frame in breakdown.user],
        quantile_dark=[frame + source_offset for frame in breakdown.quantile_dark],
        quantile_bright=[frame + source_offset for frame in breakdown.quantile_bright],
        motion=[frame + source_offset for frame in breakdown.motion],
        random=[frame + source_offset for frame in breakdown.random],
    )


def selection_details_with_source_offset(
    details_by_frame: SelectionDetailsByFrame,
    *,
    source_offset: int,
    source_fps: Fraction,
) -> SelectionDetailsByFrame:
    shifted_details: SelectionDetailsByFrame = {}
    for frame_index, detail in details_by_frame.items():
        source_frame = frame_index + source_offset
        shifted_details[source_frame] = SelectionDetail(
            frame_index=source_frame,
            label=detail.label,
            source=detail.source,
            timecode=selection_timecode_for_frame(source_frame, source_fps),
            score=detail.score,
            clip_role=detail.clip_role,
            notes=detail.notes,
        )
    return shifted_details


def selection_timecode_for_frame(frame_index: int, fps: Fraction) -> str | None:
    if fps <= 0:
        return None
    total_milliseconds = round((Fraction(frame_index, 1) * 1000) / fps)
    total_seconds, milliseconds = divmod(total_milliseconds, 1000)
    total_minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def to_overlay_selection_detail(detail: SelectionDetail) -> OverlaySelectionDetail:
    from frame_compare.render.types import OverlaySelectionDetail

    return OverlaySelectionDetail(
        frame_index=detail.frame_index,
        label=detail.label,
        source=detail.source,
        timecode=detail.timecode,
        score=detail.score,
        clip_role=detail.clip_role,
        notes=detail.notes,
    )


def source_frames_for_reference_base_domain(
    *, reference: ClipState, selected_frames: list[int]
) -> list[int]:
    return [reference.trim.trim_start_frames + frame for frame in selected_frames]


def map_aligned_to_source_frame(*, clip: ClipState, aligned_frame: int) -> int:
    source_frame = clip.trim.trim_start_frames + aligned_frame
    trim_start = clip.trim.trim_start_frames
    trim_end = (
        clip.trim.trim_end_frame_inclusive
        if clip.trim.trim_end_frame_inclusive is not None
        else clip.probe.num_frames - 1
    )
    if source_frame < trim_start:
        raise AudioAlignmentError(
            f"Aligned frame {aligned_frame} is before trimmed domain for {clip.path.name}."
        )
    if source_frame > trim_end:
        raise AudioAlignmentError(
            f"Aligned frame {aligned_frame} exceeds trimmed domain for {clip.path.name}."
        )
    return source_frame
