from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from frame_compare.config.schema_enums import ScreenshotAlignedScalePolicy, ScreenshotGeometryMode
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner, FFmpegRunner
from frame_compare.render.geometry import (
    ActiveRectDetectionMode,
    ActiveRectSource,
    GeometryRect,
    RenderGeometryOptions,
    RenderGeometryPlan,
    SourceGeometry,
    plan_render_geometry,
)
from frame_compare.render.naming import generate_screenshot_name, generate_screenshot_path
from frame_compare.render.prepare import prepare_clip_for_render, resolve_tonemap_settings
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    OverlayDiagnosticMetadata,
    OverlayMode,
    OverlaySelectionDetail,
    Renderer,
    RenderRequest,
    ScreenshotBatchRequest,
)
from frame_compare.vs.errors import TonemapRequiresVapourSynthError

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.config.schema import ConfigSchema

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class _PreparedBatchRequest:
    request: ScreenshotBatchRequest
    loaded_clip: vs.VideoNode | Path
    hdr_info: str | None
    base_text: str | None
    width: int
    height: int
    num_frames: int | None


@dataclass(frozen=True, slots=True)
class _ResolvedRequestActiveRect:
    rect: GeometryRect | None
    source: ActiveRectSource


def _validate_batch_request_lengths(request: ScreenshotBatchRequest) -> None:
    """Fail fast when a batch request carries mismatched frame metadata lists."""
    display_len = len(request.display_frames)
    source_len = len(request.source_frames)
    selection_len = len(request.selection_labels)
    selection_detail_len = (
        len(request.selection_details) if request.selection_details is not None else display_len
    )
    diagnostic_len = (
        len(request.diagnostic_metadata) if request.diagnostic_metadata is not None else display_len
    )
    if (
        display_len != source_len
        or display_len != selection_len
        or display_len != selection_detail_len
        or display_len != diagnostic_len
    ):
        raise ValueError(
            f"ScreenshotBatchRequest {request.label!r} has mismatched lengths: "
            f"display_frames={display_len}, source_frames={source_len}, "
            f"selection_labels={selection_len}, selection_details={selection_detail_len}, "
            f"diagnostic_metadata={diagnostic_len}"
        )


def resolve_target_renderer(config: ConfigSchema, renderer: Renderer) -> Renderer:
    if renderer == "auto" and config.screenshots.use_ffmpeg:
        return "ffmpeg"
    return renderer


def validate_ffmpeg_batch_tonemap_gate(
    batch_requests: list[ScreenshotBatchRequest],
    config: ConfigSchema,
    renderer: Renderer,
) -> None:
    if renderer != "ffmpeg" or not config.color.enable_tonemap:
        return

    if any(req.probe_is_hdr is not False for req in batch_requests):
        raise TonemapRequiresVapourSynthError()


def resolve_batch_ffmpeg_runner(ffmpeg_runner: FFmpegRunner | None) -> FFmpegRunner:
    if ffmpeg_runner is not None:
        return ffmpeg_runner

    return DefaultFFmpegRunner()


def validate_batch_requests(batch_requests: list[ScreenshotBatchRequest]) -> None:
    seen_labels: set[str] = set()
    seen_output_names: dict[str, tuple[str, int]] = {}
    for req in batch_requests:
        _validate_batch_request_lengths(req)
        if req.label in seen_labels:
            raise ValueError(f"Duplicate label {req.label!r} detected in batch requests")
        seen_labels.add(req.label)
        filename_label = _request_filename_label(req)
        for display_frame in req.display_frames:
            output_name = generate_screenshot_name(filename_label, display_frame)
            prior = seen_output_names.get(output_name)
            if prior is not None:
                prior_label, prior_display_frame = prior
                raise ValueError(
                    f"Duplicate screenshot output {output_name!r} detected for "
                    f"label={req.label!r}, display_frame={display_frame}; already produced by "
                    f"label={prior_label!r}, display_frame={prior_display_frame}"
                )
            seen_output_names[output_name] = (req.label, display_frame)


def _request_filename_label(request: ScreenshotBatchRequest) -> str:
    return request.filename_label if request.filename_label is not None else request.label


