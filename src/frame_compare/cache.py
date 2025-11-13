"""Helpers for constructing analysis cache metadata."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import List, Optional, Sequence

from src.datatypes import AppConfig
from src.frame_compare.analysis import FrameMetricsCacheInfo
from src.frame_compare.analysis.cache_io import (
    ClipIdentity,
    cache_hash_env_requested,
    compute_file_sha1,
    infer_clip_role,
)
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
    clip_identities: List[ClipIdentity] = []
    should_hash = cache_hash_env_requested()
    total = len(plans)
    analyzed_name = analyzed.path.name
    for idx, plan in enumerate(plans):
        resolved = plan.path.resolve()
        stat_ok = True
        try:
            stat_result = resolved.stat()
            size = int(stat_result.st_size)
            mtime = _dt.datetime.fromtimestamp(stat_result.st_mtime, tz=_dt.timezone.utc).isoformat()
        except OSError:
            stat_ok = False
            size = None
            mtime = None
        sha1 = None
        if should_hash and stat_ok:
            try:
                sha1 = compute_file_sha1(resolved)
            except OSError:
                sha1 = None
        clip_identities.append(
            ClipIdentity(
                role=infer_clip_role(idx, plan.path.name, analyzed_name, total),
                path=str(resolved),
                name=plan.path.name,
                size=size,
                mtime=mtime,
                sha1=sha1,
            )
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
        clips=clip_identities,
    )


def build_cache_info(
    root: Path,
    plans: Sequence[ClipPlan],
    cfg: AppConfig,
    analyze_index: int,
) -> Optional[FrameMetricsCacheInfo]:
    """Public wrapper around the cache metadata builder."""

    return _build_cache_info(root, plans, cfg, analyze_index)
