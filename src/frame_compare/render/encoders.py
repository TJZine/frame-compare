"""Frame rendering encoders and dispatch logic."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
from PIL import Image

from frame_compare.errors import (
    EncodingError,
    ErrorDetails,
    FrameCompareError,
    FrameExtractionError,
    OverlayError,
    RenderError,
    SourceLoadError,
)
from frame_compare.render.ffmpeg import DefaultFFmpegRunner
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import EncoderSettings, OverlayMode, Renderer, RenderRequest

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore[import-untyped]

    from frame_compare.render.types import OverlayConfig

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

    except (FrameExtractionError, RenderError, SourceLoadError):
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
    )


def _execute_ffmpeg_render(request: RenderRequest) -> None:
    path = cast(Path, request.clip)
    runner = request.ffmpeg_runner or DefaultFFmpegRunner()
    runner.extract_frame(path, request.frame_number, request.output_path)

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
    props = cast(dict[str, object], dict(clip.get_frame(0).props))
    matrix_prop = props.get("_Matrix")
    if isinstance(matrix_prop, int):
        mapped = _MATRIX_TO_ZIMG.get(matrix_prop)
        if mapped is not None:
            return mapped

    transfer_prop = props.get("_Transfer")
    primaries_prop = props.get("_Primaries")
    is_hdr = (
        isinstance(transfer_prop, int)
        and transfer_prop in {16, 18}
        and isinstance(primaries_prop, int)
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
        return clip

    if fmt.color_family != vs.RGB:  # type: ignore[attr-defined]
        matrix_in_s = _resolve_matrix_in_s(clip)
        return clip.resize.Bicubic(format=vs.RGB24, matrix_in_s=matrix_in_s)  # type: ignore[attr-defined]

    return clip.resize.Point(format=vs.RGB24)  # type: ignore[attr-defined]


def _render_vs(
    clip: vs.VideoNode,
    frame: int,
    output: Path,
    settings: EncoderSettings,
    overlay: OverlayConfig | None = None,
) -> None:
    """Render frame via VapourSynth."""
    try:
        clip = _clip_to_rgb24_for_pillow(clip)

        # 1. Get frame
        vs_frame = clip.get_frame(frame)

        # 2. Extract planes -> numpy -> Pillow
        planes = [np.array(vs_frame[i]) for i in range(vs_frame.format.num_planes)]
        if len(planes) == 1:
            array = planes[0]
        elif len(planes) == 3 or len(planes) == 4:
            array = np.dstack(planes)
        else:
            raise EncodingError(output, f"Unsupported plane count: {len(planes)}")

        image = Image.fromarray(array)

        # 3. Apply Overlay
        if overlay:
            image = apply_overlay(image, overlay)

        # 4. Save
        # Pillow save parameters: compress_level (0-9) for PNG
        image.save(output, format="PNG", compress_level=settings.compression)

    except (EncodingError, OverlayError):
        raise
    except Exception as e:
        raise EncodingError(output, f"VapourSynth render failed: {type(e).__name__}: {e}") from e


def _apply_overlay_to_file(path: Path, config: OverlayConfig) -> None:
    """Helper to apply overlay to an existing image file."""
    try:
        with Image.open(path) as img:
            img.load()
            base = img.copy()

        result = apply_overlay(base, config)

        # Save back
        result.save(path, format="PNG")

    except Exception as e:
        raise OverlayError(f"Failed to apply overlay to {path}: {e}") from e


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
