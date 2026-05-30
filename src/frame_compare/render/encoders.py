"""Frame rendering encoders and dispatch logic."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

import numpy as np
from PIL import Image

from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.errors import ErrorDetails, FrameCompareError
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.render.errors import (
    EncodingError,
    FrameExtractionError,
    OverlayError,
    RenderError,
)
from frame_compare.render.geometry import GeometryMargins, RenderGeometryPlan
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import EncoderSettings, OverlayMode, Renderer, RenderRequest
from frame_compare.vs.errors import SourceLoadError
from frame_compare.vs.props import props_indicate_limited_range

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore[import-untyped]

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
_VS_PICTURE_TYPE_PROP = "_PictType"

_MATRIX_TO_ZIMG: dict[int, str] = {
    1: "709",
    4: "fcc",
    5: "470bg",
    6: "170m",
    7: "240m",
    8: "ycgco",
    9: "2020ncl",
    10: "2020cl",
}


def _get_int_frame_prop(frame_props: Mapping[str, object], key: _ColorFramePropKey) -> int | None:
    value = frame_props.get(key)
    if isinstance(value, int):
        return value
    return None


def _should_expand_tonemapped_limited_rgb(frame_props: Mapping[str, object]) -> bool:
    if "_Tonemapped" not in frame_props or "_FrameCompareExpandRange" not in frame_props:
        return False
    return props_indicate_limited_range(frame_props) is True


def _normalize_picture_type(value: object) -> str | None:
    text: str | None
    if isinstance(value, bytes):
        text = value.decode("utf-8", "ignore")
    elif isinstance(value, str):
        text = value
    else:
        return None

    normalized = text.strip("\x00").strip().upper()
    if normalized in {"I", "P", "B"}:
        return normalized
    if normalized == "IDR":
        return "I"
    return None


def _picture_type_from_frame_props(frame_props: Mapping[str, object]) -> str | None:
    return _normalize_picture_type(frame_props.get(_VS_PICTURE_TYPE_PROP))


def render_frame(request: RenderRequest, renderer: Renderer = "auto") -> Path:
    """
    Render a single frame to image file.

    Args:
        request: Render configuration
        renderer: "vapoursynth", "ffmpeg", or "auto"

    Returns:
        Path to rendered image

    Raises:
        RenderError: If rendering fails
        FrameExtractionError: If renderer requires vs.VideoNode but Path usage detected (or vice versa)
    """
    use_vs = _use_vapoursynth_renderer(request, renderer)

    try:
        _execute_frame_render(request, use_vs)

    except (EncodingError, FrameExtractionError, RenderError, SourceLoadError):
        raise
    except Exception as e:
        details = _render_error_details(request, renderer, use_vs)
        raise RenderError(reason=_render_error_reason(e), details=details) from e

    return request.output_path


def _use_vapoursynth_renderer(request: RenderRequest, renderer: Renderer) -> bool:
    clip = request.clip
    is_path = isinstance(clip, Path)

    if renderer == "vapoursynth":
        if is_path:
            raise FrameExtractionError(
                frame_number=request.frame_number,
                clip_name=str(clip),
            )
        return True

    if renderer == "ffmpeg":
        if not is_path:
            raise FrameExtractionError(
                frame_number=request.frame_number,
                clip_name=repr(clip),
            )
        return False

    return not is_path


def _execute_frame_render(request: RenderRequest, use_vapoursynth: bool) -> None:
    if use_vapoursynth:
        _execute_vapoursynth_render(request)
        return

    _execute_ffmpeg_render(request)


def _execute_vapoursynth_render(request: RenderRequest) -> None:
    node = cast("vs.VideoNode", request.clip)
    _render_vs(
        node,
        request.frame_number,
        request.output_path,
        request.encoder_settings,
        overlay=request.overlay,
        geometry_plan=request.geometry_plan,
    )


def _execute_ffmpeg_render(request: RenderRequest) -> None:
    path = cast(Path, request.clip)
    runner = request.ffmpeg_runner or DefaultFFmpegRunner()
    if request.geometry_plan is None:
        runner.extract_frame(path, request.frame_number, request.output_path)
    else:
        runner.extract_frame(
            path,
            request.frame_number,
            request.output_path,
            geometry_plan=request.geometry_plan,
        )

    if request.overlay is not None and request.overlay.mode != OverlayMode.NONE:
        apply_overlay_to_file(request.output_path, request.overlay)


def _render_error_reason(exc: Exception) -> str:
    if isinstance(exc, FrameCompareError):
        return exc.context.message
    return f"{type(exc).__name__}: {exc}"


def _render_error_details(
    request: RenderRequest, renderer: Renderer, use_vapoursynth: bool
) -> ErrorDetails:
    details: ErrorDetails = {
        "renderer": renderer,
        "frame": request.frame_number,
        "output_path": str(request.output_path),
    }
    if use_vapoursynth:
        return details | _vapoursynth_format_details(cast("vs.VideoNode", request.clip))

    details["clip"] = str(request.clip)
    return details


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


def _resolve_matrix_in_s(clip: vs.VideoNode) -> str:
    """Resolve matrix_in_s for YUV->RGB conversion with robust fallbacks.

    Priority:
    1. _Matrix frame prop mapping when recognized
    2. HDR heuristic (_Transfer in {16,18} and _Primaries == 9) -> 2020ncl
    3. SDR default -> 709
    """
    # Read canonical color props from frame 0. VapourSynth usually caches hot frames,
    # so this metadata probe is typically low overhead relative to full rendering.
    frame_props = dict(clip.get_frame(0).props)
    matrix_prop = _get_int_frame_prop(frame_props, _VS_MATRIX_PROP)
    if matrix_prop is not None:
        mapped = _MATRIX_TO_ZIMG.get(matrix_prop)
        if mapped is not None:
            return mapped

    transfer_prop = _get_int_frame_prop(frame_props, _VS_TRANSFER_PROP)
    primaries_prop = _get_int_frame_prop(frame_props, _VS_PRIMARIES_PROP)
    is_hdr = (
        transfer_prop is not None
        and transfer_prop in {16, 18}
        and primaries_prop is not None
        and primaries_prop == 9
    )
    return "2020ncl" if is_hdr else "709"


def _clip_to_rgb24_for_pillow(clip: vs.VideoNode) -> vs.VideoNode:
    """Convert a VapourSynth clip to RGB24 for Pillow encoding.

    Pillow's `Image.fromarray()` expects an integer pixel format for RGB/RGBA images.
    The VS pipeline frequently yields YUV (integer) or RGBS (float) depending on
    source format and tonemapping. Normalizing here keeps the encoder robust.
    """
    import vapoursynth as vs  # type: ignore[import-untyped]

    fmt = getattr(clip, "format", None)
    if fmt is None:
        matrix_in_s = _resolve_matrix_in_s(clip)
        # Variable format clip: best-effort conversion via resize (will fail if unsupported).
        return clip.resize.Bicubic(format=vs.RGB24, matrix_in_s=matrix_in_s)  # type: ignore[attr-defined]

    if fmt.id == vs.RGB24:  # type: ignore[attr-defined]
        frame_props = clip.get_frame(0).props
        if _should_expand_tonemapped_limited_rgb(frame_props):
            return clip.std.SetFrameProps(_FrameCompareExpandRange=1)
        return clip

    if fmt.color_family != vs.RGB:  # type: ignore[attr-defined]
        matrix_in_s = _resolve_matrix_in_s(clip)
        return clip.resize.Bicubic(format=vs.RGB24, matrix_in_s=matrix_in_s)  # type: ignore[attr-defined]

    frame_props = clip.get_frame(0).props
    if _should_expand_tonemapped_limited_rgb(frame_props):
        rgb = clip.resize.Point(format=vs.RGB24)  # type: ignore[attr-defined]
        return rgb.std.SetFrameProps(_FrameCompareExpandRange=1)

    return clip.resize.Point(format=vs.RGB24)  # type: ignore[attr-defined]


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
    geometry_plan: RenderGeometryPlan | None = None,
) -> None:
    """Render frame via VapourSynth."""
    try:
        fpng_writer = _resolve_fpng_writer(output, settings, overlay)
        if fpng_writer is not None:
            fpng_clip = _clip_to_rgb24_for_pillow(clip)
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
            geometry_plan=geometry_plan,
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
    geometry_plan: RenderGeometryPlan | None,
) -> None:
    clip = _clip_to_rgb24_for_pillow(clip)

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
        overlay.picture_type = _picture_type_from_frame_props(vs_frame.props)
        image = apply_overlay(image, overlay)

    image.save(output, format="PNG", compress_level=settings.compression)


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

    if _has_rendered_overlay(overlay):
        return None
    return _detect_fpng_writer()


def _detect_fpng_writer() -> _FpngWriter | None:
    try:
        import vapoursynth as vs_module  # type: ignore[import-untyped]
    except ImportError:
        return None

    core = getattr(vs_module, "core", None)
    if core is None:
        get_core = getattr(vs_module, "get_core", None)
        if callable(get_core):
            core = get_core()
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


def _apply_overlay_to_file(path: Path, config: OverlayConfig) -> None:
    """Helper to apply overlay to an existing image file."""
    try:
        with Image.open(path) as img:
            img.load()
            base = img.copy()

        result = apply_overlay(base, config)

        result.save(path, format="PNG")

    except Exception as e:
        raise OverlayError(f"Failed to apply overlay to {path}: {e}") from e


def _apply_geometry_plan(
    image: Image.Image,
    geometry_plan: RenderGeometryPlan | None,
) -> Image.Image:
    if geometry_plan is None:
        return image

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


def apply_overlay_to_file(path: Path, overlay: OverlayConfig) -> None:
    """Apply an overlay to an existing image file in place.

    Args:
        path: Path to an existing image file (PNG expected).
        overlay: Overlay rendering configuration.

    Raises:
        OverlayError: If the overlay cannot be applied.
    """
    if overlay.mode == OverlayMode.NONE:
        return
    _apply_overlay_to_file(path, overlay)
