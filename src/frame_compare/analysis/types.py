"""Analysis module data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING

from frame_compare.config import SelectionMode

if TYPE_CHECKING:
    from collections.abc import Sequence


def _empty_int_list() -> list[int]:
    return []


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
class MetricsMetadata:
    """Metadata about the analysis run stored with cache.

    Fields:
        frame_count: Number of frames in source video
        fps: Source video framerate
        config_fingerprint: Hash of analysis configuration
        clips: List of clip identities involved (usually just one)
        version: Cache schema version
    """

    frame_count: int
    fps: Fraction
    config_fingerprint: str
    clips: Sequence[ClipIdentity]
    version: int = 2


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
        quantile_dark: Frames selected for lowest luminance
        quantile_bright: Frames selected for highest luminance
        motion: Frames selected for scene changes/motion
        random: Frames selected for uniform distribution
    """

    quantile_dark: Sequence[int] = field(default_factory=_empty_int_list)
    quantile_bright: Sequence[int] = field(default_factory=_empty_int_list)
    motion: Sequence[int] = field(default_factory=_empty_int_list)
    random: Sequence[int] = field(default_factory=_empty_int_list)


@dataclass(frozen=True, slots=True)
class FrameSelection:
    """Final list of selected frame numbers and metadata.

    Fields:
        frames: Sorted list of unique frame numbers
        mode: The strategy used for selection
        seed: Random seed used
        breakdown: Details of selection sources
    """

    frames: Sequence[int]
    mode: SelectionMode
    seed: int
    breakdown: SelectionBreakdown


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
    reason: str | None = None
