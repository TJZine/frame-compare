"""Report v1.2 input validation, wire shaping, and stable identity."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TypedDict, cast

from frame_compare.config.schema import OverlayMode, ReportConfig
from frame_compare.errors import PathEscapesRootError
from frame_compare.services.errors import ReportError
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.utils.paths import require_managed_descendant
from frame_compare.vs.types import TonemapSettings

REPORT_VERSION = "1.2"


def _empty_frame_details() -> list[FrameDetail]:
    return []


class ClipFingerprintProtocol(Protocol):
    @property
    def path(self) -> Path: ...
    @property
    def size_bytes(self) -> int: ...
    @property
    def mtime_ns(self) -> int: ...


class ReportHDRStaticPayload(TypedDict):
    mastering_min_nits: float | None
    mastering_max_nits: float | None
    max_cll: int | None
    max_fall: int | None


class ReportSignalPayload(TypedDict):
    is_hdr: bool
    primaries: int | None
    transfer: int | None
    matrix: int | None
    range: str | None
    dolby_vision_rpu: bool
    hdr_static: ReportHDRStaticPayload | None


class ReportPresentationPayload(TypedDict):
    state: str
    tone_curve: str | None
    target_nits: int | None


class ReportActivePicturePayload(TypedDict):
    x: int
    y: int
    width: int
    height: int
    provenance: str
    is_full_frame: bool


class ReportClipDisplayPayload(TypedDict):
    primary: str
    release: str
    control: str
    micro: str
    filename: str


class ReportClipPayload(TypedDict):
    name: str
    label: str
    frame_count: int
    resolution: tuple[int, int]
    fps: float
    size_bytes: int
    signal: ReportSignalPayload
    presentation: ReportPresentationPayload
    active_picture: ReportActivePicturePayload | None
    display: ReportClipDisplayPayload


class ReportImagePayload(TypedDict):
    clip: str
    src: str
    source_frame: int
    picture_type: str | None
    dolby_vision_rpu: bool | None


class ReportFramePayload(TypedDict):
    number: int
    label: str
    detail: str
    category: str
    images: list[ReportImagePayload]


class ReportTonemapSettingsPayload(TypedDict):
    enabled: bool
    preset: str
    tone_curve: str
    target_nits: int
    source_peak: int | None
    dynamic_peak_detection: bool
    dst_min_nits: float
    knee_offset: float
    smoothing_period: float
    scene_threshold_low: float
    scene_threshold_high: float
    percentile: float
    gamut_mapping: int
    metadata: int | None
    use_dovi: bool | None
    contrast_recovery: float
    gamma_lift: bool


class ReportTonemapPayload(TypedDict):
    applied: bool
    settings: ReportTonemapSettingsPayload | None


class ReportGeometryPayload(TypedDict):
    source_size: tuple[int, int]
    active_picture: ReportActivePicturePayload
    cropped_size: tuple[int, int]
    scaled_size: tuple[int, int]
    final_canvas_size: tuple[int, int]
    is_noop: bool


class ReportRenderingPayload(TypedDict):
    overlay_mode: str
    include_frame_number: bool
    tonemap: ReportTonemapPayload
    geometry_by_label: dict[str, ReportGeometryPayload]


class ReportIdentityClipPayload(TypedDict):
    name: str
    label: str
    frame_count: int
    resolution: tuple[int, int]
    fps: float
    size_bytes: int
    signal: ReportSignalPayload
    presentation: ReportPresentationPayload
    active_picture: ReportActivePicturePayload | None
    source_identity: str | None


class ReportIdentityImagePayload(TypedDict):
    clip: str
    source_frame: int
    picture_type: str | None
    dolby_vision_rpu: bool | None


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
    rendering: ReportRenderingPayload


@dataclass(frozen=True, slots=True)
class ReportImageInfo:
    """Screenshot input paired with canonical exact-source-frame facts."""

    path: Path
    source_frame: int
    facts: RenderedFrameFacts

    def __post_init__(self) -> None:
        if self.source_frame != self.facts.source_frame:
            raise ValueError("report image source frame does not match rendered facts")


@dataclass(frozen=True, slots=True)
class ReportClipDisplayInfo:
    primary: str
    release: str
    control: str
    micro: str
    filename: str


@dataclass(frozen=True, slots=True)
class ClipInfo:
    """Canonical clip/report input assembled by orchestration."""

    name: str
    path: Path
    frame_count: int
    resolution: tuple[int, int]
    fps: float
    size_bytes: int
    signal: SourceSignalFacts
    presentation_state: PresentationState
    tonemap_settings: TonemapSettings | None
    active_picture: ActivePictureFacts | None
    images: list[ReportImageInfo]
    display: ReportClipDisplayInfo
    label: str | None = None
    source_identity: str | None = None


@dataclass(frozen=True, slots=True)
class FrameDetail:
    """Optional report-owned display metadata for a comparison frame."""

    label: str | None = None
    detail: str | None = None
    category: str | None = None


@dataclass(frozen=True, slots=True)
class ReportRenderingInfo:
    """Effective output-affecting rendering configuration."""

    overlay_mode: OverlayMode
    include_frame_number: bool
    tonemap_settings: TonemapSettings | None
    geometry_by_label: dict[str, RenderedGeometryFacts]


@dataclass(frozen=True, slots=True)
class ReportData:
    """Validated report generation input."""

    clips: list[ClipInfo]
    frames: list[int]
    rendering: ReportRenderingInfo
    metadata: TmdbMetadata | None = None
    slowpics_url: str | None = None
    frame_details: list[FrameDetail] = field(default_factory=_empty_frame_details)

    def __post_init__(self) -> None:
        if self.frame_details and len(self.frame_details) != len(self.frames):
            raise ValueError(
                f"frame detail count mismatch: expected {len(self.frames)}, "
                f"got {len(self.frame_details)}"
            )
        labels = [clip.label or clip.name for clip in self.clips]
        if len(labels) != len(set(labels)):
            raise ValueError("report clip labels must be unique")
        if set(labels) != set(self.rendering.geometry_by_label):
            raise ValueError("report clips and rendering geometry must have identical label sets")
        for clip in self.clips:
            if len(clip.images) != len(self.frames):
                raise ValueError(
                    f"report image count mismatch for {clip.label or clip.name!r}: "
                    f"expected {len(self.frames)}, got {len(clip.images)}"
                )


def build_report_payload(
    data: ReportData, config: ReportConfig, *, report_dir: Path
) -> ReportPayload:
    """Shape validated report data into the embedded v1.2 JSON payload."""
    _validate_report_cardinality(data)
    title = data.metadata.title if data.metadata else data.clips[0].name
    clips = build_clip_payloads(data.clips)
    frames = build_frame_payloads(data, config, report_dir=report_dir)
    rendering = build_rendering_payload(data.rendering)
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
            default_mode=default_mode,
            default_selection=default_selection,
            stats=stats,
            clips=build_report_identity_clips(data.clips, clips),
            frames=frames,
            rendering=rendering,
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "title": title,
        "slowpics_url": data.slowpics_url,
        "default_mode": default_mode,
        "default_selection": default_selection,
        "stats": stats,
        "clips": clips,
        "frames": frames,
        "rendering": rendering,
    }


def _validate_report_cardinality(data: ReportData) -> None:
    """Fail at the report boundary before indexing or emitting partial HTML."""
    if not data.clips:
        raise ReportError("no clips provided")
    if not data.frames:
        raise ReportError("no frames provided")
    if data.frame_details and len(data.frame_details) != len(data.frames):
        raise ReportError(
            f"frame detail count mismatch: expected {len(data.frames)}, "
            f"got {len(data.frame_details)}"
        )
    for clip in data.clips:
        if len(clip.images) != len(data.frames):
            raise ReportError(
                f"screenshot count mismatch for {clip.name}: "
                f"expected {len(data.frames)}, got {len(clip.images)}"
            )


def build_clip_payloads(clips: list[ClipInfo]) -> list[ReportClipPayload]:
    """Build raw stable clip payload entries."""
    payloads: list[ReportClipPayload] = []
    for clip in clips:
        label = clip.label or clip.name
        display = clip.display
        payloads.append(
            {
                "name": clip.name,
                "label": label,
                "frame_count": clip.frame_count,
                "resolution": clip.resolution,
                "fps": clip.fps,
                "size_bytes": clip.size_bytes,
                "signal": _signal_payload(clip.signal),
                "presentation": _presentation_payload(
                    clip.presentation_state, clip.tonemap_settings
                ),
                "active_picture": (
                    None
                    if clip.active_picture is None or clip.active_picture.is_full_frame
                    else _active_picture_payload(clip.active_picture)
                ),
                "display": {
                    "primary": display.primary,
                    "release": display.release,
                    "control": display.control,
                    "micro": display.micro,
                    "filename": display.filename,
                },
            }
        )
    return payloads


def build_frame_payloads(
    data: ReportData, config: ReportConfig, *, report_dir: Path
) -> list[ReportFramePayload]:
    """Build comparison-domain frames with per-image source provenance."""
    frames: list[ReportFramePayload] = []
    for index, frame_number in enumerate(data.frames):
        detail = frame_detail_for_payload(data, frame_index=index, frame_number=frame_number)
        images: list[ReportImagePayload] = []
        for clip in data.clips:
            image = clip.images[index]
            images.append(
                {
                    "clip": clip.name,
                    "src": image_src_for_report(
                        image.path,
                        report_dir=report_dir,
                        embed_images=config.embed_images,
                    ),
                    "source_frame": image.source_frame,
                    "picture_type": image.facts.picture_type,
                    "dolby_vision_rpu": image.facts.dolby_vision_rpu,
                }
            )
        frames.append(
            {
                "number": frame_number,
                "label": detail.label or f"Frame {frame_number}",
                "detail": detail.detail or "Selected comparison frame",
                "category": detail.category or "selected",
                "images": images,
            }
        )
    return frames


def frame_detail_for_payload(
    data: ReportData, *, frame_index: int, frame_number: int
) -> FrameDetail:
    """Return comparison-domain display metadata without a source-frame claim."""
    if not data.frame_details:
        return FrameDetail(
            label=f"Frame {frame_number}",
            detail="Selected comparison frame",
            category="selected",
        )
    detail = data.frame_details[frame_index]
    return FrameDetail(
        label=detail.label or f"Frame {frame_number}",
        detail=detail.detail or "Selected comparison frame",
        category=detail.category or "selected",
    )


def build_rendering_payload(info: ReportRenderingInfo) -> ReportRenderingPayload:
    settings = info.tonemap_settings
    return {
        "overlay_mode": info.overlay_mode.value,
        "include_frame_number": info.include_frame_number,
        "tonemap": {
            "applied": settings is not None,
            "settings": _tonemap_settings_payload(settings) if settings is not None else None,
        },
        "geometry_by_label": {
            label: _geometry_payload(geometry)
            for label, geometry in sorted(info.geometry_by_label.items())
        },
    }


def build_default_selection(clip_count: int) -> ReportDefaultSelectionPayload:
    return {"left_clip_index": 0, "right_clip_index": 1 if clip_count > 1 else 0}


def build_report_identity_clips(
    clip_infos: list[ClipInfo], clips: list[ReportClipPayload]
) -> list[ReportIdentityClipPayload]:
    identity_clips: list[ReportIdentityClipPayload] = []
    for info, clip in zip(clip_infos, clips, strict=True):
        identity_clip = {key: value for key, value in clip.items() if key != "display"}
        identity_clips.append(
            cast(
                ReportIdentityClipPayload,
                {**identity_clip, "source_identity": info.source_identity},
            )
        )
    return identity_clips


def build_report_identity_frames(
    frames: list[ReportFramePayload],
) -> list[ReportIdentityFramePayload]:
    return [
        {
            "number": frame["number"],
            "label": frame["label"],
            "detail": frame["detail"],
            "category": frame["category"],
            "images": [
                {
                    "clip": image["clip"],
                    "source_frame": image["source_frame"],
                    "picture_type": image["picture_type"],
                    "dolby_vision_rpu": image["dolby_vision_rpu"],
                }
                for image in frame["images"]
            ],
        }
        for frame in frames
    ]


def build_report_id(
    *,
    title: str,
    default_mode: str,
    default_selection: ReportDefaultSelectionPayload,
    stats: ReportStatsPayload,
    clips: list[ReportIdentityClipPayload],
    frames: list[ReportFramePayload],
    rendering: ReportRenderingPayload,
) -> str:
    """Build stable identity without absolute paths, image sources, or timestamps."""
    identity_json = json.dumps(
        {
            "version": REPORT_VERSION,
            "title": title,
            "default_mode": default_mode,
            "default_selection": default_selection,
            "stats": stats,
            "clips": clips,
            "frames": build_report_identity_frames(frames),
            "rendering": rendering,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"report_{hashlib.sha256(identity_json.encode()).hexdigest()[:32]}"


def source_identity_from_fingerprint(fingerprint: ClipFingerprintProtocol) -> str:
    source_json = json.dumps(
        {
            "basename": fingerprint.path.name,
            "size_bytes": fingerprint.size_bytes,
            "mtime_ns": fingerprint.mtime_ns,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"source_{hashlib.sha256(source_json.encode()).hexdigest()[:32]}"


def image_src_for_report(screenshot_path: Path, *, report_dir: Path, embed_images: bool) -> str:
    resolved_screenshot = _resolve_report_screenshot(screenshot_path, report_dir)
    if embed_images:
        try:
            encoded = base64.b64encode(resolved_screenshot.read_bytes()).decode("ascii")
        except OSError as exc:
            raise ReportError(f"failed to encode image: {screenshot_path}") from exc
        return f"data:image/png;base64,{encoded}"
    try:
        relative_path = Path(os.path.relpath(resolved_screenshot, report_dir.resolve()))
    except (OSError, RuntimeError, ValueError) as exc:
        raise ReportError("screenshot path cannot be made relative to the report") from exc
    if relative_path.is_absolute():
        raise ReportError("screenshot path must be relative to the report")
    return relative_path.as_posix()


def _resolve_report_screenshot(screenshot_path: Path, report_dir: Path) -> Path:
    try:
        resolved = require_managed_descendant(report_dir, screenshot_path)
    except (OSError, RuntimeError, ValueError, PathEscapesRootError) as exc:
        raise ReportError("screenshot path is outside the report directory") from exc
    try:
        is_regular_file = resolved.is_file()
    except OSError as exc:
        raise ReportError(f"failed to inspect screenshot: {screenshot_path}") from exc
    if not is_regular_file:
        if not resolved.exists():
            raise ReportError(f"screenshot not found: {screenshot_path}")
        raise ReportError(f"screenshot is not a regular file: {screenshot_path}")
    return resolved


def _signal_payload(signal: SourceSignalFacts) -> ReportSignalPayload:
    static = signal.hdr_static
    return {
        "is_hdr": signal.is_hdr,
        "primaries": signal.primaries,
        "transfer": signal.transfer,
        "matrix": signal.matrix,
        "range": signal.color_range,
        "dolby_vision_rpu": signal.dolby_vision_rpu,
        "hdr_static": (
            {
                "mastering_min_nits": static.mastering_min_nits,
                "mastering_max_nits": static.mastering_max_nits,
                "max_cll": static.max_cll,
                "max_fall": static.max_fall,
            }
            if static is not None
            else None
        ),
    }


def _presentation_payload(
    state: PresentationState, settings: TonemapSettings | None
) -> ReportPresentationPayload:
    return {
        "state": state.value,
        "tone_curve": settings.tone_curve.value if settings is not None else None,
        "target_nits": settings.target_nits if settings is not None else None,
    }


def _active_picture_payload(active: ActivePictureFacts) -> ReportActivePicturePayload:
    return {
        "x": active.x,
        "y": active.y,
        "width": active.width,
        "height": active.height,
        "provenance": active.provenance,
        "is_full_frame": active.is_full_frame,
    }


def _tonemap_settings_payload(settings: TonemapSettings) -> ReportTonemapSettingsPayload:
    return {
        "enabled": settings.enabled,
        "preset": settings.preset.value,
        "tone_curve": settings.tone_curve.value,
        "target_nits": settings.target_nits,
        "source_peak": settings.source_peak,
        "dynamic_peak_detection": settings.dynamic_peak_detection,
        "dst_min_nits": settings.dst_min_nits,
        "knee_offset": settings.knee_offset,
        "smoothing_period": settings.smoothing_period,
        "scene_threshold_low": settings.scene_threshold_low,
        "scene_threshold_high": settings.scene_threshold_high,
        "percentile": settings.percentile,
        "gamut_mapping": settings.gamut_mapping,
        "metadata": settings.metadata,
        "use_dovi": settings.use_dovi,
        "contrast_recovery": settings.contrast_recovery,
        "gamma_lift": settings.gamma_lift,
    }


def _geometry_payload(geometry: RenderedGeometryFacts) -> ReportGeometryPayload:
    return {
        "source_size": geometry.source_size,
        "active_picture": _active_picture_payload(geometry.active_picture),
        "cropped_size": geometry.cropped_size,
        "scaled_size": geometry.scaled_size,
        "final_canvas_size": geometry.final_canvas_size,
        "is_noop": geometry.is_noop,
    }


__all__ = [
    "ClipInfo",
    "FrameDetail",
    "REPORT_VERSION",
    "ReportClipDisplayInfo",
    "ReportClipDisplayPayload",
    "ReportClipPayload",
    "ReportData",
    "ReportFramePayload",
    "ReportImageInfo",
    "ReportPayload",
    "ReportRenderingInfo",
    "build_report_payload",
    "source_identity_from_fingerprint",
]
