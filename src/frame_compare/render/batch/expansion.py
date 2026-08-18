"""Expand clip-level screenshot requests into exact frame render jobs."""

from __future__ import annotations

from pathlib import Path

from frame_compare.config.schema import ConfigSchema, OverlayMode
from frame_compare.config.schema_enums import ScreenshotAlignedScalePolicy, ScreenshotGeometryMode
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner, FFmpegRunner
from frame_compare.render.geometry import (
    ActiveRectSource,
    GeometryRect,
    RenderGeometryOptions,
    RenderGeometryPlan,
    SourceGeometry,
    plan_render_geometry,
)
from frame_compare.render.naming import generate_screenshot_name, generate_screenshot_path
from frame_compare.render.prepare import prepare_clip_for_render
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    PreparedRenderSource,
    RenderedClipFacts,
    Renderer,
    RenderRequest,
    ScreenshotBatchRequest,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    ActivePictureProvenance,
    RenderedGeometryFacts,
)


def resolve_target_renderer(config: ConfigSchema, renderer: Renderer) -> Renderer:
    if renderer == "auto" and config.screenshots.use_ffmpeg:
        return "ffmpeg"
    return renderer


def resolve_batch_ffmpeg_runner(
    ffmpeg_runner: FFmpegRunner | None, *, extraction_timeout_seconds: float = 30.0
) -> FFmpegRunner:
    return ffmpeg_runner or DefaultFFmpegRunner(
        extraction_timeout_seconds=extraction_timeout_seconds
    )


def validate_ffmpeg_batch_tonemap_gate(
    batch_requests: list[ScreenshotBatchRequest], config: ConfigSchema, renderer: Renderer
) -> None:
    if (
        renderer == "ffmpeg"
        and config.color.enable_tonemap
        and any(request.signal.is_hdr for request in batch_requests)
    ):
        from frame_compare.vs.errors import TonemapRequiresVapourSynthError

        raise TonemapRequiresVapourSynthError()


def validate_batch_requests(batch_requests: list[ScreenshotBatchRequest]) -> None:
    labels: set[str] = set()
    output_names: set[str] = set()
    for request in batch_requests:
        lengths = {
            len(request.source_frames),
            len(request.comparison_frames),
            len(request.selection_labels),
        }
        if len(lengths) != 1:
            raise ValueError(f"ScreenshotBatchRequest {request.label!r} list lengths differ")
        if request.label in labels:
            raise ValueError(f"Duplicate label {request.label!r} detected in batch requests")
        labels.add(request.label)
        filename_label = request.filename_label or request.label
        for frame in request.comparison_frames:
            output_name = generate_screenshot_name(filename_label, frame)
            if output_name in output_names:
                raise ValueError(f"Duplicate screenshot output {output_name!r}")
            output_names.add(output_name)


def expand_batch_render_requests(
    batch_requests: list[ScreenshotBatchRequest],
    *,
    output_dir: Path,
    config: ConfigSchema,
    overlay_mode: OverlayMode,
    renderer: Renderer,
    ffmpeg_runner: FFmpegRunner,
    warnings: list[str] | None = None,
) -> tuple[list[RenderRequest], dict[str, range], dict[str, RenderedClipFacts]]:
    del warnings
    prepared = [
        prepare_clip_for_render(
            request.clip_path,
            renderer,
            config,
            ffmpeg_runner=ffmpeg_runner,
        )
        for request in batch_requests
    ]
    plans = _geometry_plans(batch_requests, prepared, config)
    requests: list[RenderRequest] = []
    ranges: dict[str, range] = {}
    clip_facts: dict[str, RenderedClipFacts] = {}
    start = 0

    for batch, source, plan in zip(batch_requests, prepared, plans, strict=True):
        geometry = _geometry_facts(plan)
        source_resolution = (
            source.source_dimensions
            if all(dimension > 0 for dimension in source.source_dimensions)
            else batch.source_resolution
        )
        source_total_frames = (
            source.source_total_frames
            if source.source_total_frames is not None
            else batch.source_total_frames
        )
        # Preparation owns this state: it reflects the actual source and whether
        # the resolved tonemap was applied, rather than re-deriving it from the
        # request's clip-level signal snapshot.
        state = source.presentation_state
        clip_facts[batch.label] = RenderedClipFacts(
            size_bytes=batch.size_bytes,
            source_resolution=source_resolution,
            source_total_frames=source_total_frames,
            signal=batch.signal,
            presentation_state=state,
            tonemap_settings=source.tonemap_settings,
            geometry=geometry,
        )
        ranges[batch.label] = range(start, start + len(batch.source_frames))
        start += len(batch.source_frames)

        for index, source_frame in enumerate(batch.source_frames):
            if source_total_frames is not None and not (0 <= source_frame < source_total_frames):
                raise ValueError(
                    f"ScreenshotBatchRequest {batch.label!r} requested source frame "
                    f"{source_frame} outside valid range"
                )
            comparison_frame = batch.comparison_frames[index]
            overlay = None
            if overlay_mode != OverlayMode.NONE:
                overlay = OverlayConfig(
                    mode=overlay_mode,
                    label=batch.label,
                    comparison_frame=comparison_frame,
                    source_frame=source_frame,
                    source_total_frames=source_total_frames,
                    include_frame_number=config.screenshots.include_frame_number,
                    selection_label=batch.selection_labels[index],
                    file_size_bytes=batch.size_bytes,
                    source_resolution=source_resolution,
                    signal=batch.signal,
                    presentation_state=state,
                    tonemap_settings=source.tonemap_settings,
                    geometry=geometry,
                    font_path=None,
                    origin=plan.overlay_origin,
                )
            requests.append(
                RenderRequest(
                    clip=source.prepared_clip,
                    diagnostic_source=source.diagnostic_source,
                    frame_number=source_frame,
                    output_path=generate_screenshot_path(
                        output_dir,
                        batch.filename_label or batch.label,
                        comparison_frame,
                    ),
                    overlay=overlay,
                    encoder_settings=EncoderSettings(
                        compression=config.screenshots.png_compression,
                        vs_writer=config.screenshots.vs_writer,
                    ),
                    ffmpeg_runner=ffmpeg_runner,
                    geometry_plan=plan,
                )
            )
    return requests, ranges, clip_facts


