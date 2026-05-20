"""VapourSynth module for frame-compare."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from frame_compare.vs.color import (
        apply_color_props,
        expand_limited_rgb_to_full,
        infer_color_props,
        to_rgb24,
    )
    from frame_compare.vs.env import (
        detect_plugins,
        ensure_vs_environment,
        is_vapoursynth_available,
        require_plugin,
    )
    from frame_compare.vs.loader import DefaultVSLoader, VSLoader
    from frame_compare.vs.props import get_color_props, is_hdr
    from frame_compare.vs.source import apply_trim, load_source
    from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings
    from frame_compare.vs.types import ColorProps, HDRMetadata, SourceInfo, TonemapSettings

    tonemap = apply_tonemap

_EXPORTS: dict[str, tuple[str, str]] = {
    # color
    "apply_color_props": ("frame_compare.vs.color", "apply_color_props"),
    "expand_limited_rgb_to_full": ("frame_compare.vs.color", "expand_limited_rgb_to_full"),
    "infer_color_props": ("frame_compare.vs.color", "infer_color_props"),
    "to_rgb24": ("frame_compare.vs.color", "to_rgb24"),
    # env
    "detect_plugins": ("frame_compare.vs.env", "detect_plugins"),
    "ensure_vs_environment": ("frame_compare.vs.env", "ensure_vs_environment"),
    "is_vapoursynth_available": ("frame_compare.vs.env", "is_vapoursynth_available"),
    "require_plugin": ("frame_compare.vs.env", "require_plugin"),
    # loader
    "DefaultVSLoader": ("frame_compare.vs.loader", "DefaultVSLoader"),
    "VSLoader": ("frame_compare.vs.loader", "VSLoader"),
    # props
    "get_color_props": ("frame_compare.vs.props", "get_color_props"),
    "is_hdr": ("frame_compare.vs.props", "is_hdr"),
    # source
    "apply_trim": ("frame_compare.vs.source", "apply_trim"),
    "load_source": ("frame_compare.vs.source", "load_source"),
    # tonemap
    "apply_tonemap": ("frame_compare.vs.tonemap", "apply_tonemap"),
    "get_preset_settings": ("frame_compare.vs.tonemap", "get_preset_settings"),
    "tonemap": ("frame_compare.vs.tonemap", "apply_tonemap"),
    # types
    "ColorProps": ("frame_compare.vs.types", "ColorProps"),
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
    "ColorProps",
    "is_vapoursynth_available",
    "ensure_vs_environment",
    "detect_plugins",
    "require_plugin",
    "load_source",
    "apply_trim",
    "get_color_props",
    "is_hdr",
    "infer_color_props",
    "apply_color_props",
    "expand_limited_rgb_to_full",
    "to_rgb24",
    "tonemap",
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
