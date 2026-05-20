"""Frame rendering encoders and dispatch logic."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
from PIL import Image

from frame_compare.errors import (
    EncodingError,
    ErrorDetails,
    FFmpegError,
    FFmpegNotFoundError,
    FrameCompareError,
    FrameExtractionError,
    OverlayError,
    RenderError,
    SourceLoadError,
)
from frame_compare.render._ffmpeg_frame import build_extract_frame_argv, frame_seek_time_seconds
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import EncoderSettings, OverlayMode, Renderer, RenderRequest
from frame_compare.utils.subproc import run_subprocess

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
    clip = request.clip
    is_path = isinstance(clip, Path)

    # Dispatch logic
    use_vs = False

    if renderer == "vapoursynth":
        if is_path:
            raise FrameExtractionError(
                frame_number=request.frame_number,
                clip_name=str(clip),
            )
        use_vs = True
    elif renderer == "ffmpeg":
        if not is_path:
            raise FrameExtractionError(
                frame_number=request.frame_number,
                clip_name=repr(clip),
            )
        use_vs = False
    else:  # auto
        use_vs = not is_path

    try:
        if use_vs:
            # We know clip is not Path, so it must be vs.VideoNode (if types are correct)
            # but at runtime we cast it.
            node = cast("vs.VideoNode", clip)
            _render_vs(
                node,
                request.frame_number,
                request.output_path,
                request.encoder_settings,
                overlay=request.overlay,
            )
        else:
            path = cast(Path, clip)
            _render_ffmpeg(
                path, request.frame_number, request.output_path, request.encoder_settings
            )

            # Overlay Integration for FFmpeg
            if request.overlay is not None and request.overlay.mode != OverlayMode.NONE:
                apply_overlay_to_file(request.output_path, request.overlay)

    except (FrameExtractionError, RenderError, SourceLoadError):
        raise
    except Exception as e:
        reason: str
        if isinstance(e, FrameCompareError):
            reason = e.context.message
        else:
            reason = f"{type(e).__name__}: {e}"

        details: ErrorDetails = {
            "renderer": renderer,
            "frame": request.frame_number,
            "output_path": str(request.output_path),
        }
        if use_vs:
            node = cast("vs.VideoNode", clip)
            fmt = cast(Any, getattr(node, "format", None))
            if fmt is not None:
                details |= {
                    "clip_format": str(getattr(fmt, "name", "")),
                    "color_family": int(getattr(fmt, "color_family", 0)),
                    "sample_type": int(getattr(fmt, "sample_type", 0)),
                    "bits_per_sample": int(getattr(fmt, "bits_per_sample", 0)),
                    "num_planes": int(getattr(fmt, "num_planes", 0)),
                }
        else:
            details["clip"] = str(clip)

        raise RenderError(reason=reason, details=details) from e

    return request.output_path


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

    fmt = cast(Any, getattr(clip, "format", None))
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


def _probe_fps(video_path: Path) -> float:
    """Probe video FPS using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]

    try:
        result = run_subprocess(cmd, timeout_seconds=10)
        fps_str = result.stdout.decode().strip()
        if not fps_str:
            raise SourceLoadError(video_path, "Empty output from ffprobe")

        fps: float
        if "/" in fps_str:
            parts = fps_str.split("/", maxsplit=1)
            if len(parts) != 2:
                raise SourceLoadError(video_path, f"Invalid avg_frame_rate: {fps_str!r}")
            num_str, den_str = parts
            num = float(num_str)
            den = float(den_str)
            if den == 0.0:
                raise SourceLoadError(video_path, f"Invalid avg_frame_rate: {fps_str!r}")
            fps = num / den
        else:
            fps = float(fps_str)

        if not math.isfinite(fps) or fps <= 0.0:
            raise SourceLoadError(video_path, f"Invalid FPS from ffprobe: {fps_str!r}")
        return fps
    except FileNotFoundError as e:
        raise FFmpegNotFoundError() from e
    except (ValueError, subprocess.CalledProcessError, ZeroDivisionError) as e:
        raise SourceLoadError(video_path, f"Failed to probe FPS: {e}") from e


def _render_ffmpeg(
    video_path: Path,
    frame: int,
    output: Path,
    settings: EncoderSettings,
    timeout: int = 30,
) -> None:
    """Render frame via FFmpeg."""
    fps = _probe_fps(video_path)
    seek_time = frame_seek_time_seconds(frame, fps)
    cmd = build_extract_frame_argv(
        video=video_path,
        seek_time=seek_time,
        output=output,
        overwrite=False,
    )

    try:
        run_subprocess(cmd, timeout_seconds=timeout)
    except FileNotFoundError as e:
        raise FFmpegNotFoundError() from e
    except subprocess.CalledProcessError as e:
        raise FFmpegError(e.stderr.decode(), e.returncode) from e


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
