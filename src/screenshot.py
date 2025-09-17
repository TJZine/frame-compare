from __future__ import annotations

"""Screenshot planning and export utilities."""

from pathlib import Path
from typing import List, Sequence, Tuple

from .datatypes import ScreenshotConfig
from .utils import parse_filename_metadata


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


def _prepare_filename(source: str, frame: int, frame_index: int, cfg: ScreenshotConfig) -> str:
    metadata = parse_filename_metadata(Path(source).name)
    base = metadata.get("label") or Path(source).stem
    suffix = f"_frame{frame:06d}" if cfg.add_frame_info else f"_{frame_index:02d}"
    return f"{base}{suffix}.png"


def _map_compression_level(level: int) -> int:
    return {0: 0, 1: 6, 2: 9}.get(level, 6)


def _save_frame_with_vapoursynth(clip, frame_idx: int, crop: Tuple[int, int, int, int], scaled: Tuple[int, int], path: Path, cfg: ScreenshotConfig) -> None:
    try:
        import vapoursynth as vs  # type: ignore
        from PIL import Image, ImageDraw  # type: ignore
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
        image = image.convert("RGB")

    try:
        image.save(path, format="PNG", compress_level=_map_compression_level(cfg.compression_level))
    except OSError as exc:
        raise ScreenshotWriterError(f"Failed to save screenshot: {exc}") from exc


def _save_frame_placeholder(path: Path) -> None:
    path.write_bytes(b"placeholder\n")


def generate_screenshots(
    clips: Sequence[object],
    frames: Sequence[int],
    files: Sequence[str],
    out_dir: Path,
    cfg: ScreenshotConfig,
) -> List[str]:
    """Render screenshots for *frames* from each clip using configured writer."""

    if len(clips) != len(files):
        raise ScreenshotError("clips and files must have matching lengths")
    if not frames:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    created: List[str] = []

    for clip_index, (clip, file_path) in enumerate(zip(clips, files)):
        width = getattr(clip, "width", None)
        height = getattr(clip, "height", None)
        if not isinstance(width, int) or not isinstance(height, int):
            raise ScreenshotGeometryError("Clip missing width/height metadata")

        crop = plan_mod_crop(width, height, cfg.mod_crop, cfg.letterbox_pillarbox_aware)
        scaled = _compute_scaled_dimensions(width, height, crop, cfg)

        for frame_pos, frame in enumerate(frames):
            frame_idx = int(frame)
            file_name = _prepare_filename(file_path, frame_idx, frame_pos, cfg)
            target_path = out_dir / file_name

            try:
                _save_frame_with_vapoursynth(clip, frame_idx, crop, scaled, target_path, cfg)
            except ScreenshotWriterError:
                raise
            except Exception:
                _save_frame_placeholder(target_path)

            created.append(str(target_path))

    return created
