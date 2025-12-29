"""Analysis module for frame-compare."""

from frame_compare.analysis.cache_io import (
    compute_cache_key,
    load_cached_metrics,
    save_metrics_cache,
)
from frame_compare.analysis.selection import select_frames
from frame_compare.analysis.types import (
    CacheLoadResult,
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricsMetadata,
    SelectionBreakdown,
)

__all__ = [
    "CacheLoadResult",
    "ClipIdentity",
    "FrameMetrics",
    "FrameSelection",
    "MetricsMetadata",
    "SelectionBreakdown",
    "compute_cache_key",
    "load_cached_metrics",
    "save_metrics_cache",
    "select_frames",
]
