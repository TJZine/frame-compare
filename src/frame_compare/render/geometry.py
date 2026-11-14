"""Geometry calculation utilities for screenshot rendering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from frame_compare.utils.canvas import validate_canvas_size
from frame_compare.utils.media_facts import ActivePictureProvenance

GeometryMode = Literal["native", "aligned"]
AlignedScalePolicy = Literal[
    "largest_active",
    "smallest_active",
    "reference_active",
    "explicit_size",
]


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
    """Source dimensions plus a required resolved active-image rectangle."""

    width: int
    height: int
    active_rect: GeometryRect
    provenance: ActivePictureProvenance
    label: str | None = None


@dataclass(frozen=True, slots=True)
class RenderGeometryOptions:
    """Aligned screenshot geometry planning options."""

    aligned_scale_policy: AlignedScalePolicy = "largest_active"
    aligned_target_size: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class RenderGeometryPlan:
    """Source active-picture evidence plus one pure crop/scale/pad plan."""

    source: SourceGeometry
    source_rect: GeometryRect
    active_rect: GeometryRect
    provenance: ActivePictureProvenance
    crop_rect: GeometryRect
    crop: GeometryMargins
    cropped_size: tuple[int, int]
    scaled_size: tuple[int, int]
    pad: GeometryMargins
    final_canvas_size: tuple[int, int]
    content_origin: tuple[int, int]
    overlay_origin: tuple[int, int]

    def validate_sizes(self) -> None:
        """Check allocation sizes when accepting a plan at a backend boundary."""
        validate_canvas_size(self.source_rect.width, self.source_rect.height, label="Source")
        validate_canvas_size(self.crop_rect.width, self.crop_rect.height, label="Crop")
        validate_canvas_size(*self.cropped_size, label="Cropped frame")
        validate_canvas_size(*self.scaled_size, label="Scaled frame")
        validate_canvas_size(*self.final_canvas_size, label="Canvas")
        for margins in (self.crop, self.pad):
            if min(margins.left, margins.top, margins.right, margins.bottom) < 0:
                raise ValueError("Crop and pad margins must be non-negative")
        validate_canvas_size(
            self.scaled_size[0] + self.pad.left + self.pad.right,
            self.scaled_size[1] + self.pad.top + self.pad.bottom,
            label="Padded frame",
        )

    @property
    def is_noop(self) -> bool:
        return (
            self.crop == GeometryMargins()
            and self.scaled_size == self.cropped_size
            and self.pad == GeometryMargins()
            and self.final_canvas_size == (self.source.width, self.source.height)
        )


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
    crop_rects = tuple(_mod_safe_rect(source.active_rect) for source in sources)
    canvas_size = _target_canvas(crop_rects, options=resolved_options)
    validate_canvas_size(*canvas_size, label="Canvas")
    scaled_sizes = _fit_to_target(crop_rects, canvas_size)

    plans: list[RenderGeometryPlan] = []
    for source, crop_rect, scaled_size in zip(
        sources,
        crop_rects,
        scaled_sizes,
        strict=True,
    ):
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
                active_rect=source.active_rect,
                provenance=source.provenance,
                crop_rect=crop_rect,
                crop=_crop_margins(source_rect, crop_rect),
                cropped_size=(crop_rect.width, crop_rect.height),
                scaled_size=scaled_size,
                pad=pad,
                final_canvas_size=canvas_size,
                content_origin=(pad.left, pad.top),
                overlay_origin=overlay_origin,
            )
        )
    return tuple(plans)


def _validate_sources(sources: Sequence[SourceGeometry]) -> None:
    for source in sources:
        validate_canvas_size(source.width, source.height, label="Source")
        if not _is_safe_active_rect(source.active_rect, source):
            raise ValueError("active rectangle must be positive and within source dimensions")


def _validate_options(options: RenderGeometryOptions) -> None:
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
        validate_canvas_size(*options.aligned_target_size, label="Aligned target")


def _native_plan(source: SourceGeometry, *, overlay_margin: int) -> RenderGeometryPlan:
    source_rect = GeometryRect(0, 0, source.width, source.height)
    overlay_origin = (
        min(overlay_margin, source.width - 1),
        min(overlay_margin, source.height - 1),
    )
    return RenderGeometryPlan(
        source=source,
        source_rect=source_rect,
        active_rect=source.active_rect,
        provenance=source.provenance,
        crop_rect=source_rect,
        crop=GeometryMargins(),
        cropped_size=(source.width, source.height),
        scaled_size=(source.width, source.height),
        pad=GeometryMargins(),
        final_canvas_size=(source.width, source.height),
        content_origin=(0, 0),
        overlay_origin=overlay_origin,
    )


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
        # Cross products are bounded by MAX_CANVAS_AXIS squared. Integer
        # division avoids losing an otherwise exact pixel to float rounding.
        if target_width * rect.height <= target_height * rect.width:
            width, height = target_width, rect.height * target_width // rect.width
        else:
            width, height = rect.width * target_height // rect.height, target_height
        size = (_mod_safe_size(max(1, width)), _mod_safe_size(max(1, height)))
        validate_canvas_size(*size, label="Scaled frame")
        scaled_sizes.append(size)
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
