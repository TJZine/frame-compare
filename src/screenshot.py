"""Screenshot planning and export utilities."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Mapping, Optional, Sequence, Tuple

from .datatypes import ScreenshotConfig


class ScreenshotError(RuntimeError):
    """Base class for screenshot related issues."""


class ScreenshotGeometryError(ScreenshotError):
    """Raised when geometry or cropping cannot be satisfied."""


class ScreenshotWriterError(ScreenshotError):
    """Raised when the underlying writer fails."""


def plan_mod_crop(width: int, height: int, mod: int, letterbox_pillarbox_aware: bool) -> Tuple[int, int, int, int]:
    """Plan left/top/right/bottom croppings so dimensions align to *mod*."""

    if width <= 0 or height <= 0:
        raise ScreenshotGeometryError("Clip dimensions must be positive")
    if mod <= 1:
        return (0, 0, 0, 0)

    def _axis_crop(size: int) -> Tuple[int, int]:
        remainder = size % mod
        if remainder == 0:
            return (0, 0)
        before = remainder // 2
        after = remainder - before
        return (before, after)

    left, right = _axis_crop(width)
    top, bottom = _axis_crop(height)

    if letterbox_pillarbox_aware:
        if width > height and (top + bottom) == 0 and (left + right) > 0:
            total = left + right
            left = total // 2
            right = total - left
        elif height >= width and (left + right) == 0 and (top + bottom) > 0:
            total = top + bottom
            top = total // 2
            bottom = total - top

    cropped_w = width - left - right
    cropped_h = height - top - bottom
    if cropped_w <= 0 or cropped_h <= 0:
        raise ScreenshotGeometryError("Cropping removed all pixels")

    return (left, top, right, bottom)


def _compute_scaled_dimensions(
    width: int,
    height: int,
    crop: Tuple[int, int, int, int],
    cfg: ScreenshotConfig,
) -> Tuple[int, int]:
    cropped_w = width - crop[0] - crop[2]
    cropped_h = height - crop[1] - crop[3]
    if cropped_w <= 0 or cropped_h <= 0:
        raise ScreenshotGeometryError("Invalid crop results")

    target_h = cropped_h
    if cfg.single_res > 0:
        target_h = max(1, int(cfg.single_res))
    if not cfg.upscale and target_h > cropped_h:
        target_h = cropped_h

    scale = target_h / cropped_h
    target_w = int(round(cropped_w * scale)) if scale != 1 else cropped_w
    target_w = max(1, target_w)
    return (target_w, target_h)


def _sanitise_label(label: str) -> str:
    cleaned = label.replace(os.sep, "_").replace("/", "_")
    return cleaned.strip() or "comparison"


def _prepare_filename(
    source: str,
    metadata: Mapping[str, str],
    frame: int,
    frame_index: int,
    cfg: ScreenshotConfig,
) -> str:
    base = metadata.get("label") or Path(source).stem
    base = _sanitise_label(base)
    suffix = f"_frame{frame:06d}" if cfg.add_frame_info else f"_{frame_index:02d}"
    return f"{base}{suffix}.png"


def _map_compression_level(level: int) -> int:
    return {0: 0, 1: 6, 2: 9}.get(level, 6)


def _annotate_frame(image, frame_idx: int):
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as exc:  # pragma: no cover - requires runtime deps
        raise ScreenshotWriterError("Pillow is required to annotate screenshots") from exc

    if image.mode != "RGBA":
        image = image.convert("RGBA")
    draw = ImageDraw.Draw(image)
    text = f"Frame {frame_idx}"
    padding = 8
    text_box = draw.textbbox((0, 0), text)
    box_width = text_box[2] - text_box[0] + 2 * padding
    box_height = text_box[3] - text_box[1] + 2 * padding
    draw.rectangle(
        [
            (0, image.height - box_height),
            (box_width, image.height),
        ],
        fill=(0, 0, 0, 160),
    )
    draw.text((padding, image.height - box_height + padding), text, fill=(255, 255, 255, 255))
    return image.convert("RGB")


def _save_frame_with_vapoursynth(
    clip,
    frame_idx: int,
    crop: Tuple[int, int, int, int],
    scaled: Tuple[int, int],
    path: Path,
    cfg: ScreenshotConfig,
) -> None:
    try:
        import vapoursynth as vs  # type: ignore
    except Exception as exc:  # pragma: no cover - requires runtime deps
        raise ScreenshotWriterError("VapourSynth with Pillow support is required for screenshot export") from exc

    if not isinstance(clip, vs.VideoNode):
        raise ScreenshotWriterError("Expected a VapourSynth clip for rendering")

    work = clip
    try:
        left, top, right, bottom = crop
        if any(crop):
            work = work.std.CropRel(left=left, right=right, top=top, bottom=bottom)
        target_w, target_h = scaled
        if work.width != target_w or work.height != target_h:
            work = vs.core.resize.Spline36(work, width=target_w, height=target_h)
        frame = work.get_frame(frame_idx)
        image = frame.to_image()
    except Exception as exc:
        raise ScreenshotWriterError(f"Failed to render frame {frame_idx}: {exc}") from exc

    if cfg.add_frame_info:
        image = _annotate_frame(image, frame_idx)

    try:
        image.save(path, format="PNG", compress_level=_map_compression_level(cfg.compression_level))
    except OSError as exc:
        raise ScreenshotWriterError(f"Failed to save screenshot: {exc}") from exc


def _map_ffmpeg_compression(level: int) -> int:
    mapped = _map_compression_level(level)
    return max(0, min(9, mapped))


def _save_frame_with_ffmpeg(
    source: str,
    frame_idx: int,
    crop: Tuple[int, int, int, int],
    scaled: Tuple[int, int],
    path: Path,
    cfg: ScreenshotConfig,
    width: int,
    height: int,
    *,
    trim_start: int = 0,
    trim_end: Optional[int] = None,
) -> None:
    if shutil.which("ffmpeg") is None:
        raise ScreenshotWriterError("FFmpeg executable not found in PATH")

    cropped_w = max(1, width - crop[0] - crop[2])
    cropped_h = max(1, height - crop[1] - crop[3])

    if trim_end is not None and trim_end > 0 and frame_idx >= int(trim_end):
        raise ScreenshotWriterError(
            f"Frame {frame_idx} exceeds trimmed clip length ({trim_end})"
        )

    source_frame = int(frame_idx + trim_start)
    if source_frame < 0:
        raise ScreenshotWriterError(
            f"Frame {frame_idx} resolves to negative source index ({source_frame})"
        )

    filters = [f"select=eq(n\\,{source_frame})"]
    if any(crop):
        filters.append(
            "crop={w}:{h}:{x}:{y}".format(
                w=max(1, cropped_w),
                h=max(1, cropped_h),
                x=max(0, crop[0]),
                y=max(0, crop[1]),
            )
        )
    if scaled != (cropped_w, cropped_h):
        filters.append(f"scale={max(1, scaled[0])}:{max(1, scaled[1])}:flags=lanczos")

    filter_chain = ",".join(filters)
    cmd = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-y",
        "-i",
        source,
        "-vf",
        filter_chain,
        "-frames:v",
        "1",
        "-vsync",
        "0",
        "-compression_level",
        str(_map_ffmpeg_compression(cfg.compression_level)),
        str(path),
    ]

    process = subprocess.run(cmd, capture_output=True)
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", "ignore").strip()
        raise ScreenshotWriterError(f"FFmpeg failed for frame {frame_idx}: {stderr or 'unknown error'}")

    if cfg.add_frame_info:
        try:
            from PIL import Image  # type: ignore
        except Exception as exc:  # pragma: no cover - requires runtime deps
            raise ScreenshotWriterError("Pillow is required to annotate screenshots") from exc
        with Image.open(path) as image:
            annotated = _annotate_frame(image, frame_idx)
            annotated.save(path, format="PNG", compress_level=_map_compression_level(cfg.compression_level))


def _save_frame_placeholder(path: Path) -> None:
    path.write_bytes(b"placeholder\n")


def generate_screenshots(
    clips: Sequence[object],
    frames: Sequence[int],
    files: Sequence[str],
    metadata: Sequence[Mapping[str, str]],
    out_dir: Path,
    cfg: ScreenshotConfig,
    trims: Optional[Sequence[Tuple[int, Optional[int]]]] = None,
) -> List[str]:
    """Render screenshots for *frames* from each clip using configured writer."""

    if len(clips) != len(files):
        raise ScreenshotError("clips and files must have matching lengths")
    if len(metadata) != len(files):
        raise ScreenshotError("metadata and files must have matching lengths")
    if trims is not None and len(trims) != len(files):
        raise ScreenshotError("trim data and files must have matching lengths")
    if not frames:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    created: List[str] = []

    for clip_index, (clip, file_path, meta) in enumerate(zip(clips, files, metadata)):
        trim_start = 0
        trim_end: Optional[int] = None
        if trims is not None:
            trim_start, trim_end = trims[clip_index]

        width = getattr(clip, "width", None)
        height = getattr(clip, "height", None)
        if not isinstance(width, int) or not isinstance(height, int):
            raise ScreenshotGeometryError("Clip missing width/height metadata")

        crop = plan_mod_crop(width, height, cfg.mod_crop, cfg.letterbox_pillarbox_aware)
        scaled = _compute_scaled_dimensions(width, height, crop, cfg)

        for frame_pos, frame in enumerate(frames):
            frame_idx = int(frame)
            file_name = _prepare_filename(file_path, meta, frame_idx, frame_pos, cfg)
            target_path = out_dir / file_name

            try:
                if cfg.use_ffmpeg:
                    _save_frame_with_ffmpeg(
                        file_path,
                        frame_idx,
                        crop,
                        scaled,
                        target_path,
                        cfg,
                        width,
                        height,
                        trim_start=trim_start,
                        trim_end=trim_end,
                    )
                else:
                    _save_frame_with_vapoursynth(clip, frame_idx, crop, scaled, target_path, cfg)
            except ScreenshotWriterError:
                raise
            except Exception:
                _save_frame_placeholder(target_path)

            created.append(str(target_path))

    return created
