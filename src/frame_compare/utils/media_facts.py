"""Dependency-light canonical media facts shared across runtime domains."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, cast

type PictureType = Literal["I", "P", "B", "S", "SI", "SP", "BI"]
type ColorRange = Literal["limited", "full"]
type ActivePictureProvenance = Literal[
    "explicit",
    "dolby_vision_l5",
    "dimension_derived",
    "aspect_ratio_derived",
    "content_derived",
    "full_frame",
]

_PICTURE_TYPES: frozenset[str] = frozenset({"I", "P", "B", "S", "SI", "SP", "BI"})


class PresentationState(StrEnum):
    """How source signal was presented in rendered screenshot pixels."""

    SDR = "sdr"
    HDR_TONEMAP_OFF = "hdr_tonemap_off"
    HDR_TONEMAPPED = "hdr_tonemapped"


def normalize_picture_type(value: object) -> PictureType | None:
    """Normalize a supported exact-frame picture type without inferring it."""
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeDecodeError:
            return None
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if normalized == "IDR":
        return "I"
    if normalized not in _PICTURE_TYPES:
        return None
    return cast("PictureType", normalized)


@dataclass(frozen=True, slots=True)
class HDRStaticFacts:
    """Observed static HDR luminance metadata."""

    mastering_min_nits: float | None = None
    mastering_max_nits: float | None = None
    max_cll: int | None = None
    max_fall: int | None = None


@dataclass(frozen=True, slots=True)
class SourceSignalFacts:
    """Observed clip-level source signal evidence."""

    is_hdr: bool
    primaries: int | None = None
    transfer: int | None = None
    matrix: int | None = None
    color_range: ColorRange | None = None
    dolby_vision_rpu: bool = False
    hdr_static: HDRStaticFacts | None = None


@dataclass(frozen=True, slots=True)
class ActivePictureFacts:
    """Resolved active picture in source-frame coordinates."""

    x: int
    y: int
    width: int
    height: int
    provenance: ActivePictureProvenance
    is_full_frame: bool

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("active picture coordinates and dimensions must be valid")


@dataclass(frozen=True, slots=True)
class RenderedGeometryFacts:
    """Dependency-light snapshot of the resolved render geometry plan."""

    source_size: tuple[int, int]
    active_picture: ActivePictureFacts
    cropped_size: tuple[int, int]
    scaled_size: tuple[int, int]
    final_canvas_size: tuple[int, int]
    is_noop: bool

    def __post_init__(self) -> None:
        sizes = (
            self.source_size,
            self.cropped_size,
            self.scaled_size,
            self.final_canvas_size,
        )
        if any(width <= 0 or height <= 0 for width, height in sizes):
            raise ValueError("rendered geometry dimensions must be positive")
        source_width, source_height = self.source_size
        active = self.active_picture
        if active.x + active.width > source_width or active.y + active.height > source_height:
            raise ValueError("active picture must be contained by the source size")


@dataclass(frozen=True, slots=True)
class RenderedFrameFacts:
    """Facts collected from one exact original source frame."""

    source_frame: int
    picture_type: PictureType | None = None
    dolby_vision_rpu: bool | None = None

    def __post_init__(self) -> None:
        if self.source_frame < 0:
            raise ValueError("source_frame must be non-negative")


__all__ = [
    "ActivePictureFacts",
    "ActivePictureProvenance",
    "ColorRange",
    "HDRStaticFacts",
    "PictureType",
    "PresentationState",
    "RenderedFrameFacts",
    "RenderedGeometryFacts",
    "SourceSignalFacts",
    "normalize_picture_type",
]
