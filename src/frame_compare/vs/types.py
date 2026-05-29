"""VapourSynth module type definitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from frame_compare.config.schema import ToneCurve, TonemapPreset

if TYPE_CHECKING:
    import vapoursynth as vs


@dataclass(frozen=True)
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
    preset: TonemapPreset = TonemapPreset.REFERENCE
    tone_curve: ToneCurve = ToneCurve.BT2390
    target_nits: int = 100
    source_peak: int | None = None
    dynamic_peak_detection: bool = True
    dst_min_nits: float = 0.18
    knee_offset: float = 0.50
    smoothing_period: float = 45.0
    scene_threshold_low: float = 0.8
    scene_threshold_high: float = 2.4
    percentile: float = 99.995
    gamut_mapping: int = 1
    metadata: int | None = 0
    use_dovi: bool | None = True
    contrast_recovery: float = 0.3
    gamma_lift: bool = False


@dataclass(frozen=True)
class ColorProps:
    """Color space properties extracted from frame.

    All fields use VapourSynth integer constants.
    Defaults to 2 (unspecified) for primaries/transfer/matrix and 1 (limited) for range.
    """

    primaries: int  # _Primaries (e.g., 1=BT.709, 9=BT.2020)
    transfer: int  # _Transfer (e.g., 1=BT.709, 16=PQ, 18=HLG)
    matrix: int  # _Matrix (e.g., 1=BT.709, 9=BT.2020nc)
    color_range: int  # _ColorRange (0=full, 1=limited)
