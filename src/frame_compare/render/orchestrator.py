from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from frame_compare.render.encoders import render_frame
from frame_compare.render.naming import generate_screenshot_path
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    OverlayMode,
    Renderer,
    RenderRequest,
    ScreenshotBatchRequest,
    ScreenshotRenderOptions,
)
from frame_compare.utils.progress_protocol import ProgressReporter

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore[import-untyped]

    from frame_compare.config.overrides import TonemapCliOverrides
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.render.ffmpeg import FFmpegRunner
    from frame_compare.vs.types import SourceInfo, TonemapSettings

log = structlog.get_logger()


# ─── Tonemap Helper Functions (SSOT: render-module.md §1.4) ────────────────────


def should_tonemap(source_info: SourceInfo, config: ConfigSchema) -> bool:
    """Determine if tonemap MUST be applied.

    Args:
        source_info: Loaded source metadata from VSLoader
        config: Resolved configuration

    Returns:
        True if tonemap MUST be applied
    """
    return source_info.is_hdr and config.color.enable_tonemap


def resolve_tonemap_settings(
    config: ConfigSchema, cli_overrides: TonemapCliOverrides | None = None
) -> TonemapSettings:
    """Resolve tonemap settings from config and CLI overrides.

    Args:
        config: Resolved configuration
        cli_overrides: Optional CLI flag overrides (tm_preset, tm_target, tm_curve)

    Returns:
        Complete TonemapSettings ready for apply_tonemap()
    """
    from frame_compare.vs.tonemap import get_preset_settings

    # Start with preset
    preset = (cli_overrides or {}).get("tm_preset") or config.color.preset
    settings = get_preset_settings(preset)

    # Apply config overrides (config values always have defaults; direct access)
    settings = replace(settings, target_nits=config.color.target_nits)
    settings = replace(settings, tone_curve=config.color.tone_curve)
    settings = replace(settings, gamma_lift=config.color.gamma_lift)
    settings = replace(settings, contrast_recovery=config.color.contrast_recovery)

    # Apply CLI overrides (highest priority)
    if cli_overrides:
        target_val = cli_overrides.get("tm_target")
        if target_val is not None:
            settings = replace(settings, target_nits=target_val)
        curve_val = cli_overrides.get("tm_curve")
        if curve_val is not None:
            settings = replace(settings, tone_curve=curve_val)

    return settings


def _is_hdr_via_runner(path: Path, runner: FFmpegRunner) -> bool:
    """Determine HDR using the provided FFmpegRunner.

    Preserves the existing conservative fallback behavior:
    - Treat as HDR (returns True) if metadata is None (indicates missing/unspecified/unknown metadata).
    - Otherwise, treat as HDR if transfer characteristics are PQ (16) or HLG (18) and color primaries are BT.2020 (9).

    Raises:
        FFmpegNotFoundError: If ffprobe is missing.
        SourceLoadError: If probing fails or times out.
    """
    from frame_compare.errors import FFmpegError, FFmpegNotFoundError, SourceLoadError

    try:
        metadata = runner.probe_hdr(path)
    except FFmpegNotFoundError:
        raise
    except FFmpegError as exc:
        msg = exc.context.message
        if exc.context.details and "stderr" in exc.context.details:
            stderr = str(exc.context.details["stderr"])
            msg = f"{msg}: {stderr}"
        raise SourceLoadError(path, msg) from exc
    except Exception as exc:
        raise SourceLoadError(path, f"ffprobe failed: {exc}") from exc

    if metadata is None:
        return True

    return metadata.transfer in {16, 18} and metadata.color_primaries == 9


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
    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures: dict[Future[Path], int] = {}
        next_index = 0
        first_exception: Exception | None = None

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
                    if first_exception is None:
                        first_exception = exc
                        for pending_future in futures:
                            pending_future.cancel()
                    continue

                if first_exception is None and next_index < len(requests):
                    _submit_render_request(executor, requests, futures, next_index)
                    next_index += 1

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
        Exception: The first exception encountered during rendering (fail-fast)
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


def _apply_vs_tonemap_and_labeling(
    loaded_clip: vs.VideoNode,
    source_info: SourceInfo,
    config: ConfigSchema,
) -> tuple[vs.VideoNode, str | None]:
    """Handles VapourSynth tonemap settings resolution and application."""
    if should_tonemap(source_info, config):
        from frame_compare.vs.tonemap import apply_tonemap

        settings = resolve_tonemap_settings(config)
        loaded_clip = apply_tonemap(loaded_clip, settings, source_info.hdr_metadata)
        # Mark that tonemap was applied for overlay (§1.4.6)
        hdr_info = f"HDR (tonemapped: {settings.preset}, {settings.target_nits} nits)"
    elif source_info.is_hdr:
        # HDR source, tonemap disabled (§1.4.6)
        hdr_info = "HDR (native, no tonemap)"
    else:
        # SDR source
        hdr_info = None  # or "SDR" in DIAGNOSTIC mode
    return loaded_clip, hdr_info


