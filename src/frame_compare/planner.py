"""Clip planning helpers shared between the runner and CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence

from src.datatypes import AppConfig
from src.frame_compare.cli_runtime import ClipPlan
from src.frame_compare.metadata import match_override, normalise_override_mapping

MetadataRecord = Dict[str, str]


def build_plans(
    files: Sequence[Path],
    metadata: Sequence[MetadataRecord],
    cfg: AppConfig,
) -> list[ClipPlan]:
    """
    Construct clip plans with trim and FPS overrides applied.

    Parameters:
        files (Sequence[Path]): Ordered list of media files to plan.
        metadata (Sequence[Dict[str, str]]): Metadata entries aligned with ``files``.
        cfg (AppConfig): Loaded configuration supplying override maps.

    Returns:
        list[ClipPlan]: Planned clips mirroring the provided order with overrides applied.
    """

    trim_map = normalise_override_mapping(cfg.overrides.trim)
    trim_end_map = normalise_override_mapping(cfg.overrides.trim_end)
    fps_map = normalise_override_mapping(cfg.overrides.change_fps)

    plans: list[ClipPlan] = []
    for idx, file in enumerate(files):
        meta = dict(metadata[idx])
        plan = ClipPlan(path=file, metadata=meta)

        trim_val = match_override(idx, file, meta, trim_map)
        if trim_val is not None:
            plan.trim_start = int(trim_val)
            plan.has_trim_start_override = True

        trim_end_val = match_override(idx, file, meta, trim_end_map)
        if trim_end_val is not None:
            plan.trim_end = int(trim_end_val)
            plan.has_trim_end_override = True

        fps_val = match_override(idx, file, meta, fps_map)
        if isinstance(fps_val, str):
            if fps_val.lower() == "set":
                plan.use_as_reference = True
        elif isinstance(fps_val, list):
            if len(fps_val) == 2:
                plan.fps_override = (int(fps_val[0]), int(fps_val[1]))
        elif fps_val is not None:
            raise ValueError("Unsupported change_fps override type")

        plans.append(plan)

    return plans


__all__ = ["build_plans"]
