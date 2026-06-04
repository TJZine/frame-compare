from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from frame_compare.config.schema import OverlayMode
from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.render.geometry import GeometryRect

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.render.backend.ffmpeg import FFmpegRunner
    from frame_compare.render.geometry import RenderGeometryPlan
    from frame_compare.utils.progress_protocol import ProgressReporter


@dataclass
class EncoderSettings:
    """Encoder settings for screenshot output files."""

    format: str = "png"
    compression: int = 6  # PNG compression 0-9
    bit_depth: int = 8
    vs_writer: VsScreenshotWriter = VsScreenshotWriter.AUTO


@dataclass
class OverlayConfig:
    """Overlay rendering configuration for a single output frame."""

    mode: OverlayMode  # minimal, standard, diagnostic
    label: str  # Human clip label for non-burn-in surfaces
    frame_number: int
    resolution: tuple[int, int]
    hdr_info: str | None
    font_path: Path | None
    base_text: str | None = None
    resolution_summary: str | None = None
    origin: tuple[int, int] | None = None
    display_frame_number: int | None = None
    num_frames: int | None = None
    picture_type: str | None = None
    selection_label: str | None = None
    selection_detail: OverlaySelectionDetail | None = None
    diagnostic_metadata: OverlayDiagnosticMetadata | None = None
    burn_in_label: str | None = None  # Screenshot identity for overlay text
    include_frame_number: bool = True
    font_size: int = 24


@dataclass(frozen=True, slots=True)
class OverlaySelectionDetail:
    """Render-local per-frame selection metadata for overlay consumers."""

    frame_index: int
    label: str
    source: str
    timecode: str | None
    score: float | None = None
    clip_role: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class OverlayFrameMeasurement:
    """Render-local score-derived diagnostic measurement for a selected frame."""

    avg_nits: float
    max_nits: float
    category: str | None = None


@dataclass(frozen=True, slots=True)
class OverlayDolbyVisionMetadata:
    """Render-local clip-level Dolby Vision facts extracted from preserved props."""

    rpu_present: bool = False
    block_index: int | None = None
    block_total: int | None = None
    target_nits: float | None = None
    l2_target_nits: float | None = None
    l1_average: float | None = None
    l1_maximum: float | None = None
    l5_left: int | None = None
    l5_right: int | None = None
    l5_top: int | None = None
    l5_bottom: int | None = None
    l6_max_cll: float | None = None
    l6_max_fall: float | None = None


@dataclass(frozen=True, slots=True)
class OverlayDiagnosticMetadata:
    """Render-local structured metadata for diagnostic overlay composition."""

    mastering_display: str | None = None
    max_cll: int | None = None
    max_fall: int | None = None
    color_range: str | None = None
    dolby_vision: OverlayDolbyVisionMetadata | None = None
    measurement: OverlayFrameMeasurement | None = None


@dataclass
class RenderRequest:
    """Single frame render job"""

    clip: vs.VideoNode | Path  # VS clip or file path (FFmpeg)
    frame_number: int
    output_path: Path
    overlay: OverlayConfig | None
    encoder_settings: EncoderSettings
    ffmpeg_runner: FFmpegRunner | None = None
    geometry_plan: RenderGeometryPlan | None = None


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
    selection_details: list[OverlaySelectionDetail | None] | None = None
    diagnostic_metadata: list[OverlayDiagnosticMetadata | None] | None = None
    diagnostic_metadata_trusted_for_geometry: bool = False
    active_rect: GeometryRect | None = None
    filename_label: str | None = None


Renderer = Literal["vapoursynth", "ffmpeg", "auto"]


@dataclass(frozen=True)
class BatchRenderOptions:
    """Options for rendering pre-expanded screenshot batch requests."""

    renderer: Renderer = "auto"
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    reporter: ProgressReporter | None = None
    ffmpeg_runner: FFmpegRunner | None = None
    parallelism: int = 1
    warnings: list[str] | None = None


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
