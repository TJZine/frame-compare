"""Screenshot planning and export utilities."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import re
from functools import partial
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .datatypes import ColorConfig, ScreenshotConfig
from . import vs_core

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
            _Matrix=0,
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
OVERLAY_STYLE = 'sans-serif,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"0,0,0,0,100,100,0,0,1,2,0,7,10,10,80,1"'

_LETTERBOX_RATIO_TOLERANCE = 0.04


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
    if not callable(frame_eval) or not callable(subtitle):
        logger.debug('Required VapourSynth overlay functions unavailable; skipping frame overlay')
        return clip

    label = title.strip() if isinstance(title, str) else ''
    if not label:
        label = 'Clip'

    padding_title = " " + ("\n" * 3)

    def _draw_info(n: int, f, clip_ref):
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
        return subtitle(clip_ref, text=[info], style=FRAME_INFO_STYLE)

    try:
        info_clip = frame_eval(clip, partial(_draw_info, clip_ref=clip), prop_src=clip)
        return subtitle(info_clip, text=[padding_title + label], style=FRAME_INFO_STYLE)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug('Applying frame overlay failed: %s', exc)
        return clip


def _apply_overlay_text(
    core,
    clip,
    text: Optional[str],
    *,
    strict: bool,
    state: Dict[str, str],
    file_label: str,
) -> object:
    if not text:
        return clip
    status = state.get("overlay_status")
    if status == "error":
        return clip
    sub_ns = getattr(core, "sub", None)
    subtitle = getattr(sub_ns, "Subtitle", None) if sub_ns is not None else None
    if callable(subtitle):
        try:
            result = subtitle(clip, text=[text], style=OVERLAY_STYLE)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug('Subtitle overlay failed, falling back: %s', exc)
        else:
            if status != "ok":
                logger.info('[OVERLAY] %s applied', file_label)
                state["overlay_status"] = "ok"
            return result

    text_ns = getattr(core, "text", None)
    draw = getattr(text_ns, "Text", None) if text_ns is not None else None
    if not callable(draw):
        message = f"Overlay filter unavailable for {file_label}"
        logger.error('[OVERLAY] %s', message)
        state["overlay_status"] = "error"
        if strict:
            raise ScreenshotWriterError(message)
        return clip
    try:
        result = draw(clip, text, alignment=9)
    except Exception as exc:  # pragma: no cover - defensive
        message = f"Overlay failed for {file_label}: {exc}"
        logger.error('[OVERLAY] %s', message)
        state["overlay_status"] = "error"
        if strict:
            raise ScreenshotWriterError(message) from exc
        return clip
    std_ns = getattr(core, "std", None)
    copy_props = getattr(std_ns, "CopyFrameProps", None) if std_ns is not None else None
    if callable(copy_props):
        try:
            result = copy_props(result, clip)
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug('CopyFrameProps failed during overlay preservation: %s', exc)
    if status != "ok":
        logger.info('[OVERLAY] %s applied', file_label)
        state["overlay_status"] = "ok"
    return result


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


def _align_letterbox_pillarbox(plans: List[dict[str, object]]) -> None:
    if not plans:
        return

    widths = [int(plan["width"]) for plan in plans]
    heights = [int(plan["height"]) for plan in plans]
    same_w = len({w for w in widths if w > 0}) == 1
    same_h = len({h for h in heights if h > 0}) == 1

    if same_w:
        target_h = min(int(plan["cropped_h"]) for plan in plans)
        for plan in plans:
            current_h = int(plan["cropped_h"])
            diff = current_h - target_h
            if diff <= 0:
                continue
            add_top = diff // 2
            add_bottom = diff - add_top
            left, top, right, bottom = plan["crop"]  # type: ignore[misc]
            top += add_top
            bottom += add_bottom
            plan["crop"] = (left, top, right, bottom)
            plan["cropped_h"] = plan["height"] - top - bottom
    elif same_h:
        target_w = min(int(plan["cropped_w"]) for plan in plans)
        for plan in plans:
            current_w = int(plan["cropped_w"])
            diff = current_w - target_w
            if diff <= 0:
                continue
            add_left = diff // 2
            add_right = diff - add_left
            left, top, right, bottom = plan["crop"]  # type: ignore[misc]
            left += add_left
            right += add_right
            plan["crop"] = (left, top, right, bottom)
            plan["cropped_w"] = plan["width"] - left - right


def _plan_letterbox_offsets(
    plans: Sequence[dict[str, object]],
    *,
    mod: int,
    tolerance: float = _LETTERBOX_RATIO_TOLERANCE,
    max_target_height: int | None = None,
) -> List[tuple[int, int]]:
    ratios: List[float] = []
    for plan in plans:
        try:
            width = float(plan["width"])
            height = float(plan["height"])
        except Exception:
            continue
        if width > 0 and height > 0:
            ratios.append(width / height)

    if not ratios:
        return [(0, 0) for _ in plans]

    target_ratio = max(ratios)
    if target_ratio <= 0:
        return [(0, 0) for _ in plans]

    tolerance = max(0.0, tolerance)
    min_ratio_allowed = target_ratio * (1.0 - tolerance)

    offsets: List[tuple[int, int]] = []
    for plan in plans:
        try:
            width = int(plan["width"])
            height = int(plan["height"])
        except Exception:
            offsets.append((0, 0))
            continue
        if width <= 0 or height <= 0:
            offsets.append((0, 0))
            continue

        ratio = width / height
        if ratio >= min_ratio_allowed:
            offsets.append((0, 0))
            continue

        desired_height = width / target_ratio
        target_height = int(round(desired_height))
        if max_target_height is not None:
            target_height = min(target_height, max_target_height)

        if mod > 1:
            target_height -= target_height % mod
        target_height = max(mod if mod > 0 else 1, target_height)
        if target_height >= height:
            offsets.append((0, 0))
            continue

        crop_total = height - target_height
        if crop_total <= 0:
            offsets.append((0, 0))
            continue

        top_extra = crop_total // 2
        bottom_extra = crop_total - top_extra
        offsets.append((top_extra, bottom_extra))

    return offsets


def _split_padding(total: int, center: bool) -> tuple[int, int]:
    amount = max(0, int(total))
    if amount <= 0:
        return (0, 0)
    if center:
        first = amount // 2
        second = amount - first
        return (first, second)
    return (0, amount)


def _align_padding_mod(
    width: int,
    height: int,
    pad_left: int,
    pad_top: int,
    pad_right: int,
    pad_bottom: int,
    mod: int,
    center: bool,
) -> tuple[int, int, int, int]:
    if mod <= 1:
        return (pad_left, pad_top, pad_right, pad_bottom)

    total_pad = pad_left + pad_top + pad_right + pad_bottom
    if total_pad <= 0:
        return (pad_left, pad_top, pad_right, pad_bottom)

    final_w = width + pad_left + pad_right
    final_h = height + pad_top + pad_bottom

    remainder_w = final_w % mod
    if remainder_w:
        extra = mod - remainder_w
        add_left, add_right = _split_padding(extra, center)
        pad_left += add_left
        pad_right += add_right
        final_w += extra

    remainder_h = final_h % mod
    if remainder_h:
        extra = mod - remainder_h
        add_top, add_bottom = _split_padding(extra, center)
        pad_top += add_top
        pad_bottom += add_bottom

    return (pad_left, pad_top, pad_right, pad_bottom)


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

    if cfg.auto_letterbox_crop:
        try:
            max_target_height = min(int(plan["cropped_h"]) for plan in plans)
        except ValueError:
            max_target_height = None
        offsets = _plan_letterbox_offsets(
            plans,
            mod=cfg.mod_crop,
            max_target_height=max_target_height,
        )
        for plan, (extra_top, extra_bottom) in zip(plans, offsets):
            if not (extra_top or extra_bottom):
                continue
            left, top, right, bottom = plan["crop"]  # type: ignore[misc]
            top += int(extra_top)
            bottom += int(extra_bottom)
            new_height = int(plan["height"]) - top - bottom
            if new_height <= 0:
                raise ScreenshotGeometryError("Letterbox detection removed all pixels")
            plan["crop"] = (left, top, right, bottom)
            plan["cropped_h"] = new_height
            logger.info(
                "[LETTERBOX] Cropping %s px top / %s px bottom for width=%s height=%s",
                extra_top,
                extra_bottom,
                plan["width"],
                plan["height"],
            )

    if cfg.letterbox_pillarbox_aware:
        _align_letterbox_pillarbox(plans)

    single_res_target = int(cfg.single_res) if cfg.single_res > 0 else None
    if single_res_target is not None:
        desired_height = max(1, single_res_target)
        global_target = None
    else:
        desired_height = None
        global_target = max((plan["cropped_h"] for plan in plans), default=None) if cfg.upscale else None

    max_source_width = max((int(plan["width"]) for plan in plans), default=0)

    pad_mode = str(getattr(cfg, "pad_to_canvas", "off")).strip().lower()
    pad_enabled = pad_mode in {"on", "auto"}
    pad_force = pad_mode == "on"
    pad_tolerance = max(0, int(getattr(cfg, "letterbox_px_tolerance", 0)))
    center_pad = bool(getattr(cfg, "center_pad", True))

    target_heights: List[int] = []

    for plan in plans:
        cropped_w = int(plan["cropped_w"])
        cropped_h = int(plan["cropped_h"])
        if desired_height is not None:
            target_h = desired_height
            if not cfg.upscale and target_h > cropped_h:
                target_h = cropped_h
        elif global_target is not None:
            target_h = max(cropped_h, int(global_target))
        else:
            target_h = cropped_h

        target_heights.append(target_h)

        pad_left = pad_top = pad_right = pad_bottom = 0
        scaled_w = cropped_w
        scaled_h = cropped_h

        if target_h != cropped_h:
            if target_h > cropped_h and cfg.upscale:
                scaled_w, scaled_h = _compute_scaled_dimensions(
                    int(plan["width"]),
                    int(plan["height"]),
                    plan["crop"],
                    target_h,
                )
            elif target_h < cropped_h:
                scaled_w, scaled_h = _compute_scaled_dimensions(
                    int(plan["width"]),
                    int(plan["height"]),
                    plan["crop"],
                    target_h,
                )
            elif pad_enabled and target_h > cropped_h:
                diff = target_h - cropped_h
                if pad_force or diff <= pad_tolerance:
                    add_top, add_bottom = _split_padding(diff, center_pad)
                    pad_top += add_top
                    pad_bottom += add_bottom

        if cfg.upscale and max_source_width > 0 and scaled_w > max_source_width:
            base_w = int(plan["cropped_w"])
            if base_w > 0:
                scale = max_source_width / float(base_w)
                adjusted_h = int(round(int(plan["cropped_h"]) * scale))
                scaled_w = max_source_width
                scaled_h = max(1, adjusted_h)

        plan["scaled"] = (scaled_w, scaled_h)
        plan["pad"] = (pad_left, pad_top, pad_right, pad_bottom)

    canvas_height = None
    if desired_height is not None:
        canvas_height = desired_height
    elif global_target is not None:
        try:
            canvas_height = max(int(value) for value in target_heights)
        except ValueError:
            canvas_height = None

    canvas_width = None
    if pad_enabled:
        if single_res_target is not None and max_source_width > 0:
            canvas_width = max_source_width
        else:
            try:
                canvas_width = max(int(plan["scaled"][0]) for plan in plans)
            except ValueError:
                canvas_width = None

    for plan in plans:
        scaled_w, scaled_h = plan["scaled"]
        pad_left, pad_top, pad_right, pad_bottom = plan.get("pad", (0, 0, 0, 0))

        if canvas_height is not None and pad_enabled:
            target_h = canvas_height
            current_h = scaled_h + pad_top + pad_bottom
            diff_h = target_h - current_h
            if diff_h > 0:
                if pad_force or diff_h <= pad_tolerance:
                    add_top, add_bottom = _split_padding(diff_h, center_pad)
                    pad_top += add_top
                    pad_bottom += add_bottom
                else:
                    logger.debug(
                        "Skipping vertical padding (%s px) for width=%s due to tolerance",
                        diff_h,
                        plan.get("width"),
                    )

        if canvas_width is not None and pad_enabled:
            current_w = scaled_w + pad_left + pad_right
            diff_w = canvas_width - current_w
            if diff_w > 0:
                if pad_force or diff_w <= pad_tolerance:
                    add_left, add_right = _split_padding(diff_w, center_pad)
                    pad_left += add_left
                    pad_right += add_right
                else:
                    logger.debug(
                        "Skipping horizontal padding (%s px) for width=%s due to tolerance",
                        diff_w,
                        plan.get("width"),
                    )

        pad_left, pad_top, pad_right, pad_bottom = _align_padding_mod(
            scaled_w,
            scaled_h,
            pad_left,
            pad_top,
            pad_right,
            pad_bottom,
            cfg.mod_crop,
            center_pad,
        )

        plan["pad"] = (pad_left, pad_top, pad_right, pad_bottom)
        plan["final"] = (
            scaled_w + pad_left + pad_right,
            scaled_h + pad_top + pad_bottom,
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
    pad: Tuple[int, int, int, int],
    path: Path,
    cfg: ScreenshotConfig,
    label: str,
    requested_frame: int,
    selection_label: str | None = None,
    *,
    overlay_text: Optional[str] = None,
    overlay_state: Optional[Dict[str, str]] = None,
    strict_overlay: bool = False,
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

        pad_left, pad_top, pad_right, pad_bottom = pad
        if pad_left or pad_top or pad_right or pad_bottom:
            std_ns = getattr(core, "std", None)
            add_borders = getattr(std_ns, "AddBorders", None) if std_ns is not None else None
            if not callable(add_borders):
                raise ScreenshotWriterError("VapourSynth std.AddBorders is unavailable")
            work = add_borders(
                work,
                left=max(0, pad_left),
                right=max(0, pad_right),
                top=max(0, pad_top),
                bottom=max(0, pad_bottom),
            )
    except Exception as exc:
        raise ScreenshotWriterError(f"Failed to prepare frame {frame_idx}: {exc}") from exc

    render_clip = work
    if cfg.add_frame_info:
        render_clip = _apply_frame_info_overlay(core, render_clip, label, requested_frame, selection_label)

    overlay_state = overlay_state or {}
    render_clip = _apply_overlay_text(
        core,
        render_clip,
        overlay_text,
        strict=strict_overlay,
        state=overlay_state,
        file_label=label,
    )

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


def _escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("=", "\\=")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("'", "\\'")
        .replace("\n", "\\\n")
    )


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
    pad: Tuple[int, int, int, int],
    path: Path,
    cfg: ScreenshotConfig,
    width: int,
    height: int,
    selection_label: str | None,
    *,
    overlay_text: Optional[str] = None,
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
    pad_left, pad_top, pad_right, pad_bottom = pad
    final_w = max(1, scaled[0] + pad_left + pad_right)
    final_h = max(1, scaled[1] + pad_top + pad_bottom)
    if pad_left or pad_top or pad_right or pad_bottom:
        filters.append(
            "pad={w}:{h}:{x}:{y}".format(
                w=final_w,
                h=final_h,
                x=max(0, pad_left),
                y=max(0, pad_top),
            )
        )
    if cfg.add_frame_info:
        text_lines = [f"Frame\\ {int(frame_idx)}"]
        if selection_label:
            text_lines.append(f"Content Type\\: {selection_label}")
        text = "\\\\n".join(text_lines)
        drawtext = (
            "drawtext=text={text}:fontcolor=white:borderw=2:bordercolor=black:"
            "box=0:shadowx=1:shadowy=1:shadowcolor=black:x=10:y=10"
        ).format(text=_escape_drawtext(text))
        filters.append(drawtext)
    if overlay_text:
        overlay_cmd = (
            "drawtext=text={text}:fontcolor=white:borderw=2:bordercolor=black:"
            "box=0:shadowx=1:shadowy=1:shadowcolor=black:x=10:y=80"
        ).format(text=_escape_drawtext(overlay_text))
        filters.append(overlay_cmd)

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
    color_cfg: ColorConfig,
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

    processed_results: List[vs_core.ClipProcessResult] = []
    overlay_states: List[Dict[str, str]] = []

    for clip, file_path in zip(clips, files):
        result = vs_core.process_clip_for_screenshot(
            clip,
            file_path,
            color_cfg,
            enable_overlay=True,
            enable_verification=True,
            logger_override=logger,
        )
        processed_results.append(result)
        overlay_states.append({})
        if result.verification is not None:
            logger.info(
                "[VERIFY] %s frame=%d avg=%.4f max=%.4f",
                file_path,
                result.verification.frame,
                result.verification.average,
                result.verification.maximum,
            )

    geometry = _plan_geometry([result.clip for result in processed_results], cfg)

    for clip_index, (result, file_path, meta, plan, trim_start) in enumerate(
        zip(processed_results, files, metadata, geometry, trim_offsets)
    ):
        if frame_labels:
            logger.debug('frame_labels keys: %s', list(frame_labels.keys()))
        crop = plan["crop"]  # type: ignore[assignment]
        scaled = plan["scaled"]  # type: ignore[assignment]
        pad = plan.get("pad", (0, 0, 0, 0))
        width = int(plan["width"])
        height = int(plan["height"])
        trim_start = int(trim_start)
        raw_label, safe_label = _derive_labels(file_path, meta)

        overlay_state = overlay_states[clip_index]
        overlay_text = result.overlay_text

        for frame in frames:
            frame_idx = int(frame)
            selection_label = frame_labels.get(frame_idx) if frame_labels else None
            if selection_label is not None:
                logger.debug('Selection label for frame %s: %s', frame_idx, selection_label)
            actual_idx, was_clamped = _clamp_frame_index(result.clip, frame_idx)
            if was_clamped:
                logger.debug(
                    "Frame %s exceeds available frames (%s) in %s; using %s",
                    frame_idx,
                    getattr(result.clip, 'num_frames', 'unknown'),
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
                    if overlay_text and overlay_state.get("overlay_status") != "ok":
                        logger.info("[OVERLAY] %s applied (ffmpeg)", file_path)
                        overlay_state["overlay_status"] = "ok"
                    _save_frame_with_ffmpeg(
                        file_path,
                        resolved_frame,
                        crop,
                        scaled,
                        pad,
                        target_path,
                        cfg,
                        width,
                        height,
                        selection_label,
                        overlay_text=overlay_text,
                    )
                else:
                    _save_frame_with_fpng(
                        result.clip,
                        actual_idx,
                        crop,
                        scaled,
                        pad,
                        target_path,
                        cfg,
                        raw_label,
                        frame_idx,
                        selection_label,
                        overlay_text=overlay_text,
                        overlay_state=overlay_state,
                        strict_overlay=bool(getattr(color_cfg, "strict", False)),
                    )
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
