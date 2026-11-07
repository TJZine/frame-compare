"""Shared FFmpeg frame extraction command policy for render owners."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from frame_compare.render.color import BT2020_CL_TRANSFER, MATRIX_TO_ZIMG, untagged_matrix
from frame_compare.render.geometry import GeometryMargins, GeometryRect, RenderGeometryPlan
from frame_compare.utils.media_facts import SourceSignalFacts


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

    # Negotiate full chroma in the input's color family and retain high depth
    # through geometry. RGB sources can pad without a round trip through YUV.
    full_chroma_format = "format=pix_fmts=yuv444p|yuv444p16le|gbrp|gbrp16le"
    filters: list[str] = []
    odd_crop = False
    if geometry_plan.crop_rect != geometry_plan.source_rect:
        crop = geometry_plan.crop_rect
        odd_crop = bool(crop.x % 2 or crop.y % 2)
        if odd_crop:
            # High-depth subsampled crop buffers can also lose chroma alignment
            # at odd origins, even with exact=1. Convert before that boundary.
            filters.append(full_chroma_format)
        filters.append(f"crop={crop.width}:{crop.height}:{crop.x}:{crop.y}:exact=1")
    resize = geometry_plan.scaled_size != geometry_plan.cropped_size
    if resize:
        width, height = geometry_plan.scaled_size
        filters.append(f"scale={width}:{height}")
    if geometry_plan.pad != GeometryMargins():
        width, height = geometry_plan.final_canvas_size
        x, y = geometry_plan.content_origin
        if x < 0 or y < 0:
            raise ValueError("pad content origin must be non-negative")
        if resize or not odd_crop:
            filters.append(full_chroma_format)
        filters.append(f"pad={width}:{height}:{x}:{y}:color=black")
    return filters


_SWSCALE_MATRICES = {
    "709": "bt709",
    "fcc": "fcc",
    "470bg": "bt601",
    "170m": "bt601",
    "240m": "smpte240m",
    "2020ncl": "bt2020",
}


def _png_filters(
    geometry_plan: RenderGeometryPlan | None,
    source_signal: SourceSignalFacts | None,
) -> list[str]:
    geometry = _geometry_filters(geometry_plan)
    matrix = None
    if source_signal is not None and source_signal.matrix != 0:  # Identity / RGB
        if source_signal.matrix is not None:
            matrix = MATRIX_TO_ZIMG.get(source_signal.matrix)
        if matrix is None and geometry_plan is not None:
            matrix = untagged_matrix(
                geometry_plan.source.width,
                geometry_plan.source.height,
                is_hdr=source_signal.is_hdr,
            )

    if matrix in {"ycgco", "2020cl"}:
        # Swscale cannot negotiate these matrix tags, even for YUV geometry.
        # Clear the graph-local tag and use the prepared matrix at conversion.
        zscale = "zscale=matrixin=ycgco"
        if matrix == "2020cl":
            # Constant-luminance decoding needs the BT.2020 transfer curve.
            transfer = source_signal.transfer if source_signal is not None else None
            if transfer in (None, 2):
                transfer = BT2020_CL_TRANSFER
            zscale = f"zscale=matrixin=bt2020c:transferin={transfer}:transfer={transfer}"
        return ["setparams=colorspace=unknown", *geometry, zscale, "format=gbrp", "format=rgb24"]

    if matrix is not None:
        geometry.append(f"scale=in_color_matrix={_SWSCALE_MATRICES[matrix]}")
    return [*geometry, "format=rgb24"]


def build_extract_frame_argv(
    *,
    video: Path,
    frame_num: int,
    output: Path,
    overwrite: bool,
    geometry_plan: RenderGeometryPlan | None = None,
    source_signal: SourceSignalFacts | None = None,
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
        *_png_filters(geometry_plan, source_signal),
    ]

    argv = ["ffmpeg"]
    if overwrite:
        argv.append("-y")
    argv.extend(
        [
            "-noautorotate",
            "-i",
            str(video),
            "-map",
            "0:V:0",
            "-vf",
            ",".join(filters),
            "-frames:v",
            "1",
            "-q:v",
            "1",
            "-update",
            "1",
            str(output),
        ]
    )
    return argv


def build_extract_frames_argv(
    *,
    video: Path,
    frame_nums: Sequence[int],
    output_pattern: Path,
    overwrite: bool,
    geometry_plan: RenderGeometryPlan | None = None,
    source_signal: SourceSignalFacts | None = None,
) -> list[str]:
    """Build FFmpeg argv for one-pass extraction of ordered exact frames."""
    if not frame_nums:
        raise ValueError("frame_nums must not be empty")
    if any(frame_num < 0 for frame_num in frame_nums):
        raise ValueError("frame_nums must be non-negative")
    if any(
        current >= following for current, following in zip(frame_nums, frame_nums[1:], strict=False)
    ):
        raise ValueError("frame_nums must be strictly increasing")

    selector = "+".join(f"eq(n\\,{frame_num})" for frame_num in frame_nums)
    filters = [
        f"select={selector}",
        "showinfo=checksum=0",
        *_png_filters(geometry_plan, source_signal),
    ]

    argv = ["ffmpeg"]
    if overwrite:
        argv.append("-y")
    argv.extend(
        [
            "-noautorotate",
            "-i",
            str(video),
            "-map",
            "0:V:0",
            "-vf",
            ",".join(filters),
            "-fps_mode",
            "passthrough",
            "-frames:v",
            str(len(frame_nums)),
            "-q:v",
            "1",
            "-start_number",
            "0",
            str(output_pattern),
        ]
    )
    return argv
