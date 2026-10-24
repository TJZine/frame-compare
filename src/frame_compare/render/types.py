from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from frame_compare.config.schema import OverlayMode
from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.vs.types import AppliedTonemap

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.render.backend.ffmpeg import FFmpegRunner
    from frame_compare.render.geometry import RenderGeometryPlan
    from frame_compare.utils.progress_protocol import ProgressReporter


@dataclass
class EncoderSettings:
    """Encoder settings for screenshot output files."""

    compression: int = 6
    vs_writer: VsScreenshotWriter = VsScreenshotWriter.AUTO


@dataclass(frozen=True, slots=True, kw_only=True)
class OverlayConfig:
    """Immutable presentation input for one screenshot overlay."""

    mode: OverlayMode
    label: str
    comparison_frame: int
    source_frame: int
    source_total_frames: int | None
    include_frame_number: bool
    selection_label: str | None
    file_size_bytes: int
    source_resolution: tuple[int, int]
    signal: SourceSignalFacts
    presentation_state: PresentationState
    tonemap: AppliedTonemap | None
    geometry: RenderedGeometryFacts
    font_path: Path | None
    origin: tuple[int, int] | None = None
    font_size: int = 24


@dataclass(frozen=True, slots=True)
class PreparedRenderSource:
    """Original diagnostic source and prepared image-producing render graph."""

    diagnostic_source: vs.VideoNode | Path
    prepared_clip: vs.VideoNode | Path
    source_dimensions: tuple[int, int]
    source_total_frames: int | None
    source_is_hdr: bool
    presentation_state: PresentationState
    tonemap: AppliedTonemap | None


@dataclass(frozen=True, slots=True)
class RenderedClipFacts:
    """Canonical clip facts produced while expanding a render batch."""

    size_bytes: int
    source_resolution: tuple[int, int]
    source_total_frames: int | None
    signal: SourceSignalFacts
    presentation_state: PresentationState
    tonemap: AppliedTonemap | None
    geometry: RenderedGeometryFacts


@dataclass(frozen=True, slots=True)
class RenderedFrameResult:
    """Rendered screenshot path plus exact-source-frame facts."""

    path: Path
    facts: RenderedFrameFacts


@dataclass(frozen=True, slots=True)
class SelectedScreenshot:
    comparison_frame: int
    source_frame: int
    selection_label: str | None


@dataclass
class RenderRequest:
    """Single exact-source-frame render job."""

    clip: vs.VideoNode | Path
    diagnostic_source: vs.VideoNode | Path
    frame_number: int
    output_path: Path
    overlay: OverlayConfig | None
    encoder_settings: EncoderSettings
    ffmpeg_runner: FFmpegRunner | None = None
    geometry_plan: RenderGeometryPlan | None = None


@dataclass(frozen=True)
class ScreenshotBatchRequest:
    """Batch request for one clip's selected source frames."""

    clip_path: Path
    label: str
    frames: tuple[SelectedScreenshot, ...]
    size_bytes: int
    source_resolution: tuple[int, int]
    source_total_frames: int | None
    signal: SourceSignalFacts
    active_picture: ActivePictureFacts
    filename_label: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedClipRender:
    label: str
    clip_facts: RenderedClipFacts
    frames: tuple[SelectedScreenshot, ...]
    requests: tuple[RenderRequest, ...]

    def __post_init__(self) -> None:
        if len(self.frames) != len(self.requests):
            raise ValueError("prepared clip must have one request per selected screenshot")
        for selection, request in zip(self.frames, self.requests, strict=True):
            if request.frame_number != selection.source_frame:
                raise ValueError("prepared request source frame differs from selection")


@dataclass(frozen=True, slots=True)
class RenderedScreenshot:
    selection: SelectedScreenshot
    result: RenderedFrameResult

    def __post_init__(self) -> None:
        if self.result.facts.source_frame != self.selection.source_frame:
            raise ValueError("rendered source frame differs from selected screenshot")


@dataclass(frozen=True, slots=True)
class RenderedClip:
    label: str
    clip_facts: RenderedClipFacts
    screenshots: tuple[RenderedScreenshot, ...]


Renderer = Literal["vapoursynth", "ffmpeg", "auto"]


@dataclass(frozen=True)
class BatchRenderOptions:
    """Options for rendering pre-expanded screenshot batch requests."""

    renderer: Renderer = "auto"
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    reporter: ProgressReporter | None = None
    ffmpeg_runner: FFmpegRunner | None = None
    parallelism: int = 1


__all__ = [
    "BatchRenderOptions",
    "EncoderSettings",
    "OverlayConfig",
    "PreparedRenderSource",
    "RenderRequest",
    "PreparedClipRender",
    "SelectedScreenshot",
    "RenderedScreenshot",
    "RenderedClip",
    "RenderedClipFacts",
    "RenderedFrameResult",
    "Renderer",
    "ScreenshotBatchRequest",
]
