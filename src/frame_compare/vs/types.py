"""VapourSynth module type definitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore


@dataclass
class HDRMetadata:
    """HDR metadata extracted from source."""

    mastering_display: str | None
    max_cll: int | None
    max_fall: int | None
    color_primaries: int
    transfer: int
    matrix: int


@dataclass
class SourceInfo:
    """Video source metadata."""

    clip: vs.VideoNode
    width: int
    height: int
    num_frames: int
    fps: Fraction
    format: vs.VideoFormat
    frame_props: Mapping[str, object]
    is_hdr: bool
    hdr_metadata: HDRMetadata | None


@dataclass
class TonemapSettings:
    """Resolved tonemap settings for VS operations."""

    enabled: bool = True
    preset: str = "reference"
    tone_curve: str = "bt2390"
    target_nits: int = 203
    source_peak: int | None = None
    contrast_recovery: float = 0.0
    gamma_lift: bool = False