def _resolve_auto_mode_fallback(
    clip_path: Path,
    vs_load_failure: Exception,
    config: ConfigSchema,
    renderer: Renderer,
    ffmpeg_runner: FFmpegRunner,
) -> None:
    """Probes HDR and resolves fallback policy when VapourSynth load fails in auto mode."""
    from frame_compare.errors import TonemapRequiresVapourSynthError

    if config.color.enable_tonemap:
        # Must probe HDR status before deciding
        try:
            is_hdr = _is_hdr_via_runner(clip_path, ffmpeg_runner)
        except Exception:
            # Probe failed — propagate (no fallback)
            log.debug(
                "probe_failed_no_fallback",
                path=str(clip_path),
                exc_info=True,
            )
            raise  # Propagate probe exception

        if is_hdr:
            # HDR + tonemap required in auto mode + VS unavailable → raise TonemapRequiresVapourSynthError from original VS failure.
            log.debug(
                "hdr_tonemap_required_no_fallback",
                path=str(clip_path),
            )
            raise TonemapRequiresVapourSynthError() from vs_load_failure
        else:
            # SDR — fallback allowed
            log.warning(
                "vs_load_failed_falling_back",
                path=str(clip_path),
                renderer=renderer,
                exc_info=True,
            )
    else:
        # enable_tonemap=False — fallback allowed
        log.warning(
            "vs_load_failed_falling_back",
            path=str(clip_path),
            renderer=renderer,
            exc_info=True,
        )


def _validate_ffmpeg_tonemap_gate(
    clip_path: Path,
    config: ConfigSchema,
    ffmpeg_runner: FFmpegRunner,
) -> None:
    """Validates whether the tonemap gate is violated for FFmpeg renderer."""
    from frame_compare.errors import TonemapRequiresVapourSynthError

    try:
        is_hdr = _is_hdr_via_runner(clip_path, ffmpeg_runner)
    except Exception:
        # Probe failed — propagate (no FFmpeg path)
        log.debug(
            "probe_failed_no_ffmpeg",
            path=str(clip_path),
            exc_info=True,
        )
        raise  # Propagate probe exception

    if is_hdr:
        # HDR + tonemap required → FFmpeg-only path is invalid.
        raise TonemapRequiresVapourSynthError()


def _prepare_clip_for_render(
    clip_path: Path,
    renderer: Renderer,
    config: ConfigSchema,
    ffmpeg_runner: FFmpegRunner | None = None,
) -> tuple[vs.VideoNode | Path, tuple[int, int], str | None, SourceInfo | None]:
    """Prepare a source clip for rendering, applying tonemap and fallback policies.

    Args:
        clip_path: Path to the video file
        renderer: Renderer to use ("vapoursynth", "ffmpeg", or "auto")
        config: Resolved configuration
        ffmpeg_runner: Optional FFmpegRunner for probing/extraction

    Returns:
        tuple containing (loaded_clip, resolution, hdr_info, source_info)

    Raises:
        PluginNotFoundError: If required VS plugin is missing
        SourceLoadError: If source loading fails
        TonemapRequiresVapourSynthError: If HDR + enable_tonemap=True on FFmpeg-only path
        FFmpegNotFoundError: If ffprobe is missing for HDR probe
        RenderError: For other rendering failures
    """
    from frame_compare.errors import (
        PluginNotFoundError,
        RenderError,
        SourceLoadError,
        VapourSynthNotFoundError,
    )

    if ffmpeg_runner is None:
        from frame_compare.render.ffmpeg import DefaultFFmpegRunner

        ffmpeg_runner = DefaultFFmpegRunner()

    loaded_clip: vs.VideoNode | Path = clip_path
    resolution = (0, 0)
    hdr_info: str | None = None
    source_info: SourceInfo | None = None
    vs_load_failure: Exception | None = None

    if renderer in ("vapoursynth", "auto"):
        try:
            from frame_compare.vs.loader import DefaultVSLoader

            loader = DefaultVSLoader()
            source_info = loader.load(clip_path)
            loaded_clip = source_info.clip
            resolution = (source_info.width, source_info.height)

            loaded_clip, hdr_info = _apply_vs_tonemap_and_labeling(loaded_clip, source_info, config)

        except (VapourSynthNotFoundError, PluginNotFoundError, SourceLoadError) as exc:
            if renderer == "vapoursynth":
                raise
            # Store failure for fallback logic
            vs_load_failure = exc
        except Exception as e:
            raise RenderError(reason=f"{type(e).__name__}: {e}") from e

    # === DETERMINISTIC FALLBACK LOGIC (§1.4.1, §1.4.4) ===
    if vs_load_failure is not None and renderer == "auto":
        _resolve_auto_mode_fallback(clip_path, vs_load_failure, config, renderer, ffmpeg_runner)

    # === RENDERER=FFMPEG WITH TONEMAP GATING (§1.4.4) ===
    if renderer == "ffmpeg" and config.color.enable_tonemap:
        _validate_ffmpeg_tonemap_gate(clip_path, config, ffmpeg_runner)

    return loaded_clip, resolution, hdr_info, source_info


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
            probe_width=0,
            probe_height=0,
            probe_num_frames=0,
            probe_is_hdr=False,
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


