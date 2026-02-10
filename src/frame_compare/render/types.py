from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore


class OverlayMode(str, Enum):
    """Overlay verbosity level."""

    MINIMAL = "minimal"  # Label only
    STANDARD = "standard"  # Label + frame + resolution
    DIAGNOSTIC = "diagnostic"  # Standard + HDR info
    NONE = "none"  # No overlay drawn


@dataclass
class EncoderSettings:
    """Encoder settings for screenshot output files."""

    format: str = "png"
    compression: int = 6  # PNG compression 0-9
    bit_depth: int = 8


@dataclass
class OverlayConfig:
    """Overlay rendering configuration for a single output frame."""

    mode: OverlayMode  # minimal, standard, diagnostic
    label: str  # Video label
    frame_number: int
    resolution: tuple[int, int]
    hdr_info: str | None
    font_path: Path | None
    font_size: int = 24
    position: str = "top-left"  # top-left, top-right, bottom-left, bottom-right


@dataclass
class RenderRequest:
    """Single frame render job"""

    clip: vs.VideoNode | Path  # VS clip or file path (FFmpeg)
    frame_number: int
    output_path: Path
    overlay: OverlayConfig | None
    encoder_settings: EncoderSettings


Renderer = Literal["vapoursynth", "ffmpeg", "auto"]


@dataclass(frozen=True)
class ScreenshotResult:
    """Result of a batch screenshot operation."""

    label: str  # Video label
    paths: list[Path]  # List of generated screenshot paths
    frame_count: int  # Number of frames rendered
