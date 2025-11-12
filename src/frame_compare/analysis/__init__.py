"""Public entrypoints for frame comparison analysis helpers."""

from __future__ import annotations

from .cache_io import (
    CachedMetrics,
    CacheLoadResult,
    FrameMetricsCacheInfo,
    probe_cached_metrics,
    write_selection_cache_file,
)
from .selection import (
    SelectionDetail,
    SelectionWindowSpec,
    compute_selection_window,
    dedupe,
    select_frames,
    selection_details_to_json,
    selection_hash_for_config,
)

__all__ = [
    "CacheLoadResult",
    "CachedMetrics",
    "FrameMetricsCacheInfo",
    "SelectionDetail",
    "SelectionWindowSpec",
    "compute_selection_window",
    "dedupe",
    "probe_cached_metrics",
    "select_frames",
    "selection_details_to_json",
    "selection_hash_for_config",
    "write_selection_cache_file",
]
