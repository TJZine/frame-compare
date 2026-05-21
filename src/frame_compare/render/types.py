from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from frame_compare.config.schema import OverlayMode

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore

    from frame_compare.render.ffmpeg import FFmpegRunner


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
    display_frame_number: int | None = None
    num_frames: int | None = None
    picture_type: str | None = None
    selection_label: str | None = None
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
    ffmpeg_runner: FFmpegRunner | None = None


@dataclass(frozen=True)
class ScreenshotBatchRequest:
    """Batch request representing a single clip's screenshot render task."""

    clip_path: Path
    label: str
    source_frames: list[int]
    display_frames: list[int]
    selection_labels: list[str | None]
    probe_width: int
    probe_height: int
    probe_num_frames: int
    probe_is_hdr: bool


Renderer = Literal["vapoursynth", "ffmpeg", "auto"]


@dataclass(frozen=True)
class ScreenshotResult:
    """Result of a batch screenshot operation."""

    label: str  # Video label
    paths: list[Path]  # List of generated screenshot paths
    frame_count: int  # Number of frames rendered
