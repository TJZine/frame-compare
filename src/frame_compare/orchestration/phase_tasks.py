"""Concrete orchestration phase work.

The execution module owns phase ordering and timing. This module owns the
phase bodies and shared translation helpers used by preparation and execution.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

import frame_compare.analysis.cache_io as cache_io
from frame_compare.analysis.frame_plan import create_frame_plan
from frame_compare.analysis.metrics import calculate_metrics
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.types import SelectionBreakdown
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import (
    ClipAlignmentState,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.types import MetadataPrefetch, RenderArtifacts, RunArtifacts
from frame_compare.render.ffmpeg import FFmpegRunner
from frame_compare.services.alignment import align_clips, calculate_alignment_trims
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.metadata import resolve_metadata
from frame_compare.services.publishers import publish_to_slowpics
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import ReportData, clip_info_from_state
from frame_compare.services.types import AlignmentConfig, MetadataConfig, TmdbMetadata
from frame_compare.utils.types import WorkspacePaths

if TYPE_CHECKING:
    from frame_compare.vs.loader import VSLoader


def build_metadata_config(config: ConfigSchema) -> MetadataConfig:
    """Build metadata service config from run config."""
    return MetadataConfig(
        api_key=config.tmdb.api_key,
        unattended=config.tmdb.unattended,
        timeout_seconds=config.tmdb.timeout_seconds,
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


def select_initial_frame_plan(ctx: RunContext, *, selected_frames: list[int]) -> None:
    selected_frames.extend(
        create_frame_plan(
            num_frames=ctx.reference.effective_num_frames(),
            count=ctx.config.analysis.frame_count,
            seed=ctx.config.analysis.random_seed,
        ).frames
    )


def run_analyze_phase(
    ctx: RunContext,
    *,
    input_videos: list[Path],
    workspace: WorkspacePaths,
    selected_frames: list[int],
    artifacts: RunArtifacts,
    vs_loader: VSLoader | None = None,
) -> None:
    fingerprint = cache_io.compute_cache_key(input_videos, ctx.config.analysis)
    cache_result = cache_io.load_cached_metrics(workspace.cache_dir, fingerprint, clips=[])
    artifacts.metrics_cache_hit = cache_result.success and cache_result.metrics is not None
    metrics = calculate_metrics(
        video_paths=input_videos,
        config=ctx.config.analysis,
        cache_dir=workspace.cache_dir,
        reporter=ctx.reporter,
        vs_loader=vs_loader,
    )
    selection = select_frames(metrics=metrics, config=ctx.config.analysis)
    selected_frames[:] = selection.frames
    ctx.selection_breakdown = selection.breakdown


def selection_label_for_frame(frame: int, breakdown: SelectionBreakdown | None) -> str | None:
    if breakdown is None:
        return None
    if frame in breakdown.quantile_dark:
        return "Dark"
    if frame in breakdown.quantile_bright:
        return "Bright"
    if frame in breakdown.motion:
        return "Motion"
    if frame in breakdown.random:
        return "Random"
    return None


def run_align_phase(ctx: RunContext, *, selected_frames: list[int]) -> None:
    if not ctx.comparisons:
        return
    alignment_config = AlignmentConfig(
        enable=ctx.config.audio_alignment.enable,
        sample_rate=ctx.config.audio_alignment.sample_rate,
        max_offset_seconds=ctx.config.audio_alignment.max_offset_seconds,
        use_vspreview=ctx.config.audio_alignment.use_vspreview,
        force_interactive=ctx.config.audio_alignment.force_interactive,
        cache_results=ctx.config.audio_alignment.cache_results,
    )
    results = align_clips(
        reference=ctx.reference.path,
        comparisons=[comp.path for comp in ctx.comparisons],
        config=alignment_config,
        cache_dir=ctx.workspace.generated_dir,
        progress=ctx.reporter,
    )

    updated_comparisons: list[ClipState] = []
    for comparison, result in zip(ctx.comparisons, results, strict=True):
        updated_comparisons.append(
            replace(
                comparison,
                alignment=ClipAlignmentState(
                    reference_stem=Path(result.reference_clip).stem,
                    comparison_stem=Path(result.comparison_clip).stem,
                    relative_offset_frames=result.frame_offset,
                    source=result.source,
                ),
            )
        )
    ref_trim, comp_trims = calculate_alignment_trims(
        ref_num_frames=ctx.reference.probe.num_frames,
        comp_offsets=[
            comp.alignment.relative_offset_frames if comp.alignment is not None else None
            for comp in updated_comparisons
        ],
        comp_num_frames=[comp.probe.num_frames for comp in updated_comparisons],
    )
    ctx.reference = ctx.reference.with_trim(
        trim_start_frames=ref_trim[0],
        trim_end_frame_inclusive=ref_trim[1],
    )
    ctx.comparisons = [
        comp.with_trim(
            trim_start_frames=comp_trim[0],
            trim_end_frame_inclusive=comp_trim[1],
        )
        for comp, comp_trim in zip(updated_comparisons, comp_trims, strict=True)
    ]
    selected_frames[:] = _normalize_selected_frames_for_trimmed_domain(
        selected_frames=selected_frames,
        reference=ctx.reference,
        comparisons=ctx.comparisons,
        requested_count=ctx.config.analysis.frame_count,
        seed=ctx.config.analysis.random_seed,
    )


def run_render_phase(
    ctx: RunContext,
    *,
    frames: list[int],
    runner: FFmpegRunner,
    artifacts: RunArtifacts,
) -> None:
    from frame_compare.render.batch.orchestrator import render_screenshots_from_batch
    from frame_compare.render.types import ScreenshotBatchRequest

    clips_state = [ctx.reference, *ctx.comparisons]
    output_dir = ctx.workspace.screenshots_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    overlay_mode = ctx.config.screenshots.overlay_mode
    selection_labels = [
        selection_label_for_frame(
            _map_aligned_to_source_frame(clip=ctx.reference, aligned_frame=aligned_frame),
            ctx.selection_breakdown,
        )
        for aligned_frame in frames
    ]

    batch_requests: list[ScreenshotBatchRequest] = []
    for clip in clips_state:
        source_frames = [
            _map_aligned_to_source_frame(clip=clip, aligned_frame=aligned_frame)
            for aligned_frame in frames
        ]
        batch_requests.append(
            ScreenshotBatchRequest(
                clip_path=clip.path,
                label=clip.label,
                source_frames=source_frames,
                display_frames=frames,
                selection_labels=selection_labels,
                probe_width=clip.probe.width,
                probe_height=clip.probe.height,
                probe_num_frames=clip.probe.num_frames,
                probe_is_hdr=clip.probe.is_hdr,
            )
        )

    rendered = render_screenshots_from_batch(
        batch_requests=batch_requests,
        output_dir=output_dir,
        config=ctx.config,
        overlay_mode=overlay_mode,
        ffmpeg_runner=runner,
        reporter=ctx.reporter,
    )

    artifacts.render = RenderArtifacts(screenshots_by_label=rendered, screenshot_dir=output_dir)


async def run_metadata_phase(
    ctx: RunContext,
    *,
    client: httpx.AsyncClient | None,
    metadata_prefetch: MetadataPrefetch,
    artifacts: RunArtifacts,
) -> None:
    if metadata_prefetch.was_attempted:
        artifacts.resolved_metadata = metadata_prefetch.metadata
        return

    if client is None or not ctx.config.tmdb.enabled:
        artifacts.resolved_metadata = None
        return
    metadata = await resolve_run_metadata(
        filenames=[ctx.reference.path.name],
        config=ctx.config,
        client=client,
    )
    artifacts.resolved_metadata = metadata


def record_dovi_not_implemented_warning(_ctx: RunContext, *, warnings: list[str]) -> None:
    warnings.append(
        "dovi: DOVI processing is not implemented yet; continuing without Dolby Vision extraction."
    )


async def run_publish_phase(
    ctx: RunContext,
    *,
    client: httpx.AsyncClient | None,
    artifacts: RunArtifacts,
) -> None:
    if client is None:
        artifacts.slowpics_url = None
        return
    result = await publish_to_slowpics(
        screenshot_dir=ctx.workspace.screenshots_dir,
        config=ctx.config.slowpics,
        client=client,
        metadata=artifacts.resolved_metadata,
        progress=ctx.reporter,
    )
    artifacts.slowpics_url = result.url


def run_report_phase(
    ctx: RunContext,
    *,
    frames: list[int],
    artifacts: RunArtifacts,
) -> None:
    if artifacts.render is None or not artifacts.render.screenshots_by_label:
        artifacts.report_path = None
        return

    clips = [ctx.reference, *ctx.comparisons]
    clip_info = [
        clip_info_from_state(clip, artifacts.render.screenshots_by_label[clip.label])
        for clip in clips
    ]
    report_data = ReportData(
        clips=clip_info,
        frames=frames,
        metadata=artifacts.resolved_metadata,
        slowpics_url=artifacts.slowpics_url,
    )
    report_path = generate_report(report_data, ctx.config.report)
    artifacts.report_path = report_path


def _normalize_selected_frames_for_trimmed_domain(
    *,
    selected_frames: list[int],
    reference: ClipState,
    comparisons: list[ClipState],
    requested_count: int,
    seed: int,
) -> list[int]:
    common_length = min(
        [
            reference.effective_num_frames(),
            *[comparison.effective_num_frames() for comparison in comparisons],
        ]
    )
    if common_length <= 0:
        raise AudioAlignmentError("No overlapping frames remain after alignment.")

    reference_start = reference.trim.trim_start_frames
    reference_end_exclusive = reference_start + common_length
    normalized_frames = sorted(
        {
            frame - reference_start
            for frame in selected_frames
            if reference_start <= frame < reference_end_exclusive
        }
    )
    target_count = min(requested_count, common_length)
    if target_count <= 0:
        return []
    if len(normalized_frames) < target_count:
        return create_frame_plan(num_frames=common_length, count=target_count, seed=seed).frames
    return normalized_frames[:target_count]


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