def _resolve_target_renderer(config: ConfigSchema, renderer: Renderer) -> Renderer:
    if renderer == "auto" and config.screenshots.use_ffmpeg:
        return "ffmpeg"
    return renderer


def _validate_ffmpeg_batch_tonemap_gate(
    batch_requests: list[ScreenshotBatchRequest],
    config: ConfigSchema,
    renderer: Renderer,
) -> None:
    if (
        renderer == "ffmpeg"
        and config.color.enable_tonemap
        and any(req.probe_is_hdr for req in batch_requests)
    ):
        from frame_compare.errors import TonemapRequiresVapourSynthError

        raise TonemapRequiresVapourSynthError()


def _resolve_batch_ffmpeg_runner(ffmpeg_runner: FFmpegRunner | None) -> FFmpegRunner:
    if ffmpeg_runner is not None:
        return ffmpeg_runner

    from frame_compare.render.ffmpeg import DefaultFFmpegRunner

    return DefaultFFmpegRunner()


def _validate_batch_requests(batch_requests: list[ScreenshotBatchRequest]) -> None:
    for req in batch_requests:
        _validate_batch_request_lengths(req)


def _build_overlay_config(
    request: ScreenshotBatchRequest,
    *,
    overlay_mode: OverlayMode,
    source_frame: int,
    display_frame: int,
    selection_label: str | None,
    resolution: tuple[int, int],
    hdr_info: str | None,
    num_frames: int,
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
        resolution=resolution,
        hdr_info=hdr_info,
        font_path=None,
    )


def _expand_batch_render_requests(
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
        loaded_clip, _, hdr_info, source_info = _prepare_clip_for_render(
            req.clip_path, renderer, config, ffmpeg_runner=ffmpeg_runner
        )

        width = source_info.width if source_info is not None else req.probe_width
        height = source_info.height if source_info is not None else req.probe_height
        num_frames = source_info.num_frames if source_info is not None else req.probe_num_frames
        resolved_hdr_info = (
            hdr_info if source_info is not None else ("HDR" if req.probe_is_hdr else None)
        )

        num_frames_for_req = len(req.source_frames)
        label_to_range[req.label] = range(start_idx, start_idx + num_frames_for_req)
        start_idx += num_frames_for_req

        for idx, source_frame in enumerate(req.source_frames):
            aligned_frame = req.display_frames[idx]
            selection_label = req.selection_labels[idx]

            output_path = generate_screenshot_path(output_dir, req.label, aligned_frame)
            overlay = _build_overlay_config(
                req,
                overlay_mode=overlay_mode,
                source_frame=source_frame,
                display_frame=aligned_frame,
                selection_label=selection_label,
                resolution=(width, height),
                hdr_info=resolved_hdr_info,
                num_frames=num_frames,
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


def _render_batch_results_by_label(
    batch_requests: list[ScreenshotBatchRequest],
    rendered_paths: list[Path],
    label_to_range: dict[str, range],
) -> dict[str, list[Path]]:
    results: dict[str, list[Path]] = {}
    for req in batch_requests:
        result_range = label_to_range[req.label]
        results[req.label] = rendered_paths[result_range.start : result_range.stop]
    return results


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
    resolved_ffmpeg_runner = _resolve_batch_ffmpeg_runner(ffmpeg_runner)
    target_renderer = _resolve_target_renderer(config, renderer)

    _validate_ffmpeg_batch_tonemap_gate(batch_requests, config, target_renderer)
    _validate_batch_requests(batch_requests)

    all_requests, label_to_range = _expand_batch_render_requests(
        batch_requests,
        output_dir=output_dir,
        config=config,
        overlay_mode=overlay_mode,
        renderer=target_renderer,
        ffmpeg_runner=resolved_ffmpeg_runner,
    )

    # Execute all requests in a single batch
    rendered_paths = render_batch(all_requests, parallelism=1, reporter=reporter)
    return _render_batch_results_by_label(batch_requests, rendered_paths, label_to_range)
