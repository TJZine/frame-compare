"""Frame rendering encoders and dispatch logic."""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
from PIL import Image

from frame_compare.errors import (
    EncodingError,
    FFmpegError,
    FFmpegNotFoundError,
    FrameExtractionError,
    OverlayError,
    RenderError,
    SourceLoadError,
)
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import EncoderSettings, Renderer, RenderRequest
from frame_compare.utils.subproc import run_subprocess

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore[import-untyped]

    from frame_compare.render.types import OverlayConfig


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
            if request.overlay is not None:
                _apply_overlay_to_file(request.output_path, request.overlay)

    except FrameExtractionError:
        raise
    except Exception as e:
        raise RenderError() from e

    return request.output_path


def _render_vs(
    clip: vs.VideoNode,
    frame: int,
    output: Path,
    settings: EncoderSettings,
    overlay: OverlayConfig | None = None,
) -> None:
    """Render frame via VapourSynth."""
    try:
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
        raise EncodingError(output, f"VapourSynth render failed: {e}") from e


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

    # Deterministic seek time: floor((frame / fps) * 1000) / 1000
    seek_time = f"{math.floor((frame / fps) * 1000) / 1000:.3f}"

    cmd = [
        "ffmpeg",
        "-ss",
        seek_time,
        "-i",
        str(video_path),
        "-vframes",
        "1",
        "-q:v",
        "1",
        str(output),
    ]

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
