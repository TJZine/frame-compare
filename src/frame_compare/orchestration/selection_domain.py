"""Selection-window and cache-domain helpers for orchestration.

These helpers are pure and deterministic so production preparation logic and
tests can share the same owner seam without importing private preparation
helpers.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from frame_compare.analysis.window import (
    ClipWindowInput,
    SelectionWindow,
    compute_shared_selection_window,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection, SourceMatchFpsMode
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.active_rect import (
    active_rect_identity,
    active_rect_policy_identity,
    resolve_active_rects_for_clips,
)
from frame_compare.orchestration.context import (
    ACTIVE_RECT_RESOLUTION_ALGORITHM,
    ClipProbeSnapshot,
    ClipState,
)
from frame_compare.orchestration.errors import SourceSelectionError


@dataclass(frozen=True)
class FpsMatchDiagnostics:
    """Human-facing details about automatic FPS matching."""

    target_fps: str | None = None
    reason: str | None = None
    changed_clips: tuple[str, ...] = ()

    def messages(self) -> list[str]:
        if not self.changed_clips and self.reason != "reference fallback; no FPS majority":
            return []
        messages: list[str] = []
        if self.target_fps is not None and self.reason is not None:
            messages.append(f"FPS target: {self.target_fps} ({self.reason})")
        messages.extend(f"FPS matched: {changed}" for changed in self.changed_clips)
        return messages

    def warnings(self) -> list[str]:
        if self.reason != "reference fallback; no FPS majority" or self.target_fps is None:
            return []
        return [f"sources: FPS target {self.target_fps} ({self.reason})"]


@dataclass(frozen=True)
class SelectionDomainClips:
    """Prepared clips plus FPS matching diagnostics."""

    clips: list[ClipState]
    fps_diagnostics: FpsMatchDiagnostics


def build_selection_domain_clips(
    *,
    ordered_paths: list[Path],
    snapshots_by_path: dict[Path, ClipProbeSnapshot],
    overrides_by_path: dict[Path, SourceOverrideConfig],
    match_fps: SourceMatchFpsMode = SourceMatchFpsMode.DISABLED,
    active_rect_detection: ScreenshotActiveRectDetection = (
        ScreenshotActiveRectDetection.ASPECT_RATIO
    ),
) -> list[ClipState]:
    """Build prepared clip states for selection-domain and cache decisions."""
    return build_selection_domain_clips_with_diagnostics(
        ordered_paths=ordered_paths,
        snapshots_by_path=snapshots_by_path,
        overrides_by_path=overrides_by_path,
        match_fps=match_fps,
        active_rect_detection=active_rect_detection,
    ).clips


def build_selection_domain_clips_with_diagnostics(
    *,
    ordered_paths: list[Path],
    snapshots_by_path: dict[Path, ClipProbeSnapshot],
    overrides_by_path: dict[Path, SourceOverrideConfig],
    match_fps: SourceMatchFpsMode = SourceMatchFpsMode.DISABLED,
    active_rect_detection: ScreenshotActiveRectDetection = (
        ScreenshotActiveRectDetection.ASPECT_RATIO
    ),
) -> SelectionDomainClips:
    """Build prepared clip states and return automatic FPS matching diagnostics."""
    clips = [
        _build_selection_domain_clip(
            index=index,
            path=path,
            snapshot=snapshots_by_path[path],
            override=overrides_by_path.get(path),
        )
        for index, path in enumerate(ordered_paths)
    ]
    clips = resolve_active_rects_for_clips(
        clips=clips,
        overrides_by_path=overrides_by_path,
        detection=active_rect_detection,
    )
    if match_fps == SourceMatchFpsMode.ASSUME_REFERENCE:
        matched = _apply_reference_fps_match(
            clips=clips,
            ordered_paths=ordered_paths,
            overrides_by_path=overrides_by_path,
        )
        return SelectionDomainClips(clips=matched, fps_diagnostics=FpsMatchDiagnostics())
    if match_fps == SourceMatchFpsMode.MAJORITY:
        return _apply_majority_fps_match(
            clips=clips,
            ordered_paths=ordered_paths,
            overrides_by_path=overrides_by_path,
        )
    return SelectionDomainClips(clips=clips, fps_diagnostics=FpsMatchDiagnostics())


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


def _apply_majority_fps_match(
    *,
    clips: list[ClipState],
    ordered_paths: list[Path],
    overrides_by_path: dict[Path, SourceOverrideConfig],
) -> SelectionDomainClips:
    if len(clips) < 2:
        return SelectionDomainClips(clips=clips, fps_diagnostics=FpsMatchDiagnostics())

    counts = Counter(clip.effective_fps for clip in clips)
    majority_fps = next((fps for fps, count in counts.items() if count > len(clips) / 2), None)
    if majority_fps is None:
        target_fps = clips[0].effective_fps
        reason = "reference fallback; no FPS majority"
    else:
        target_fps = majority_fps
        reason = "majority"

    matched: list[ClipState] = []
    changed: list[str] = []
    for path, clip in zip(ordered_paths, clips, strict=True):
        override = overrides_by_path.get(path)
        if override is not None and override.effective_fps is not None:
            matched.append(clip)
            continue
        if clip.effective_fps == target_fps:
            matched.append(clip)
            continue
        matched.append(replace(clip, effective_fps=target_fps))
        changed.append(f"{clip.path.name} {clip.effective_fps} -> {target_fps}")

    return SelectionDomainClips(
        clips=matched,
        fps_diagnostics=FpsMatchDiagnostics(
            target_fps=str(target_fps),
            reason=reason,
            changed_clips=tuple(changed),
        ),
    )


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
    analysis_clip: ClipState | None = None,
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
        "active_rect_policy": active_rect_policy_identity(
            config.screenshots.active_rect_detection
        ),
        "clips": [
            {
                "active_rect": (
                    active_rect_identity(clip.active_rect)
                    if clip.active_rect is not None
                    else _full_frame_active_rect_identity_fallback(clip, config)
                ),
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
        "analysis_source_path": analysis_clip.path.as_posix()
        if analysis_clip is not None
        else None,
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


def _full_frame_active_rect_identity_fallback(
    clip: ClipState,
    config: ConfigSchema,
) -> object:
    return {
        "x": 0,
        "y": 0,
        "width": clip.probe.width,
        "height": clip.probe.height,
        "source": "full-frame",
        "detection_mode": config.screenshots.active_rect_detection.value,
        "algorithm_id": ACTIVE_RECT_RESOLUTION_ALGORITHM,
    }
