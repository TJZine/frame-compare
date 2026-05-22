"""Report data payload shaping."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from frame_compare.config.schema import ReportConfig
from frame_compare.errors import ReportError
from frame_compare.services.types import TmdbMetadata

REPORT_VERSION = "1.0"


class ReportClipPayload(TypedDict):
    name: str
    label: str
    resolution: tuple[int, int]
    fps: float
    hdr: bool


class ReportImagePayload(TypedDict):
    clip: str
    src: str


class ReportFramePayload(TypedDict):
    number: int
    images: list[ReportImagePayload]


class ReportStatsPayload(TypedDict):
    frame_count: int
    clip_count: int


class ReportPayload(TypedDict):
    version: str
    generated_at: str
    title: str
    slowpics_url: str | None
    default_mode: str
    stats: ReportStatsPayload
    clips: list[ReportClipPayload]
    frames: list[ReportFramePayload]


@dataclass(frozen=True)
class ClipInfo:
    """Information about a video clip for report generation."""

    name: str  # Display name (filename or custom label)
    path: Path  # Source video path (for reference, not embedded)
    frame_count: int  # Total frames in source
    resolution: tuple[int, int]  # (width, height)
    fps: float  # Frames per second
    hdr: bool  # True if HDR source
    label: str | None = None  # Short label for UI (e.g., "REF", "ENC")
    screenshots: list[Path] = field(default_factory=list[Path])


@dataclass(frozen=True)
class ReportData:
    """Data for report generation."""

    clips: list[ClipInfo]  # At least 2 clips for comparison
    frames: list[int]  # Selected frame numbers
    metadata: TmdbMetadata | None = None  # Optional TMDB info
    slowpics_url: str | None = None  # Link if uploaded


def build_report_payload(
    data: ReportData, config: ReportConfig, *, report_dir: Path
) -> ReportPayload:
    """Shape validated report data into the embedded JSON payload."""
    return {
        "version": REPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "title": data.metadata.title if data.metadata else data.clips[0].name,
        "slowpics_url": data.slowpics_url,
        "default_mode": config.default_mode.value,
        "stats": {
            "frame_count": len(data.frames),
            "clip_count": len(data.clips),
        },
        "clips": build_clip_payloads(data.clips),
        "frames": build_frame_payloads(data, config, report_dir=report_dir),
    }


def build_clip_payloads(clips: list[ClipInfo]) -> list[ReportClipPayload]:
    """Build stable clip payload entries."""
    json_clips: list[ReportClipPayload] = []
    for clip in clips:
        json_clips.append(
            {
                "name": clip.name,
                "label": clip.label or clip.name,
                "resolution": clip.resolution,
                "fps": clip.fps,
                "hdr": clip.hdr,
            }
        )
    return json_clips


def build_frame_payloads(
    data: ReportData, config: ReportConfig, *, report_dir: Path
) -> list[ReportFramePayload]:
    """Build stable frame payload entries and resolve each image source."""
    json_frames: list[ReportFramePayload] = []
    for i, frame_num in enumerate(data.frames):
        frame_images: list[ReportImagePayload] = []
        for clip in data.clips:
            screenshot_path = clip.screenshots[i]

            if not screenshot_path.exists():
                raise ReportError(f"screenshot not found: {screenshot_path}")

            frame_images.append(
                {
                    "clip": clip.name,
                    "src": image_src_for_report(
                        screenshot_path,
                        report_dir=report_dir,
                        embed_images=config.embed_images,
                    ),
                }
            )

        json_frames.append(
            {
                "number": frame_num,
                "images": frame_images,
            }
        )

    return json_frames


def image_src_for_report(screenshot_path: Path, *, report_dir: Path, embed_images: bool) -> str:
    """Resolve an image src for the report payload."""
    if embed_images:
        try:
            image_bytes = screenshot_path.read_bytes()
            b64_str = base64.b64encode(image_bytes).decode("ascii")
            return f"data:image/png;base64,{b64_str}"
        except OSError as e:
            raise ReportError(f"failed to encode image: {screenshot_path}") from e

    try:
        # Use relative path for portability if possible.
        return str(Path(os_path_relpath(screenshot_path, report_dir)).as_posix())
    except ValueError:
        # Use a browser-safe URI when Windows drives prevent a relative path.
        return screenshot_path.resolve().as_uri()


def os_path_relpath(path: Path, start: Path) -> str:
    """Wrapper for os.path.relpath to handle Path objects."""
    return os.path.relpath(path, start)
