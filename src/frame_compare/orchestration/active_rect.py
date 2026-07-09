"""Prepared active-picture rectangle resolution for orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from frame_compare.config.schema_enums import ScreenshotActiveRectDetection
from frame_compare.config.schema_models import SourceOverrideConfig
from frame_compare.orchestration.context import (
    ACTIVE_RECT_RESOLUTION_ALGORITHM,
    ClipActiveRect,
    ClipActiveRectDetectionMode,
    ClipActiveRectSource,
    ClipState,
)
from frame_compare.orchestration.errors import SourceSelectionError

ASPECT_RATIO_MATCH_REL_TOLERANCE = 0.005
ASPECT_RATIO_MIN_CROP_REL_DELTA = 0.005
ASPECT_RATIO_MAX_HEIGHT_REMOVAL_FRACTION = 0.35


@dataclass(frozen=True, slots=True)
class _AspectCandidate:
    ratio: float
    first_source_index: int
    evidence_rank: int


def resolve_active_rects_for_clips(
    *,
    clips: Sequence[ClipState],
    overrides_by_path: Mapping[Path, SourceOverrideConfig],
    detection: ScreenshotActiveRectDetection,
) -> list[ClipState]:
    """Return clips with final active-picture rectangles and provenance."""
    mode = _detection_mode(detection)
    explicit_rects = tuple(
        _explicit_active_rect_for_clip(clip, overrides_by_path.get(clip.path), mode)
        for clip in clips
    )
    metadata_rects = tuple(_metadata_active_rect_for_clip(clip, mode) for clip in clips)
    dimension_rects = (
        _dimension_derived_active_rects(clips, mode)
        if detection
        in (
            ScreenshotActiveRectDetection.DIMENSION,
            ScreenshotActiveRectDetection.ASPECT_RATIO,
            ScreenshotActiveRectDetection.AUTO,
        )
        else tuple(None for _clip in clips)
    )

    resolved: list[ClipActiveRect] = []
    for clip, explicit, metadata, dimension in zip(
        clips,
        explicit_rects,
        metadata_rects,
        dimension_rects,
        strict=True,
    ):
        if explicit is not None:
            resolved.append(explicit)
        elif metadata is not None:
            resolved.append(metadata)
        elif dimension is not None:
            resolved.append(dimension)
        else:
            resolved.append(_full_frame_rect(clip, mode))

    if detection in (
        ScreenshotActiveRectDetection.ASPECT_RATIO,
        ScreenshotActiveRectDetection.AUTO,
    ):
        resolved = list(_aspect_ratio_derived_active_rects(clips, tuple(resolved), mode))

    return [replace(clip, active_rect=rect) for clip, rect in zip(clips, resolved, strict=True)]


def active_rect_identity(rect: ClipActiveRect) -> dict[str, object]:
    """Stable JSON-ready identity payload for a resolved active rectangle."""
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
        "source": rect.source,
        "detection_mode": rect.detection_mode,
        "algorithm_id": rect.algorithm_id,
    }


def active_rect_policy_identity(detection: ScreenshotActiveRectDetection) -> dict[str, str]:
    """Stable JSON-ready active-rect resolver policy payload."""
    return {
        "detection_mode": detection.value,
        "algorithm_id": ACTIVE_RECT_RESOLUTION_ALGORITHM,
    }


def _detection_mode(detection: ScreenshotActiveRectDetection) -> ClipActiveRectDetectionMode:
    if detection == ScreenshotActiveRectDetection.PROVIDED:
        return "provided"
    if detection == ScreenshotActiveRectDetection.DIMENSION:
        return "dimension"
    if detection == ScreenshotActiveRectDetection.ASPECT_RATIO:
        return "aspect_ratio"
    if detection == ScreenshotActiveRectDetection.AUTO:
        return "auto"
    raise ValueError(f"Unsupported active rect detection mode: {detection}")


def _explicit_active_rect_for_clip(
    clip: ClipState,
    override: SourceOverrideConfig | None,
    mode: ClipActiveRectDetectionMode,
) -> ClipActiveRect | None:
    if override is None or override.active_rect is None:
        return None
    rect = override.active_rect
    if (
        rect.x < 0
        or rect.y < 0
        or rect.width <= 0
        or rect.height <= 0
        or rect.x + rect.width > clip.probe.width
        or rect.y + rect.height > clip.probe.height
    ):
        raise SourceSelectionError(
            selector=clip.path.name,
            reason="active_rect is outside source dimensions",
            role="sources.overrides",
            matches=[clip.path],
        )
    return _rect(
        x=rect.x,
        y=rect.y,
        width=rect.width,
        height=rect.height,
        source="explicit",
        mode=mode,
    )


def _metadata_active_rect_for_clip(
    clip: ClipState,
    mode: ClipActiveRectDetectionMode,
) -> ClipActiveRect | None:
    margins = _dolby_vision_l5_margins(clip.probe.preserved_frame_props)
    if margins is None:
        return None
    left, top, right, bottom = margins
    if left == 0 and top == 0 and right == 0 and bottom == 0:
        return None

    active_width = clip.probe.width - left - right
    active_height = clip.probe.height - top - bottom
    if active_width <= 0 or active_height <= 0:
        return None
    return _rect(
        x=left,
        y=top,
        width=active_width,
        height=active_height,
        source="metadata",
        mode=mode,
    )


def _dolby_vision_l5_margins(
    preserved_props: Mapping[str, str | int | float],
) -> tuple[int, int, int, int] | None:
    margins: dict[str, int] = {}
    for key, value in preserved_props.items():
        normalized = _normalize_preserved_prop_key(key)
        if "l5" not in normalized:
            continue
        margin_name = _l5_margin_name(normalized)
        if margin_name is None or margin_name in margins:
            continue
        coerced = _coerce_int(value)
        if coerced is None or coerced < 0:
            return None
        margins[margin_name] = coerced
    if set(margins) != {"left", "right", "top", "bottom"}:
        return None
    return margins["left"], margins["top"], margins["right"], margins["bottom"]


def _normalize_preserved_prop_key(key: str) -> str:
    return key.lstrip("_").lower()


def _l5_margin_name(normalized_key: str) -> str | None:
    for name in ("left", "right", "top", "bottom"):
        if name in normalized_key:
            return name
    return None


def _coerce_int(value: str | int | float) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else None


def _dimension_derived_active_rects(
    clips: Sequence[ClipState],
    mode: ClipActiveRectDetectionMode,
) -> tuple[ClipActiveRect | None, ...]:
    if len(clips) < 2:
        return tuple(None for _clip in clips)

    widths = {clip.probe.width for clip in clips}
    heights = {clip.probe.height for clip in clips}
    if len(heights) == 1 and len(widths) > 1:
        target_width = min(widths)
        return tuple(
            _rect(
                x=(clip.probe.width - target_width) // 2,
                y=0,
                width=target_width,
                height=clip.probe.height,
                source="dimension-derived",
                mode=mode,
            )
            for clip in clips
        )
    if len(widths) == 1 and len(heights) > 1:
        target_height = min(heights)
        return tuple(
            _rect(
                x=0,
                y=(clip.probe.height - target_height) // 2,
                width=clip.probe.width,
                height=target_height,
                source="dimension-derived",
                mode=mode,
            )
            for clip in clips
        )
    return tuple(None for _clip in clips)


def _aspect_ratio_derived_active_rects(
    clips: Sequence[ClipState],
    resolved: tuple[ClipActiveRect, ...],
    mode: ClipActiveRectDetectionMode,
) -> tuple[ClipActiveRect, ...]:
    if len(clips) < 2:
        return resolved

    target_ratio = _select_aspect_ratio_candidate(resolved)
    if target_ratio is None:
        return resolved

    updated: list[ClipActiveRect] = []
    for clip, rect in zip(clips, resolved, strict=True):
        if rect.source != "full-frame":
            updated.append(rect)
            continue

        full_ratio = clip.probe.width / clip.probe.height
        if (target_ratio - full_ratio) / target_ratio <= ASPECT_RATIO_MIN_CROP_REL_DELTA:
            updated.append(rect)
            continue

        inferred = _contained_vertical_rect(clip, target_ratio=target_ratio, mode=mode)
        updated.append(inferred if inferred is not None else rect)
    return tuple(updated)


def _contained_vertical_rect(
    clip: ClipState,
    *,
    target_ratio: float,
    mode: ClipActiveRectDetectionMode,
) -> ClipActiveRect | None:
    computed_height = int(clip.probe.width / target_ratio)
    if computed_height <= 0 or computed_height > clip.probe.height:
        return None
    removed_fraction = (clip.probe.height - computed_height) / clip.probe.height
    if removed_fraction > ASPECT_RATIO_MAX_HEIGHT_REMOVAL_FRACTION:
        return None
    return _rect(
        x=0,
        y=(clip.probe.height - computed_height) // 2,
        width=clip.probe.width,
        height=computed_height,
        source="aspect-ratio-derived",
        mode=mode,
    )


def _select_aspect_ratio_candidate(resolved: tuple[ClipActiveRect, ...]) -> float | None:
    candidates = _aspect_ratio_candidates(resolved)
    if not candidates:
        return None
    reference_ratio = _rect_ratio(resolved[0])
    return min(
        candidates,
        key=lambda candidate: (
            -_aspect_candidate_support_count(candidate.ratio, resolved),
            candidate.evidence_rank,
            _ratio_relative_delta(candidate.ratio, reference_ratio),
            candidate.first_source_index,
        ),
    ).ratio


def _aspect_ratio_candidates(resolved: tuple[ClipActiveRect, ...]) -> tuple[_AspectCandidate, ...]:
    raw_candidates: list[_AspectCandidate] = []
    for evidence_rank, source_kind in ((0, "explicit"), (1, "metadata")):
        for index, rect in enumerate(resolved):
            if rect.source == source_kind:
                raw_candidates.append(_AspectCandidate(_rect_ratio(rect), index, evidence_rank))

    for index, rect in enumerate(resolved):
        if rect.source not in ("dimension-derived", "full-frame"):
            continue
        ratio = _rect_ratio(rect)
        if _aspect_candidate_support_count(ratio, resolved) >= 2:
            raw_candidates.append(_AspectCandidate(ratio, index, 2))

    merged: list[_AspectCandidate] = []
    for candidate in raw_candidates:
        if any(_ratio_matches(candidate.ratio, existing.ratio) for existing in merged):
            continue
        merged.append(candidate)
    return tuple(merged)


def _aspect_candidate_support_count(
    candidate_ratio: float,
    resolved: tuple[ClipActiveRect, ...],
) -> int:
    return sum(1 for rect in resolved if _ratio_matches(candidate_ratio, _rect_ratio(rect)))


def _rect_ratio(rect: ClipActiveRect) -> float:
    return rect.width / rect.height


def _ratio_matches(candidate_ratio: float, observed_ratio: float) -> bool:
    return _ratio_relative_delta(candidate_ratio, observed_ratio) <= (
        ASPECT_RATIO_MATCH_REL_TOLERANCE
    )


def _ratio_relative_delta(candidate_ratio: float, observed_ratio: float) -> float:
    return abs(candidate_ratio - observed_ratio) / max(candidate_ratio, observed_ratio)


def _full_frame_rect(clip: ClipState, mode: ClipActiveRectDetectionMode) -> ClipActiveRect:
    return _rect(
        x=0,
        y=0,
        width=clip.probe.width,
        height=clip.probe.height,
        source="full-frame",
        mode=mode,
    )


def _rect(
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    source: ClipActiveRectSource,
    mode: ClipActiveRectDetectionMode,
) -> ClipActiveRect:
    return ClipActiveRect(
        x=x,
        y=y,
        width=width,
        height=height,
        source=source,
        detection_mode=mode,
        algorithm_id=ACTIVE_RECT_RESOLUTION_ALGORITHM,
    )
