"""Screenshot planning and export utilities."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import re
from functools import partial
from pathlib import Path
from typing import Callable, List, Mapping, Sequence, Tuple

from .datatypes import ScreenshotConfig

_INVALID_LABEL_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


logger = logging.getLogger(__name__)


def _ensure_rgb24(core, clip, frame_idx):
    try:
        import vapoursynth as vs  # type: ignore
    except Exception as exc:  # pragma: no cover - requires runtime deps
        raise ScreenshotWriterError("VapourSynth is required for screenshot export") from exc

    fmt = getattr(clip, "format", None)
    color_family = getattr(fmt, "color_family", None) if fmt is not None else None
    bits = getattr(fmt, "bits_per_sample", None) if fmt is not None else None
    if color_family == getattr(vs, "RGB", object()) and bits == 8:
        return clip

    resize_ns = getattr(core, "resize", None)
    if resize_ns is None:
        raise ScreenshotWriterError("VapourSynth core is missing resize namespace")
    point = getattr(resize_ns, "Point", None)
    if not callable(point):
        raise ScreenshotWriterError("VapourSynth resize.Point is unavailable")

    dither = "error_diffusion" if isinstance(bits, int) and bits > 8 else "none"
    try:
        converted = point(clip, format=vs.RGB24, range=vs.RANGE_FULL, dither_type=dither)
    except Exception as exc:  # pragma: no cover - defensive
        raise ScreenshotWriterError(f"Failed to convert frame {frame_idx} to RGB24: {exc}") from exc

    try:
        converted = converted.std.SetFrameProps(
            _Matrix=1,
            _Primaries=1,
            _Transfer=1,
            _ColorRange=0,
        )
    except Exception:  # pragma: no cover - best effort
        pass
    return converted


def _clamp_frame_index(clip, frame_idx: int) -> tuple[int, bool]:
    total_frames = getattr(clip, "num_frames", None)
    if not isinstance(total_frames, int) or total_frames <= 0:
        return max(0, int(frame_idx)), False
    max_index = max(0, total_frames - 1)
    clamped = max(0, min(int(frame_idx), max_index))
    return clamped, clamped != frame_idx


FRAME_INFO_STYLE = 'sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"0,0,0,0,100,100,0,0,1,2,0,7,10,10,10,1"'


def _decode_prop_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "ignore")
    if isinstance(value, str):
        return value
    return ""


def _apply_frame_info_overlay(core, clip, title: str, requested_frame: int | None, selection_label: str | None) -> object:
    try:
        import vapoursynth as vs  # type: ignore
    except Exception:  # pragma: no cover - requires runtime deps
        return clip

    std_ns = getattr(core, "std", None)
    sub_ns = getattr(core, "sub", None)
    if std_ns is None or sub_ns is None:
        logger.debug('VapourSynth core missing std/sub namespaces; skipping frame overlay')
        return clip

    frame_eval = getattr(std_ns, 'FrameEval', None)
    subtitle = getattr(sub_ns, 'Subtitle', None)
    text_ns = getattr(core, 'text', None)
    draw_text = getattr(text_ns, 'Text', None) if text_ns is not None else None
    if not callable(frame_eval) or not callable(subtitle):
        logger.debug('Required VapourSynth overlay functions unavailable; skipping frame overlay')
        return clip

    label = title.strip() if isinstance(title, str) else ''
    if not label:
        label = 'Clip'

    padding_title = " " + ("\n" * 3)

    def _draw_info(n: int, f, clip_ref, *, draw_text_fn=None):
        pict = f.props.get('_PictType')
        if isinstance(pict, bytes):
            pict_text = pict.decode('utf-8', 'ignore')
        elif isinstance(pict, str):
            pict_text = pict
        else:
            pict_text = 'N/A'
        display_idx = requested_frame if requested_frame is not None else n
        lines = [
            f"Frame {display_idx} of {clip_ref.num_frames}",
            f"Picture type: {pict_text}",
        ]
        if selection_label:
            lines.append(f"Content Type: {selection_label}")
        info = "\n".join(lines)
        result = subtitle(clip_ref, text=[info], style=FRAME_INFO_STYLE)
        tonemap_text = _decode_prop_text(
            f.props.get('_TonemapOverlay') or f.props.get('_Tonemapped')
        )
        if tonemap_text and callable(draw_text_fn):
            try:
                result = draw_text_fn(result, tonemap_text, alignment=9, scale=1)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug('Tonemap overlay draw failed: %s', exc)
        return result

    try:
        info_clip = frame_eval(
            clip,
            partial(_draw_info, clip_ref=clip, draw_text_fn=draw_text),
            prop_src=clip,
        )
        return subtitle(info_clip, text=[padding_title + label], style=FRAME_INFO_STYLE)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug('Applying frame overlay failed: %s', exc)
        return clip


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
    target_height: int,
) -> Tuple[int, int]:
    cropped_w = width - crop[0] - crop[2]
    cropped_h = height - crop[1] - crop[3]
    if cropped_w <= 0 or cropped_h <= 0:
        raise ScreenshotGeometryError("Invalid crop results")

    desired_h = max(1, int(round(target_height)))
    scale = desired_h / cropped_h if cropped_h else 1.0
    target_w = int(round(cropped_w * scale)) if scale != 1 else cropped_w
    target_w = max(1, target_w)
    return (target_w, desired_h)


def _plan_geometry(clips: Sequence[object], cfg: ScreenshotConfig) -> List[dict[str, object]]:
    plans: List[dict[str, object]] = []
    for clip in clips:
        width = getattr(clip, "width", None)
        height = getattr(clip, "height", None)
        if not isinstance(width, int) or not isinstance(height, int):
            raise ScreenshotGeometryError("Clip missing width/height metadata")

        crop = plan_mod_crop(width, height, cfg.mod_crop, cfg.letterbox_pillarbox_aware)
        cropped_w = width - crop[0] - crop[2]
        cropped_h = height - crop[1] - crop[3]
        if cropped_w <= 0 or cropped_h <= 0:
            raise ScreenshotGeometryError("Invalid crop results")

        plans.append(
            {
                "width": width,
                "height": height,
                "crop": crop,
                "cropped_w": cropped_w,
                "cropped_h": cropped_h,
            }
        )

    single_res_target = int(cfg.single_res) if cfg.single_res > 0 else None
    if single_res_target is not None:
        desired_height = max(1, single_res_target)
        global_target = None
    else:
        desired_height = None
        global_target = max((plan["cropped_h"] for plan in plans), default=None) if cfg.upscale else None

    for plan in plans:
        cropped_h = int(plan["cropped_h"])
        if desired_height is not None:
            target_h = desired_height
            if not cfg.upscale and target_h > cropped_h:
                target_h = cropped_h
        elif global_target is not None:
            target_h = max(cropped_h, int(global_target))
        else:
            target_h = cropped_h

        plan["scaled"] = _compute_scaled_dimensions(
            int(plan["width"]),
            int(plan["height"]),
            plan["crop"],
            target_h,
        )

    return plans


def _sanitise_label(label: str) -> str:
    cleaned = _INVALID_LABEL_PATTERN.sub("_", label)
    if os.name == "nt":
        cleaned = cleaned.rstrip(" .")
    cleaned = cleaned.strip()
    return cleaned or "comparison"


def _derive_labels(source: str, metadata: Mapping[str, str]) -> tuple[str, str]:
    raw = metadata.get("label") or Path(source).stem
    cleaned = _sanitise_label(raw)
    return raw.strip() or cleaned, cleaned


def _prepare_filename(frame: int, label: str) -> str:
    return f"{frame} - {label}.png"


def _normalise_compression_level(level: int) -> int:
    try:
        value = int(level)
    except Exception:
        return 1
    return max(0, min(2, value))


def _map_fpng_compression(level: int) -> int:
    normalised = _normalise_compression_level(level)
    return {0: 0, 1: 1, 2: 2}.get(normalised, 1)


def _map_png_compression_level(level: int) -> int:
    """Translate the user configured level into a PNG compress level."""

    normalised = _normalise_compression_level(level)
    mapping = {0: 0, 1: 6, 2: 9}
    return mapping.get(normalised, 6)


def _save_frame_with_fpng(
    clip,
    frame_idx: int,
    crop: Tuple[int, int, int, int],
    scaled: Tuple[int, int],
    path: Path,
    cfg: ScreenshotConfig,
    label: str,
    requested_frame: int,
    selection_label: str | None = None,
) -> None:
    try:
        import vapoursynth as vs  # type: ignore
    except Exception as exc:  # pragma: no cover - requires runtime deps
        raise ScreenshotWriterError("VapourSynth is required for screenshot export") from exc

    if not isinstance(clip, vs.VideoNode):
        raise ScreenshotWriterError("Expected a VapourSynth clip for rendering")

    core = getattr(clip, "core", None) or getattr(vs, "core", None)
    fpng_ns = getattr(core, "fpng", None) if core is not None else None
    writer = getattr(fpng_ns, "Write", None) if fpng_ns is not None else None
    if not callable(writer):
        raise ScreenshotWriterError("VapourSynth fpng.Write plugin is unavailable")

    work = clip
    try:
        left, top, right, bottom = crop
        if any(crop):
            work = work.std.CropRel(left=left, right=right, top=top, bottom=bottom)
        target_w, target_h = scaled
        if work.width != target_w or work.height != target_h:
            resize_ns = getattr(core, "resize", None)
            if resize_ns is None:
                raise ScreenshotWriterError("VapourSynth core is missing resize namespace")
            resampler = getattr(resize_ns, "Spline36", None)
            if not callable(resampler):
                raise ScreenshotWriterError("VapourSynth resize.Spline36 is unavailable")
            work = resampler(work, width=target_w, height=target_h)
    except Exception as exc:
        raise ScreenshotWriterError(f"Failed to prepare frame {frame_idx}: {exc}") from exc

    render_clip = work
    if cfg.add_frame_info:
        render_clip = _apply_frame_info_overlay(core, render_clip, label, requested_frame, selection_label)

    render_clip = _ensure_rgb24(core, render_clip, frame_idx)

    compression = _map_fpng_compression(cfg.compression_level)
    try:
        job = writer(render_clip, str(path), compression=compression, overwrite=True)
        job.get_frame(frame_idx)
    except Exception as exc:
        raise ScreenshotWriterError(f"fpng failed for frame {frame_idx}: {exc}") from exc


def _map_ffmpeg_compression(level: int) -> int:
    """Map config compression level to ffmpeg's PNG compression scale."""

    return _map_png_compression_level(level)


