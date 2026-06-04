"""Concrete orchestration phase work.

The execution module owns phase ordering and timing. This module owns the
phase bodies and shared translation helpers used by preparation and execution.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import structlog

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
from frame_compare.config.errors import ConfigValidationError
from frame_compare.config.schema import AnalysisConfig, ConfigSchema, OverlayMode
from frame_compare.errors import JSONValue
from frame_compare.orchestration.context import (
    ClipAlignmentState,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.types import (
    AlignPhaseOutput,
    AnalyzePhaseOutput,
    ConfirmSlowpicsUploadPhaseOutput,
    DoviPhaseOutput,
    FramePlanPhaseOutput,
    MetadataPhaseOutput,
    MetadataPrefetch,
    PostReportCleanupPhaseOutput,
    PublishPhaseOutput,
    RenderArtifacts,
    RenderPhaseOutput,
    ReportPhaseOutput,
    SlowpicsUploadConfirmationFn,
    SlowpicsUploadConfirmationRequest,
)
from frame_compare.render.backend.ffmpeg import FFmpegRunner
from frame_compare.services.alignment import (
    align_clips,
    calculate_alignment_trims,
    format_rejected_alignment_warning,
)
from frame_compare.services.errors import AudioAlignmentError, SlowpicsError
from frame_compare.services.metadata import resolve_metadata
from frame_compare.services.publishers import publish_to_slowpics
from frame_compare.services.report.display import (
    SourceFrameSelectionDetail,
    frame_detail_for_source_frame,
)
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    FrameDetail,
    ReportData,
    clip_info_from_state,
)
from frame_compare.services.slowpics_post_upload import (
    SlowpicsPostUploadRequest,
    run_slowpics_post_upload_actions,
)
from frame_compare.services.slowpics_upload_plan import (
    SlowpicsUploadClip,
    build_slowpics_upload_plan,
)
from frame_compare.services.types import AlignmentConfig, MetadataConfig, TmdbMetadata
from frame_compare.utils.cache_errors import CacheCorruptionError, CacheVersionMismatchError
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.props import range_label_from_props

log = structlog.get_logger()

REPORT_CONFIRMATION_UNAVAILABLE_WARNING = (
    "slow.pics upload skipped because report confirmation was unavailable"
)

if TYPE_CHECKING:
    from frame_compare.render.types import (
        OverlayDiagnosticMetadata,
        OverlayDolbyVisionMetadata,
        OverlayFrameMeasurement,
        OverlaySelectionDetail,
    )
    from frame_compare.vs.loader import VSLoader


def build_metadata_config(config: ConfigSchema) -> MetadataConfig:
    """Build metadata service config from run config."""
    return MetadataConfig(
        api_key=config.tmdb.api_key,
        unattended=config.tmdb.unattended,
        timeout_seconds=config.tmdb.timeout_seconds,
        year_tolerance=config.tmdb.year_tolerance,
        category_preference=config.tmdb.category_preference,
    )


async def resolve_run_metadata(
    *,
    filenames: list[str],
    config: ConfigSchema,
    client: httpx.AsyncClient,
) -> TmdbMetadata | None:
    return await resolve_metadata(
        filenames=filenames,
        config=build_metadata_config(config),
        client=client,
    )


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
        selection_details_by_source_frame=_initial_selection_details_by_source_frame(
            user_source_frames=user_frames,
            random_source_frames=random_source_frames,
            fps=ctx.reference.effective_fps,
        ),
        warnings=warnings,
    )


def _initial_selection_details_by_source_frame(
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
            timecode=_selection_timecode_for_frame(frame, fps),
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
                timecode=_selection_timecode_for_frame(frame, fps),
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


def _generated_frame_count(config: AnalysisConfig) -> int:
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
    selection_domain = ctx.analysis_selection_domain
    fingerprint = cache_io.compute_cache_key(
        input_videos,
        ctx.config.analysis,
        selection_domain=selection_domain,
    )
    cache_result = cache_io.load_cached_metrics(workspace.cache_dir, fingerprint, clips=[])
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
            config=ctx.config.analysis,
            cache_dir=workspace.cache_dir,
            reporter=ctx.reporter,
            vs_loader=vs_loader,
            selection_domain=selection_domain,
            effective_fps=ctx.reference.effective_fps,
        )
    selection = _select_frames_for_selection_domain(
        metrics=metrics,
        reference=ctx.reference,
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
    selection_window: SelectionWindow,
    config: AnalysisConfig,
) -> FrameSelection:
    window_start, frame_count = (
        (selection_window.start_frame, selection_window.frame_count)
        if selection_window.frame_count > 0
        else (0, reference.effective_num_frames())
    )
    if (
        reference.trim.trim_start_frames == 0
        and reference.trim.trim_end_frame_inclusive is None
        and frame_count == reference.effective_num_frames()
        and window_start == 0
    ):
        return select_frames(
            metrics=metrics,
            config=_config_for_selection_window(
                config=config,
                reference=reference,
                window_start=window_start,
                frame_count=frame_count,
            ),
        )

    if frame_count <= 0:
        raise SelectionError("reference source trims leave no selectable frames", 0, 0)

    trimmed_metrics = _trimmed_metrics_for_overlap(
        metrics=metrics,
        trim_start_frame=reference.trim.trim_start_frames + window_start,
        frame_count=frame_count,
    )
    selection = select_frames(
        metrics=trimmed_metrics,
        config=_config_for_selection_window(
            config=config,
            reference=reference,
            window_start=window_start,
            frame_count=frame_count,
        ),
    )
    source_offset = _source_offset_for_reference_window(reference, window_start)
    return FrameSelection(
        frames=[frame + window_start for frame in selection.frames],
        seed=selection.seed,
        breakdown=_selection_breakdown_with_source_offset(
            selection.breakdown,
            source_offset=source_offset,
        ),
        selection_details=_selection_details_with_source_offset(
            dict(selection.selection_details),
            source_offset=source_offset,
            fps=trimmed_metrics.metadata.fps,
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


def _selection_detail_for_frame(
    frame: int,
    details_by_source_frame: dict[int, SelectionDetail] | None,
) -> SelectionDetail | None:
    if details_by_source_frame is None:
        return None
    return details_by_source_frame.get(frame)


def _report_selection_detail(detail: SelectionDetail | None) -> SourceFrameSelectionDetail | None:
    if detail is None:
        return None
    return SourceFrameSelectionDetail(
        label=detail.label,
        timecode=detail.timecode,
        notes=detail.notes,
    )


def _report_frame_details_for_frames(ctx: RunContext, *, frames: list[int]) -> list[FrameDetail]:
    if ctx.selection_breakdown is None and ctx.selection_details_by_source_frame is None:
        return []

    frame_details: list[FrameDetail] = []
    for aligned_frame in frames:
        source_frame = _map_aligned_to_source_frame(
            clip=ctx.reference,
            aligned_frame=aligned_frame,
        )
        selection_detail = _selection_detail_for_frame(
            source_frame,
            ctx.selection_details_by_source_frame,
        )
        selection_label = (
            selection_detail.label
            if selection_detail is not None
            else selection_label_for_frame(source_frame, ctx.selection_breakdown)
        )
        frame_details.append(
            frame_detail_for_source_frame(
                source_frame=source_frame,
                selection_detail=_report_selection_detail(selection_detail),
                selection_label=selection_label,
            )
        )
    return frame_details


def _selection_breakdown_with_source_offset(
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


def _selection_details_with_source_offset(
    details_by_frame: SelectionDetailsByFrame,
    *,
    source_offset: int,
    fps: Fraction,
) -> SelectionDetailsByFrame:
    shifted_details: SelectionDetailsByFrame = {}
    for frame_index, detail in details_by_frame.items():
        source_frame = frame_index + source_offset
        shifted_details[source_frame] = SelectionDetail(
            frame_index=source_frame,
            label=detail.label,
            source=detail.source,
            timecode=_selection_timecode_for_frame(source_frame, fps),
            score=detail.score,
            clip_role=detail.clip_role,
            notes=detail.notes,
        )
    return shifted_details


def _selection_timecode_for_frame(frame_index: int, fps: Fraction) -> str | None:
    if fps <= 0:
        return None
    total_milliseconds = round((Fraction(frame_index, 1) * 1000) / fps)
    total_seconds, milliseconds = divmod(total_milliseconds, 1000)
    total_minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"


def _to_overlay_selection_detail(detail: SelectionDetail) -> OverlaySelectionDetail:
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


def _normalize_preserved_prop_key(key: str) -> str:
    return key.lstrip("_").lower()


def _coerce_float(value: str | int | float) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_int(value: str | int | float) -> int | None:
    number = _coerce_float(value)
    if number is None:
        return None
    return int(round(number))


def _color_range_from_preserved_props(
    preserved_props: dict[str, str | int | float],
) -> str | None:
    normalized_props: dict[str, int] = {}
    for key, value in preserved_props.items():
        normalized = _normalize_preserved_prop_key(key)
        if normalized not in {"range", "colorrange"}:
            continue
        coerced = _coerce_int(value)
        if coerced is not None:
            if normalized == "range":
                normalized_props["_Range"] = coerced
            else:
                normalized_props["_ColorRange"] = coerced
    return range_label_from_props(normalized_props)


def _dolby_vision_metadata_from_preserved_props(
    preserved_props: dict[str, str | int | float],
) -> OverlayDolbyVisionMetadata | None:
    from frame_compare.render.types import OverlayDolbyVisionMetadata

    rpu_present = False
    block_index: int | None = None
    block_total: int | None = None
    target_nits: float | None = None
    l2_target_nits: float | None = None
    l1_average: float | None = None
    l1_maximum: float | None = None
    l5_left: int | None = None
    l5_right: int | None = None
    l5_top: int | None = None
    l5_bottom: int | None = None
    l6_max_cll: float | None = None
    l6_max_fall: float | None = None

    for key, value in preserved_props.items():
        normalized = _normalize_preserved_prop_key(key)
        if normalized == "dolbyvisionrpu":
            rpu_present = True
            continue
        if not any(
            token in normalized for token in ("dolby", "dovi", "rpu", "l1", "l2", "l5", "l6")
        ):
            continue
        if "l2" in normalized and "target" in normalized:
            if l2_target_nits is None:
                l2_target_nits = _coerce_float(value)
            continue
        if "l1" in normalized and any(token in normalized for token in ("avg", "average", "mean")):
            if l1_average is None:
                l1_average = _coerce_float(value)
            continue
        if "l1" in normalized and "max" in normalized:
            if l1_maximum is None:
                l1_maximum = _coerce_float(value)
            continue
        if "l5" in normalized:
            coerced = _coerce_int(value)
            if coerced is None or coerced < 0:
                continue
            if "left" in normalized and l5_left is None:
                l5_left = coerced
            elif "right" in normalized and l5_right is None:
                l5_right = coerced
            elif "top" in normalized and l5_top is None:
                l5_top = coerced
            elif "bottom" in normalized and l5_bottom is None:
                l5_bottom = coerced
            continue
        if "l6" in normalized:
            if "cll" in normalized and l6_max_cll is None:
                l6_max_cll = _coerce_float(value)
            elif "fall" in normalized and l6_max_fall is None:
                l6_max_fall = _coerce_float(value)
            continue
        if "block" in normalized and "index" in normalized and block_index is None:
            block_index = _coerce_int(value)
            continue
        if (
            "block" in normalized
            and ("total" in normalized or "count" in normalized)
            and block_total is None
        ):
            block_total = _coerce_int(value)
            continue
        if (
            "target" in normalized
            and any(token in normalized for token in ("nit", "pq", "brightness"))
            and target_nits is None
        ):
            target_nits = _coerce_float(value)

    has_metadata = rpu_present or any(
        value is not None
        for value in (
            block_index,
            block_total,
            target_nits,
            l2_target_nits,
            l1_average,
            l1_maximum,
            l5_left,
            l5_right,
            l5_top,
            l5_bottom,
            l6_max_cll,
            l6_max_fall,
        )
    )
    if not has_metadata:
        return None
    return OverlayDolbyVisionMetadata(
        rpu_present=rpu_present,
        block_index=block_index,
        block_total=block_total,
        target_nits=target_nits,
        l2_target_nits=l2_target_nits,
        l1_average=l1_average,
        l1_maximum=l1_maximum,
        l5_left=l5_left,
        l5_right=l5_right,
        l5_top=l5_top,
        l5_bottom=l5_bottom,
        l6_max_cll=l6_max_cll,
        l6_max_fall=l6_max_fall,
    )


def _score_measurement_for_selection(
    *,
    selection_detail: OverlaySelectionDetail | None,
    overlay_mode: OverlayMode,
    per_frame_nits_enabled: bool,
    target_nits: int,
) -> OverlayFrameMeasurement | None:
    from frame_compare.render.types import OverlayFrameMeasurement

    if (
        not per_frame_nits_enabled
        or overlay_mode != OverlayMode.DIAGNOSTIC
        or selection_detail is None
        or selection_detail.score is None
    ):
        return None
    score = float(selection_detail.score)
    if score != score:
        return None
    clamped_score = max(0.0, min(score, 1.0))
    measurement_nits = clamped_score * float(target_nits)
    category = selection_detail.label.strip() or None
    return OverlayFrameMeasurement(
        avg_nits=measurement_nits,
        max_nits=measurement_nits,
        category=category,
    )


def _overlay_diagnostic_metadata_for_frame(
    *,
    probe: ClipProbeSnapshot,
    selection_detail: OverlaySelectionDetail | None,
    overlay_mode: OverlayMode,
    per_frame_nits_enabled: bool,
    target_nits: int,
) -> OverlayDiagnosticMetadata | None:
    from frame_compare.render.types import OverlayDiagnosticMetadata

    hdr_metadata = probe.hdr_metadata
    measurement = _score_measurement_for_selection(
        selection_detail=selection_detail,
        overlay_mode=overlay_mode,
        per_frame_nits_enabled=per_frame_nits_enabled,
        target_nits=target_nits,
    )
    color_range = _color_range_from_preserved_props(probe.preserved_frame_props)
    dolby_vision = _dolby_vision_metadata_from_preserved_props(probe.preserved_frame_props)
    mastering_display = hdr_metadata.mastering_display if hdr_metadata is not None else None
    max_cll = hdr_metadata.max_cll if hdr_metadata is not None else None
    max_fall = hdr_metadata.max_fall if hdr_metadata is not None else None
    if (
        mastering_display is None
        and max_cll is None
        and max_fall is None
        and color_range is None
        and dolby_vision is None
        and measurement is None
    ):
        return None
    return OverlayDiagnosticMetadata(
        mastering_display=mastering_display,
        max_cll=max_cll,
        max_fall=max_fall,
        color_range=color_range,
        dolby_vision=dolby_vision,
        measurement=measurement,
    )


def run_align_phase(ctx: RunContext, *, selected_frames: list[int]) -> AlignPhaseOutput:
    if not ctx.comparisons:
        return AlignPhaseOutput(
            reference=ctx.reference,
            comparisons=list(ctx.comparisons),
            selected_frames=list(selected_frames),
        )
    alignment_config = AlignmentConfig(
        enable=ctx.config.audio_alignment.enable,
        sample_rate=ctx.config.audio_alignment.sample_rate,
        max_offset_seconds=ctx.config.audio_alignment.max_offset_seconds,
        use_vspreview=ctx.config.audio_alignment.use_vspreview,
        force_interactive=ctx.config.audio_alignment.force_interactive,
        cache_results=ctx.config.audio_alignment.cache_results,
        correlation_mode=ctx.config.audio_alignment.correlation_mode,
        preprocessing_mode=ctx.config.audio_alignment.preprocessing_mode,
        channel_strategy=ctx.config.audio_alignment.channel_strategy,
        confidence_threshold=ctx.config.audio_alignment.confidence_threshold,
        ambiguity_peak_ratio=ctx.config.audio_alignment.ambiguity_peak_ratio,
        window_length_seconds=ctx.config.audio_alignment.window_length_seconds,
        window_stride_seconds=ctx.config.audio_alignment.window_stride_seconds,
        minimum_valid_windows=ctx.config.audio_alignment.minimum_valid_windows,
        consensus_minimum_ratio=ctx.config.audio_alignment.consensus_minimum_ratio,
        refinement_mode=ctx.config.audio_alignment.refinement_mode,
        refinement_sample_rate=ctx.config.audio_alignment.refinement_sample_rate,
        reference_stream=ctx.config.audio_alignment.reference_stream,
        comparison_streams=dict(ctx.config.audio_alignment.comparison_streams),
        no_color=ctx.no_color,
    )
    results = align_clips(
        reference=ctx.reference.path,
        comparisons=[comp.path for comp in ctx.comparisons],
        config=alignment_config,
        cache_dir=ctx.workspace.generated_dir,
        progress=ctx.reporter,
        reference_fps=ctx.reference.effective_fps,
        frame_props_by_stem={
            ctx.reference.path.stem: dict(ctx.reference.probe.preserved_frame_props),
            **{comp.path.stem: dict(comp.probe.preserved_frame_props) for comp in ctx.comparisons},
        },
    )

    updated_comparisons: list[ClipState] = []
    warnings = [
        format_rejected_alignment_warning(result) for result in results if not result.applied
    ]
    for comparison, result in zip(ctx.comparisons, results, strict=True):
        alignment = None
        if result.applied:
            frame_offset = result.frame_offset
            if frame_offset is None:
                raise AudioAlignmentError("Applied alignment result is missing frame offset.")
            alignment = ClipAlignmentState(
                reference_stem=Path(result.reference_clip).stem,
                comparison_stem=Path(result.comparison_clip).stem,
                relative_offset_frames=frame_offset,
                source=result.source,
            )
        updated_comparisons.append(
            replace(
                comparison,
                alignment=alignment,
            )
        )
    ref_trim, comp_trims = calculate_alignment_trims(
        ref_num_frames=ctx.reference.effective_num_frames(),
        comp_offsets=[
            comp.alignment.relative_offset_frames if comp.alignment is not None else None
            for comp in updated_comparisons
        ],
        comp_num_frames=[comp.effective_num_frames() for comp in updated_comparisons],
    )
    reference = _compose_alignment_trim(ctx.reference, ref_trim)
    comparisons = [
        _compose_alignment_trim(comp, comp_trim)
        for comp, comp_trim in zip(updated_comparisons, comp_trims, strict=True)
    ]
    selection_source_window = _selection_source_window_for_alignment(ctx)
    selected_source_frames = _source_frames_for_reference_base_domain(
        reference=ctx.reference,
        selected_frames=selected_frames,
    )
    normalized_selection = _normalize_selected_frames_for_trimmed_domain(
        selected_frames=selected_source_frames,
        user_source_frames=set(ctx.config.analysis.user_frames),
        reference=reference,
        comparisons=comparisons,
        selection_source_window=selection_source_window,
        generated_requested_count=_generated_frame_count(ctx.config.analysis),
        seed=ctx.config.analysis.random_seed,
        allow_fallback=_generated_frame_count(ctx.config.analysis) > 0,
    )
    normalized_selected_frames = normalized_selection.selected_frames
    if normalized_selection.dropped_user_source_frames:
        warnings.append(
            "frame selection: dropped user frame(s) outside aligned renderable range: "
            + ", ".join(str(frame) for frame in normalized_selection.dropped_user_source_frames)
        )
    selection_breakdown: SelectionBreakdown | None = None
    selection_details_by_source_frame: SelectionDetailsByFrame | None = None
    if normalized_selection.used_fallback_frame_plan and ctx.analysis_metrics is not None:
        configured_user_source_frames = set(ctx.config.analysis.user_frames)
        normalized_user_frames = [
            frame
            for frame in normalized_selected_frames
            if frame + reference.trim.trim_start_frames in configured_user_source_frames
        ]
        trimmed_selection = _reselect_frames_for_trimmed_overlap(
            metrics=ctx.analysis_metrics,
            reference=reference,
            comparisons=comparisons,
            selection_source_window=selection_source_window,
            config=ctx.config.analysis,
            accepted_user_source_frames={
                frame + reference.trim.trim_start_frames for frame in normalized_user_frames
            },
        )
        if trimmed_selection is not None:
            normalized_selected_frames = sorted(
                {*normalized_user_frames, *trimmed_selection.selected_frames}
            )
            selection_breakdown = trimmed_selection.selection_breakdown
            if normalized_user_frames:
                selection_breakdown = SelectionBreakdown(
                    user=[
                        frame + reference.trim.trim_start_frames for frame in normalized_user_frames
                    ],
                    quantile_dark=selection_breakdown.quantile_dark,
                    quantile_bright=selection_breakdown.quantile_bright,
                    motion=selection_breakdown.motion,
                    random=selection_breakdown.random,
                )
            selection_details_by_source_frame = trimmed_selection.selection_details_by_source_frame
            if normalized_user_frames:
                user_selection_details = {
                    frame + reference.trim.trim_start_frames: SelectionDetail(
                        frame_index=frame + reference.trim.trim_start_frames,
                        label="User",
                        source="frame_plan",
                        timecode=_selection_timecode_for_frame(
                            frame + reference.trim.trim_start_frames,
                            reference.effective_fps,
                        ),
                        clip_role="frame_plan",
                        notes="user",
                    )
                    for frame in normalized_user_frames
                }
                selection_details_by_source_frame = {
                    **selection_details_by_source_frame,
                    **user_selection_details,
                }
    elif normalized_selection.used_fallback_frame_plan:
        selection_breakdown = SelectionBreakdown(
            user=normalized_selection.user_source_frames,
            random=normalized_selection.generated_source_frames,
        )
        selection_details_by_source_frame = _initial_selection_details_by_source_frame(
            user_source_frames=normalized_selection.user_source_frames,
            random_source_frames=normalized_selection.generated_source_frames,
            fps=reference.effective_fps,
        )
    return AlignPhaseOutput(
        reference=reference,
        comparisons=comparisons,
        selected_frames=normalized_selected_frames,
        selection_breakdown=selection_breakdown,
        selection_details_by_source_frame=selection_details_by_source_frame,
        warnings=warnings,
    )


def _source_frames_for_reference_base_domain(
    *, reference: ClipState, selected_frames: list[int]
) -> list[int]:
    return [reference.trim.trim_start_frames + frame for frame in selected_frames]


def _selection_source_window_for_alignment(ctx: RunContext) -> tuple[int, int] | None:
    if ctx.selection_window.frame_count <= 0:
        return None
    source_start = ctx.reference.trim.trim_start_frames + ctx.selection_window.start_frame
    source_end = ctx.reference.trim.trim_start_frames + ctx.selection_window.end_frame_exclusive
    return source_start, source_end


def _compose_alignment_trim(clip: ClipState, alignment_trim: tuple[int, int | None]) -> ClipState:
    base_end = (
        clip.trim.trim_end_frame_inclusive
        if clip.trim.trim_end_frame_inclusive is not None
        else clip.probe.num_frames - 1
    )
    alignment_end = (
        clip.trim.trim_start_frames + alignment_trim[1]
        if alignment_trim[1] is not None
        else base_end
    )
    return clip.with_trim(
        trim_start_frames=clip.trim.trim_start_frames + alignment_trim[0],
        trim_end_frame_inclusive=min(base_end, alignment_end),
    )


def run_render_phase(
    ctx: RunContext,
    *,
    frames: list[int],
    runner: FFmpegRunner,
) -> RenderPhaseOutput:
    from frame_compare.render.batch.orchestrator import render_screenshots_from_batch
    from frame_compare.render.geometry import GeometryRect
    from frame_compare.render.types import (
        BatchRenderOptions,
        ScreenshotBatchRequest,
    )

    clips_state = [ctx.reference, *ctx.comparisons]
    output_dir = ctx.workspace.screenshots_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    overlay_mode = ctx.config.screenshots.overlay_mode
    reference_source_frames = [
        _map_aligned_to_source_frame(clip=ctx.reference, aligned_frame=aligned_frame)
        for aligned_frame in frames
    ]
    selection_details: list[OverlaySelectionDetail | None] = [
        _to_overlay_selection_detail(detail)
        if (
            detail := _selection_detail_for_frame(
                source_frame,
                ctx.selection_details_by_source_frame,
            )
        )
        is not None
        else None
        for source_frame in reference_source_frames
    ]
    selection_labels = [
        detail.label
        if detail is not None
        else selection_label_for_frame(source_frame, ctx.selection_breakdown)
        for source_frame, detail in zip(reference_source_frames, selection_details, strict=True)
    ]

    batch_requests: list[ScreenshotBatchRequest] = []
    for clip in clips_state:
        source_frames = [
            _map_aligned_to_source_frame(clip=clip, aligned_frame=aligned_frame)
            for aligned_frame in frames
        ]
        diagnostic_metadata = [
            _overlay_diagnostic_metadata_for_frame(
                probe=clip.probe,
                selection_detail=detail,
                overlay_mode=overlay_mode,
                per_frame_nits_enabled=ctx.config.diagnostics.per_frame_nits,
                target_nits=ctx.config.color.target_nits,
            )
            for detail in selection_details
        ]
        batch_requests.append(
            ScreenshotBatchRequest(
                clip_path=clip.path,
                label=clip.label,
                filename_label=clip.path.stem,
                source_frames=source_frames,
                display_frames=frames,
                selection_labels=selection_labels,
                selection_details=selection_details,
                diagnostic_metadata=diagnostic_metadata,
                active_rect=(
                    GeometryRect(
                        clip.active_rect.x,
                        clip.active_rect.y,
                        clip.active_rect.width,
                        clip.active_rect.height,
                    )
                    if clip.active_rect is not None
                    else None
                ),
                probe_width=clip.probe.width,
                probe_height=clip.probe.height,
                probe_num_frames=clip.probe.num_frames,
                probe_is_hdr=clip.probe.is_hdr,
            )
        )

    render_warnings: list[str] = []
    rendered = render_screenshots_from_batch(
        batch_requests=batch_requests,
        output_dir=output_dir,
        config=ctx.config,
        options=BatchRenderOptions(
            overlay_mode=overlay_mode,
            ffmpeg_runner=runner,
            reporter=ctx.reporter,
            warnings=render_warnings,
        ),
    )

    return RenderPhaseOutput(
        render=RenderArtifacts(
            screenshots_by_label=rendered,
            screenshot_dir=output_dir,
            warnings=render_warnings,
        )
    )


async def run_metadata_phase(
    ctx: RunContext,
    *,
    client: httpx.AsyncClient | None,
    metadata_prefetch: MetadataPrefetch,
) -> MetadataPhaseOutput:
    if metadata_prefetch.was_attempted:
        return MetadataPhaseOutput(resolved_metadata=metadata_prefetch.metadata)

    if client is None or not ctx.config.tmdb.enabled:
        return MetadataPhaseOutput(resolved_metadata=None)
    metadata = await resolve_run_metadata(
        filenames=[ctx.reference.path.name],
        config=ctx.config,
        client=client,
    )
    return MetadataPhaseOutput(resolved_metadata=metadata)


def record_dovi_not_implemented_warning(_ctx: RunContext) -> DoviPhaseOutput:
    return DoviPhaseOutput(
        warning="dovi: DOVI processing is not implemented yet; continuing without Dolby Vision extraction."
    )


async def run_publish_phase(
    ctx: RunContext,
    *,
    client: httpx.AsyncClient | None,
    metadata: TmdbMetadata | None,
    render: RenderArtifacts | None = None,
    selected_frames: list[int] | None = None,
) -> PublishPhaseOutput:
    if client is None:
        return PublishPhaseOutput(slowpics_url=None)
    if render is None:
        raise SlowpicsError("No render artifacts available for slow.pics upload")
    if selected_frames is None:
        raise SlowpicsError("No selected frames available for slow.pics upload")

    upload_plan = build_slowpics_upload_plan(
        selected_frames=selected_frames,
        clips=_slowpics_upload_clips(ctx),
        screenshots_by_label=render.screenshots_by_label,
    )
    screenshot_dir = (
        render.screenshot_dir
        if render.screenshot_dir is not None
        else ctx.workspace.screenshots_dir
    )
    result = await publish_to_slowpics(
        screenshot_dir=screenshot_dir,
        config=ctx.config.slowpics,
        client=client,
        metadata=metadata,
        progress=ctx.reporter,
        upload_plan=upload_plan,
    )
    post_upload_actions = await run_slowpics_post_upload_actions(
        SlowpicsPostUploadRequest(
            workspace=ctx.workspace,
            config=ctx.config.slowpics,
            slowpics_url=result.url,
            metadata_title=metadata.title if metadata is not None else None,
            upload_title=screenshot_dir.name,
        )
    )
    return PublishPhaseOutput(
        slowpics_url=result.url,
        uploaded_file_paths=result.uploaded_file_paths,
        post_upload_actions=post_upload_actions,
    )


def run_confirm_slowpics_upload_phase(
    _ctx: RunContext,
    *,
    report_path: Path | None,
    report_succeeded: bool,
    confirm_slowpics_upload: SlowpicsUploadConfirmationFn | None,
) -> ConfirmSlowpicsUploadPhaseOutput:
    if not report_succeeded or report_path is None:
        return ConfirmSlowpicsUploadPhaseOutput(
            status="report_unavailable",
            warnings=[REPORT_CONFIRMATION_UNAVAILABLE_WARNING],
        )
    if confirm_slowpics_upload is None:
        validation_errors: list[dict[str, JSONValue]] = [
            {
                "type": "value_error",
                "loc": ["slowpics", "confirm_upload_after_report"],
                "msg": "Report-confirmed slow.pics upload requires a confirmation callback.",
                "input": True,
            }
        ]
        raise ConfigValidationError(
            validation_errors,
            message="Report-confirmed slow.pics upload requires a confirmation callback",
            hint=(
                "Provide RunDependencies.confirm_slowpics_upload, or disable "
                "slowpics.confirm_upload_after_report."
            ),
        )

    decision = confirm_slowpics_upload(SlowpicsUploadConfirmationRequest(report_path=report_path))
    return ConfirmSlowpicsUploadPhaseOutput(status=decision)


def _slowpics_upload_clips(ctx: RunContext) -> list[SlowpicsUploadClip]:
    clips = [ctx.reference, *ctx.comparisons]
    seen_labels: set[str] = set()
    upload_clips: list[SlowpicsUploadClip] = []
    for clip in clips:
        if clip.label in seen_labels:
            raise SlowpicsError(f"Duplicate clip label in slow.pics upload input: {clip.label!r}")
        seen_labels.add(clip.label)
        upload_clips.append(SlowpicsUploadClip(label=clip.label, image_name=clip.path.stem))
    return upload_clips


def run_report_phase(
    ctx: RunContext,
    *,
    frames: list[int],
    render: RenderArtifacts | None,
    metadata: TmdbMetadata | None,
    slowpics_url: str | None,
) -> ReportPhaseOutput:
    if render is None or not render.screenshots_by_label:
        return ReportPhaseOutput(report_path=None, report_succeeded=True)

    clips = [ctx.reference, *ctx.comparisons]
    clip_info = [
        clip_info_from_state(clip, render.screenshots_by_label[clip.label]) for clip in clips
    ]
    report_data = ReportData(
        clips=clip_info,
        frames=frames,
        metadata=metadata,
        slowpics_url=slowpics_url,
        frame_details=_report_frame_details_for_frames(ctx, frames=frames),
    )
    report_path = generate_report(report_data, ctx.config.report)
    return ReportPhaseOutput(report_path=report_path, report_succeeded=True)


def run_post_report_cleanup_phase(
    ctx: RunContext,
    *,
    uploaded_file_paths: tuple[Path, ...],
    report_succeeded: bool,
) -> PostReportCleanupPhaseOutput:
    if not _should_delete_uploaded_files_after_report(
        ctx,
        uploaded_file_paths=uploaded_file_paths,
        report_succeeded=report_succeeded,
    ):
        return PostReportCleanupPhaseOutput()

    warnings: list[str] = []
    deleted_count = 0
    for path in uploaded_file_paths:
        try:
            path.unlink()
            deleted_count += 1
        except OSError as exc:
            message = f"cleanup: failed to delete uploaded screenshot {path}: {exc}"
            warnings.append(message)
            log.warning(
                "slowpics_uploaded_file_delete_failed",
                path=str(path),
                error=str(exc),
            )

    if deleted_count:
        log.info("slowpics_uploaded_files_deleted", count=deleted_count)

    return PostReportCleanupPhaseOutput(warnings=warnings)


def _should_delete_uploaded_files_after_report(
    ctx: RunContext,
    *,
    uploaded_file_paths: tuple[Path, ...],
    report_succeeded: bool,
) -> bool:
    if not ctx.config.slowpics.delete_after_upload:
        return False
    if not uploaded_file_paths:
        return False
    if not ctx.config.report.enable:
        return True
    if not report_succeeded:
        return False
    return ctx.config.report.embed_images


@dataclass(frozen=True)
class _TrimmedOverlapSelection:
    selected_frames: list[int]
    selection_breakdown: SelectionBreakdown
    selection_details_by_source_frame: SelectionDetailsByFrame


@dataclass(frozen=True, slots=True)
class _NormalizedFrameSelection:
    selected_frames: list[int]
    used_fallback_frame_plan: bool
    dropped_user_source_frames: list[int]
    user_source_frames: list[int]
    generated_source_frames: list[int]


def _trimmed_metrics_for_overlap(
    *,
    metrics: FrameMetrics,
    trim_start_frame: int,
    frame_count: int,
) -> FrameMetrics:
    trim_end_frame = trim_start_frame + frame_count
    return FrameMetrics(
        luminance=metrics.luminance[trim_start_frame:trim_end_frame],
        motion=metrics.motion[trim_start_frame:trim_end_frame],
        metadata=replace(metrics.metadata, frame_count=frame_count),
    )


def _reselect_frames_for_trimmed_overlap(
    *,
    metrics: FrameMetrics,
    reference: ClipState,
    comparisons: list[ClipState],
    selection_source_window: tuple[int, int] | None,
    config: AnalysisConfig,
    accepted_user_source_frames: set[int],
) -> _TrimmedOverlapSelection | None:
    selectable_start, selectable_length = _selectable_aligned_source_window(
        reference=reference,
        comparisons=comparisons,
        selection_source_window=selection_source_window,
    )
    target_count = _generated_frame_count(config)
    if selectable_length <= 0 or target_count <= 0:
        return None
    if target_count > selectable_length:
        raise SelectionError(
            "insufficient generated candidates after alignment",
            requested=target_count,
            found=selectable_length,
        )
    trimmed_metrics = _trimmed_metrics_for_overlap(
        metrics=metrics,
        trim_start_frame=selectable_start,
        frame_count=selectable_length,
    )
    local_user_frames = sorted(
        frame - selectable_start
        for frame in accepted_user_source_frames
        if selectable_start <= frame < selectable_start + selectable_length
    )
    trimmed_selection = select_frames(
        metrics=trimmed_metrics,
        config=config.model_copy(
            update=_generated_selection_counts(
                config,
                local_user_frames=local_user_frames,
            )
        ),
    )
    local_user_frame_set = set(local_user_frames)
    return _TrimmedOverlapSelection(
        selected_frames=[
            frame + selectable_start - reference.trim.trim_start_frames
            for frame in trimmed_selection.frames
            if frame not in local_user_frame_set
        ],
        selection_breakdown=_selection_breakdown_with_source_offset(
            trimmed_selection.breakdown,
            source_offset=selectable_start,
        ),
        selection_details_by_source_frame=_selection_details_with_source_offset(
            dict(trimmed_selection.selection_details),
            source_offset=selectable_start,
            fps=trimmed_metrics.metadata.fps,
        ),
    )


def _generated_selection_counts(
    config: AnalysisConfig,
    *,
    local_user_frames: list[int],
) -> dict[str, int | list[int]]:
    return {
        "user_frames": local_user_frames,
        "dark_frame_count": config.dark_frame_count,
        "bright_frame_count": config.bright_frame_count,
        "motion_frame_count": config.motion_frame_count,
        "random_frame_count": config.random_frame_count,
    }


def _normalize_selected_frames_for_trimmed_domain(
    *,
    selected_frames: list[int],
    user_source_frames: set[int],
    reference: ClipState,
    comparisons: list[ClipState],
    selection_source_window: tuple[int, int] | None,
    generated_requested_count: int,
    seed: int,
    allow_fallback: bool = True,
) -> _NormalizedFrameSelection:
    selectable_start, selectable_length = _selectable_aligned_source_window(
        reference=reference,
        comparisons=comparisons,
        selection_source_window=selection_source_window,
    )
    if selectable_length <= 0:
        raise AudioAlignmentError("No overlapping frames remain after alignment.")

    selectable_end = selectable_start + selectable_length
    normalized_user_frames = sorted(
        {
            frame - reference.trim.trim_start_frames
            for frame in selected_frames
            if frame in user_source_frames and selectable_start <= frame < selectable_end
        }
    )
    normalized_generated_frames = sorted(
        {
            frame - reference.trim.trim_start_frames
            for frame in selected_frames
            if frame not in user_source_frames
            if selectable_start <= frame < selectable_end
        }
    )
    selected_user_source_frames = sorted(set(selected_frames) & user_source_frames)
    normalized_user_source_frames = {
        frame + reference.trim.trim_start_frames for frame in normalized_user_frames
    }
    dropped_user_source_frames = [
        frame for frame in selected_user_source_frames if frame not in normalized_user_source_frames
    ]
    generated_capacity = max(0, selectable_length - len(normalized_user_frames))
    if generated_requested_count > generated_capacity:
        raise SelectionError(
            "insufficient generated candidates after alignment",
            requested=generated_requested_count,
            found=generated_capacity,
        )
    generated_target_count = generated_requested_count
    normalized_frames = sorted(
        {*normalized_user_frames, *normalized_generated_frames[:generated_target_count]}
    )
    if generated_target_count <= 0:
        if normalized_frames:
            return _normalized_frame_selection_result(
                selected_frames=normalized_frames,
                used_fallback_frame_plan=False,
                dropped_user_source_frames=dropped_user_source_frames,
                reference_trim_start=reference.trim.trim_start_frames,
                user_source_frames=user_source_frames,
            )
        if not allow_fallback:
            raise AudioAlignmentError("No selected frames remain after alignment.")
        return _normalized_frame_selection_result(
            selected_frames=[],
            used_fallback_frame_plan=False,
            dropped_user_source_frames=dropped_user_source_frames,
            reference_trim_start=reference.trim.trim_start_frames,
            user_source_frames=user_source_frames,
        )
    if not allow_fallback:
        if not normalized_frames:
            raise AudioAlignmentError("No selected frames remain after alignment.")
        return _normalized_frame_selection_result(
            selected_frames=normalized_frames,
            used_fallback_frame_plan=False,
            dropped_user_source_frames=dropped_user_source_frames,
            reference_trim_start=reference.trim.trim_start_frames,
            user_source_frames=user_source_frames,
        )
    if len(normalized_generated_frames) < generated_target_count:
        fallback_frames = _fallback_generated_frames_for_aligned_window(
            selectable_length=selectable_length,
            selectable_start=selectable_start,
            reference_trim_start=reference.trim.trim_start_frames,
            seed=seed,
            count=generated_target_count,
            excluded_frames={
                frame + reference.trim.trim_start_frames for frame in normalized_user_frames
            },
        )
        return _normalized_frame_selection_result(
            selected_frames=sorted({*normalized_user_frames, *fallback_frames}),
            used_fallback_frame_plan=True,
            dropped_user_source_frames=dropped_user_source_frames,
            reference_trim_start=reference.trim.trim_start_frames,
            user_source_frames=user_source_frames,
        )
    return _normalized_frame_selection_result(
        selected_frames=normalized_frames,
        used_fallback_frame_plan=False,
        dropped_user_source_frames=dropped_user_source_frames,
        reference_trim_start=reference.trim.trim_start_frames,
        user_source_frames=user_source_frames,
    )


def _normalized_frame_selection_result(
    *,
    selected_frames: list[int],
    used_fallback_frame_plan: bool,
    dropped_user_source_frames: list[int],
    reference_trim_start: int,
    user_source_frames: set[int],
) -> _NormalizedFrameSelection:
    selected_source_frames = [frame + reference_trim_start for frame in selected_frames]
    final_user_source_frames = [
        frame for frame in selected_source_frames if frame in user_source_frames
    ]
    final_generated_source_frames = [
        frame for frame in selected_source_frames if frame not in user_source_frames
    ]
    return _NormalizedFrameSelection(
        selected_frames=selected_frames,
        used_fallback_frame_plan=used_fallback_frame_plan,
        dropped_user_source_frames=dropped_user_source_frames,
        user_source_frames=final_user_source_frames,
        generated_source_frames=final_generated_source_frames,
    )


def _fallback_generated_frames_for_aligned_window(
    *,
    selectable_length: int,
    selectable_start: int,
    reference_trim_start: int,
    seed: int,
    count: int,
    excluded_frames: set[int],
) -> list[int]:
    if count <= 0:
        return []
    fallback_offset = selectable_start - reference_trim_start
    sample_count = min(selectable_length, count + len(excluded_frames))
    while True:
        selected = [
            frame + fallback_offset
            for frame in create_frame_plan(
                num_frames=selectable_length,
                count=sample_count,
                seed=seed,
            ).frames
            if frame + selectable_start not in excluded_frames
        ]
        if len(selected) >= count or sample_count >= selectable_length:
            return selected[:count]
        sample_count = min(selectable_length, sample_count * 2)


def _selectable_aligned_source_window(
    *,
    reference: ClipState,
    comparisons: list[ClipState],
    selection_source_window: tuple[int, int] | None,
) -> tuple[int, int]:
    common_length = min(
        [
            reference.effective_num_frames(),
            *[comparison.effective_num_frames() for comparison in comparisons],
        ]
    )
    overlap_start = reference.trim.trim_start_frames
    overlap_end = overlap_start + common_length
    if selection_source_window is not None:
        selection_start, selection_end = selection_source_window
        overlap_start = max(overlap_start, selection_start)
        overlap_end = min(overlap_end, selection_end)
    return overlap_start, max(0, overlap_end - overlap_start)


def _map_aligned_to_source_frame(*, clip: ClipState, aligned_frame: int) -> int:
    source_frame = clip.trim.trim_start_frames + aligned_frame
    trim_end = (
        clip.trim.trim_end_frame_inclusive
        if clip.trim.trim_end_frame_inclusive is not None
        else clip.probe.num_frames - 1
    )
    if source_frame > trim_end:
        raise AudioAlignmentError(
            f"Aligned frame {aligned_frame} exceeds trimmed domain for {clip.path.name}."
        )
    return source_frame