def render_batch_results_by_label(
    batch_requests: list[ScreenshotBatchRequest],
    rendered_paths: list[Path],
    label_to_range: dict[str, range],
) -> dict[str, list[Path]]:
    return {
        request.label: rendered_paths[
            label_to_range[request.label].start : label_to_range[request.label].stop
        ]
        for request in batch_requests
    }


def _geometry_plans(
    requests: list[ScreenshotBatchRequest],
    prepared: list[PreparedRenderSource],
    config: ConfigSchema,
) -> tuple[RenderGeometryPlan, ...]:
    sources: list[SourceGeometry] = []
    for request, source in zip(requests, prepared, strict=True):
        dimensions = source.source_dimensions
        width, height = (
            dimensions
            if all(dimension > 0 for dimension in dimensions)
            else request.source_resolution
        )
        active = request.active_picture
        if request.source_resolution[0] <= 0 or request.source_resolution[1] <= 0:
            active = ActivePictureFacts(0, 0, width, height, "full_frame", True)
        sources.append(
            SourceGeometry(
                width=width,
                height=height,
                active_rect=GeometryRect(active.x, active.y, active.width, active.height),
                active_rect_source=_to_geometry_provenance(active.provenance),
                label=request.label,
            )
        )
    mode = (
        "aligned"
        if config.screenshots.geometry_mode == ScreenshotGeometryMode.ALIGNED
        else "native"
    )
    return plan_render_geometry(
        tuple(sources),
        mode=mode,
        options=RenderGeometryOptions(
            # Active-picture facts and provenance arrive canonically on the
            # request; expansion must not re-detect or replace them from config.
            active_rect_detection="provided",
            aligned_scale_policy=config.screenshots.aligned_scale_policy.value,
            aligned_target_size=_target_size(config),
        ),
    )


def _target_size(config: ConfigSchema) -> tuple[int, int] | None:
    if config.screenshots.aligned_scale_policy != ScreenshotAlignedScalePolicy.EXPLICIT_SIZE:
        return None
    width = config.screenshots.aligned_target_width
    height = config.screenshots.aligned_target_height
    if width is None or height is None:
        raise ValueError("explicit screenshot geometry target size is incomplete")
    return width, height


def _geometry_facts(plan: RenderGeometryPlan) -> RenderedGeometryFacts:
    provenance = _from_geometry_provenance(plan.active_rect_source)
    active = ActivePictureFacts(
        x=plan.active_rect.x,
        y=plan.active_rect.y,
        width=plan.active_rect.width,
        height=plan.active_rect.height,
        provenance=provenance,
        is_full_frame=plan.active_rect == plan.source_rect,
    )
    return RenderedGeometryFacts(
        source_size=(plan.source.width, plan.source.height),
        active_picture=active,
        cropped_size=plan.cropped_size,
        scaled_size=plan.scaled_size,
        final_canvas_size=plan.final_canvas_size,
        is_noop=plan.is_noop,
    )


def _to_geometry_provenance(provenance: ActivePictureProvenance) -> ActiveRectSource:
    match provenance:
        case "explicit":
            return "explicit"
        case "dolby_vision_l5":
            return "metadata"
        case "dimension_derived":
            return "dimension-derived"
        case "aspect_ratio_derived":
            return "aspect-ratio-derived"
        case "content_derived":
            return "content-derived"
        case "full_frame":
            return "full-frame"


def _from_geometry_provenance(provenance: ActiveRectSource) -> ActivePictureProvenance:
    match provenance:
        case "explicit":
            return "explicit"
        case "metadata":
            return "dolby_vision_l5"
        case "dimension-derived":
            return "dimension_derived"
        case "aspect-ratio-derived":
            return "aspect_ratio_derived"
        case "content-derived":
            return "content_derived"
        case "full-frame":
            return "full_frame"
