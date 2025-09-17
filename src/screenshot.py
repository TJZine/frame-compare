from __future__ import annotations

"""Screenshot planning and export utilities."""

from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

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
        total = remainder
        before = total // 2
        after = total - before
        return (before, after)

    left, right = _axis_crop(width)
    top, bottom = _axis_crop(height)

    if letterbox_pillarbox_aware:
        # Prefer to remove remainder from the longer axis to keep content centered.
        if width > height and (top + bottom) == 0 and (left + right) > 0:
            # distribute columns evenly but concentrate additional pixel to one side for stability
            left = (left + right) // 2
            right = (left + right + 1) // 2
        elif height >= width and (left + right) == 0 and (top + bottom) > 0:
            top = (top + bottom) // 2
            bottom = (top + bottom + 1) // 2

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
        target_h = cfg.single_res
    if not cfg.upscale and target_h > cropped_h:
        target_h = cropped_h

    if target_h <= 0:
        raise ScreenshotGeometryError("Target height invalid")

    scale = target_h / cropped_h
    target_w = int(round(cropped_w * scale)) if scale != 1 else cropped_w
    target_w = max(1, target_w)
    return (target_w, target_h)


def _prepare_filename(source: str, frame: int, clip_index: int, frame_index: int, cfg: ScreenshotConfig) -> str:
    metadata = parse_filename_metadata(Path(source).name)
    base = metadata.get("label") or Path(source).stem
    if cfg.add_frame_info:
        suffix = f"_frame{frame:06d}"
    else:
        suffix = f"_{frame_index:02d}"
    return f"{base}{suffix}.png"


def _write_with_fpng(**kwargs) -> None:
    path: Path = kwargs["path"]
    try:
        path.write_bytes(b"fpng placeholder\n")
    except OSError as exc:  # pragma: no cover - filesystem failure
        raise ScreenshotWriterError(f"Failed to write fpng output: {exc}") from exc


def _write_with_ffmpeg(**kwargs) -> None:
    path: Path = kwargs["path"]
    try:
        path.write_bytes(b"ffmpeg placeholder\n")
    except OSError as exc:  # pragma: no cover - filesystem failure
        raise ScreenshotWriterError(f"Failed to write ffmpeg output: {exc}") from exc


def _fetch_frame(clip, frame: int):
    getter = getattr(clip, "get_frame", None)
    if callable(getter):
        return getter(frame)
    return None


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

    writer = _write_with_ffmpeg if cfg.use_ffmpeg else _write_with_fpng

    for clip_index, (clip, file_path) in enumerate(zip(clips, files)):
        width = getattr(clip, "width", None)
        height = getattr(clip, "height", None)
        if not isinstance(width, int) or not isinstance(height, int):
            raise ScreenshotGeometryError("Clip missing width/height metadata")

        crop = plan_mod_crop(width, height, cfg.mod_crop, cfg.letterbox_pillarbox_aware)
        scaled = _compute_scaled_dimensions(width, height, crop, cfg)

        for frame_pos, frame in enumerate(frames):
            frame_idx = int(frame)
            file_name = _prepare_filename(file_path, frame_idx, clip_index, frame_pos, cfg)
            target_path = out_dir / file_name

            try:
                frame_data = _fetch_frame(clip, frame_idx)
                writer(
                    clip=clip,
                    frame=frame_idx,
                    frame_data=frame_data,
                    path=target_path,
                    crop=crop,
                    scaled_dimensions=scaled,
                    compression_level=cfg.compression_level,
                    add_frame_info=cfg.add_frame_info,
                )
            except ScreenshotError:
                raise
            except Exception as exc:
                raise ScreenshotWriterError(f"Writer failed for frame {frame_idx}: {exc}") from exc

            created.append(str(target_path))

    return created
