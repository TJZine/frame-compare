"""VapourSynth module for frame-compare."""

from frame_compare.vs.env import (
    detect_plugins,
    ensure_vs_environment,
    is_vapoursynth_available,
    require_plugin,
)
from frame_compare.vs.loader import DefaultVSLoader, VSLoader
from frame_compare.vs.props import get_color_props, is_hdr
from frame_compare.vs.source import apply_trim, load_source
from frame_compare.vs.types import ColorProps, HDRMetadata, SourceInfo, TonemapSettings

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
]
