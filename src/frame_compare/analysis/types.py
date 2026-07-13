"""Analysis module data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence


CacheLoadReason = Literal["not_found", "corrupted", "version_mismatch", "mismatched_inputs"]
ActiveRectSource = Literal[
    "explicit",
    "metadata",
    "dimension-derived",
    "aspect-ratio-derived",
    "content-derived",
    "full-frame",
]
ActiveRectDetectionMode = Literal["provided", "dimension", "aspect_ratio", "auto"]
ActiveRectAlgorithmId = Literal["active_rect_resolution_v2"]
type SelectionDetailsByFrame = dict[int, SelectionDetail]


def _empty_int_list() -> list[int]:
    return []


def _empty_selection_detail_map() -> SelectionDetailsByFrame:
    return {}


@dataclass(frozen=True, slots=True)
class ClipIdentity:
    """Unique identity of a video clip for caching purposes.

    Fields:
        path: Original input path
        size: File size in bytes
        mtime: Modification time
        sha1: Optional full or partial file hash
    """

    path: str
    size: int
    mtime: float
    sha1: str | None = None


@dataclass(frozen=True, slots=True)
class MetricActiveRect:
    """Analysis-owned active image rectangle in source-frame coordinates."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class MetricFrameRange:
    """Contiguous source-frame domain represented by cached metric arrays."""

    source_frame_count: int
    start: int
    end_exclusive: int

    def __post_init__(self) -> None:
        if self.source_frame_count < 0:
            raise ValueError("Metric source frame count must be non-negative")
        if self.start < 0 or self.end_exclusive < self.start:
            raise ValueError("Metric frame range boundaries are invalid")
        if self.end_exclusive > self.source_frame_count:
            raise ValueError("Metric frame range exceeds the source frame count")

    @property
    def frame_count(self) -> int:
        return self.end_exclusive - self.start


@dataclass(frozen=True, slots=True)
class MetricCacheRequest:
    """Complete requested identity for metric-array cache lookup and validation."""

    analysis_source_path: Path | None
    metric_frame_range: MetricFrameRange | None = None
    effective_fps: Fraction | None = None
    metric_active_rect: MetricActiveRect | None = None
    active_rect_source: ActiveRectSource = "full-frame"
    active_rect_detection_mode: ActiveRectDetectionMode = "aspect_ratio"
    active_rect_algorithm_id: ActiveRectAlgorithmId = "active_rect_resolution_v2"


@dataclass(frozen=True, slots=True)
class MetricsMetadata:
    """Metadata about the analysis run stored with cache.

    Fields:
        frame_count: Number of frames in source video
        fps: Source video framerate
        config_fingerprint: Hash of analysis configuration
        clips: List of clip identities involved (usually just one)
        analysis_source_path: Path to the source used for analysis, if any
        performance_mode: Analysis performance mode that produced the arrays
        algorithm_id: Stable ID for the metric algorithm identity
        metric_backend: Metric backend family that produced the arrays
        algorithm_identity_json: Stable JSON identity payload for cache/debugging
        metric_active_rect: Active rectangle used for metric arrays; None means full frame
        active_rect_source: Provenance for the metric active rectangle
        active_rect_detection_mode: Active-rect detection mode used by preparation
        active_rect_algorithm_id: Resolver algorithm ID used by preparation
        version: Cache schema version
    """

    frame_count: int
    fps: Fraction
    config_fingerprint: str
    clips: Sequence[ClipIdentity]
    source_frame_count: int = -1
    metric_source_start: int = 0
    metric_source_end_exclusive: int = -1
    analysis_source_path: str = ""
    performance_mode: str = "quality"
    algorithm_id: str = ""
    metric_backend: str = ""
    algorithm_identity_json: str = "{}"
    metric_active_rect: MetricActiveRect | None = None
    active_rect_source: ActiveRectSource = "full-frame"
    active_rect_detection_mode: ActiveRectDetectionMode = "aspect_ratio"
    active_rect_algorithm_id: ActiveRectAlgorithmId = "active_rect_resolution_v2"
    version: int = 7

    def __post_init__(self) -> None:
        """Normalize legacy in-memory constructors to a full-source metric domain."""
        if self.source_frame_count == -1:
            object.__setattr__(self, "source_frame_count", self.frame_count)
        if self.metric_source_end_exclusive == -1:
            object.__setattr__(self, "metric_source_end_exclusive", self.frame_count)
        if self.frame_count < 0 or self.source_frame_count < 0:
            raise ValueError("Metric frame counts must be non-negative")
        if (
            self.metric_source_start < 0
            or self.metric_source_end_exclusive < self.metric_source_start
            or self.metric_source_end_exclusive > self.source_frame_count
            or self.metric_source_end_exclusive - self.metric_source_start != self.frame_count
        ):
            raise ValueError("Metric metadata frame range is inconsistent")


@dataclass(frozen=True, slots=True)
class FrameMetrics:
    """Calculated metrics for all frames in a video.

    Fields:
        luminance: Array of luminance values (0.0-1.0) per frame
        motion: Array of scene change probabilities (0.0-1.0) per frame
        metadata: Source metadata
    """

    luminance: Sequence[float]
    motion: Sequence[float]
    metadata: MetricsMetadata


@dataclass(frozen=True, slots=True)
class SelectionBreakdown:
    """Breakdown of which frames were selected by which criteria.

    Fields:
        user: Explicit user-selected frames
        quantile_dark: Frames selected for lowest luminance
        quantile_bright: Frames selected for highest luminance
        motion: Frames selected for scene changes/motion
        random: Frames selected for uniform distribution
    """

    user: Sequence[int] = field(default_factory=_empty_int_list)
    quantile_dark: Sequence[int] = field(default_factory=_empty_int_list)
    quantile_bright: Sequence[int] = field(default_factory=_empty_int_list)
    motion: Sequence[int] = field(default_factory=_empty_int_list)
    random: Sequence[int] = field(default_factory=_empty_int_list)


@dataclass(frozen=True, slots=True)
class SelectionDetail:
    """Typed per-frame selection metadata in the reference source-frame domain."""

    frame_index: int
    label: str
    source: str
    timecode: str | None = None
    score: float | None = None
    clip_role: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class FrameSelection:
    """Final list of selected frame numbers and metadata.

    Fields:
        frames: Sorted list of unique frame numbers
        seed: Random seed used
        breakdown: Details of selection sources
        selection_details: Source-frame keyed typed metadata
    """

    frames: Sequence[int]
    seed: int
    breakdown: SelectionBreakdown
    selection_details: SelectionDetailsByFrame = field(default_factory=_empty_selection_detail_map)


@dataclass(frozen=True, slots=True)
class CacheLoadResult:
    """Result of attempting to load metrics from cache.

    Fields:
        success: Whether load was successful
        metrics: The loaded metrics if success=True
        reason: Why load failed (miss, invalid, stale) if success=False
    """

    success: bool
    metrics: FrameMetrics | None = None
    reason: CacheLoadReason | None = None