def _validate_source_frame_range(
    request: ScreenshotBatchRequest,
    *,
    source_frame: int,
    num_frames: int | None,
) -> None:
    if num_frames is None:
        return

    if 0 <= source_frame < num_frames:
        return

    raise ValueError(
        f"ScreenshotBatchRequest {request.label!r} requested source frame "
        f"{source_frame} outside valid range 0..{num_frames - 1} "
        f"for {request.clip_path}"
    )


def _resolve_num_frames(
    source_num_frames: object,
    probe_num_frames: int | None,
) -> int | None:
    if type(source_num_frames) is int:
        return source_num_frames
    return probe_num_frames


def _build_overlay_config(
    request: ScreenshotBatchRequest,
    *,
    overlay_mode: OverlayMode,
    source_frame: int,
    display_frame: int,
    selection_label: str | None,
    selection_detail: OverlaySelectionDetail | None,
    diagnostic_metadata: OverlayDiagnosticMetadata | None,
    resolution: tuple[int, int],
    resolution_summary: str | None,
    origin: tuple[int, int] | None,
    hdr_info: str | None,
    base_text: str | None,
    num_frames: int | None,
    include_frame_number: bool,
) -> OverlayConfig | None:
    if overlay_mode == OverlayMode.NONE:
        return None
    return OverlayConfig(
        mode=overlay_mode,
        label=request.label,
        frame_number=source_frame,
        display_frame_number=display_frame,
        base_text=base_text,
        resolution_summary=resolution_summary,
        num_frames=num_frames,
        selection_label=selection_label,
        selection_detail=selection_detail,
        diagnostic_metadata=diagnostic_metadata,
        burn_in_label=_request_filename_label(request),
        include_frame_number=include_frame_number,
        resolution=resolution,
        origin=origin,
        hdr_info=hdr_info,
        font_path=None,
    )


def _format_dimensions(width: int, height: int) -> str:
    return f"{int(width)} × {int(height)}"


def _overlay_resolution_summary(
    *,
    source_size: tuple[int, int],
    geometry_plan: RenderGeometryPlan | None,
) -> str | None:
    transformed = False
    if geometry_plan is None:
        original = source_size
        final = source_size
    else:
        original = source_size
        final = geometry_plan.final_canvas_size
        transformed = not geometry_plan.is_noop

    original_width, original_height = original
    final_width, final_height = final
    if original_width <= 0 or original_height <= 0 or final_width <= 0 or final_height <= 0:
        return None

    original_text = _format_dimensions(original_width, original_height)
    final_text = _format_dimensions(final_width, final_height)
    if not transformed:
        return f"{original_text}  (native)"
    return f"{original_text} → {final_text}  (original → target)"


def _overlay_base_text_for_request(
    *,
    config: ConfigSchema,
    source_is_hdr: bool,
) -> str | None:
    if not source_is_hdr or not config.color.enable_tonemap:
        return None

    settings = resolve_tonemap_settings(config)
    return (
        "Tonemapping Algorithm: "
        f"{settings.tone_curve.value} "
        f"dpd = {int(settings.dynamic_peak_detection)} "
        f"dst = {settings.target_nits} nits"
    )


def _dovi_l5_active_rect(
    metadata: OverlayDiagnosticMetadata | None,
    *,
    width: int,
    height: int,
) -> GeometryRect | None:
    dovi = metadata.dolby_vision if metadata is not None else None
    if dovi is None:
        return None
    margins = (dovi.l5_left, dovi.l5_top, dovi.l5_right, dovi.l5_bottom)
    if any(value is None for value in margins):
        return None

    left, top, right, bottom = margins
    if left is None or top is None or right is None or bottom is None:
        return None
    if left < 0 or top < 0 or right < 0 or bottom < 0:
        return None
    if left == 0 and top == 0 and right == 0 and bottom == 0:
        return None

    active_width = width - left - right
    active_height = height - top - bottom
    if active_width <= 0 or active_height <= 0:
        return None
    return GeometryRect(left, top, active_width, active_height)


