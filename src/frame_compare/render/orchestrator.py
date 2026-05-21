from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

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
    - If probe_hdr returns None, check if it was because of missing/unknown metadata.
    - Treat as HDR if transfer is smpte2084 or arib-std-b67 and color_primaries is bt2020.
    - Treat as HDR (returns True) on missing/unknown metadata (transfer or primaries == 2).

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
        return False

    return metadata.transfer in {16, 18, 2} and metadata.color_primaries in {9, 2}


def _render_description(request: RenderRequest) -> str:
    """Build a consistent progress description for a render request."""
    label = request.overlay.label if request.overlay is not None else None
    return f"{label} — Frame {request.frame_number}" if label else f"Frame {request.frame_number}"


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
            for i, req in enumerate(requests):
                if reporter:
                    reporter.set_description(_render_description(req))
                results[i] = render_frame(req)
                if reporter:
                    reporter.advance(1)
        else:
            with ThreadPoolExecutor(max_workers=parallelism) as executor:
                futures: dict[Future[Path], int] = {}
                next_idx = 0
                first_exc: Exception | None = None

                # Initial fill
                while next_idx < min(parallelism, len(requests)):
                    futures[executor.submit(render_frame, requests[next_idx])] = next_idx
                    next_idx += 1

                while futures:
                    done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
                    for f in done:
                        idx = futures.pop(f)
                        try:
                            results[idx] = f.result()
                            if reporter:
                                reporter.set_description(_render_description(requests[idx]))
                                reporter.advance(1)

                            # Submit next if no exception yet
                            if first_exc is None and next_idx < len(requests):
                                futures[executor.submit(render_frame, requests[next_idx])] = (
                                    next_idx
                                )
                                next_idx += 1
                        except Exception as e:
                            if first_exc is None:
                                first_exc = e
                                # Cancel remaining pending tasks
                                for pending_f in futures:
                                    pending_f.cancel()

                    if first_exc:
                        # We continue to wait for already running tasks to finish
                        # but we won't submit more.
                        pass

                if first_exc:
                    raise first_exc

    finally:
        if reporter:
            reporter.complete_phase()

    return cast(list[Path], results)


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


def _assemble_overlay(
    overlay_mode: OverlayMode,
    label: str,
    frame_number: int,
    display_frame_number: int,
    num_frames: int | None,
    selection_label: str | None,
    resolution: tuple[int, int],
    hdr_info: str | None,
) -> OverlayConfig | None:
    """Construct an OverlayConfig if overlay mode is not NONE."""
    if overlay_mode == OverlayMode.NONE:
        return None
    return OverlayConfig(
        mode=overlay_mode,
        label=label,
        frame_number=frame_number,
        display_frame_number=display_frame_number,
        num_frames=num_frames,
        selection_label=selection_label,
        resolution=resolution,
        hdr_info=hdr_info,
        font_path=None,
    )


def render_screenshots(
    clips: list[Path],
    frames: list[int],
    output_dir: Path,
    config: ConfigSchema,
    label_map: dict[Path, str] | None = None,
    renderer: Renderer = "auto",
    overlay_mode: OverlayMode = OverlayMode.STANDARD,
    reporter: ProgressReporter | None = None,
    *,
    output_frames: list[int] | None = None,
    selection_labels: list[str | None] | None = None,
    ffmpeg_runner: FFmpegRunner | None = None,
) -> dict[str, list[Path]]:
    """Render multiple frames from multiple clips.

    Args:
        clips: List of video paths
        frames: List of frame indices to render
        output_frames: Optional list of frame indices used for output filenames and overlay display.
        output_dir: Base output directory
        config: Resolved configuration (required for tonemap gating)
        label_map: Optional mapping of Path -> label string
        renderer: "vapoursynth", "ffmpeg", or "auto"
        overlay_mode: Overlay verbosity
        reporter: Optional progress reporter
        ffmpeg_runner: Optional FFmpegRunner for probing/extraction

    Returns:
        Dict mapping label -> list of rendered screenshot paths

    Raises:
        TonemapRequiresVapourSynthError: If HDR + enable_tonemap=True on FFmpeg-only path
        PluginNotFoundError: If required VS plugin is missing (renderer=vapoursynth)
        SourceLoadError: If source loading fails (renderer=vapoursynth)
        FFmpegNotFoundError: If ffprobe is missing for HDR probe
        RenderError: For other rendering failures
    """
    label_map = label_map or {}

    if output_frames is not None and len(output_frames) != len(frames):
        raise ValueError("output_frames must have the same length as frames")
    if selection_labels is not None and len(selection_labels) != len(frames):
        raise ValueError("selection_labels must have the same length as frames")

    batch_requests: list[ScreenshotBatchRequest] = []
    for clip_path in clips:
        label = label_map.get(clip_path, clip_path.stem)
        display_frames = output_frames if output_frames is not None else frames
        sel_labels: list[str | None] = (
            selection_labels if selection_labels is not None else [None] * len(frames)
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
        overlay_mode=overlay_mode,
        renderer=renderer,
        ffmpeg_runner=ffmpeg_runner,
        reporter=reporter,
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
    if ffmpeg_runner is None:
        from frame_compare.render.ffmpeg import DefaultFFmpegRunner

        ffmpeg_runner = DefaultFFmpegRunner()

    target_renderer = renderer
    if target_renderer == "auto" and config.screenshots.use_ffmpeg:
        target_renderer = "ffmpeg"

    # Fast preflight check if FFmpeg is requested
    if (
        target_renderer == "ffmpeg"
        and config.color.enable_tonemap
        and any(req.probe_is_hdr for req in batch_requests)
    ):
        from frame_compare.errors import TonemapRequiresVapourSynthError

        raise TonemapRequiresVapourSynthError()

    for req in batch_requests:
        _validate_batch_request_lengths(req)

    all_requests: list[RenderRequest] = []
    label_to_range: dict[str, range] = {}
    start_idx = 0

    for req in batch_requests:
        loaded_clip, _, hdr_info, source_info = _prepare_clip_for_render(
            req.clip_path, target_renderer, config, ffmpeg_runner=ffmpeg_runner
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

            overlay = _assemble_overlay(
                overlay_mode=overlay_mode,
                label=req.label,
                frame_number=source_frame,
                display_frame_number=aligned_frame,
                num_frames=num_frames,
                selection_label=selection_label,
                resolution=(width, height),
                hdr_info=resolved_hdr_info,
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

    # Execute all requests in a single batch
    rendered_paths = render_batch(all_requests, parallelism=1, reporter=reporter)

    # Reconstruct results dict maintaining the order of batch requests
    results: dict[str, list[Path]] = {}
    for req in batch_requests:
        r = label_to_range[req.label]
        results[req.label] = rendered_paths[r.start : r.stop]

    return results
