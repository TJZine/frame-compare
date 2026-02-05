"""VapourSynth module for frame-compare."""

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
