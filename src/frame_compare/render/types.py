from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from frame_compare.config.schema import OverlayMode

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.render.backend.ffmpeg import FFmpegRunner
    from frame_compare.utils.progress_protocol import ProgressReporter


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
    probe_width: int | None
    probe_height: int | None
    probe_num_frames: int | None
    probe_is_hdr: bool | None


Renderer = Literal["vapoursynth", "ffmpeg", "auto"]


@dataclass(frozen=True)
class BatchRenderOptions:
    """Options for rendering pre-expanded screenshot batch requests."""

    renderer: Renderer = "auto"
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    reporter: ProgressReporter | None = None
    ffmpeg_runner: FFmpegRunner | None = None


@dataclass(frozen=True)
class ScreenshotRenderOptions:
    """Convenience options for render_screenshots."""

    label_map: dict[Path, str] | None = None
    renderer: Renderer = "auto"
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    reporter: ProgressReporter | None = None
    display_frames: list[int] | None = None
    selection_labels: list[str | None] | None = None
    ffmpeg_runner: FFmpegRunner | None = None


@dataclass(frozen=True)
class ScreenshotResult:
    """Result of a batch screenshot operation."""

    label: str  # Video label
    paths: list[Path]  # List of generated screenshot paths
    frame_count: int  # Number of frames rendered
