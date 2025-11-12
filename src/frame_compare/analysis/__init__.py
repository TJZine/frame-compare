"""Public entrypoints for frame comparison analysis helpers."""

from __future__ import annotations

from src.frame_compare import vs as vs_core

from .cache_io import (
    CachedMetrics,
    CacheLoadResult,
    FrameMetricsCacheInfo,
    _save_cached_metrics,  # pyright: ignore[reportPrivateUsage]
    build_clip_inputs_from_paths,
    export_selection_metadata,
    probe_cached_metrics,
    write_selection_cache_file,
)
from .metrics import (
    _collect_metrics_vapoursynth,  # pyright: ignore[reportPrivateUsage]
    _generate_metrics_fallback,  # pyright: ignore[reportPrivateUsage]
    _quantile,  # pyright: ignore[reportPrivateUsage]
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
    "build_clip_inputs_from_paths",
    "SelectionDetail",
    "SelectionWindowSpec",
    "compute_selection_window",
    "dedupe",
    "export_selection_metadata",
    "probe_cached_metrics",
    "select_frames",
    "selection_details_to_json",
    "selection_hash_for_config",
    "write_selection_cache_file",
    "_collect_metrics_vapoursynth",
    "_generate_metrics_fallback",
    "_quantile",
    "_save_cached_metrics",
    "vs_core",
]
