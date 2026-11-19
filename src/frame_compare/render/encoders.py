"""VapourSynth frame rendering and screenshot encoding."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.errors import ErrorDetails, FrameCompareError
from frame_compare.render.color import BT2020_CL_TRANSFER, MATRIX_TO_ZIMG, untagged_matrix
from frame_compare.render.errors import (
    EncodingError,
    OverlayError,
    RenderError,
)
from frame_compare.render.geometry import GeometryMargins, RenderGeometryPlan
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import (
    EncoderSettings,
    OverlayMode,
    RenderedFrameResult,
    RenderRequest,
)
from frame_compare.utils.canvas import validate_canvas_size
from frame_compare.utils.media_facts import (
    RenderedFrameFacts,
    SourceSignalFacts,
    normalize_picture_type,
)
from frame_compare.vs.props import props_indicate_limited_range

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.render.types import OverlayConfig

type _ColorFramePropKey = Literal["_Matrix", "_Transfer", "_Primaries"]


class _FpngJob(Protocol):
    def get_frame(self, n: int) -> object: ...


class _FpngWriter(Protocol):
    def __call__(
        self,
        clip: vs.VideoNode,
        filename: str,
        *,
        compression: int,
        overwrite: bool,
    ) -> _FpngJob: ...


_VS_MATRIX_PROP: _ColorFramePropKey = "_Matrix"
_VS_TRANSFER_PROP: _ColorFramePropKey = "_Transfer"
_VS_PRIMARIES_PROP: _ColorFramePropKey = "_Primaries"


def _get_int_frame_prop(frame_props: Mapping[str, object], key: _ColorFramePropKey) -> int | None:
    value = frame_props.get(key)
    if isinstance(value, int):
        return value
    return None


def _should_expand_tonemapped_limited_rgb(frame_props: Mapping[str, object]) -> bool:
    if "_Tonemapped" not in frame_props or "_FrameCompareExpandRange" not in frame_props:
        return False
    return props_indicate_limited_range(frame_props) is True


def render_frame_detailed(request: RenderRequest) -> RenderedFrameResult:
    """Render one frame and retain its exact source identity facts."""
    facts = RenderedFrameFacts(source_frame=request.frame_number)

    try:
        facts = _execute_vapoursynth_render(request, facts)
    except (EncodingError, RenderError):
        raise
    except Exception as e:
        details = _render_error_details(request)
        raise RenderError(reason=_render_error_reason(e), details=details) from e

    return RenderedFrameResult(path=request.output_path, facts=facts)


def _execute_vapoursynth_render(
    request: RenderRequest, facts: RenderedFrameFacts
) -> RenderedFrameFacts:
    node = request.clip
    validate_canvas_size(node.width, node.height, label="Source video")
    if request.geometry_plan is not None:
        request.geometry_plan.validate_sizes()
    facts = _facts_from_vapoursynth_source(request, facts)
    _render_vs(
        node,
        request.frame_number,
        request.output_path,
        request.encoder_settings,
        overlay=request.overlay,
        frame_facts=facts,
        geometry_plan=request.geometry_plan,
        source_signal=request.source_signal,
    )
    return facts


def _facts_from_vapoursynth_source(
    request: RenderRequest, facts: RenderedFrameFacts
) -> RenderedFrameFacts:
    """Read exact-frame properties from the original source node only.

    A transformed render graph is deliberately never consulted for picture type:
    filters and writer conversion are allowed to drop or alter reserved props.
    Metadata failure is non-fatal because the image itself remains renderable.
    """
    source = request.diagnostic_source
    validate_canvas_size(source.width, source.height, label="Source video")
    try:
        frame = source.get_frame(request.frame_number)
        frame_props = dict(frame.props)
        picture_type = normalize_picture_type(frame_props.get("_PictType"))
        dolby_vision_rpu = "DolbyVisionRPU" in frame_props
    except Exception:
        picture_type = None
        dolby_vision_rpu = None
    return replace(
        facts,
        picture_type=picture_type,
        dolby_vision_rpu=dolby_vision_rpu,
    )


def _render_error_reason(exc: Exception) -> str:
    if isinstance(exc, FrameCompareError):
        return exc.context.message
    return f"{type(exc).__name__}: {exc}"


def _render_error_details(request: RenderRequest) -> ErrorDetails:
    return {
        "frame": request.frame_number,
        "output_path": str(request.output_path),
    } | _vapoursynth_format_details(request.clip)


def _vapoursynth_format_details(clip: vs.VideoNode) -> ErrorDetails:
    fmt = getattr(clip, "format", None)
    if fmt is None:
        return {}

    return {
        "clip_format": str(getattr(fmt, "name", "")),
        "color_family": int(getattr(fmt, "color_family", 0)),
        "sample_type": int(getattr(fmt, "sample_type", 0)),
        "bits_per_sample": int(getattr(fmt, "bits_per_sample", 0)),
        "num_planes": int(getattr(fmt, "num_planes", 0)),
    }


def _resolve_matrix_in_s(
    clip: vs.VideoNode,
    source_signal: SourceSignalFacts | None = None,
    source_size: tuple[int, int] | None = None,
) -> str:
    """Prefer native matrix tags, then prepared tags, HDR evidence and coded size."""
    # VapourSynth usually caches frame 0, which supplies the clip's native signal.
    frame_props = clip.get_frame(0).props
    matrix_prop = _get_int_frame_prop(frame_props, _VS_MATRIX_PROP)
    if matrix_prop is not None and matrix_prop in MATRIX_TO_ZIMG:
        return MATRIX_TO_ZIMG[matrix_prop]

    transfer = _get_int_frame_prop(frame_props, _VS_TRANSFER_PROP)
    primaries = _get_int_frame_prop(frame_props, _VS_PRIMARIES_PROP)
    prepared_hdr = False
    if source_signal is not None:
        if source_signal.matrix is not None and source_signal.matrix in MATRIX_TO_ZIMG:
            return MATRIX_TO_ZIMG[source_signal.matrix]
        if transfer in (None, 2):
            transfer = source_signal.transfer
        if primaries in (None, 2):
            primaries = source_signal.primaries
        prepared_hdr = source_signal.is_hdr

    is_hdr = (transfer in {16, 18} or (transfer in (None, 2) and prepared_hdr)) and (
        primaries == 9 or (primaries in (None, 2) and prepared_hdr)
    )
    width, height = source_size or (clip.width, clip.height)
    return untagged_matrix(width, height, is_hdr=is_hdr)


def _clip_to_rgb24_for_pillow(
    clip: vs.VideoNode,
    source_signal: SourceSignalFacts | None = None,
    geometry_plan: RenderGeometryPlan | None = None,
) -> vs.VideoNode:
    """Convert a VapourSynth clip to RGB24 for Pillow encoding.

    Pillow's `Image.fromarray()` expects an integer pixel format for RGB/RGBA images.
    The VS pipeline frequently yields YUV (integer) or RGBS (float) depending on
    source format and tonemapping. Normalizing here keeps the encoder robust.
    """
    import vapoursynth as vs

    fmt = getattr(clip, "format", None)
    if fmt is None or fmt.color_family != vs.RGB:
        source_size = (
            (geometry_plan.source.width, geometry_plan.source.height) if geometry_plan else None
        )
        matrix = _resolve_matrix_in_s(clip, source_signal, source_size)
        if matrix == "2020cl":
            # The input hint fills a missing tag. Native frame tags keep priority.
            transfer = source_signal.transfer if source_signal is not None else None
            return clip.resize.Bicubic(
                format=vs.RGB24,
                matrix_in_s=matrix,
                transfer_in=BT2020_CL_TRANSFER if transfer in (None, 2) else transfer,
            )
        return clip.resize.Bicubic(format=vs.RGB24, matrix_in_s=matrix)

    if fmt.id == vs.RGB24:
        return clip
    return clip.resize.Point(format=vs.RGB24)


def _expand_video_range_rgb_array(array: np.ndarray) -> np.ndarray:
    max_code = float(np.iinfo(array.dtype).max)
    scale = max_code / 255.0
    min_in = 16.0 * scale
    max_in = 235.0 * scale
    expanded = (array.astype(np.float32) - min_in) * (max_code / (max_in - min_in))
    return np.clip(np.rint(expanded), 0, max_code).astype(array.dtype)


def _maybe_expand_tonemapped_video_range(
    array: np.ndarray,
    frame_props: Mapping[str, object],
) -> np.ndarray:
    if not _should_expand_tonemapped_limited_rgb(frame_props):
        return array
    return _expand_video_range_rgb_array(array)


def _render_vs(
    clip: vs.VideoNode,
    frame: int,
    output: Path,
    settings: EncoderSettings,
    overlay: OverlayConfig | None = None,
    frame_facts: RenderedFrameFacts | None = None,
    geometry_plan: RenderGeometryPlan | None = None,
    source_signal: SourceSignalFacts | None = None,
) -> None:
    """Render frame via VapourSynth."""
    try:
        fpng_writer = _resolve_fpng_writer(
            output,
            settings,
            overlay,
            geometry_plan=geometry_plan,
        )
        if fpng_writer is not None:
            fpng_clip = _clip_to_rgb24_for_pillow(clip, source_signal, geometry_plan)
            fpng_frame_props = dict(fpng_clip.get_frame(frame).props)
            if _should_expand_tonemapped_limited_rgb(fpng_frame_props):
                if settings.vs_writer == VsScreenshotWriter.FPNG:
                    raise EncodingError(
                        output,
                        "VapourSynth fpng writer cannot preserve tonemapped limited-range "
                        "RGB expansion yet; use vs_writer='auto' or 'pillow'",
                    )
            else:
                _render_vs_fpng(
                    fpng_clip,
                    frame,
                    output,
                    settings=settings,
                    writer=fpng_writer,
                    geometry_plan=geometry_plan,
                )
                return

        _render_vs_pillow(
            clip,
            frame,
            output,
            settings=settings,
            overlay=overlay,
            frame_facts=frame_facts,
            geometry_plan=geometry_plan,
            source_signal=source_signal,
        )

    except (EncodingError, OverlayError):
        raise
    except Exception as e:
        raise EncodingError(output, f"VapourSynth render failed: {type(e).__name__}: {e}") from e


def _render_vs_pillow(
    clip: vs.VideoNode,
    frame: int,
    output: Path,
    *,
    settings: EncoderSettings,
    overlay: OverlayConfig | None,
    frame_facts: RenderedFrameFacts | None,
    geometry_plan: RenderGeometryPlan | None,
    source_signal: SourceSignalFacts | None = None,
) -> None:
    clip = _clip_to_rgb24_for_pillow(clip, source_signal, geometry_plan)

    vs_frame = clip.get_frame(frame)

    planes = [np.array(vs_frame[i]) for i in range(vs_frame.format.num_planes)]
    if len(planes) == 1:
        array = planes[0]
    elif len(planes) == 3 or len(planes) == 4:
        array = np.dstack(planes)
    else:
        raise EncodingError(output, f"Unsupported plane count: {len(planes)}")

    array = _maybe_expand_tonemapped_video_range(array, vs_frame.props)

    image = Image.fromarray(array)
    image = _apply_geometry_plan(image, geometry_plan)

    if overlay:
        if frame_facts is None:
            raise OverlayError("rendered frame facts are required for overlay composition")
        image = apply_overlay(image, overlay, frame_facts)

    pnginfo = None
    if (
        _get_int_frame_prop(vs_frame.props, _VS_TRANSFER_PROP) == 13
        and _get_int_frame_prop(vs_frame.props, _VS_PRIMARIES_PROP) == 1
        and props_indicate_limited_range(vs_frame.props) is False
    ):
        pnginfo = PngInfo()
        pnginfo.add(b"sRGB", b"\x00")
    image.save(output, format="PNG", compress_level=settings.compression, pnginfo=pnginfo)


def _render_vs_fpng(
    clip: vs.VideoNode,
    frame: int,
    output: Path,
    *,
    settings: EncoderSettings,
    writer: _FpngWriter,
    geometry_plan: RenderGeometryPlan | None,
) -> None:
    work = _apply_geometry_plan_to_vs_clip(clip, geometry_plan)
    compression = _map_fpng_compression(settings.compression)

    try:
        job = writer(work, str(output), compression=compression, overwrite=True)
        job.get_frame(frame)
    except (RuntimeError, ValueError) as exc:
        raise EncodingError(output, f"VapourSynth fpng.Write failed: {exc}") from exc


def _resolve_fpng_writer(
    output: Path,
    settings: EncoderSettings,
    overlay: OverlayConfig | None,
    *,
    geometry_plan: RenderGeometryPlan | None,
) -> _FpngWriter | None:
    if settings.vs_writer == VsScreenshotWriter.PILLOW:
        return None

    if settings.vs_writer == VsScreenshotWriter.FPNG:
        if _has_rendered_overlay(overlay):
            raise EncodingError(
                output,
                "VapourSynth fpng writer cannot preserve overlays yet; use vs_writer='auto' or 'pillow'",
            )
        writer = _detect_fpng_writer()
        if writer is None:
            raise EncodingError(output, "VapourSynth fpng.Write plugin is unavailable")
        return writer

    if geometry_plan is None or _has_rendered_overlay(overlay):
        return None
    return _detect_fpng_writer()


def _detect_fpng_writer() -> _FpngWriter | None:
    try:
        import vapoursynth as vs_module
    except ImportError:
        return None

    core = getattr(vs_module, "core", None)
    fpng = getattr(core, "fpng", None) if core is not None else None
    writer = getattr(fpng, "Write", None) if fpng is not None else None
    if not callable(writer):
        return None
    return cast("_FpngWriter", writer)


def _has_rendered_overlay(overlay: OverlayConfig | None) -> bool:
    return overlay is not None and overlay.mode != OverlayMode.NONE


def _map_fpng_compression(level: int) -> int:
    if level < 0 or level > 9:
        raise ValueError("fpng compression level must be between 0 and 9")
    if level <= 3:
        return 0
    if level <= 6:
        return 1
    return 2


def _apply_geometry_plan(
    image: Image.Image,
    geometry_plan: RenderGeometryPlan | None,
) -> Image.Image:
    validate_canvas_size(*image.size, label="Rendered image")
    if geometry_plan is None:
        return image

    geometry_plan.validate_sizes()
    crop_rect = geometry_plan.crop_rect
    if crop_rect != geometry_plan.source_rect:
        image = image.crop((crop_rect.x, crop_rect.y, crop_rect.right, crop_rect.bottom))

    if image.size != geometry_plan.scaled_size:
        image = image.resize(geometry_plan.scaled_size, Image.Resampling.LANCZOS)

    if image.size == geometry_plan.final_canvas_size and geometry_plan.pad == GeometryMargins():
        return image

    canvas = Image.new(image.mode, geometry_plan.final_canvas_size)
    canvas.paste(image, geometry_plan.content_origin)
    return canvas


def _apply_geometry_plan_to_vs_clip(
    clip: vs.VideoNode,
    geometry_plan: RenderGeometryPlan | None,
) -> vs.VideoNode:
    if geometry_plan is None:
        return clip

    geometry_plan.validate_sizes()
    work = clip
    crop_rect = geometry_plan.crop_rect
    if crop_rect != geometry_plan.source_rect:
        crop = geometry_plan.crop
        work = cast(
            "vs.VideoNode",
            work.std.CropRel(  # type: ignore[attr-defined]
                left=crop.left,
                right=crop.right,
                top=crop.top,
                bottom=crop.bottom,
            ),
        )

    if geometry_plan.scaled_size != geometry_plan.cropped_size:
        width, height = geometry_plan.scaled_size
        work = cast(
            "vs.VideoNode",
            work.resize.Spline36(width=width, height=height),  # type: ignore[attr-defined]
        )

    if geometry_plan.pad != GeometryMargins():
        pad = geometry_plan.pad
        # Verify the actual input to AddBorders even if a caller supplied a
        # plan whose declared scale size differs from the real source node.
        validate_canvas_size(
            work.width + pad.left + pad.right,
            work.height + pad.top + pad.bottom,
            label="Padded frame",
        )
        work = cast(
            "vs.VideoNode",
            work.std.AddBorders(  # type: ignore[attr-defined]
                left=pad.left,
                right=pad.right,
                top=pad.top,
                bottom=pad.bottom,
            ),
        )
    return work
