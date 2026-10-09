"""VapourSynth module for frame-compare."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frame_compare.vs.env import (
        detect_plugins,
        ensure_vs_environment,
        is_vapoursynth_available,
        require_plugin,
    )
    from frame_compare.vs.loader import DefaultVSLoader, VSLoader
    from frame_compare.vs.props import detect_hdr
    from frame_compare.vs.source import LWLibavSourceOptions, apply_trim, load_source
    from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings
    from frame_compare.vs.types import HDRMetadata, SourceInfo, TonemapSettings


_EXPORTS: dict[str, tuple[str, str]] = {
    # env
    "detect_plugins": ("frame_compare.vs.env", "detect_plugins"),
    "ensure_vs_environment": ("frame_compare.vs.env", "ensure_vs_environment"),
    "is_vapoursynth_available": ("frame_compare.vs.env", "is_vapoursynth_available"),
    "require_plugin": ("frame_compare.vs.env", "require_plugin"),
    # loader
    "DefaultVSLoader": ("frame_compare.vs.loader", "DefaultVSLoader"),
    "VSLoader": ("frame_compare.vs.loader", "VSLoader"),
    # props
    "detect_hdr": ("frame_compare.vs.props", "detect_hdr"),
    # source
    "LWLibavSourceOptions": ("frame_compare.vs.source", "LWLibavSourceOptions"),
    "apply_trim": ("frame_compare.vs.source", "apply_trim"),
    "load_source": ("frame_compare.vs.source", "load_source"),
    # tonemap
    "apply_tonemap": ("frame_compare.vs.tonemap", "apply_tonemap"),
    "get_preset_settings": ("frame_compare.vs.tonemap", "get_preset_settings"),
    # types
    "HDRMetadata": ("frame_compare.vs.types", "HDRMetadata"),
    "SourceInfo": ("frame_compare.vs.types", "SourceInfo"),
    "TonemapSettings": ("frame_compare.vs.types", "TonemapSettings"),
}

__all__ = [
    "VSLoader",
    "DefaultVSLoader",
    "SourceInfo",
    "HDRMetadata",
    "TonemapSettings",
    "LWLibavSourceOptions",
    "is_vapoursynth_available",
    "ensure_vs_environment",
    "detect_plugins",
    "require_plugin",
    "load_source",
    "apply_trim",
    "detect_hdr",
    "apply_tonemap",
    "get_preset_settings",
]


def __getattr__(name: str) -> Any:
    export = _EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = export
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