def _dovi_l5_metadata_warning_reason(
    request: ScreenshotBatchRequest,
    *,
    width: int,
    height: int,
) -> str | None:
    if request.diagnostic_metadata is None:
        return None

    if not request.diagnostic_metadata:
        return "no selected-frame metadata entries were available"

    rects: set[GeometryRect] = set()
    partial_count = 0
    invalid_count = 0
    missing_count = 0
    for metadata in request.diagnostic_metadata:
        dovi = metadata.dolby_vision if metadata is not None else None
        if dovi is None:
            missing_count += 1
            continue

        margins = (dovi.l5_left, dovi.l5_top, dovi.l5_right, dovi.l5_bottom)
        if all(value is None for value in margins):
            missing_count += 1
            continue
        if any(value is None for value in margins):
            partial_count += 1
            continue

        rect = _dovi_l5_active_rect(metadata, width=width, height=height)
        if rect is None:
            invalid_count += 1
            continue
        rects.add(rect)

    if partial_count:
        return "one or more selected-frame entries had partial Dolby Vision L5 margins"
    if invalid_count:
        return "one or more selected-frame entries had invalid Dolby Vision L5 margins"
    if missing_count and (rects or partial_count or invalid_count):
        return "one or more selected-frame entries had no Dolby Vision L5 margins"
    if len(rects) > 1:
        return "selected-frame Dolby Vision L5 margins were inconsistent"
    return None


def _trusted_metadata_active_rect(
    request: ScreenshotBatchRequest,
    *,
    width: int,
    height: int,
) -> GeometryRect | None:
    if request.diagnostic_metadata is None:
        return None

    rects: set[GeometryRect] = set()
    for metadata in request.diagnostic_metadata:
        rect = _dovi_l5_active_rect(metadata, width=width, height=height)
        if rect is None:
            return None
        rects.add(rect)

    if len(rects) == 1:
        return next(iter(rects))
    return None


def _resolve_request_active_rect(
    request: ScreenshotBatchRequest,
    *,
    width: int,
    height: int,
    warnings: list[str] | None,
) -> _ResolvedRequestActiveRect:
    if request.active_rect is not None:
        if request.active_rect_source is not None:
            return _ResolvedRequestActiveRect(
                request.active_rect,
                _validated_active_rect_source(request.active_rect_source),
            )
        if request.diagnostic_metadata_trusted_for_geometry:
            _warn_if_metadata_geometry_rejected(
                request,
                width=width,
                height=height,
                fallback="explicit active rect override",
                warnings=warnings,
            )
        return _ResolvedRequestActiveRect(request.active_rect, "explicit")

    if request.diagnostic_metadata_trusted_for_geometry:
        metadata_rect = _trusted_metadata_active_rect(request, width=width, height=height)
        if metadata_rect is not None:
            return _ResolvedRequestActiveRect(metadata_rect, "metadata")
        _warn_if_metadata_geometry_rejected(
            request,
            width=width,
            height=height,
            fallback="geometry fallback",
            warnings=warnings,
        )

    return _ResolvedRequestActiveRect(None, "explicit")


def _validated_active_rect_source(value: str) -> ActiveRectSource:
    if value not in (
        "explicit",
        "metadata",
        "dimension-derived",
        "aspect-ratio-derived",
        "content-derived",
        "full-frame",
    ):
        raise ValueError(f"Unsupported active rect source {value!r}")
    return value


def _warn_if_metadata_geometry_rejected(
    request: ScreenshotBatchRequest,
    *,
    width: int,
    height: int,
    fallback: str,
    warnings: list[str] | None,
) -> None:
    warning_reason = _dovi_l5_metadata_warning_reason(request, width=width, height=height)
    if warning_reason is None:
        return

    warning = (
        f"Screenshot geometry alignment ignored Dolby Vision L5 active rect metadata "
        f"for {request.label}: {warning_reason}; using {fallback}."
    )
    log.warning(
        "screenshot_geometry_metadata_active_rect_ignored",
        reason=warning_reason,
        label=request.label,
        has_explicit_active_rect=request.active_rect is not None,
    )
    if warnings is not None:
        warnings.append(warning)


