"""Helpers for constructing analysis cache metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from src.analysis import FrameMetricsCacheInfo
from src.datatypes import AppConfig
from src.frame_compare.cli_runtime import ClipPlan

from .preflight import resolve_subdir

__all__ = ["build_cache_info", "_build_cache_info"]


def _build_cache_info(
    root: Path,
    plans: Sequence[ClipPlan],
    cfg: AppConfig,
    analyze_index: int,
) -> Optional[FrameMetricsCacheInfo]:
    """
    Build cache metadata describing frame-metrics that can be saved for reuse.

    Returns ``None`` when frame-data saving is disabled.
    """

    if not cfg.analysis.save_frames_data:
        return None

    analyzed = plans[analyze_index]
    fps_num, fps_den = analyzed.effective_fps or (24000, 1001)
    if fps_den <= 0:
        fps_den = 1

    cache_path = resolve_subdir(
        root,
        cfg.analysis.frame_data_filename,
        purpose="analysis.frame_data_filename",
    )
    return FrameMetricsCacheInfo(
        path=cache_path,
        files=[plan.path.name for plan in plans],
        analyzed_file=analyzed.path.name,
        release_group=analyzed.metadata.get("release_group", ""),
        trim_start=analyzed.trim_start,
        trim_end=analyzed.trim_end,
        fps_num=fps_num,
        fps_den=fps_den,
    )


def build_cache_info(
    root: Path,
    plans: Sequence[ClipPlan],
    cfg: AppConfig,
    analyze_index: int,
) -> Optional[FrameMetricsCacheInfo]:
    """Public wrapper around the cache metadata builder."""

    return _build_cache_info(root, plans, cfg, analyze_index)
