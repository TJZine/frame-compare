from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner, FFmpegRunner
from frame_compare.render.naming import generate_screenshot_name, generate_screenshot_path
from frame_compare.render.prepare import prepare_clip_for_render
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    OverlayMode,
    Renderer,
    RenderRequest,
    ScreenshotBatchRequest,
)
from frame_compare.vs.errors import TonemapRequiresVapourSynthError

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema


def _validate_batch_request_lengths(request: ScreenshotBatchRequest) -> None:
    """Fail fast when a batch request carries mismatched frame metadata lists."""
    display_len = len(request.display_frames)
    source_len = len(request.source_frames)
    selection_len = len(request.selection_labels)
    if display_len != source_len or display_len != selection_len:
        raise ValueError(
            f"ScreenshotBatchRequest {request.label!r} has mismatched lengths: "
            f"display_frames={display_len}, source_frames={source_len}, "
            f"selection_labels={selection_len}"
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
    resolution: tuple[int, int],
    hdr_info: str | None,
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
        num_frames=num_frames,
        selection_label=selection_label,
        include_frame_number=include_frame_number,
        resolution=resolution,
        hdr_info=hdr_info,
        font_path=None,
    )


def expand_batch_render_requests(
    batch_requests: list[ScreenshotBatchRequest],
    *,
    output_dir: Path,
    config: ConfigSchema,
    overlay_mode: OverlayMode,
    renderer: Renderer,
    ffmpeg_runner: FFmpegRunner,
) -> tuple[list[RenderRequest], dict[str, range]]:
    all_requests: list[RenderRequest] = []
    label_to_range: dict[str, range] = {}
    start_idx = 0

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

        num_frames_for_req = len(req.source_frames)
        label_to_range[req.label] = range(start_idx, start_idx + num_frames_for_req)
        start_idx += num_frames_for_req

        for idx, source_frame in enumerate(req.source_frames):
            _validate_source_frame_range(req, source_frame=source_frame, num_frames=num_frames)
            display_frame = req.display_frames[idx]
            selection_label = req.selection_labels[idx]

            output_path = generate_screenshot_path(
                output_dir, _request_filename_label(req), display_frame
            )
            overlay = _build_overlay_config(
                req,
                overlay_mode=overlay_mode,
                source_frame=source_frame,
                display_frame=display_frame,
                selection_label=selection_label,
                resolution=(width, height),
                hdr_info=resolved_hdr_info,
                num_frames=num_frames,
                include_frame_number=config.screenshots.include_frame_number,
            )

            render_req = RenderRequest(
                clip=loaded_clip,
                frame_number=source_frame,
                output_path=output_path,
                overlay=overlay,
                encoder_settings=EncoderSettings(),
                ffmpeg_runner=ffmpeg_runner,
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
