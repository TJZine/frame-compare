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
)
from frame_compare.utils.progress_protocol import ProgressReporter

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore[import-untyped]

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
    config: ConfigSchema, cli_overrides: dict[str, object] | None = None
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
    preset_name = (cli_overrides or {}).get("tm_preset") or config.color.preset.value
    if preset_name is None:
        preset_name = "reference"
    settings = get_preset_settings(str(preset_name))

    # Apply config overrides (config values always have defaults; direct access)
    settings = replace(settings, target_nits=config.color.target_nits)
    settings = replace(settings, tone_curve=config.color.tone_curve.value)
    settings = replace(settings, gamma_lift=config.color.gamma_lift)
    settings = replace(settings, contrast_recovery=config.color.contrast_recovery)

    # Apply CLI overrides (highest priority)
    if cli_overrides:
        if cli_overrides.get("tm_target") is not None:
            settings = replace(settings, target_nits=int(cli_overrides["tm_target"]))  # type: ignore[arg-type]
        if cli_overrides.get("tm_curve") is not None:
            settings = replace(settings, tone_curve=str(cli_overrides["tm_curve"]))

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
        TonemapRequiresVapourSynthError,
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

            # === TONEMAP INTEGRATION POINT (§1.4.3) ===
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

        except (VapourSynthNotFoundError, PluginNotFoundError, SourceLoadError) as exc:
            if renderer == "vapoursynth":
                raise
            # Store failure for fallback logic
            vs_load_failure = exc
        except Exception as e:
            if renderer == "vapoursynth":
                raise RenderError(reason=f"{type(e).__name__}: {e}") from e
            vs_load_failure = e

    # === DETERMINISTIC FALLBACK LOGIC (§1.4.1, §1.4.4) ===
    if vs_load_failure is not None and renderer == "auto":
        # VS load failed, check if we can fall back to FFmpeg
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

    # === RENDERER=FFMPEG WITH TONEMAP GATING (§1.4.4) ===
    if renderer == "ffmpeg" and config.color.enable_tonemap:
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

    return loaded_clip, resolution, hdr_info, source_info


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
    all_requests: list[RenderRequest] = []

    if output_frames is not None and len(output_frames) != len(frames):
        raise ValueError("output_frames must have the same length as frames")
    if selection_labels is not None and len(selection_labels) != len(frames):
        raise ValueError("selection_labels must have the same length as frames")

    # Store labels in order to preserve clip ordering in result dict
    ordered_labels: list[str] = []

    for clip_path in clips:
        label = label_map.get(clip_path, clip_path.stem)
        ordered_labels.append(label)

        loaded_clip, resolution, hdr_info, source_info = _prepare_clip_for_render(
            clip_path, renderer, config, ffmpeg_runner=ffmpeg_runner
        )

        for idx, frame in enumerate(frames):
            output_frame = output_frames[idx] if output_frames is not None else frame
            output_path = generate_screenshot_path(output_dir, label, output_frame)
            selection_label = selection_labels[idx] if selection_labels is not None else None

            overlay: OverlayConfig | None = None
            if overlay_mode != OverlayMode.NONE:
                overlay = OverlayConfig(
                    mode=overlay_mode,
                    label=label,
                    frame_number=frame,
                    display_frame_number=output_frame,
                    num_frames=source_info.num_frames if source_info is not None else None,
                    selection_label=selection_label,
                    resolution=resolution,
                    hdr_info=hdr_info,
                    font_path=None,
                )

            req = RenderRequest(
                clip=loaded_clip,
                frame_number=frame,
                output_path=output_path,
                overlay=overlay,
                encoder_settings=EncoderSettings(),
            )
            all_requests.append(req)

    # Execute batch
    # Plan says: "Delegate execution to render_batch". Default parallelism=1.
    rendered_paths = render_batch(all_requests, parallelism=1, reporter=reporter)

    # Reconstruct results dict
    results: dict[str, list[Path]] = {}
    path_idx = 0
    for label in ordered_labels:
        results[label] = []
        for _ in frames:
            results[label].append(rendered_paths[path_idx])
            path_idx += 1

    return results
