"""Metadata, publish, report, and cleanup phase work."""

from __future__ import annotations

from pathlib import Path

import httpx
import structlog

from frame_compare.analysis.types import SelectionDetail
from frame_compare.config.errors import ConfigValidationError
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import JSONValue
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution_types import (
    ConfirmSlowpicsUploadPhaseOutput,
    MetadataPhaseOutput,
    MetadataPrefetch,
    PostReportCleanupPhaseOutput,
    PublishPhaseOutput,
    RenderArtifacts,
    ReportPhaseOutput,
)
from frame_compare.orchestration.phase_selection import (
    map_aligned_to_source_frame,
    selection_detail_for_frame,
    selection_label_for_frame,
)
from frame_compare.orchestration.presentation import clip_role
from frame_compare.orchestration.slowpics_metadata import (
    resolve_slowpics_collection_metadata,
)
from frame_compare.orchestration.types import (
    SlowpicsUploadConfirmationFn,
    SlowpicsUploadConfirmationRequest,
)
from frame_compare.services.errors import SlowpicsError
from frame_compare.services.metadata import resolve_metadata
from frame_compare.services.metadata_parsing import parse_filename
from frame_compare.services.publishers import publish_to_slowpics
from frame_compare.services.release_identity import (
    format_compact_identity,
    format_micro_descriptor,
    format_release_descriptor,
    unique_presentation_names,
)
from frame_compare.services.report.display import (
    SourceFrameSelectionDetail,
    frame_detail_for_comparison_frame,
)
from frame_compare.services.report.entry import generate_report
from frame_compare.services.report.payload import (
    ClipInfo,
    FrameDetail,
    ReportClipDisplayInfo,
    ReportData,
    ReportImageInfo,
    ReportRenderingInfo,
    source_identity_from_fingerprint,
)
from frame_compare.services.slowpics_post_upload import (
    SlowpicsPostUploadRequest,
    run_slowpics_post_upload_actions,
)
from frame_compare.services.slowpics_upload_plan import (
    SlowpicsUploadClip,
    build_slowpics_upload_plan,
)
from frame_compare.services.types import MetadataConfig, TmdbMetadata

log = structlog.get_logger()

REPORT_CONFIRMATION_UNAVAILABLE_WARNING = (
    "slow.pics upload skipped because report confirmation was unavailable"
)

__all__ = [
    "REPORT_CONFIRMATION_UNAVAILABLE_WARNING",
    "build_metadata_config",
    "resolve_run_metadata",
    "run_confirm_slowpics_upload_phase",
    "run_metadata_phase",
    "run_post_report_cleanup_phase",
    "run_publish_phase",
    "run_report_phase",
]


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
    collection_resolution = resolve_slowpics_collection_metadata(
        config=ctx.config.slowpics,
        reference_path=ctx.reference.path,
        reference_label=ctx.reference.label,
        parsed_reference=parse_filename(
            ctx.reference.path.name,
            parser_priority=ctx.config.sources.label_parser,
            alternate_policy="fallback",
        ),
        resolved_tmdb=metadata,
    )
    for warning in collection_resolution.warnings:
        log.warning("slowpics_tmdb_association_mismatch", warning=warning)
    result = await publish_to_slowpics(
        collection_metadata=collection_resolution.metadata,
        config=ctx.config.slowpics,
        client=client,
        progress=ctx.reporter,
        upload_plan=upload_plan,
    )
    post_upload_actions = await run_slowpics_post_upload_actions(
        SlowpicsPostUploadRequest(
            workspace=ctx.workspace,
            config=ctx.config.slowpics,
            slowpics_url=result.url,
            collection_title=collection_resolution.metadata.title,
        )
    )
    return PublishPhaseOutput(
        slowpics_url=result.url,
        uploaded_file_paths=result.uploaded_file_paths,
        post_upload_actions=post_upload_actions,
    )


