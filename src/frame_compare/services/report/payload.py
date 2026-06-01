"""Report data payload shaping."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Protocol, TypedDict

from frame_compare.config.schema import ReportConfig
from frame_compare.services.errors import ReportError
from frame_compare.services.types import TmdbMetadata


class ClipProbeProtocol(Protocol):
    @property
    def num_frames(self) -> int: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def is_hdr(self) -> bool: ...
    @property
    def fingerprint(self) -> ClipFingerprintProtocol: ...


class ClipFingerprintProtocol(Protocol):
    @property
    def path(self) -> Path: ...
    @property
    def size_bytes(self) -> int: ...
    @property
    def mtime_ns(self) -> int: ...


class ClipStateProtocol(Protocol):
    @property
    def label(self) -> str: ...
    @property
    def path(self) -> Path: ...
    @property
    def probe(self) -> ClipProbeProtocol: ...
    @property
    def effective_fps(self) -> Fraction: ...


def clip_info_from_state(clip: ClipStateProtocol, screenshots: list[Path]) -> ClipInfo:
    """Map clip state protocol to ClipInfo DTO."""
    return ClipInfo(
        name=clip.label,
        path=clip.path,
        frame_count=clip.probe.num_frames,
        resolution=(clip.probe.width, clip.probe.height),
        fps=float(clip.effective_fps),
        hdr=clip.probe.is_hdr,
        label=clip.label,
        source_identity=source_identity_from_fingerprint(clip.probe.fingerprint),
        screenshots=screenshots,
    )


REPORT_VERSION = "1.0"


class ReportClipPayload(TypedDict):
    name: str
    label: str
    frame_count: int
    resolution: tuple[int, int]
    fps: float
    hdr: bool


class ReportImagePayload(TypedDict):
    clip: str
    src: str


class ReportFramePayload(TypedDict):
    number: int
    label: str
    detail: str
    category: str
    images: list[ReportImagePayload]


class ReportIdentityImagePayload(TypedDict):
    clip: str


class ReportIdentityClipPayload(TypedDict):
    name: str
    label: str
    frame_count: int
    resolution: tuple[int, int]
    fps: float
    hdr: bool
    source_identity: str | None


class ReportIdentityFramePayload(TypedDict):
    number: int
    label: str
    detail: str
    category: str
    images: list[ReportIdentityImagePayload]


class ReportDefaultSelectionPayload(TypedDict):
    left_clip_index: int
    right_clip_index: int


class ReportStatsPayload(TypedDict):
    frame_count: int
    clip_count: int


class ReportPayload(TypedDict):
    version: str
    report_id: str
    generated_at: str
    title: str
    slowpics_url: str | None
    default_mode: str
    default_selection: ReportDefaultSelectionPayload
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
    source_identity: str | None = None  # Stable, non-absolute source discriminator
    screenshots: list[Path] = field(default_factory=list[Path])


@dataclass(frozen=True)
class FrameDetail:
    """Optional report-owned display metadata for a selected frame."""

    label: str | None = None
    detail: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class ReportData:
    """Data for report generation."""

    clips: list[ClipInfo]  # At least 2 clips for comparison
    frames: list[int]  # Selected frame numbers
    metadata: TmdbMetadata | None = None  # Optional TMDB info
    slowpics_url: str | None = None  # Link if uploaded
    frame_details: list[FrameDetail] = field(default_factory=list[FrameDetail])


def build_report_payload(
    data: ReportData, config: ReportConfig, *, report_dir: Path
) -> ReportPayload:
    """Shape validated report data into the embedded JSON payload."""
    title = data.metadata.title if data.metadata else data.clips[0].name
    clips = build_clip_payloads(data.clips)
    frames = build_frame_payloads(data, config, report_dir=report_dir)
    default_selection = build_default_selection(len(data.clips))
    stats: ReportStatsPayload = {
        "frame_count": len(data.frames),
        "clip_count": len(data.clips),
    }
    default_mode = config.default_mode.value
    return {
        "version": REPORT_VERSION,
        "report_id": build_report_id(
            title=title,
            slowpics_url=data.slowpics_url,
            default_mode=default_mode,
            default_selection=default_selection,
            stats=stats,
            clips=build_report_identity_clips(data.clips, clips),
            frames=frames,
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "title": title,
        "slowpics_url": data.slowpics_url,
        "default_mode": default_mode,
        "default_selection": default_selection,
        "stats": stats,
        "clips": clips,
        "frames": frames,
    }


def build_clip_payloads(clips: list[ClipInfo]) -> list[ReportClipPayload]:
    """Build stable clip payload entries."""
    json_clips: list[ReportClipPayload] = []
    for clip in clips:
        json_clips.append(
            {
                "name": clip.name,
                "label": clip.label or clip.name,
                "frame_count": clip.frame_count,
                "resolution": clip.resolution,
                "fps": clip.fps,
                "hdr": clip.hdr,
            }
        )
    return json_clips


def build_report_identity_clips(
    clip_infos: list[ClipInfo], clips: list[ReportClipPayload]
) -> list[ReportIdentityClipPayload]:
    """Build clip identity entries with safe source discriminators."""
    identity_clips: list[ReportIdentityClipPayload] = []
    for clip_info, clip in zip(clip_infos, clips, strict=True):
        identity_clips.append(
            {
                "name": clip["name"],
                "label": clip["label"],
                "frame_count": clip["frame_count"],
                "resolution": clip["resolution"],
                "fps": clip["fps"],
                "hdr": clip["hdr"],
                "source_identity": clip_info.source_identity,
            }
        )
    return identity_clips


def build_frame_payloads(
    data: ReportData, config: ReportConfig, *, report_dir: Path
) -> list[ReportFramePayload]:
    """Build stable frame payload entries and resolve each image source."""
    if data.frame_details and len(data.frame_details) != len(data.frames):
        raise ReportError(
            f"frame detail count mismatch: expected {len(data.frames)}, "
            f"got {len(data.frame_details)}"
        )

    json_frames: list[ReportFramePayload] = []
    for i, frame_num in enumerate(data.frames):
        frame_detail = frame_detail_for_payload(data, frame_index=i, frame_number=frame_num)
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
                "label": frame_detail.label or f"Frame {frame_num}",
                "detail": frame_detail.detail or f"Source frame {frame_num}",
                "category": frame_detail.category or "selected",
                "images": frame_images,
            }
        )

    return json_frames


def frame_detail_for_payload(
    data: ReportData, *, frame_index: int, frame_number: int
) -> FrameDetail:
    """Return frame display metadata, deriving stable defaults when absent."""
    if not data.frame_details:
        return FrameDetail(
            label=f"Frame {frame_number}",
            detail=f"Source frame {frame_number}",
            category="selected",
        )

    detail = data.frame_details[frame_index]
    return FrameDetail(
        label=detail.label or f"Frame {frame_number}",
        detail=detail.detail or f"Source frame {frame_number}",
        category=detail.category or "selected",
    )


def build_default_selection(clip_count: int) -> ReportDefaultSelectionPayload:
    """Build safe default clip selection indices for the viewer payload."""
    return {
        "left_clip_index": 0,
        "right_clip_index": 1 if clip_count > 1 else 0,
    }


def build_report_id(
    *,
    title: str,
    slowpics_url: str | None,
    default_mode: str,
    default_selection: ReportDefaultSelectionPayload,
    stats: ReportStatsPayload,
    clips: list[ReportIdentityClipPayload],
    frames: list[ReportFramePayload],
) -> str:
    """Build a stable report-local identifier without timestamps or source paths."""
    identity_payload = {
        "version": REPORT_VERSION,
        "title": title,
        "slowpics_url": slowpics_url,
        "default_mode": default_mode,
        "default_selection": default_selection,
        "stats": stats,
        "clips": clips,
        "frames": build_report_identity_frames(frames),
    }
    identity_json = json.dumps(
        identity_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(identity_json.encode("utf-8")).hexdigest()
    return f"report_{digest[:32]}"


def source_identity_from_fingerprint(fingerprint: ClipFingerprintProtocol) -> str:
    """Build a safe source identity without embedding absolute source paths."""
    source_payload = {
        "basename": fingerprint.path.name,
        "size_bytes": fingerprint.size_bytes,
        "mtime_ns": fingerprint.mtime_ns,
    }
    source_json = json.dumps(
        source_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(source_json.encode("utf-8")).hexdigest()
    return f"source_{digest[:32]}"


def build_report_identity_frames(frames: list[ReportFramePayload]) -> list[ReportIdentityFramePayload]:
    """Build frame identity entries without image src paths or embedded bytes."""
    identity_frames: list[ReportIdentityFramePayload] = []
    for frame in frames:
        identity_frames.append(
            {
                "number": frame["number"],
                "label": frame["label"],
                "detail": frame["detail"],
                "category": frame["category"],
                "images": [{"clip": image["clip"]} for image in frame["images"]],
            }
        )
    return identity_frames


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
        return str(Path(os.path.relpath(screenshot_path, report_dir)).as_posix())
    except ValueError:
        # Use a browser-safe URI when Windows drives prevent a relative path.
        return screenshot_path.resolve().as_uri()
