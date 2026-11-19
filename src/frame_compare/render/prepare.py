from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from frame_compare.config.schema_enums import TonemapSpeed
from frame_compare.render.types import PreparedRenderSource
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.media_facts import PresentationState

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.config.schema import ConfigSchema
    from frame_compare.vs.loader import VSLoader
    from frame_compare.vs.types import AppliedTonemap, SourceInfo, TonemapSettings


def should_tonemap(source_info: SourceInfo, config: ConfigSchema) -> bool:
    return source_info.is_hdr and config.color.enable_tonemap


def resolve_tonemap_settings(config: ConfigSchema) -> TonemapSettings:
    from frame_compare.vs.tonemap import get_preset_settings
    from frame_compare.vs.tonemap_presets import CURVE_PARAMETER_DEFAULTS

    preset = config.color.preset
    settings = get_preset_settings(preset)

    explicit_color_fields = config.color.model_fields_set

    if "target_nits" in explicit_color_fields:
        settings = replace(settings, target_nits=config.color.target_nits)
    if "tone_curve" in explicit_color_fields:
        # The plugin's generic parameter has different meanings across curves.
        # Do not carry a preset's tuned knee into spline contrast or Reinhard.
        parameter = (
            settings.knee_offset
            if config.color.tone_curve is settings.tone_curve
            else CURVE_PARAMETER_DEFAULTS[config.color.tone_curve]
        )
        settings = replace(settings, tone_curve=config.color.tone_curve, knee_offset=parameter)
    if "gamma_lift" in explicit_color_fields:
        settings = replace(settings, gamma_lift=config.color.gamma_lift)
    if "contrast_recovery" in explicit_color_fields:
        settings = replace(settings, contrast_recovery=config.color.contrast_recovery)

    settings = replace(settings, tonemap_speed=config.color.tonemap_speed)
    if config.color.tonemap_speed is TonemapSpeed.FAST:
        settings = replace(settings, dynamic_peak_detection=False)

    return settings


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


def prepare_clip_for_render(
    clip_path: Path,
    config: ConfigSchema,
    *,
    vs_loader: VSLoader | None = None,
) -> PreparedRenderSource:
    from frame_compare.render.errors import RenderError
    from frame_compare.vs.errors import (
        PluginNotFoundError,
        SourceLoadError,
        VapourSynthNotFoundError,
    )

    raise_if_cancelling()
    try:
        from frame_compare.vs.loader import DefaultVSLoader

        loader = vs_loader or DefaultVSLoader(
            memory_limit_mb=config.runtime.memory_limit_mb,
            scan_frame_geometry=config.sources.scan_frame_geometry,
        )
        raise_if_cancelling()
        source_info = loader.load(clip_path)
        prepared_clip, tonemap = _apply_vs_tonemap_and_labeling(
            source_info.clip, source_info, config
        )
    except (VapourSynthNotFoundError, PluginNotFoundError, SourceLoadError):
        raise
    except Exception as e:
        raise RenderError(reason=f"{type(e).__name__}: {e}") from e

    raise_if_cancelling()
    presentation_state = (
        PresentationState.HDR_TONEMAPPED
        if tonemap is not None
        else PresentationState.HDR_TONEMAP_OFF
        if source_info.is_hdr
        else PresentationState.SDR
    )
    return PreparedRenderSource(
        diagnostic_source=source_info.clip,
        prepared_clip=prepared_clip,
        source_dimensions=(source_info.width, source_info.height),
        source_total_frames=source_info.num_frames,
        presentation_state=presentation_state,
        tonemap=tonemap,
    )
