from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.render.types import PreparedRenderSource, Renderer
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.media_facts import PresentationState

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.config.schema import ConfigSchema
    from frame_compare.render.backend.ffmpeg import FFmpegRunner
    from frame_compare.vs.types import AppliedTonemap, SourceInfo, TonemapSettings

log = structlog.get_logger()


def should_tonemap(source_info: SourceInfo, config: ConfigSchema) -> bool:
    return source_info.is_hdr and config.color.enable_tonemap


def resolve_tonemap_settings(config: ConfigSchema) -> TonemapSettings:
    from frame_compare.vs.tonemap import get_preset_settings

    preset = config.color.preset
    settings = get_preset_settings(preset)

    explicit_color_fields = config.color.model_fields_set

    if "target_nits" in explicit_color_fields:
        settings = replace(settings, target_nits=config.color.target_nits)
    if "tone_curve" in explicit_color_fields:
        settings = replace(settings, tone_curve=config.color.tone_curve)
    if "gamma_lift" in explicit_color_fields:
        settings = replace(settings, gamma_lift=config.color.gamma_lift)
    if "contrast_recovery" in explicit_color_fields:
        settings = replace(settings, contrast_recovery=config.color.contrast_recovery)

    return settings


def is_hdr_via_runner(path: Path, runner: FFmpegRunner) -> bool:
    from frame_compare.utils.ffmpeg_errors import FFmpegError, FFmpegNotFoundError
    from frame_compare.vs.errors import SourceLoadError

    raise_if_cancelling()
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
) -> tuple[vs.VideoNode, AppliedTonemap | None]:
    raise_if_cancelling()
    if should_tonemap(source_info, config):
        from frame_compare.vs.tonemap import apply_tonemap

        settings = resolve_tonemap_settings(config)
        result = apply_tonemap(loaded_clip, settings, source_info.hdr_metadata, still_image=True)
        return result.clip, result.applied
    return loaded_clip, None


def _resolve_auto_mode_fallback(
    clip_path: Path,
    vs_load_failure: Exception,
    config: ConfigSchema,
    renderer: Renderer,
    ffmpeg_runner: FFmpegRunner,
    supplied_source_is_hdr: bool | None = None,
) -> bool:
    from frame_compare.vs.errors import TonemapRequiresVapourSynthError

    if supplied_source_is_hdr is None:
        try:
            is_hdr = is_hdr_via_runner(clip_path, ffmpeg_runner)
        except Exception:
            log.debug(
                "probe_failed_no_fallback",
                path=str(clip_path),
                exc_info=True,
            )
            raise
    else:
        is_hdr = supplied_source_is_hdr

    if config.color.enable_tonemap and is_hdr:
        log.debug(
            "hdr_tonemap_required_no_fallback",
            path=str(clip_path),
        )
        raise TonemapRequiresVapourSynthError() from vs_load_failure

    log.warning(
        "vs_load_failed_falling_back",
        path=str(clip_path),
        renderer=renderer,
        exc_info=True,
    )
    return is_hdr


def _validate_ffmpeg_tonemap_gate(
    clip_path: Path,
    config: ConfigSchema,
    ffmpeg_runner: FFmpegRunner,
    supplied_source_is_hdr: bool | None = None,
) -> bool:
    from frame_compare.vs.errors import TonemapRequiresVapourSynthError

    if supplied_source_is_hdr is None:
        try:
            is_hdr = is_hdr_via_runner(clip_path, ffmpeg_runner)
        except Exception:
            log.debug(
                "probe_failed_no_ffmpeg",
                path=str(clip_path),
                exc_info=True,
            )
            raise
    else:
        is_hdr = supplied_source_is_hdr

    if is_hdr:
        raise TonemapRequiresVapourSynthError()
    return is_hdr


def prepare_clip_for_render(
    clip_path: Path,
    renderer: Renderer,
    config: ConfigSchema,
    ffmpeg_runner: FFmpegRunner | None = None,
    source_is_hdr: bool | None = None,
) -> PreparedRenderSource:
    from frame_compare.render.errors import RenderError
    from frame_compare.vs.errors import (
        PluginNotFoundError,
        SourceLoadError,
        VapourSynthNotFoundError,
    )

    raise_if_cancelling()
    if ffmpeg_runner is None:
        from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner

        ffmpeg_runner = DefaultFFmpegRunner()

    prepared_clip: vs.VideoNode | Path = clip_path
    resolution = (0, 0)
    diagnostic_source: vs.VideoNode | Path = clip_path
    tonemap: AppliedTonemap | None = None
    source_info: SourceInfo | None = None
    vs_load_failure: Exception | None = None
    fallback_source_is_hdr: bool | None = None
    ffmpeg_source_is_hdr: bool | None = None

    if renderer in ("vapoursynth", "auto"):
        try:
            from frame_compare.vs.loader import DefaultVSLoader

            loader = DefaultVSLoader(memory_limit_mb=config.runtime.memory_limit_mb)
            raise_if_cancelling()
            source_info = loader.load(clip_path)
            diagnostic_source = source_info.clip
            prepared_clip = source_info.clip
            resolution = (source_info.width, source_info.height)

            prepared_clip, tonemap = _apply_vs_tonemap_and_labeling(
                prepared_clip, source_info, config
            )

        except (VapourSynthNotFoundError, PluginNotFoundError, SourceLoadError) as exc:
            if renderer == "vapoursynth":
                raise
            vs_load_failure = exc
        except Exception as e:
            raise RenderError(reason=f"{type(e).__name__}: {e}") from e

    raise_if_cancelling()

    if vs_load_failure is not None and renderer == "auto":
        if config.screenshots.vs_writer == VsScreenshotWriter.FPNG:
            raise vs_load_failure
        fallback_source_is_hdr = _resolve_auto_mode_fallback(
            clip_path,
            vs_load_failure,
            config,
            renderer,
            ffmpeg_runner,
            supplied_source_is_hdr=source_is_hdr,
        )

    if renderer == "ffmpeg" and config.color.enable_tonemap:
        ffmpeg_source_is_hdr = _validate_ffmpeg_tonemap_gate(
            clip_path,
            config,
            ffmpeg_runner,
            supplied_source_is_hdr=source_is_hdr,
        )

    resolved_source_is_hdr = (
        source_info.is_hdr
        if source_info is not None
        else fallback_source_is_hdr
        if fallback_source_is_hdr is not None
        else source_is_hdr
        if source_is_hdr is not None
        else ffmpeg_source_is_hdr
        if ffmpeg_source_is_hdr is not None
        else is_hdr_via_runner(clip_path, ffmpeg_runner)
        if renderer == "ffmpeg"
        else False
    )
    presentation_state = (
        PresentationState.HDR_TONEMAPPED
        if tonemap is not None
        else PresentationState.HDR_TONEMAP_OFF
        if resolved_source_is_hdr
        else PresentationState.SDR
    )
    return PreparedRenderSource(
        diagnostic_source=diagnostic_source,
        prepared_clip=prepared_clip,
        source_dimensions=resolution,
        source_total_frames=source_info.num_frames if source_info is not None else None,
        source_is_hdr=resolved_source_is_hdr,
        presentation_state=presentation_state,
        tonemap=tonemap,
    )
