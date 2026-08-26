"""Geometry calculation utilities for screenshot rendering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, assert_never

from frame_compare.utils.media_facts import ActivePictureProvenance

GeometryMode = Literal["native", "aligned"]
ActiveRectDetectionMode = Literal["provided", "dimension", "aspect_ratio", "auto"]
AlignedScalePolicy = Literal[
    "largest_active",
    "smallest_active",
    "reference_active",
    "explicit_size",
]
ActiveRectSource = Literal[
    "explicit",
    "metadata",
    "dimension-derived",
    "aspect-ratio-derived",
    "content-derived",
    "full-frame",
]
ProvidedActiveRectSource = ActiveRectSource

ASPECT_RATIO_MATCH_REL_TOLERANCE = 0.005
ASPECT_RATIO_MIN_CROP_REL_DELTA = 0.005
ASPECT_RATIO_MAX_HEIGHT_REMOVAL_FRACTION = 0.35


def active_rect_source_from_provenance(
    provenance: ActivePictureProvenance,
) -> ActiveRectSource:
    """Convert canonical active-picture provenance to render geometry provenance."""
    match provenance:
        case "explicit":
            return "explicit"
        case "dolby_vision_l5":
            return "metadata"
        case "dimension_derived":
            return "dimension-derived"
        case "aspect_ratio_derived":
            return "aspect-ratio-derived"
        case "content_derived":
            return "content-derived"
        case "full_frame":
            return "full-frame"
    assert_never(provenance)


def active_picture_provenance_from_rect_source(
    source: ActiveRectSource,
) -> ActivePictureProvenance:
    """Convert render geometry provenance to canonical active-picture provenance."""
    match source:
        case "explicit":
            return "explicit"
        case "metadata":
            return "dolby_vision_l5"
        case "dimension-derived":
            return "dimension_derived"
        case "aspect-ratio-derived":
            return "aspect_ratio_derived"
        case "content-derived":
            return "content_derived"
        case "full-frame":
            return "full_frame"
    assert_never(source)


@dataclass(frozen=True, slots=True)
class GeometryRect:
    """Integer rectangle in source or canvas coordinates."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class GeometryMargins:
    """Left/top/right/bottom crop or pad margins."""

    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0


@dataclass(frozen=True, slots=True)
class SourceGeometry:
    """Source dimensions plus an optional known active-image rectangle."""

    width: int
    height: int
    active_rect: GeometryRect | None = None
    active_rect_source: ProvidedActiveRectSource = "explicit"
    label: str | None = None


@dataclass(frozen=True, slots=True)
class RenderGeometryOptions:
    """Aligned screenshot geometry planning options."""

    active_rect_detection: ActiveRectDetectionMode = "aspect_ratio"
    aligned_scale_policy: AlignedScalePolicy = "largest_active"
    aligned_target_size: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class RenderGeometryPlan:
    """Source active-picture evidence plus one pure crop/scale/pad plan."""

    source: SourceGeometry
    source_rect: GeometryRect
    active_rect: GeometryRect
    active_rect_source: ActiveRectSource
    crop_rect: GeometryRect
    crop: GeometryMargins
    cropped_size: tuple[int, int]
    scaled_size: tuple[int, int]
    pad: GeometryMargins
    final_canvas_size: tuple[int, int]
    content_origin: tuple[int, int]
    overlay_origin: tuple[int, int]
    source_overlay_origin: tuple[int, int]

    @property
    def is_noop(self) -> bool:
        return (
            self.crop == GeometryMargins()
            and self.scaled_size == self.cropped_size
            and self.pad == GeometryMargins()
            and self.final_canvas_size == (self.source.width, self.source.height)
        )


@dataclass(frozen=True, slots=True)
class _AspectCandidate:
    ratio: float
    first_source_index: int
    evidence_rank: int