def _resolve_source_frame_index(frame_idx: int, trim_start: int) -> int | None:
    if trim_start == 0:
        return frame_idx
    if trim_start > 0:
        return frame_idx + trim_start
    blank = abs(int(trim_start))
    if frame_idx < blank:
        return None
    return frame_idx - blank


def _save_frame_with_ffmpeg(
    source: str,
    frame_idx: int,
    crop: Tuple[int, int, int, int],
    scaled: Tuple[int, int],
    path: Path,
    cfg: ScreenshotConfig,
    width: int,
    height: int,
    selection_label: str | None,
) -> None:
    if shutil.which("ffmpeg") is None:
        raise ScreenshotWriterError("FFmpeg executable not found in PATH")

    cropped_w = max(1, width - crop[0] - crop[2])
    cropped_h = max(1, height - crop[1] - crop[3])

    filters = [f"select=eq(n\\,{int(frame_idx)})"]
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
    if cfg.add_frame_info:
        text_lines = [f"Frame\\ {int(frame_idx)}"]
        if selection_label:
            text_lines.append(f"Content Type\\: {selection_label}")
        text = "\\\\n".join(text_lines)
        drawtext = (
            "drawtext=text={text}:fontcolor=white:box=1:boxcolor=black@0.6:"
            "boxborderw=6:x=10:y=10"
        ).format(text=text)
        filters.append(drawtext)

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



