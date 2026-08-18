from __future__ import annotations

from dataclasses import dataclass, field
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
from frame_compare.vs.types import TonemapSettings

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.render.backend.ffmpeg import FFmpegRunner
    from frame_compare.render.geometry import RenderGeometryPlan
    from frame_compare.utils.progress_protocol import ProgressReporter


@dataclass
class EncoderSettings:
    """Encoder settings for screenshot output files."""

    format: str = "png"
    compression: int = 6
    bit_depth: int = 8
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
    tonemap_settings: TonemapSettings | None
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
    tonemap_settings: TonemapSettings | None


@dataclass(frozen=True, slots=True)
class RenderedClipFacts:
    """Canonical clip facts produced while expanding a render batch."""

    size_bytes: int
    source_resolution: tuple[int, int]
    source_total_frames: int | None
    signal: SourceSignalFacts
    presentation_state: PresentationState
    tonemap_settings: TonemapSettings | None
    geometry: RenderedGeometryFacts


@dataclass(frozen=True, slots=True)
class RenderedFrameResult:
    """Rendered screenshot path plus exact-source-frame facts."""

    path: Path
    facts: RenderedFrameFacts


def _empty_screenshots_by_label() -> dict[str, list[Path]]:
    return {}


def _empty_frame_facts_by_label() -> dict[str, list[RenderedFrameFacts]]:
    return {}


def _empty_clip_facts_by_label() -> dict[str, RenderedClipFacts]:
    return {}


@dataclass(frozen=True, slots=True)
class RenderedBatchResult:
    """One-to-one screenshot, frame-fact, and clip-fact mappings."""

    screenshots_by_label: dict[str, list[Path]] = field(default_factory=_empty_screenshots_by_label)
    frame_facts_by_label: dict[str, list[RenderedFrameFacts]] = field(
        default_factory=_empty_frame_facts_by_label
    )
    clip_facts_by_label: dict[str, RenderedClipFacts] = field(
        default_factory=_empty_clip_facts_by_label
    )

    def __post_init__(self) -> None:
        labels = set(self.screenshots_by_label)
        if labels != set(self.frame_facts_by_label) or labels != set(self.clip_facts_by_label):
            raise ValueError("rendered batch mappings must have identical label sets")
        for label in labels:
            paths = self.screenshots_by_label[label]
            facts = self.frame_facts_by_label[label]
            if len(paths) != len(facts):
                raise ValueError(
                    f"rendered batch path/fact count mismatch for {label!r}: "
                    f"{len(paths)} != {len(facts)}"
                )


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
    source_frames: list[int]
    comparison_frames: list[int]
    selection_labels: list[str | None]
    size_bytes: int
    source_resolution: tuple[int, int]
    source_total_frames: int | None
    signal: SourceSignalFacts
    active_picture: ActivePictureFacts
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


__all__ = [
    "BatchRenderOptions",
    "EncoderSettings",
    "OverlayConfig",
    "PreparedRenderSource",
    "RenderRequest",
    "RenderedBatchResult",
    "RenderedClipFacts",
    "RenderedFrameResult",
    "Renderer",
    "ScreenshotBatchRequest",
]
