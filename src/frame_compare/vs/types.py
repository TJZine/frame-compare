"""VapourSynth module type definitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import TYPE_CHECKING, Literal

from frame_compare.config.schema import ToneCurve, TonemapPreset
from frame_compare.config.schema_enums import TonemapSpeed

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


@dataclass(frozen=True, slots=True)
class TonemapSettings:
    """Resolved tonemap settings for VS operations."""

    enabled: bool = True
    preset: TonemapPreset = TonemapPreset.REFERENCE
    tonemap_speed: TonemapSpeed = TonemapSpeed.QUALITY
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


class TonemapFallbackCause(StrEnum):
    PLUGIN_UNAVAILABLE = "plugin_unavailable"
    RUNTIME_UNUSABLE = "runtime_unusable"
    RUNTIME_CALL_FAILED = "runtime_call_failed"


@dataclass(frozen=True, slots=True)
class ResolvedSourcePeak:
    nits: int
    origin: Literal["configured", "max_cll", "default"]


@dataclass(frozen=True, slots=True)
class LibplaceboTonemap:
    curve: ToneCurve
    settings: TonemapSettings
    source_peak: ResolvedSourcePeak
    frame_policy: Literal["sequence", "independent_frames", "shared_stateless"] = "sequence"


@dataclass(frozen=True, slots=True)
class FallbackTonemap:
    algorithm: Literal["frame_compare_peak_scaled_rational_v1"]
    target_nits: int
    gamma_lift: bool
    source_peak: ResolvedSourcePeak
    cause: TonemapFallbackCause


@dataclass(frozen=True, slots=True)
class AppliedTonemap:
    requested: TonemapSettings
    transform: LibplaceboTonemap | FallbackTonemap


@dataclass(frozen=True, slots=True)
class TonemapResult:
    clip: vs.VideoNode
    applied: AppliedTonemap | None
