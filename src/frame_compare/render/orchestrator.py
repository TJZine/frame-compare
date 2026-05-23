from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from frame_compare.render.encoders import render_frame
from frame_compare.render.expansion import (
    expand_batch_render_requests,
    render_batch_results_by_label,
    resolve_batch_ffmpeg_runner,
    resolve_target_renderer,
    validate_batch_requests,
    validate_ffmpeg_batch_tonemap_gate,
)
from frame_compare.render.prepare import is_hdr_via_runner
from frame_compare.render.types import (
    Renderer,
    RenderRequest,
    ScreenshotBatchRequest,
    ScreenshotRenderOptions,
)
from frame_compare.utils.progress_protocol import ProgressReporter

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.render.ffmpeg import FFmpegRunner
    from frame_compare.render.types import OverlayMode

log = structlog.get_logger()


def _resolve_probe_is_hdr(
    clip_path: Path,
    *,
    config: ConfigSchema,
    renderer: Renderer,
    ffmpeg_runner: FFmpegRunner | None,
) -> bool | None:
    target_renderer = resolve_target_renderer(config, renderer)
    if target_renderer != "ffmpeg" or not config.color.enable_tonemap:
        return None
    resolved_ffmpeg_runner = resolve_batch_ffmpeg_runner(ffmpeg_runner)
    return is_hdr_via_runner(clip_path, resolved_ffmpeg_runner)


def _render_description(request: RenderRequest) -> str:
    """Build a consistent progress description for a render request."""
    label = request.overlay.label if request.overlay is not None else None
    return f"{label} — Frame {request.frame_number}" if label else f"Frame {request.frame_number}"


def _record_render_progress(
    reporter: ProgressReporter | None,
    request: RenderRequest,
) -> None:
    if reporter is None:
        return
    reporter.set_description(_render_description(request))
    reporter.advance(1)


def _submit_render_request(
    executor: ThreadPoolExecutor,
    requests: list[RenderRequest],
    futures: dict[Future[Path], int],
    index: int,
) -> None:
    futures[executor.submit(render_frame, requests[index])] = index


def _render_batch_sequential(
    requests: list[RenderRequest],
    results: list[Path | None],
    reporter: ProgressReporter | None,
) -> None:
    for index, request in enumerate(requests):
        results[index] = render_frame(request)
        _record_render_progress(reporter, request)


def _render_batch_parallel(
    requests: list[RenderRequest],
    results: list[Path | None],
    parallelism: int,
    reporter: ProgressReporter | None,
) -> None:
    executor = ThreadPoolExecutor(max_workers=parallelism)
    futures: dict[Future[Path], int] = {}
    next_index = 0
    first_exception: Exception | None = None

    try:
        while next_index < min(parallelism, len(requests)):
            _submit_render_request(executor, requests, futures, next_index)
            next_index += 1

        while futures:
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                index = futures.pop(future)
                try:
                    results[index] = future.result()
                    _record_render_progress(reporter, requests[index])
                except Exception as exc:
                    first_exception = exc
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                if first_exception is None and next_index < len(requests):
                    _submit_render_request(executor, requests, futures, next_index)
                    next_index += 1

            if first_exception is not None:
                break
    finally:
        executor.shutdown(wait=first_exception is None, cancel_futures=True)

    if first_exception is not None:
        raise first_exception


def _completed_render_results(results: list[Path | None]) -> list[Path]:
    completed: list[Path] = []
    for result in results:
        if result is None:
            raise RuntimeError("render batch completed without a rendered path")
        completed.append(result)
    return completed


def render_batch(
    requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None
) -> list[Path]:
    """
    Execute a batch of render requests.

    Args:
        requests: List of requests to process
        parallelism: Number of concurrent threads
        reporter: Optional progress reporter

    Returns:
        List of paths to rendered files in input order

    Raises:
        Exception: The first exception encountered during rendering (fail-fast).
            Note that when executing in parallel, already-running tasks on other
            threads will continue executing in the background after the exception
            is raised, but no new tasks will be scheduled and the function returns
            immediately.
    """
    if not requests:
        return []

    results: list[Path | None] = [None] * len(requests)

    if reporter:
        reporter.start_phase("Rendering", len(requests))

    try:
        if parallelism <= 1:
            _render_batch_sequential(requests, results, reporter)
        else:
            _render_batch_parallel(requests, results, parallelism, reporter)
    finally:
        if reporter:
            reporter.complete_phase()

    return _completed_render_results(results)


