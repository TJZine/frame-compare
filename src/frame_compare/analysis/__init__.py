"""Analysis module for frame-compare."""

from __future__ import annotations

import typing

from frame_compare.analysis.cache_io import (
    compute_cache_key,
    load_cached_metrics,
    save_metrics_cache,
)
from frame_compare.analysis.frame_plan import (
    FramePlan,
    create_frame_plan,
    select_uniform_seeded_frames,
)
from frame_compare.analysis.types import (
    CacheLoadResult,
    ClipIdentity,
    FrameMetrics,
    FrameSelection,
    MetricsMetadata,
    SelectionBreakdown,
)

if typing.TYPE_CHECKING:
    from frame_compare.analysis.metrics import ANALYZE_PROGRESS_TOTAL, calculate_metrics
    from frame_compare.analysis.selection import select_frames

__all__ = [
    "ANALYZE_PROGRESS_TOTAL",
    "CacheLoadResult",
    "ClipIdentity",
    "FrameMetrics",
    "FramePlan",
    "FrameSelection",
    "MetricsMetadata",
    "SelectionBreakdown",
    "calculate_metrics",
    "compute_cache_key",
    "create_frame_plan",
    "load_cached_metrics",
    "save_metrics_cache",
    "select_frames",
    "select_uniform_seeded_frames",
]


def __getattr__(name: str) -> typing.Any:
    if name == "ANALYZE_PROGRESS_TOTAL":
        from frame_compare.analysis.metrics import ANALYZE_PROGRESS_TOTAL

        return ANALYZE_PROGRESS_TOTAL

    if name == "calculate_metrics":
        from frame_compare.analysis.metrics import calculate_metrics

        return calculate_metrics

    if name == "select_frames":
        from frame_compare.analysis.selection import select_frames

        return select_frames

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
