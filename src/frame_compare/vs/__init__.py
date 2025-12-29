"""VapourSynth module for frame-compare."""

from frame_compare.vs.env import (
    detect_plugins,
    ensure_vs_environment,
    is_vapoursynth_available,
    require_plugin,
)
from frame_compare.vs.loader import DefaultVSLoader, VSLoader
from frame_compare.vs.types import HDRMetadata, SourceInfo, TonemapSettings

__all__ = [
    "VSLoader",
    "DefaultVSLoader",
    "SourceInfo",
    "HDRMetadata",
    "TonemapSettings",
    "is_vapoursynth_available",
    "ensure_vs_environment",
    "detect_plugins",
    "require_plugin",
]