def render_screenshots(
    clips: list[Path],
    frames: list[int],
    output_dir: Path,
    config: ConfigSchema,
    options: ScreenshotRenderOptions | None = None,
) -> dict[str, list[Path]]:
    """Render multiple frames from multiple clips.

    Args:
        clips: List of video paths
        frames: List of frame indices to render
        output_dir: Base output directory
        config: Resolved configuration (required for tonemap gating)
        options: Render options for labels, renderer, overlay, progress, and FFmpeg probing

    Returns:
        Dict mapping label -> list of rendered screenshot paths

    Raises:
        TonemapRequiresVapourSynthError: If HDR + enable_tonemap=True on FFmpeg-only path
        PluginNotFoundError: If required VS plugin is missing (renderer=vapoursynth)
        SourceLoadError: If source loading fails (renderer=vapoursynth)
        FFmpegNotFoundError: If ffprobe is missing for HDR probe
        RenderError: For other rendering failures
    """
    resolved_options = options or ScreenshotRenderOptions()
    label_map = resolved_options.label_map or {}

    if resolved_options.output_frames is not None and len(resolved_options.output_frames) != len(
        frames
    ):
        raise ValueError("output_frames must have the same length as frames")
    if resolved_options.selection_labels is not None and len(
        resolved_options.selection_labels
    ) != len(frames):
        raise ValueError("selection_labels must have the same length as frames")

    batch_requests: list[ScreenshotBatchRequest] = []
    for clip_path in clips:
        label = label_map.get(clip_path, clip_path.stem)
        display_frames = (
            resolved_options.output_frames if resolved_options.output_frames is not None else frames
        )
        sel_labels: list[str | None] = (
            resolved_options.selection_labels
            if resolved_options.selection_labels is not None
            else [None] * len(frames)
        )

        req = ScreenshotBatchRequest(
            clip_path=clip_path,
            label=label,
            source_frames=frames,
            display_frames=display_frames,
            selection_labels=sel_labels,
            probe_width=None,
            probe_height=None,
            probe_num_frames=None,
            probe_is_hdr=_resolve_probe_is_hdr(
                clip_path,
                config=config,
                renderer=resolved_options.renderer,
                ffmpeg_runner=resolved_options.ffmpeg_runner,
            ),
        )
        batch_requests.append(req)

    return render_screenshots_from_batch(
        batch_requests=batch_requests,
        output_dir=output_dir,
        config=config,
        overlay_mode=resolved_options.overlay_mode,
        renderer=resolved_options.renderer,
        ffmpeg_runner=resolved_options.ffmpeg_runner,
        reporter=resolved_options.reporter,
    )


def render_screenshots_from_batch(
    batch_requests: list[ScreenshotBatchRequest],
    output_dir: Path,
    config: ConfigSchema,
    overlay_mode: OverlayMode,
    renderer: Renderer = "auto",
    ffmpeg_runner: FFmpegRunner | None = None,
    reporter: ProgressReporter | None = None,
) -> dict[str, list[Path]]:
    """Render screenshots from batch requests, choosing FFmpeg or VapourSynth path accordingly.

    Args:
        batch_requests: List of ScreenshotBatchRequest
        output_dir: Output directory
        config: Configuration
        overlay_mode: Overlay mode
        renderer: Renderer choice ("vapoursynth", "ffmpeg", or "auto")
        ffmpeg_runner: Optional FFmpegRunner
        reporter: Optional progress reporter

    Returns:
        Dict mapping label -> list of rendered screenshot paths
    """
    resolved_ffmpeg_runner = resolve_batch_ffmpeg_runner(ffmpeg_runner)
    target_renderer = resolve_target_renderer(config, renderer)

    validate_ffmpeg_batch_tonemap_gate(batch_requests, config, target_renderer)
    validate_batch_requests(batch_requests)

    all_requests, label_to_range = expand_batch_render_requests(
        batch_requests,
        output_dir=output_dir,
        config=config,
        overlay_mode=overlay_mode,
        renderer=target_renderer,
        ffmpeg_runner=resolved_ffmpeg_runner,
    )

    # Execute all requests in a single batch
    rendered_paths = render_batch(all_requests, parallelism=1, reporter=reporter)
    return render_batch_results_by_label(batch_requests, rendered_paths, label_to_range)