def _save_frame_placeholder(path: Path) -> None:
    path.write_bytes(b"placeholder\n")


def generate_screenshots(
    clips: Sequence[object],
    frames: Sequence[int],
    files: Sequence[str],
    metadata: Sequence[Mapping[str, str]],
    out_dir: Path,
    cfg: ScreenshotConfig,
    *,
    trim_offsets: Sequence[int] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    frame_labels: Mapping[int, str] | None = None,
) -> List[str]:
    """Render screenshots for *frames* from each clip using configured writer."""

    if len(clips) != len(files):
        raise ScreenshotError("clips and files must have matching lengths")
    if len(metadata) != len(files):
        raise ScreenshotError("metadata and files must have matching lengths")
    if not frames:
        return []

    if trim_offsets is None:
        trim_offsets = [0] * len(files)
    if len(trim_offsets) != len(files):
        raise ScreenshotError("trim_offsets and files must have matching lengths")

    out_dir.mkdir(parents=True, exist_ok=True)
    created: List[str] = []

    geometry = _plan_geometry(clips, cfg)

    for clip_index, (clip, file_path, meta, plan, trim_start) in enumerate(
        zip(clips, files, metadata, geometry, trim_offsets)
    ):
        if frame_labels:
            logger.debug('frame_labels keys: %s', list(frame_labels.keys()))
        crop = plan["crop"]  # type: ignore[assignment]
        scaled = plan["scaled"]  # type: ignore[assignment]
        width = int(plan["width"])
        height = int(plan["height"])
        trim_start = int(trim_start)
        raw_label, safe_label = _derive_labels(file_path, meta)

        for frame in frames:
            frame_idx = int(frame)
            selection_label = frame_labels.get(frame_idx) if frame_labels else None
            if selection_label is not None:
                logger.debug('Selection label for frame %s: %s', frame_idx, selection_label)
            actual_idx, was_clamped = _clamp_frame_index(clip, frame_idx)
            if was_clamped:
                logger.debug(
                    "Frame %s exceeds available frames (%s) in %s; using %s",
                    frame_idx,
                    getattr(clip, 'num_frames', 'unknown'),
                    file_path,
                    actual_idx,
                )
            file_name = _prepare_filename(frame_idx, safe_label)
            target_path = out_dir / file_name

            try:
                resolved_frame = _resolve_source_frame_index(actual_idx, trim_start)
                use_ffmpeg = cfg.use_ffmpeg and resolved_frame is not None
                if cfg.use_ffmpeg and resolved_frame is None:
                    logger.debug(
                        "Frame %s for %s falls within synthetic trim padding; using VapourSynth writer",
                        frame_idx,
                        file_path,
                    )
                if use_ffmpeg:
                    _save_frame_with_ffmpeg(
                        file_path,
                        resolved_frame,
                        crop,
                        scaled,
                        target_path,
                        cfg,
                        width,
                        height,
                        selection_label,
                    )
                else:
                    _save_frame_with_fpng(clip, actual_idx, crop, scaled, target_path, cfg, raw_label, frame_idx, selection_label)
            except ScreenshotWriterError:
                raise
            except Exception as exc:
                logger.warning(
                    "Falling back to placeholder for frame %s of %s: %s",
                    frame_idx,
                    file_path,
                    exc,
                )
                _save_frame_placeholder(target_path)

            created.append(str(target_path))
            if progress_callback is not None:
                progress_callback(1)

    return created