def run_confirm_slowpics_upload_phase(
    ctx: RunContext,
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

    progress = ctx.reporter
    if progress is not None:
        progress.suspend()
    try:
        decision = confirm_slowpics_upload(
            SlowpicsUploadConfirmationRequest(report_path=report_path)
        )
    finally:
        if progress is not None:
            progress.resume()
    return ConfirmSlowpicsUploadPhaseOutput(status=decision)


def _slowpics_upload_clips(ctx: RunContext) -> list[SlowpicsUploadClip]:
    clips = [ctx.reference, *ctx.comparisons]
    image_names = unique_presentation_names(
        [
            clip.label
            if clip.label_is_explicit or clip.release_identity is None
            else format_release_descriptor(clip.release_identity) or clip.label
            for clip in clips
        ],
        roles=[clip_role(index) for index in range(len(clips))],
        protected=[clip.label_is_explicit for clip in clips],
    )
    seen_labels: set[str] = set()
    upload_clips: list[SlowpicsUploadClip] = []
    for clip, image_name in zip(clips, image_names, strict=True):
        if clip.label in seen_labels:
            raise SlowpicsError(f"Duplicate clip label in slow.pics upload input: {clip.label!r}")
        seen_labels.add(clip.label)
        upload_clips.append(SlowpicsUploadClip(label=clip.label, image_name=image_name))
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
    roles = [clip_role(index) for index in range(len(clips))]
    protected = [clip.label_is_explicit for clip in clips]
    releases = [
        format_release_descriptor(clip.release_identity) if clip.release_identity else ""
        for clip in clips
    ]
    primaries = unique_presentation_names(
        [
            clip.label
            if clip.label_is_explicit or clip.release_identity is None
            else format_compact_identity(clip.release_identity) or clip.label
            for clip in clips
        ],
        roles=roles,
        protected=protected,
    )
    controls = unique_presentation_names(
        [
            clip.label if clip.label_is_explicit else releases[index] or primaries[index]
            for index, clip in enumerate(clips)
        ],
        roles=roles,
        protected=protected,
    )
    micros = unique_presentation_names(
        [
            clip.label
            if clip.label_is_explicit
            else (format_micro_descriptor(clip.release_identity) if clip.release_identity else "")
            or controls[index]
            for index, clip in enumerate(clips)
        ],
        roles=roles,
        protected=protected,
    )
    clip_info: list[ClipInfo] = []
    for clip_index, clip in enumerate(clips):
        paths = render.screenshots_by_label[clip.label]
        facts = render.frame_facts_by_label[clip.label]
        if len(paths) != len(frames) or len(facts) != len(frames):
            raise ValueError(
                f"report artifacts for {clip.label!r} must contain one path and fact "
                f"per frame: expected {len(frames)}, got {len(paths)} paths and "
                f"{len(facts)} facts"
            )
        images: list[ReportImageInfo] = []
        for index, comparison_frame in enumerate(frames):
            source_frame = map_aligned_to_source_frame(
                clip=clip,
                aligned_frame=comparison_frame,
            )
            if facts[index].source_frame != source_frame:
                raise ValueError(
                    f"report source-frame mapping mismatch for {clip.label!r} at "
                    f"comparison frame {comparison_frame}"
                )
            images.append(ReportImageInfo(paths[index], source_frame, facts[index]))
        clip_facts = render.clip_facts_by_label[clip.label]
        clip_info.append(
            ClipInfo(
                name=clip.label,
                path=clip.path,
                frame_count=clip.probe.num_frames,
                resolution=(clip.probe.width, clip.probe.height),
                fps=float(clip.effective_fps),
                size_bytes=clip_facts.size_bytes,
                signal=clip_facts.signal,
                presentation_state=clip_facts.presentation_state,
                tonemap_settings=clip_facts.tonemap_settings,
                active_picture=clip_facts.geometry.active_picture,
                images=images,
                label=clip.label,
                source_identity=source_identity_from_fingerprint(clip.probe.fingerprint),
                display=ReportClipDisplayInfo(
                    primary=primaries[clip_index],
                    release=releases[clip_index],
                    control=controls[clip_index],
                    micro=micros[clip_index],
                    filename=clip.path.name,
                ),
            )
        )
    applied_settings = next(
        (
            facts.tonemap_settings
            for facts in render.clip_facts_by_label.values()
            if facts.tonemap_settings is not None
        ),
        None,
    )
    if applied_settings is not None and any(
        facts.tonemap_settings is not None and facts.tonemap_settings != applied_settings
        for facts in render.clip_facts_by_label.values()
    ):
        raise ValueError(
            "report rendering disclosure cannot represent mixed effective tonemap settings"
        )
    report_data = ReportData(
        clips=clip_info,
        frames=frames,
        rendering=ReportRenderingInfo(
            # These deterministic presentation policies come from resolved config;
            # batch expansion has no post-render override or fallback for them.
            overlay_mode=ctx.config.screenshots.overlay_mode,
            include_frame_number=ctx.config.screenshots.include_frame_number,
            tonemap_settings=applied_settings,
            geometry_by_label={
                label: facts.geometry for label, facts in render.clip_facts_by_label.items()
            },
        ),
        metadata=metadata,
        slowpics_url=slowpics_url,
        frame_details=report_frame_details_for_frames(ctx, frames=frames),
    )
    if ctx.workspace.run_dir is None:
        raise RuntimeError("report generation requires a reserved run folder")
    report_path = generate_report(
        report_data,
        ctx.config.report,
        output_path=ctx.workspace.run_dir / "report.html",
    )
    return ReportPhaseOutput(report_path=report_path, report_succeeded=True)


def _report_selection_detail(detail: SelectionDetail | None) -> SourceFrameSelectionDetail | None:
    if detail is None:
        return None
    return SourceFrameSelectionDetail(
        label=detail.label,
        timecode=detail.timecode,
        notes=detail.notes,
    )


def report_frame_details_for_frames(ctx: RunContext, *, frames: list[int]) -> list[FrameDetail]:
    if ctx.selection_breakdown is None and ctx.selection_details_by_source_frame is None:
        return []

    frame_details: list[FrameDetail] = []
    for aligned_frame in frames:
        source_frame = map_aligned_to_source_frame(
            clip=ctx.reference,
            aligned_frame=aligned_frame,
        )
        detail = selection_detail_for_frame(
            source_frame,
            ctx.selection_details_by_source_frame,
        )
        selection_label = (
            detail.label
            if detail is not None
            else selection_label_for_frame(source_frame, ctx.selection_breakdown)
        )
        frame_details.append(
            frame_detail_for_comparison_frame(
                comparison_frame=aligned_frame,
                selection_detail=_report_selection_detail(detail),
                selection_label=selection_label,
            )
        )
    return frame_details


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
