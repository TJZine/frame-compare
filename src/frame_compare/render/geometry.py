"""Geometry calculation utilities for screenshot rendering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

GeometryMode = Literal["native", "aligned"]
ProvidedActiveRectSource = Literal["explicit", "metadata"]
ActiveRectSource = Literal["explicit", "metadata", "dimension-derived", "full-frame"]


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
class RenderGeometryPlan:
    """Pure crop/scale/pad plan for one rendered screenshot source."""

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


def calculate_dimensions(
    source_width: int,
    source_height: int,
    max_width: int | None = None,
    max_height: int | None = None,
) -> tuple[int, int]:
    """
    Calculate output dimensions preserving aspect ratio.

    Algorithm:
    1. If both max_width and max_height are None, return (source_width, source_height).
    2. Compute aspect ratio: ratio = source_width / source_height.
    3. If only max_width is set: new_width = min(source_width, max_width),
       new_height = int(new_width / ratio).
    4. If only max_height is set: new_height = min(source_height, max_height),
       new_width = int(new_height * ratio).
    5. If both are set: compute width-constrained and height-constrained sizes;
       pick the one that fits within *both* constraints.
    6. Round down (truncate) to integer; never exceed constraints.

    Raises:
        ValueError: If dimensions are non-positive.
    """
    if source_width <= 0 or source_height <= 0:
        raise ValueError("source dimensions must be positive")
    if (max_width is not None and max_width <= 0) or (max_height is not None and max_height <= 0):
        raise ValueError("max dimensions must be positive")

    if max_width is None and max_height is None:
        return (source_width, source_height)

    width_scale = (max_width / source_width) if max_width is not None else 1.0
    height_scale = (max_height / source_height) if max_height is not None else 1.0
    scale = min(1.0, width_scale, height_scale)

    new_width = max(1, int(source_width * scale))
    new_height = max(1, int(source_height * scale))
    return (new_width, new_height)


def ensure_mod2(width: int, height: int) -> tuple[int, int]:
    """
    Round dimensions up to nearest even values for video encoding compatibility.

    Algorithm:
    - Round each dimension up to the nearest even number:
      (width + width % 2, height + height % 2).

    Raises:
        ValueError: If dimensions are non-positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError("dimensions must be positive")

    return (width + width % 2, height + height % 2)


def plan_render_geometry(
    sources: Sequence[SourceGeometry],
    *,
    mode: GeometryMode = "native",
    overlay_margin: int = 10,
) -> tuple[RenderGeometryPlan, ...]:
    """Plan pure screenshot geometry for one or more sources.

    ``native`` preserves current full-frame behavior. ``aligned`` crops to safe
    active rectangles, scales active content proportionally to a shared height,
    and centers padding on a common canvas.
    """

    if mode not in ("native", "aligned"):
        raise ValueError("geometry mode must be 'native' or 'aligned'")
    if overlay_margin < 0:
        raise ValueError("overlay margin must be non-negative")

    _validate_sources(sources)
    if mode == "native":
        return tuple(_native_plan(source, overlay_margin=overlay_margin) for source in sources)

    active_rects = _resolve_active_rects(sources)
    crop_rects = tuple(
        _mod_safe_rect(rect)
        for (rect, _source_kind), _source in zip(active_rects, sources, strict=True)
    )
    scaled_sizes = _scale_to_common_height(crop_rects)
    canvas_size = _common_canvas(scaled_sizes)

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


def _native_plan(source: SourceGeometry, *, overlay_margin: int) -> RenderGeometryPlan:
    source_rect = GeometryRect(0, 0, source.width, source.height)
    overlay_origin = (
        min(overlay_margin, source.width - 1),
        min(overlay_margin, source.height - 1),
    )
    return RenderGeometryPlan(
        source=source,
        source_rect=source_rect,
        active_rect=source_rect,
        active_rect_source="full-frame",
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
) -> tuple[tuple[GeometryRect, ActiveRectSource], ...]:
    dimension_rects = _dimension_derived_active_rects(sources)
    resolved: list[tuple[GeometryRect, ActiveRectSource]] = []
    for source, dimension_rect in zip(sources, dimension_rects, strict=True):
        provided = source.active_rect
        if provided is not None and _is_safe_active_rect(provided, source):
            resolved.append((provided, source.active_rect_source))
        elif dimension_rect is not None:
            resolved.append((dimension_rect, "dimension-derived"))
        else:
            resolved.append((GeometryRect(0, 0, source.width, source.height), "full-frame"))
    return tuple(resolved)


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
    width = _mod_safe_size(rect.width)
    height = _mod_safe_size(rect.height)
    return GeometryRect(
        rect.x + ((rect.width - width) // 2),
        rect.y + ((rect.height - height) // 2),
        width,
        height,
    )


def _mod_safe_size(value: int) -> int:
    if value <= 1:
        return value
    return value - (value % 2)


def _scale_to_common_height(rects: Sequence[GeometryRect]) -> tuple[tuple[int, int], ...]:
    target_height = max((_mod_safe_size(rect.height) for rect in rects), default=0)
    if target_height <= 0:
        return ()

    scaled_sizes: list[tuple[int, int]] = []
    for rect in rects:
        if rect.height == target_height:
            scaled_sizes.append((rect.width, rect.height))
            continue
        scale = target_height / rect.height
        scaled_width = max(1, int(round(rect.width * scale)))
        scaled_sizes.append(ensure_mod2(scaled_width, target_height))
    return tuple(scaled_sizes)


def _common_canvas(scaled_sizes: Sequence[tuple[int, int]]) -> tuple[int, int]:
    width = max((size[0] for size in scaled_sizes), default=1)
    height = max((size[1] for size in scaled_sizes), default=1)
    return ensure_mod2(width, height)


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