def _prepare_batch_requests(
    batch_requests: list[ScreenshotBatchRequest],
    *,
    config: ConfigSchema,
    renderer: Renderer,
    ffmpeg_runner: FFmpegRunner,
) -> list[_PreparedBatchRequest]:
    prepared_requests: list[_PreparedBatchRequest] = []
    for req in batch_requests:
        loaded_clip, _, hdr_info, source_info = prepare_clip_for_render(
            req.clip_path, renderer, config, ffmpeg_runner=ffmpeg_runner
        )

        width = source_info.width if source_info is not None else (req.probe_width or 0)
        height = source_info.height if source_info is not None else (req.probe_height or 0)
        num_frames = (
            _resolve_num_frames(source_info.num_frames, req.probe_num_frames)
            if source_info is not None
            else req.probe_num_frames
        )
        resolved_hdr_info = (
            hdr_info if source_info is not None else ("HDR" if req.probe_is_hdr else None)
        )
        prepared_requests.append(
            _PreparedBatchRequest(
                request=req,
                loaded_clip=loaded_clip,
                hdr_info=resolved_hdr_info,
                base_text=_overlay_base_text_for_request(
                    config=config,
                    source_is_hdr=(
                        source_info.is_hdr if source_info is not None else req.probe_is_hdr is True
                    ),
                ),
                width=width,
                height=height,
                num_frames=num_frames,
            )
        )
    return prepared_requests


def _geometry_plans_for_batch(
    prepared_requests: list[_PreparedBatchRequest],
    *,
    config: ConfigSchema,
    warnings: list[str] | None = None,
) -> tuple[RenderGeometryPlan | None, ...]:
    if config.screenshots.geometry_mode == ScreenshotGeometryMode.NATIVE:
        return tuple(None for _prepared in prepared_requests)
    if not any(prepared.request.source_frames for prepared in prepared_requests):
        return tuple(None for _prepared in prepared_requests)
    missing_dimension_labels = tuple(
        prepared.request.label
        for prepared in prepared_requests
        if prepared.width <= 0 or prepared.height <= 0
    )
    if missing_dimension_labels:
        visible_labels = ", ".join(missing_dimension_labels[:3])
        if len(missing_dimension_labels) > 3:
            visible_labels += f", ... ({len(missing_dimension_labels) - 3} more)"
        warning = (
            "Screenshot geometry alignment skipped: source dimensions were unavailable "
            f"for {visible_labels}; using native screenshot geometry for this batch."
        )
        log.warning(
            "screenshot_geometry_alignment_skipped",
            reason="missing_source_dimensions",
            labels=list(missing_dimension_labels),
        )
        if warnings is not None:
            warnings.append(warning)
        return tuple(None for _prepared in prepared_requests)

    sources = tuple(
        _source_geometry_for_request(prepared, warnings=warnings) for prepared in prepared_requests
    )
    return plan_render_geometry(
        sources,
        mode="aligned",
        options=_geometry_options_from_config(config, prepared_requests),
    )


def _geometry_options_from_config(
    config: ConfigSchema,
    prepared_requests: list[_PreparedBatchRequest] | None = None,
) -> RenderGeometryOptions:
    target_size: tuple[int, int] | None = None
    if config.screenshots.aligned_scale_policy == ScreenshotAlignedScalePolicy.EXPLICIT_SIZE:
        target_width = config.screenshots.aligned_target_width
        target_height = config.screenshots.aligned_target_height
        if target_width is None or target_height is None:
            raise ValueError("explicit screenshot geometry target size is incomplete")
        target_size = (target_width, target_height)

    return RenderGeometryOptions(
        active_rect_detection=_active_rect_detection_for_geometry(config, prepared_requests),
        aligned_scale_policy=config.screenshots.aligned_scale_policy.value,
        aligned_target_size=target_size,
    )


def _active_rect_detection_for_geometry(
    config: ConfigSchema,
    prepared_requests: list[_PreparedBatchRequest] | None,
) -> ActiveRectDetectionMode:
    if prepared_requests and all(
        prepared.request.active_rect is not None
        and prepared.request.active_rect_source is not None
        and prepared.request.active_rect_detection_mode is not None
        for prepared in prepared_requests
    ):
        return "provided"
    return config.screenshots.active_rect_detection.value


