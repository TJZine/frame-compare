"""Selection-window and cache-domain helpers for orchestration.

These helpers are pure and deterministic so production preparation logic and
tests can share the same owner seam without importing private preparation
helpers.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from frame_compare.analysis.window import (
    ClipWindowInput,
    SelectionWindow,
    compute_shared_selection_window,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import SourceMatchFpsMode
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.context import (
    ClipActiveRect,
    ClipProbeSnapshot,
    ClipState,
)
from frame_compare.orchestration.errors import SourceSelectionError


def build_selection_domain_clips(
    *,
    ordered_paths: list[Path],
    snapshots_by_path: dict[Path, ClipProbeSnapshot],
    overrides_by_path: dict[Path, SourceOverrideConfig],
    match_fps: SourceMatchFpsMode = SourceMatchFpsMode.DISABLED,
) -> list[ClipState]:
    """Build prepared clip states for selection-domain and cache decisions."""
    clips = [
        _build_selection_domain_clip(
            index=index,
            path=path,
            snapshot=snapshots_by_path[path],
            override=overrides_by_path.get(path),
        )
        for index, path in enumerate(ordered_paths)
    ]
    if match_fps == SourceMatchFpsMode.ASSUME_REFERENCE:
        return _apply_reference_fps_match(
            clips=clips,
            ordered_paths=ordered_paths,
            overrides_by_path=overrides_by_path,
        )
    return clips


def _apply_reference_fps_match(
    *,
    clips: list[ClipState],
    ordered_paths: list[Path],
    overrides_by_path: dict[Path, SourceOverrideConfig],
) -> list[ClipState]:
    if len(clips) < 2:
        return clips

    reference_fps = clips[0].effective_fps
    matched: list[ClipState] = [clips[0]]
    for path, clip in zip(ordered_paths[1:], clips[1:], strict=True):
        override = overrides_by_path.get(path)
        if override is not None and override.effective_fps is not None:
            matched.append(clip)
            continue
        matched.append(replace(clip, effective_fps=reference_fps))
    return matched


def _build_selection_domain_clip(
    *,
    index: int,
    path: Path,
    snapshot: ClipProbeSnapshot,
    override: SourceOverrideConfig | None,
) -> ClipState:
    trim_start_frames = override.trim_start_frames if override is not None else 0
    trim_end_frames = override.trim_end_frames if override is not None else 0
    end_inclusive = snapshot.num_frames - 1 - trim_end_frames if trim_end_frames > 0 else None
    effective_end = end_inclusive if end_inclusive is not None else snapshot.num_frames - 1
    if trim_start_frames > effective_end:
        raise SourceSelectionError(
            selector=path.name,
            reason="source trims remove every frame",
            role="sources.overrides",
            matches=[path],
        )

    active_rect = None
    if override is not None and override.active_rect is not None:
        rect = override.active_rect
        if rect.x + rect.width > snapshot.width or rect.y + rect.height > snapshot.height:
            raise SourceSelectionError(
                selector=path.name,
                reason="active_rect is outside source dimensions",
                role="sources.overrides",
                matches=[path],
            )
        active_rect = ClipActiveRect(
            x=rect.x,
            y=rect.y,
            width=rect.width,
            height=rect.height,
        )

    effective_fps = (
        override.effective_fps
        if override is not None and override.effective_fps is not None
        else snapshot.fps
    )
    label = "Reference" if index == 0 else f"Encode {index}"
    return ClipState(
        path=path,
        label=label,
        probe=snapshot,
        source_fps=snapshot.fps,
        effective_fps=effective_fps,
        active_rect=active_rect,
    ).with_trim(
        trim_start_frames=trim_start_frames,
        trim_end_frame_inclusive=end_inclusive,
    )


def compute_selection_window_for_clips(
    *,
    clips: list[ClipState],
    config: ConfigSchema,
) -> SelectionWindow:
    """Compute the shared selection window across prepared clips."""
    return compute_shared_selection_window(
        [
            ClipWindowInput(frame_count=clip.effective_num_frames(), fps=clip.effective_fps)
            for clip in clips
        ],
        ignore_lead_seconds=config.analysis.ignore_lead_seconds,
        ignore_trail_seconds=config.analysis.ignore_trail_seconds,
        min_window_seconds=config.analysis.min_window_seconds,
    )


def build_analysis_selection_domain_token(
    *,
    clips: list[ClipState],
    config: ConfigSchema,
    selection_window: SelectionWindow,
) -> str:
    """Build the stable cache-domain token for analysis selection."""
    analysis = config.analysis
    payload = {
        "analysis": {
            "ignore_lead_seconds": analysis.ignore_lead_seconds,
            "ignore_trail_seconds": analysis.ignore_trail_seconds,
            "min_window_seconds": analysis.min_window_seconds,
        },
        "clips": [
            {
                "effective_fps": {
                    "denominator": clip.effective_fps.denominator,
                    "numerator": clip.effective_fps.numerator,
                },
                "mtime_ns": clip.probe.fingerprint.mtime_ns,
                "path": clip.path.as_posix(),
                "size_bytes": clip.probe.fingerprint.size_bytes,
                "trim_end_frame_inclusive": clip.trim.trim_end_frame_inclusive,
                "trim_start_frames": clip.trim.trim_start_frames,
            }
            for clip in clips
        ],
        "reference_path": clips[0].path.as_posix() if clips else None,
        "selection_window": {
            "end_frame_exclusive": selection_window.end_frame_exclusive,
            "start_frame": selection_window.start_frame,
        },
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
