"""Audio-alignment phase execution and aligned-frame normalization."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import structlog

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.metrics import slice_frame_metrics
from frame_compare.analysis.selection import select_frames, select_random_frames
from frame_compare.analysis.types import (
    FrameMetrics,
    SelectionBreakdown,
    SelectionDetail,
    SelectionDetailsByFrame,
)
from frame_compare.config.schema import AnalysisConfig
from frame_compare.orchestration.context import ClipAlignmentState, ClipState, RunContext
from frame_compare.orchestration.execution_types import AlignPhaseOutput
from frame_compare.orchestration.full_window_retry import raise_if_full_window_retry_failed
from frame_compare.orchestration.phase_selection import (
    build_initial_selection_details_by_source_frame,
    generated_frame_count,
    selection_breakdown_with_source_offset,
    selection_details_with_source_offset,
    selection_timecode_for_frame,
    source_frames_for_reference_base_domain,
)
from frame_compare.services.alignment import (
    align_clips_from_request,
    calculate_alignment_trims,
    format_rejected_alignment_warning,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.release_identity import (
    common_content_identity,
    format_compact_identity,
    format_content_identity,
    format_release_descriptor,
)
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.types import (
    AlignmentCacheSettings,
    AlignmentClipIdentity,
    AlignmentClipRequest,
    AlignmentRequest,
    AlignmentSelectedReferenceRelationship,
)

log = structlog.get_logger()


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
        previous_offsets=ctx.config.audio_alignment.previous_offsets,
        no_color=ctx.no_color,
    )
    alignment_request = _alignment_request_from_context(ctx)
    log.debug(
        "alignment_request_prepared",
        comparisons=len(alignment_request.comparisons),
        generated_dir=str(alignment_request.generated_dir),
        previous_offsets=alignment_request.previous_offsets,
        shared_alignment_cache_dir=str(alignment_request.shared_alignment_cache_dir),
    )
    results = align_clips_from_request(
        alignment_request,
        alignment_config,
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
    for comparison_index, (comparison, result) in enumerate(
        zip(ctx.comparisons, results, strict=True), start=1
    ):
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
                stability=result.stability,
            )
            if result.stability is not None and result.stability.classification in {
                "possible_drift",
                "possible_discontinuity",
                "variable",
            }:
                detail = {
                    "possible_drift": "may drift across the source",
                    "possible_discontinuity": "varies across the source; possible edit discontinuity",
                    "variable": "varies across the source",
                }[result.stability.classification]
                position = result.stability.change_position_seconds
                if (
                    position is not None
                    and result.stability.classification == "possible_discontinuity"
                ):
                    seconds = round(position)
                    detail += (
                        f" near {seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
                    )
                warnings.append(
                    f"align: Comparison {comparison_index} alignment {detail}. "
                    "The applied constant offset was retained and should be verified."
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
    selected_source_frames = source_frames_for_reference_base_domain(
        reference=ctx.reference,
        selected_frames=selected_frames,
    )
    try:
        normalized_selection = _normalize_selected_frames_for_trimmed_domain(
            selected_frames=selected_source_frames,
            user_source_frames=set(ctx.config.analysis.user_frames),
            reference=reference,
            comparisons=comparisons,
            selection_source_window=selection_source_window,
            generated_requested_count=generated_frame_count(ctx.config.analysis),
            seed=ctx.config.analysis.random_seed,
            allow_fallback=(
                generated_frame_count(ctx.config.analysis) > 0
                and ctx.full_window_retry_override is None
            ),
            require_full_generated_selection=ctx.full_window_retry_override is not None,
        )
    except SelectionError as error:
        raise_if_full_window_retry_failed(ctx, error)
        raise
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
        try:
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
        except SelectionError as error:
            raise_if_full_window_retry_failed(ctx, error)
            raise
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
                        timecode=selection_timecode_for_frame(
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
        selection_details_by_source_frame = build_initial_selection_details_by_source_frame(
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


def _alignment_request_from_context(ctx: RunContext) -> AlignmentRequest:
    settings = AlignmentCacheSettings(
        sample_rate=ctx.config.audio_alignment.sample_rate,
        max_offset_seconds=ctx.config.audio_alignment.max_offset_seconds,
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
    )
    clips = [ctx.reference, *ctx.comparisons]
    identities = [clip.release_identity for clip in clips]
    common_content = (
        common_content_identity([identity for identity in identities if identity is not None])
        if all(identity is not None for identity in identities)
        else None
    )
    presentation_names = [
        _alignment_presentation_name(clip, common_content is not None) for clip in clips
    ]
    counts = {name: presentation_names.count(name) for name in presentation_names}
    presentation_names = [
        clip.path.name if not name or counts[name] > 1 else name
        for clip, name in zip(clips, presentation_names, strict=True)
    ]
    return AlignmentRequest(
        reference=_alignment_clip_request(
            ctx.reference,
            selected_audio_stream=ctx.config.audio_alignment.reference_stream,
            presentation_name=presentation_names[0],
        ),
        selected_reference_relationship=_selected_reference_relationship(ctx),
        comparisons=[
            _alignment_clip_request(
                comparison,
                selected_audio_stream=ctx.config.audio_alignment.comparison_streams.get(
                    comparison.path.stem
                ),
                presentation_name=presentation_names[index],
            )
            for index, comparison in enumerate(ctx.comparisons, start=1)
        ],
        previous_offsets=ctx.config.audio_alignment.previous_offsets,
        generated_dir=ctx.workspace.generated_dir,
        shared_alignment_cache_dir=ctx.workspace.shared_alignment_cache_dir,
        settings=settings,
        presentation_content=(
            None if common_content is None else format_content_identity(common_content)
        ),
    )


def _alignment_presentation_name(clip: ClipState, has_common_content: bool) -> str:
    if clip.label_is_explicit and clip.label.strip():
        return clip.label.strip()
    if clip.release_identity is None:
        return clip.path.name
    formatter = format_release_descriptor if has_common_content else format_compact_identity
    return formatter(clip.release_identity) or clip.path.name


def _selected_reference_relationship(ctx: RunContext) -> AlignmentSelectedReferenceRelationship:
    configured_reference = ctx.config.sources.reference
    if configured_reference is None or configured_reference == "auto":
        return "auto"
    return "configured"


def _alignment_clip_request(
    clip: ClipState, *, selected_audio_stream: int | None, presentation_name: str | None = None
) -> AlignmentClipRequest:
    fingerprint = clip.probe.fingerprint
    return AlignmentClipRequest(
        path=clip.path,
        label=clip.label,
        identity=AlignmentClipIdentity(
            path=fingerprint.path,
            size_bytes=fingerprint.size_bytes,
            mtime_ns=fingerprint.mtime_ns,
        ),
        trim_start_frames=clip.trim.trim_start_frames,
        trim_end_frame_inclusive=clip.trim.trim_end_frame_inclusive,
        effective_fps_num=clip.effective_fps.numerator,
        effective_fps_den=clip.effective_fps.denominator,
        selected_audio_stream=selected_audio_stream,
        preserved_frame_props=dict(clip.probe.preserved_frame_props),
        presentation_name=presentation_name,
    )


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
    target_count = generated_frame_count(config)
    if selectable_length <= 0 or target_count <= 0:
        return None
    if target_count > selectable_length:
        raise SelectionError(
            "insufficient generated candidates after alignment",
            requested=target_count,
            found=selectable_length,
        )
    metric_reference_start = (
        selection_source_window[0]
        if selection_source_window is not None
        else metrics.metadata.metric_source_start
    )
    trimmed_metrics = slice_frame_metrics(
        metrics=metrics,
        start_index=selectable_start - metric_reference_start,
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
        selection_breakdown=selection_breakdown_with_source_offset(
            trimmed_selection.breakdown,
            source_offset=selectable_start,
        ),
        selection_details_by_source_frame=selection_details_with_source_offset(
            dict(trimmed_selection.selection_details),
            source_offset=selectable_start,
            source_fps=reference.effective_fps,
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
    require_full_generated_selection: bool = False,
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
    if (
        require_full_generated_selection
        and len(normalized_generated_frames) < generated_target_count
    ):
        raise SelectionError(
            "insufficient generated frames after full-window retry alignment",
            requested=generated_target_count,
            found=len(normalized_generated_frames),
        )
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
    local_exclusions = {
        frame - selectable_start
        for frame in excluded_frames
        if selectable_start <= frame < selectable_start + selectable_length
    }
    return [
        frame + fallback_offset
        for frame in select_random_frames(
            selectable_length,
            count,
            seed,
            local_exclusions,
        )
    ]


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
