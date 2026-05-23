from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from frame_compare.render.types import Renderer

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore[import-untyped]

    from frame_compare.config.overrides import TonemapCliOverrides
    from frame_compare.config.schema import ConfigSchema
    from frame_compare.render.ffmpeg import FFmpegRunner
    from frame_compare.vs.types import SourceInfo, TonemapSettings

log = structlog.get_logger()


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


def is_hdr_via_runner(path: Path, runner: FFmpegRunner) -> bool:
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
    from frame_compare.vs.errors import TonemapRequiresVapourSynthError

    if config.color.enable_tonemap:
        # Must probe HDR status before deciding
        try:
            is_hdr = is_hdr_via_runner(clip_path, ffmpeg_runner)
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
    from frame_compare.vs.errors import TonemapRequiresVapourSynthError

    try:
        is_hdr = is_hdr_via_runner(clip_path, ffmpeg_runner)
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


def prepare_clip_for_render(
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
        tuple containing (prepared_clip, resolution, hdr_info, source_info)

    Raises:
        PluginNotFoundError: If required VS plugin is missing
        SourceLoadError: If source loading fails
        TonemapRequiresVapourSynthError: If HDR + enable_tonemap=True on FFmpeg-only path
        FFmpegNotFoundError: If ffprobe is missing for HDR probe
        RenderError: For other rendering failures
    """
    from frame_compare.errors import (
        RenderError,
        SourceLoadError,
    )
    from frame_compare.vs.errors import (
        PluginNotFoundError,
        VapourSynthNotFoundError,
    )

    if ffmpeg_runner is None:
        from frame_compare.render.ffmpeg import DefaultFFmpegRunner

        ffmpeg_runner = DefaultFFmpegRunner()

    prepared_clip: vs.VideoNode | Path = clip_path
    resolution = (0, 0)
    hdr_info: str | None = None
    source_info: SourceInfo | None = None
    vs_load_failure: Exception | None = None

    if renderer in ("vapoursynth", "auto"):
        try:
            from frame_compare.vs.loader import DefaultVSLoader

            loader = DefaultVSLoader()
            source_info = loader.load(clip_path)
            prepared_clip = source_info.clip
            resolution = (source_info.width, source_info.height)

            prepared_clip, hdr_info = _apply_vs_tonemap_and_labeling(
                prepared_clip, source_info, config
            )

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

    return prepared_clip, resolution, hdr_info, source_info
