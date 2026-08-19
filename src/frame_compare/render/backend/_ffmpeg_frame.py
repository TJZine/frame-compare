"""Shared FFmpeg frame extraction command policy for render owners."""

from __future__ import annotations

from pathlib import Path

from frame_compare.render.geometry import GeometryMargins, GeometryRect, RenderGeometryPlan


def _validate_positive_size(width: int, height: int, *, label: str) -> None:
    if width <= 0 or height <= 0:
        raise ValueError(f"{label} dimensions must be positive")


def _validate_rect(rect: GeometryRect, *, label: str) -> None:
    _validate_positive_size(rect.width, rect.height, label=label)
    if rect.x < 0 or rect.y < 0:
        raise ValueError(f"{label} origin must be non-negative")


def _validate_margins(margins: GeometryMargins, *, label: str) -> None:
    if margins.left < 0 or margins.top < 0 or margins.right < 0 or margins.bottom < 0:
        raise ValueError(f"{label} margins must be non-negative")


def _geometry_filters(geometry_plan: RenderGeometryPlan | None) -> list[str]:
    if geometry_plan is None:
        return []

    _validate_rect(geometry_plan.source_rect, label="source")
    _validate_rect(geometry_plan.crop_rect, label="crop")
    _validate_positive_size(*geometry_plan.scaled_size, label="scale")
    _validate_positive_size(*geometry_plan.final_canvas_size, label="pad")
    _validate_margins(geometry_plan.pad, label="pad")

    filters: list[str] = []
    if geometry_plan.crop_rect != geometry_plan.source_rect:
        crop = geometry_plan.crop_rect
        filters.append(f"crop={crop.width}:{crop.height}:{crop.x}:{crop.y}")
    if geometry_plan.scaled_size != geometry_plan.cropped_size:
        width, height = geometry_plan.scaled_size
        filters.append(f"scale={width}:{height}")
    if geometry_plan.pad != GeometryMargins():
        width, height = geometry_plan.final_canvas_size
        x, y = geometry_plan.content_origin
        if x < 0 or y < 0:
            raise ValueError("pad content origin must be non-negative")
        filters.append(f"pad={width}:{height}:{x}:{y}:color=black")
    return filters


def build_extract_frame_argv(
    *,
    video: Path,
    frame_num: int,
    output: Path,
    overwrite: bool,
    geometry_plan: RenderGeometryPlan | None = None,
) -> list[str]:
    """Build the canonical FFmpeg argv for single-frame extraction."""
    if frame_num < 0:
        raise ValueError("frame_num must be non-negative")
    # showinfo must inspect the selected source frame before any geometry filter.
    # Keeping it in this extraction process means the diagnostic fact and image
    # share the same decode/selection operation.
    filters = [
        f"select=eq(n\\,{frame_num})",
        "showinfo=checksum=0",
        *_geometry_filters(geometry_plan),
    ]

    argv = ["ffmpeg"]
    if overwrite:
        argv.append("-y")
    argv.extend(
        [
            "-i",
            str(video),
            "-vf",
            ",".join(filters),
            "-frames:v",
            "1",
            "-q:v",
            "1",
            str(output),
        ]
    )
    return argv
