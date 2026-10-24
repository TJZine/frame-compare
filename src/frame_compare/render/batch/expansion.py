"""Expand clip-level screenshot requests into exact frame render jobs."""

from __future__ import annotations

from pathlib import Path

from frame_compare.config.schema import ConfigSchema, OverlayMode
from frame_compare.config.schema_enums import ScreenshotAlignedScalePolicy, ScreenshotGeometryMode
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner, FFmpegRunner
from frame_compare.render.errors import RenderError
from frame_compare.render.geometry import (
    GeometryRect,
    RenderGeometryOptions,
    RenderGeometryPlan,
    SourceGeometry,
    plan_render_geometry,
)
from frame_compare.render.naming import generate_screenshot_path, validate_screenshot_paths
from frame_compare.render.prepare import prepare_clip_for_render
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    PreparedClipRender,
    PreparedRenderSource,
    RenderedClipFacts,
    Renderer,
    RenderRequest,
    ScreenshotBatchRequest,
)
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
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
    for request in batch_requests:
        width, height = request.source_resolution
        if width <= 0 or height <= 0:
            raise ValueError(
                f"ScreenshotBatchRequest {request.label!r} requires positive source dimensions"
            )
        active = request.active_picture
        if active.x + active.width > width or active.y + active.height > height:
            raise ValueError(
                f"ScreenshotBatchRequest {request.label!r} active picture is outside "
                "the source dimensions"
            )
        if request.label in labels:
            raise ValueError(f"Duplicate label {request.label!r} detected in batch requests")
        labels.add(request.label)


def expand_batch_render_requests(
    batch_requests: list[ScreenshotBatchRequest],
    *,
    output_dir: Path,
    config: ConfigSchema,
    overlay_mode: OverlayMode,
    renderer: Renderer,
    ffmpeg_runner: FFmpegRunner,
) -> tuple[PreparedClipRender, ...]:
    output_paths = [
        [
            generate_screenshot_path(
                output_dir, batch.filename_label or batch.label, selection.comparison_frame
            )
            for selection in batch.frames
        ]
        for batch in batch_requests
    ]
    validate_screenshot_paths([path for paths in output_paths for path in paths])
    prepared: list[PreparedRenderSource] = []
    for request in batch_requests:
        raise_if_cancelling()
        prepared.append(
            prepare_clip_for_render(
                request.clip_path,
                renderer,
                config,
                ffmpeg_runner=ffmpeg_runner,
                source_is_hdr=request.signal.is_hdr,
            )
        )
    raise_if_cancelling()
    plans = _geometry_plans(batch_requests, prepared, config)
    jobs: list[PreparedClipRender] = []

    for batch, source, plan, paths in zip(
        batch_requests, prepared, plans, output_paths, strict=True
    ):
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
        clip_facts = RenderedClipFacts(
            size_bytes=batch.size_bytes,
            source_resolution=source_resolution,
            source_total_frames=source_total_frames,
            signal=batch.signal,
            presentation_state=state,
            tonemap=source.tonemap,
            geometry=geometry,
        )
        requests: list[RenderRequest] = []
        for selection, output_path in zip(batch.frames, paths, strict=True):
            source_frame = selection.source_frame
            if source_total_frames is not None and not (0 <= source_frame < source_total_frames):
                raise ValueError(
                    f"ScreenshotBatchRequest {batch.label!r} requested source frame "
                    f"{source_frame} outside valid range"
                )
            comparison_frame = selection.comparison_frame
            overlay = None
            if overlay_mode != OverlayMode.NONE:
                overlay = OverlayConfig(
                    mode=overlay_mode,
                    label=batch.label,
                    comparison_frame=comparison_frame,
                    source_frame=source_frame,
                    source_total_frames=source_total_frames,
                    include_frame_number=config.screenshots.include_frame_number,
                    selection_label=selection.selection_label,
                    file_size_bytes=batch.size_bytes,
                    source_resolution=source_resolution,
                    signal=batch.signal,
                    presentation_state=state,
                    tonemap=source.tonemap,
                    geometry=geometry,
                    font_path=None,
                    origin=plan.overlay_origin,
                )
            requests.append(
                RenderRequest(
                    clip=source.prepared_clip,
                    diagnostic_source=source.diagnostic_source,
                    frame_number=source_frame,
                    output_path=output_path,
                    overlay=overlay,
                    encoder_settings=EncoderSettings(
                        compression=config.screenshots.png_compression,
                        vs_writer=config.screenshots.vs_writer,
                    ),
                    ffmpeg_runner=ffmpeg_runner,
                    geometry_plan=plan,
                )
            )
        jobs.append(PreparedClipRender(batch.label, clip_facts, batch.frames, tuple(requests)))
    return tuple(jobs)


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
        if active.x + active.width > width or active.y + active.height > height:
            raise RenderError(
                reason=f"active picture for {request.label!r} is outside prepared source dimensions {width}x{height}"
            )
        sources.append(
            SourceGeometry(
                width=width,
                height=height,
                active_rect=GeometryRect(active.x, active.y, active.width, active.height),
                provenance=active.provenance,
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
    active = ActivePictureFacts(
        x=plan.active_rect.x,
        y=plan.active_rect.y,
        width=plan.active_rect.width,
        height=plan.active_rect.height,
        provenance=plan.provenance,
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