def _source_geometry_for_request(
    prepared: _PreparedBatchRequest,
    *,
    warnings: list[str] | None,
) -> SourceGeometry:
    active_rect = _resolve_request_active_rect(
        prepared.request,
        width=prepared.width,
        height=prepared.height,
        warnings=warnings,
    )
    return SourceGeometry(
        width=prepared.width,
        height=prepared.height,
        active_rect=active_rect.rect,
        active_rect_source=active_rect.source,
        label=prepared.request.label,
    )


def expand_batch_render_requests(
    batch_requests: list[ScreenshotBatchRequest],
    *,
    output_dir: Path,
    config: ConfigSchema,
    overlay_mode: OverlayMode,
    renderer: Renderer,
    ffmpeg_runner: FFmpegRunner,
    warnings: list[str] | None = None,
) -> tuple[list[RenderRequest], dict[str, range]]:
    all_requests: list[RenderRequest] = []
    label_to_range: dict[str, range] = {}
    start_idx = 0
    prepared_requests = _prepare_batch_requests(
        batch_requests,
        config=config,
        renderer=renderer,
        ffmpeg_runner=ffmpeg_runner,
    )
    geometry_plans = _geometry_plans_for_batch(
        prepared_requests,
        config=config,
        warnings=warnings,
    )

    for prepared, geometry_plan in zip(prepared_requests, geometry_plans, strict=True):
        req = prepared.request
        num_frames_for_req = len(req.source_frames)
        label_to_range[req.label] = range(start_idx, start_idx + num_frames_for_req)
        start_idx += num_frames_for_req
        overlay_resolution = (
            geometry_plan.final_canvas_size
            if geometry_plan is not None
            else (prepared.width, prepared.height)
        )
        overlay_origin = geometry_plan.overlay_origin if geometry_plan is not None else None
        overlay_resolution_summary = _overlay_resolution_summary(
            source_size=(prepared.width, prepared.height),
            geometry_plan=geometry_plan,
        )

        for idx, source_frame in enumerate(req.source_frames):
            _validate_source_frame_range(
                req, source_frame=source_frame, num_frames=prepared.num_frames
            )
            display_frame = req.display_frames[idx]
            selection_detail = (
                req.selection_details[idx] if req.selection_details is not None else None
            )
            diagnostic_metadata = (
                req.diagnostic_metadata[idx] if req.diagnostic_metadata is not None else None
            )
            selection_label = (
                selection_detail.label
                if selection_detail is not None
                else req.selection_labels[idx]
            )

            output_path = generate_screenshot_path(
                output_dir, _request_filename_label(req), display_frame
            )
            overlay = _build_overlay_config(
                req,
                overlay_mode=overlay_mode,
                source_frame=source_frame,
                display_frame=display_frame,
                selection_label=selection_label,
                selection_detail=selection_detail,
                diagnostic_metadata=diagnostic_metadata,
                resolution=overlay_resolution,
                resolution_summary=overlay_resolution_summary,
                origin=overlay_origin,
                hdr_info=prepared.hdr_info,
                base_text=prepared.base_text,
                num_frames=prepared.num_frames,
                include_frame_number=config.screenshots.include_frame_number,
            )

            render_req = RenderRequest(
                clip=prepared.loaded_clip,
                frame_number=source_frame,
                output_path=output_path,
                overlay=overlay,
                encoder_settings=EncoderSettings(
                    compression=config.screenshots.png_compression,
                    vs_writer=config.screenshots.vs_writer,
                ),
                ffmpeg_runner=ffmpeg_runner,
                geometry_plan=geometry_plan,
            )
            all_requests.append(render_req)

    return all_requests, label_to_range


def render_batch_results_by_label(
    batch_requests: list[ScreenshotBatchRequest],
    rendered_paths: list[Path],
    label_to_range: dict[str, range],
) -> dict[str, list[Path]]:
    results: dict[str, list[Path]] = {}
    for req in batch_requests:
        result_range = label_to_range[req.label]
        results[req.label] = rendered_paths[result_range.start : result_range.stop]
    return results
