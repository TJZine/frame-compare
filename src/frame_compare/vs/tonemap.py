"""HDR tonemapping module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from frame_compare.vs import tonemap_conversion as _conversion
from frame_compare.vs import tonemap_libplacebo as _libplacebo
from frame_compare.vs.env import detect_plugins
from frame_compare.vs.tonemap_fallback import fallback_tonemap
from frame_compare.vs.tonemap_presets import TONEMAP_PRESETS, get_preset_settings
from frame_compare.vs.tonemap_runtime import (
    LibplaceboRuntimeState,
    libplacebo_runtime_usable,
    probe_libplacebo_runtime,
)
from frame_compare.vs.types import HDRMetadata, TonemapSettings

if TYPE_CHECKING:
    import vapoursynth as vs

_HdrTonemapInputs = _conversion.HdrTonemapInputs
_apply_post_processing = _conversion.apply_post_processing
_convert_non_rgb_with_matrix_hint = _conversion.convert_non_rgb_with_matrix_hint
_deduce_src_csp_hint = _conversion.deduce_src_csp_hint
_normalize_rgb_props = _conversion.normalize_rgb_props
_resolve_hdr_tonemap_inputs = _conversion.resolve_hdr_tonemap_inputs
_to_rgbs = _conversion.to_rgbs
_validate_target_nits = _conversion.validate_target_nits
_fallback_tonemap = fallback_tonemap
_TONE_CURVE_MAP = _libplacebo.TONE_CURVE_MAP
_apply_libplacebo = _libplacebo.apply_libplacebo
_build_libplacebo_tonemap_kwargs = _libplacebo.build_libplacebo_tonemap_kwargs
_call_libplacebo_with_compat_retry = _libplacebo.call_libplacebo_with_compat_retry
_convert_for_libplacebo = _libplacebo.convert_for_libplacebo
_TONEMAP_PRESETS = TONEMAP_PRESETS
_LibplaceboRuntimeState = LibplaceboRuntimeState
_LIBPLACEBO_RUNTIME_STATE = _LibplaceboRuntimeState()


def _probe_libplacebo_runtime() -> bool:
    """Run the subprocess probe to check if libplacebo is usable."""
    return probe_libplacebo_runtime()


def _libplacebo_runtime_usable() -> bool:
    """Return whether libplacebo is safe to call in this process."""
    return libplacebo_runtime_usable(_LIBPLACEBO_RUNTIME_STATE, _probe_libplacebo_runtime)


def apply_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """Apply HDR to SDR tonemapping."""
    if not settings.enabled:
        return clip
    _validate_target_nits(settings)

    import vapoursynth as vs

    core = vs.core

    plugins = detect_plugins(core)

    if plugins.get("libplacebo", False) and _libplacebo_runtime_usable():
        result = _apply_libplacebo(clip, settings, core, hdr_metadata)
        if result is not None:
            return result
    return _fallback_tonemap(clip, settings, hdr_metadata)


__all__ = [
    "_HdrTonemapInputs",
    "_LIBPLACEBO_RUNTIME_STATE",
    "_LibplaceboRuntimeState",
    "_TONEMAP_PRESETS",
    "_TONE_CURVE_MAP",
    "_apply_libplacebo",
    "_apply_post_processing",
    "_build_libplacebo_tonemap_kwargs",
    "_call_libplacebo_with_compat_retry",
    "_convert_for_libplacebo",
    "_convert_non_rgb_with_matrix_hint",
    "_deduce_src_csp_hint",
    "_fallback_tonemap",
    "_libplacebo_runtime_usable",
    "_normalize_rgb_props",
    "_probe_libplacebo_runtime",
    "_resolve_hdr_tonemap_inputs",
    "_to_rgbs",
    "_validate_target_nits",
    "apply_tonemap",
    "get_preset_settings",
]
