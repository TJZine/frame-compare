"""Tonemapping subsystem entry points."""

from .config import TMConfig, DEFAULT_TM_CONFIG
from .core import apply_tonemap
from .detect import is_hdr
from .overlay import apply_overlay, build_overlay_lines
from .verify import run_verification
from .exceptions import TonemapError, HDRDetectError, VerificationError, TonemapConfigError

__all__ = [
    "TMConfig",
    "DEFAULT_TM_CONFIG",
    "apply_tonemap",
    "is_hdr",
    "apply_overlay",
    "build_overlay_lines",
    "run_verification",
    "TonemapError",
    "HDRDetectError",
    "VerificationError",
    "TonemapConfigError",
]
