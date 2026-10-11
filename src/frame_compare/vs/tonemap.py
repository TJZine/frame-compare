"""HDR tonemapping module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from frame_compare.vs import (
    env,
    tonemap_conversion,
    tonemap_fallback,
    tonemap_libplacebo,
    tonemap_runtime,
)
from frame_compare.vs.tonemap_presets import get_preset_settings
from frame_compare.vs.types import HDRMetadata, TonemapSettings

if TYPE_CHECKING:
    import vapoursynth as vs

_LIBPLACEBO_RUNTIME_STATE = tonemap_runtime.LibplaceboRuntimeState()


def _libplacebo_runtime_usable() -> bool:
    """Return whether libplacebo is safe to call in this process."""
    return tonemap_runtime.libplacebo_runtime_usable(
        _LIBPLACEBO_RUNTIME_STATE,
        tonemap_runtime.probe_libplacebo_runtime,
    )


def apply_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """Apply HDR to SDR tonemapping."""
    if not settings.enabled:
        return clip
    tonemap_conversion.validate_target_nits(settings)

    import vapoursynth as vs

    core = vs.core

    plugins = env.detect_plugins(core)

    if plugins.get("libplacebo", False) and _libplacebo_runtime_usable():
        result = tonemap_libplacebo.apply_libplacebo(clip, settings, core, hdr_metadata)
        if result is not None:
            return result
    return tonemap_fallback.fallback_tonemap(clip, settings, hdr_metadata)


__all__ = [
    "apply_tonemap",
    "get_preset_settings",
]