def plan_render_geometry(
    sources: Sequence[SourceGeometry],
    *,
    mode: GeometryMode = "native",
    overlay_margin: int = 10,
    options: RenderGeometryOptions | None = None,
) -> tuple[RenderGeometryPlan, ...]:
    """Plan pure screenshot geometry for one or more sources.

    ``native`` preserves full-frame output while retaining known active-picture
    evidence. ``aligned`` crops to safe active rectangles, fits active content
    inside a selected target canvas, and centers padding on that canvas.
    """

    if mode not in ("native", "aligned"):
        raise ValueError("geometry mode must be 'native' or 'aligned'")
    if overlay_margin < 0:
        raise ValueError("overlay margin must be non-negative")

    _validate_sources(sources)
    if mode == "native":
        return tuple(_native_plan(source, overlay_margin=overlay_margin) for source in sources)

    resolved_options = options or RenderGeometryOptions()
    _validate_options(resolved_options)
    active_rects = _resolve_active_rects(
        sources,
        active_rect_detection=resolved_options.active_rect_detection,
    )
    crop_rects = tuple(
        _mod_safe_rect(rect)
        for (rect, _source_kind), _source in zip(active_rects, sources, strict=True)
    )
    canvas_size = _target_canvas(crop_rects, options=resolved_options)
    scaled_sizes = _fit_to_target(crop_rects, canvas_size)

    plans: list[RenderGeometryPlan] = []
    for source, active_info, crop_rect, scaled_size in zip(
        sources,
        active_rects,
        crop_rects,
        scaled_sizes,
        strict=True,
    ):
        active_rect, active_rect_source = active_info
        source_rect = GeometryRect(0, 0, source.width, source.height)
        pad = _center_pad(scaled_size, canvas_size)
        content_max_x = pad.left + scaled_size[0] - 1
        content_max_y = pad.top + scaled_size[1] - 1
        overlay_origin = (
            min(pad.left + overlay_margin, content_max_x),
            min(pad.top + overlay_margin, content_max_y),
        )
        plans.append(
            RenderGeometryPlan(
                source=source,
                source_rect=source_rect,
                active_rect=active_rect,
                active_rect_source=active_rect_source,
                crop_rect=crop_rect,
                crop=_crop_margins(source_rect, crop_rect),
                cropped_size=(crop_rect.width, crop_rect.height),
                scaled_size=scaled_size,
                pad=pad,
                final_canvas_size=canvas_size,
                content_origin=(pad.left, pad.top),
                overlay_origin=overlay_origin,
                source_overlay_origin=(
                    min(crop_rect.x + overlay_margin, crop_rect.right - 1),
                    min(crop_rect.y + overlay_margin, crop_rect.bottom - 1),
                ),
            )
        )
    return tuple(plans)


def _validate_sources(sources: Sequence[SourceGeometry]) -> None:
    for source in sources:
        if source.width <= 0 or source.height <= 0:
            raise ValueError("source dimensions must be positive")


def _validate_options(options: RenderGeometryOptions) -> None:
    if options.active_rect_detection not in ("provided", "dimension", "aspect_ratio", "auto"):
        raise ValueError(
            "active rect detection must be 'provided', 'dimension', 'aspect_ratio', or 'auto'"
        )
    if options.aligned_scale_policy not in (
        "largest_active",
        "smallest_active",
        "reference_active",
        "explicit_size",
    ):
        raise ValueError("aligned scale policy is not supported")
    if options.aligned_scale_policy == "explicit_size":
        if options.aligned_target_size is None:
            raise ValueError("explicit_size requires an aligned target size")
        width, height = options.aligned_target_size
        if width <= 0 or height <= 0:
            raise ValueError("aligned target dimensions must be positive")


def _native_plan(source: SourceGeometry, *, overlay_margin: int) -> RenderGeometryPlan:
    source_rect = GeometryRect(0, 0, source.width, source.height)
    active_rect, active_rect_source = _resolve_active_rects(
        (source,), active_rect_detection="provided"
    )[0]
    overlay_origin = (
        min(overlay_margin, source.width - 1),
        min(overlay_margin, source.height - 1),
    )
    return RenderGeometryPlan(
        source=source,
        source_rect=source_rect,
        active_rect=active_rect,
        active_rect_source=active_rect_source,
        crop_rect=source_rect,
        crop=GeometryMargins(),
        cropped_size=(source.width, source.height),
        scaled_size=(source.width, source.height),
        pad=GeometryMargins(),
        final_canvas_size=(source.width, source.height),
        content_origin=(0, 0),
        overlay_origin=overlay_origin,
        source_overlay_origin=overlay_origin,
    )


def _resolve_active_rects(
    sources: Sequence[SourceGeometry],
    *,
    active_rect_detection: ActiveRectDetectionMode,
) -> tuple[tuple[GeometryRect, ActiveRectSource], ...]:
    dimension_rects = (
        _dimension_derived_active_rects(sources)
        if active_rect_detection in ("dimension", "aspect_ratio", "auto")
        else tuple(None for _source in sources)
    )
    resolved: list[tuple[GeometryRect, ActiveRectSource]] = []
    for source, dimension_rect in zip(sources, dimension_rects, strict=True):
        provided = source.active_rect
        if provided is not None and _is_safe_active_rect(provided, source):
            resolved.append((provided, source.active_rect_source))
        elif dimension_rect is not None:
            resolved.append((dimension_rect, "dimension-derived"))
        else:
            resolved.append((GeometryRect(0, 0, source.width, source.height), "full-frame"))
    resolved_tuple = tuple(resolved)
    if active_rect_detection not in ("aspect_ratio", "auto"):
        return resolved_tuple
    return _aspect_ratio_derived_active_rects(sources, resolved_tuple)


def _dimension_derived_active_rects(
    sources: Sequence[SourceGeometry],
) -> tuple[GeometryRect | None, ...]:
    if len(sources) < 2:
        return tuple(None for _source in sources)

    widths = {source.width for source in sources}
    heights = {source.height for source in sources}
    if len(heights) == 1 and len(widths) > 1:
        target_width = min(widths)
        return tuple(
            GeometryRect((source.width - target_width) // 2, 0, target_width, source.height)
            for source in sources
        )
    if len(widths) == 1 and len(heights) > 1:
        target_height = min(heights)
        return tuple(
            GeometryRect(0, (source.height - target_height) // 2, source.width, target_height)
            for source in sources
        )
    return tuple(None for _source in sources)


def _is_safe_active_rect(rect: GeometryRect, source: SourceGeometry) -> bool:
    return (
        rect.x >= 0
        and rect.y >= 0
        and rect.width > 0
        and rect.height > 0
        and rect.right <= source.width
        and rect.bottom <= source.height
    )


def _mod_safe_rect(rect: GeometryRect) -> GeometryRect:
    x_offset = rect.x % 2 if rect.width > 1 else 0
    y_offset = rect.y % 2 if rect.height > 1 else 0
    width = _mod_safe_size(rect.width - x_offset)
    height = _mod_safe_size(rect.height - y_offset)
    if width <= 1 or height <= 1:
        return rect
    return GeometryRect(
        rect.x + x_offset + ((rect.width - x_offset - width) // 2),
        rect.y + y_offset + ((rect.height - y_offset - height) // 2),
        width,
        height,
    )


def _mod_safe_contained_vertical_rect(
    source: SourceGeometry,
    *,
    target_ratio: float,
) -> GeometryRect | None:
    computed_height = int(source.width / target_ratio)
    crop_height = _mod_safe_size(computed_height)
    if crop_height <= 0 or crop_height > source.height:
        return None
    removed_fraction = (source.height - crop_height) / source.height
    if removed_fraction > ASPECT_RATIO_MAX_HEIGHT_REMOVAL_FRACTION:
        return None

    y = (source.height - crop_height) // 2
    if y % 2 != 0:
        y -= 1
    y = max(0, min(y, source.height - crop_height))
    return GeometryRect(0, y, _mod_safe_size(source.width), crop_height)


def _aspect_ratio_derived_active_rects(
    sources: Sequence[SourceGeometry],
    resolved: tuple[tuple[GeometryRect, ActiveRectSource], ...],
) -> tuple[tuple[GeometryRect, ActiveRectSource], ...]:
    if len(sources) < 2:
        return resolved

    target_ratio = _select_aspect_ratio_candidate(resolved)
    if target_ratio is None:
        return resolved

    updated: list[tuple[GeometryRect, ActiveRectSource]] = []
    for source, active_info in zip(sources, resolved, strict=True):
        _rect, rect_source = active_info
        if rect_source != "full-frame":
            updated.append(active_info)
            continue

        full_ratio = source.width / source.height
        if (target_ratio - full_ratio) / target_ratio <= ASPECT_RATIO_MIN_CROP_REL_DELTA:
            updated.append(active_info)
            continue

        inferred = _mod_safe_contained_vertical_rect(source, target_ratio=target_ratio)
        if inferred is None:
            updated.append(active_info)
            continue
        updated.append((inferred, "aspect-ratio-derived"))
    return tuple(updated)


def _select_aspect_ratio_candidate(
    resolved: tuple[tuple[GeometryRect, ActiveRectSource], ...],
) -> float | None:
    candidates = _aspect_ratio_candidates(resolved)
    if not candidates:
        return None

    reference_ratio = _rect_ratio(resolved[0][0])
    return min(
        candidates,
        key=lambda candidate: (
            -_aspect_candidate_support_count(candidate.ratio, resolved),
            candidate.evidence_rank,
            _ratio_relative_delta(candidate.ratio, reference_ratio),
            candidate.first_source_index,
        ),
    ).ratio


def _aspect_ratio_candidates(
    resolved: tuple[tuple[GeometryRect, ActiveRectSource], ...],
) -> tuple[_AspectCandidate, ...]:
    raw_candidates: list[_AspectCandidate] = []
    for evidence_rank, source_kind in ((0, "explicit"), (1, "metadata")):
        for index, (rect, rect_source) in enumerate(resolved):
            if rect_source == source_kind:
                raw_candidates.append(_AspectCandidate(_rect_ratio(rect), index, evidence_rank))

    for index, (rect, rect_source) in enumerate(resolved):
        if rect_source not in ("dimension-derived", "full-frame", "content-derived"):
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
    resolved: tuple[tuple[GeometryRect, ActiveRectSource], ...],
) -> int:
    return sum(
        1 for rect, _source in resolved if _ratio_matches(candidate_ratio, _rect_ratio(rect))
    )


def _rect_ratio(rect: GeometryRect) -> float:
    return rect.width / rect.height


def _ratio_matches(candidate_ratio: float, observed_ratio: float) -> bool:
    return _ratio_relative_delta(candidate_ratio, observed_ratio) <= (
        ASPECT_RATIO_MATCH_REL_TOLERANCE
    )


def _ratio_relative_delta(candidate_ratio: float, observed_ratio: float) -> float:
    return abs(candidate_ratio - observed_ratio) / max(candidate_ratio, observed_ratio)


def _mod_safe_size(value: int) -> int:
    if value <= 1:
        return value
    return value - (value % 2)


def _target_canvas(
    rects: Sequence[GeometryRect],
    *,
    options: RenderGeometryOptions,
) -> tuple[int, int]:
    if not rects:
        return (1, 1)
    if options.aligned_scale_policy == "explicit_size":
        if options.aligned_target_size is None:
            raise ValueError("explicit_size requires an aligned target size")
        return options.aligned_target_size
    if options.aligned_scale_policy == "largest_active":
        target = (
            max(rect.width for rect in rects),
            max(rect.height for rect in rects),
        )
    elif options.aligned_scale_policy == "smallest_active":
        target = (
            min(rect.width for rect in rects),
            min(rect.height for rect in rects),
        )
    elif options.aligned_scale_policy == "reference_active":
        reference = rects[0]
        target = (reference.width, reference.height)
    else:
        raise ValueError("aligned scale policy is not supported")
    return _normalize_derived_target(target)


def _normalize_derived_target(target: tuple[int, int]) -> tuple[int, int]:
    width = _mod_safe_size(target[0])
    height = _mod_safe_size(target[1])
    if width <= 0 or height <= 0:
        raise ValueError("aligned target dimensions must be positive after normalization")
    return (width, height)


def _fit_to_target(
    rects: Sequence[GeometryRect],
    target: tuple[int, int],
) -> tuple[tuple[int, int], ...]:
    target_width, target_height = target
    scaled_sizes: list[tuple[int, int]] = []
    for rect in rects:
        scale = min(target_width / rect.width, target_height / rect.height)
        scaled_width = min(target_width, _mod_safe_size(max(1, int(rect.width * scale))))
        scaled_height = min(target_height, _mod_safe_size(max(1, int(rect.height * scale))))
        if scaled_width <= 0 or scaled_height <= 0:
            raise ValueError("scaled dimensions must be positive")
        scaled_sizes.append((scaled_width, scaled_height))
    return tuple(scaled_sizes)


def _center_pad(size: tuple[int, int], canvas_size: tuple[int, int]) -> GeometryMargins:
    width_diff = max(0, canvas_size[0] - size[0])
    height_diff = max(0, canvas_size[1] - size[1])
    return GeometryMargins(
        left=width_diff // 2,
        top=height_diff // 2,
        right=width_diff - (width_diff // 2),
        bottom=height_diff - (height_diff // 2),
    )


def _crop_margins(source_rect: GeometryRect, crop_rect: GeometryRect) -> GeometryMargins:
    return GeometryMargins(
        left=crop_rect.x - source_rect.x,
        top=crop_rect.y - source_rect.y,
        right=source_rect.right - crop_rect.right,
        bottom=source_rect.bottom - crop_rect.bottom,
    )
