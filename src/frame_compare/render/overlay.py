"""Text overlay rendering for screenshots."""

import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from frame_compare.render.overlay_text import (
    compose_frame_info_lines,
    compose_overlay_text_lines,
)
from frame_compare.render.types import (
    OverlayConfig,
    OverlayDiagnosticMetadata,
    OverlayDolbyVisionMetadata,
    OverlayFrameMeasurement,
    OverlayMode,
)

type Font = ImageFont.ImageFont | ImageFont.FreeTypeFont
type ImageInput = Image.Image | np.ndarray | None

_LABEL_POSITION = (10, 10)
_DEFAULT_DETAILS_Y = 140
_DEFAULT_DETAILS_OFFSET_Y = _DEFAULT_DETAILS_Y - _LABEL_POSITION[1]
_FILL = (255, 255, 255, 255)
_STROKE_FILL = (0, 0, 0, 255)
_STROKE_WIDTH = 2
_MASTERING_DISPLAY_PATTERN = re.compile(r"L\(([-+]?\d+(?:\.\d+)?),([-+]?\d+(?:\.\d+)?)\)")
_DEFAULT_FONT_CANDIDATES = (
    "segoeui.ttf",
    "arial.ttf",
    "tahoma.ttf",
    "calibri.ttf",
    "verdana.ttf",
)


def _label_position(config: OverlayConfig) -> tuple[int, int]:
    return config.origin if config.origin is not None else _LABEL_POSITION


def _resolve_mode(mode: object) -> OverlayMode:
    if isinstance(mode, OverlayMode):
        return mode
    raise ValueError("invalid overlay mode")


def _normalize_image(image: ImageInput) -> Image.Image | np.ndarray:
    if image is None:
        raise ValueError("image must not be None")
    return image


def _to_pil_image(image: Image.Image | np.ndarray) -> Image.Image:
    return Image.fromarray(image) if isinstance(image, np.ndarray) else image


def _load_font(config: OverlayConfig) -> Font:
    if config.font_path:
        try:
            return ImageFont.truetype(str(config.font_path), size=config.font_size)
        except OSError:
            pass
    for font_name in _DEFAULT_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(font_name, size=config.font_size)
        except OSError:
            continue
    return ImageFont.load_default(size=config.font_size)


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: Font,
) -> None:
    draw.multiline_text(
        position,
        text,
        font=font,
        fill=_FILL,
        stroke_width=_STROKE_WIDTH,
        stroke_fill=_STROKE_FILL,
    )


def _font_line_gap(font: Font) -> int:
    try:
        bbox = font.getbbox("Ag", stroke_width=_STROKE_WIDTH)
    except TypeError:
        try:
            bbox = font.getbbox("Ag")
        except (AttributeError, OSError, ValueError, RuntimeError):
            return 24
    except (AttributeError, OSError, ValueError, RuntimeError):
        return 24
    return max(1, int(bbox[3] - bbox[1]))


def _resolve_details_y(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: Font,
) -> int:
    try:
        bbox = draw.multiline_textbbox(
            position,
            text,
            font=font,
            stroke_width=_STROKE_WIDTH,
        )
    except (OSError, ValueError, RuntimeError):
        return position[1] + _DEFAULT_DETAILS_OFFSET_Y
    return int(bbox[3]) + _font_line_gap(font)


def _resolve_display_frame_number(config: OverlayConfig) -> int:
    if config.display_frame_number is not None:
        return config.display_frame_number
    return config.frame_number


def _resolve_burn_in_label(config: OverlayConfig) -> str:
    if config.burn_in_label is not None:
        return config.burn_in_label
    return config.label


def _resolve_selection_label(config: OverlayConfig) -> str | None:
    if config.selection_detail is not None:
        return config.selection_detail.label
    return config.selection_label


def _format_nits(value: float | int | None) -> str | None:
    if value is None:
        return None
    numeric = float(value)
    if abs(numeric - round(numeric)) < 1e-3:
        return f"{round(numeric):.0f}"
    return f"{numeric:.1f}"


def _format_luminance_value(value: float) -> str:
    if value < 1.0:
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text or "0"
    return f"{value:.1f}"


def _mastering_display_luminance(
    mastering_display: str | None,
) -> tuple[float | None, float | None]:
    if mastering_display is None:
        return None, None
    match = _MASTERING_DISPLAY_PATTERN.search(mastering_display)
    if match is None:
        return None, None
    max_value = float(match.group(1))
    min_value = float(match.group(2))
    if max_value > 10000 or min_value > 10:
        max_value /= 10000.0
        min_value /= 10000.0
    return min_value, max_value


def _format_mastering_display_line(metadata: OverlayDiagnosticMetadata) -> str | None:
    min_value, max_value = _mastering_display_luminance(metadata.mastering_display)
    if min_value is None or max_value is None:
        return None
    return (
        f"MDL: min: {_format_luminance_value(min_value)} cd/m², "
        f"max: {_format_luminance_value(max_value)} cd/m²"
    )


def _format_hdr_line(metadata: OverlayDiagnosticMetadata) -> str | None:
    segments: list[str] = []
    max_cll = _format_nits(metadata.max_cll)
    max_fall = _format_nits(metadata.max_fall)
    if max_cll:
        segments.append(f"MaxCLL {max_cll}")
    if max_fall:
        segments.append(f"MaxFALL {max_fall}")
    if not segments:
        return None
    return f"HDR: {' / '.join(segments)}"


def _format_dolby_vision_line(metadata: OverlayDolbyVisionMetadata) -> str | None:
    parts = ["DoVi: on"]
    l2_target = _format_nits(metadata.l2_target_nits)
    if l2_target:
        parts.append(f"(Target: {l2_target}nits)")
    if metadata.block_index is not None and metadata.block_index >= 0:
        if metadata.block_total is not None and metadata.block_total > 0:
            parts.append(f"L2 {metadata.block_index}/{metadata.block_total}")
        else:
            parts.append(f"L2 block {metadata.block_index}")
    elif metadata.block_total is not None and metadata.block_total > 0:
        parts.append(f"L2 blocks={metadata.block_total}")
    target_nits = _format_nits(metadata.target_nits)
    if target_nits:
        parts.append(f"target {target_nits} nits")
    return " ".join(parts)


def _format_dolby_vision_l1_line(metadata: OverlayDolbyVisionMetadata) -> str | None:
    average = _format_nits(metadata.l1_average)
    maximum = _format_nits(metadata.l1_maximum)
    if maximum is None and average is None:
        return None
    values: list[str] = []
    if maximum is not None:
        values.append(f"{maximum}nits")
    if average is not None:
        values.append(f"{average}nits")
    descriptor = "MAX/AVG" if maximum is not None and average is not None else "MAX"
    if maximum is None and average is not None:
        descriptor = "AVG"
    return f"DV RPU Level 1 {descriptor}: {' / '.join(values)}"


def _format_dolby_vision_l5_line(metadata: OverlayDolbyVisionMetadata) -> str | None:
    if all(
        value in (None, 0)
        for value in (metadata.l5_left, metadata.l5_right, metadata.l5_top, metadata.l5_bottom)
    ):
        return None
    parts: list[str] = []
    if metadata.l5_left is not None:
        parts.append(f"L:{metadata.l5_left}")
    if metadata.l5_right is not None:
        parts.append(f"R:{metadata.l5_right}")
    if metadata.l5_top is not None:
        parts.append(f"T:{metadata.l5_top}")
    if metadata.l5_bottom is not None:
        parts.append(f"B:{metadata.l5_bottom}")
    if not parts:
        return None
    return f"DV L5 Active Area: {' '.join(parts)}"


def _format_dolby_vision_l6_line(metadata: OverlayDolbyVisionMetadata) -> str | None:
    max_cll = _format_nits(metadata.l6_max_cll)
    max_fall = _format_nits(metadata.l6_max_fall)
    parts: list[str] = []
    if max_cll:
        parts.append(f"MaxCLL {max_cll}")
    if max_fall:
        parts.append(f"MaxFALL {max_fall}")
    if not parts:
        return None
    return f"DV L6 Metadata: {' / '.join(parts)}"


def _format_range_line(metadata: OverlayDiagnosticMetadata) -> str | None:
    if metadata.color_range is None:
        return None
    text = metadata.color_range.strip()
    if not text:
        return None
    return f"Range: {text.capitalize()}"


def _format_measurement_line(measurement: OverlayFrameMeasurement) -> str:
    max_value = _format_nits(measurement.max_nits)
    avg_value = _format_nits(measurement.avg_nits)
    values: list[str] = []
    if max_value:
        values.append(f"{max_value}nits")
    if avg_value:
        values.append(f"{avg_value}nits")
    descriptor = "MAX/AVG" if max_value and avg_value else "MAX"
    if not max_value and avg_value:
        descriptor = "AVG"
    suffix = f" ({measurement.category})" if measurement.category else ""
    return f"Measurement {descriptor}: {' / '.join(values)}{suffix}"


def _compose_frame_info_text(config: OverlayConfig, mode: OverlayMode) -> str | None:
    frame_info_lines = compose_frame_info_lines(
        mode=mode,
        label=_resolve_burn_in_label(config),
        display_frame_number=_resolve_display_frame_number(config),
        num_frames=config.num_frames,
        picture_type=config.picture_type,
        selection_label=_resolve_selection_label(config),
        include_frame_number=config.include_frame_number,
    )
    if not frame_info_lines:
        return None
    return "\n".join(frame_info_lines)


def _diagnostic_lines(config: OverlayConfig, mode: OverlayMode) -> list[str]:
    if mode != OverlayMode.DIAGNOSTIC:
        return []
    lines: list[str] = []
    if config.hdr_info:
        lines.append(config.hdr_info)
    metadata = config.diagnostic_metadata
    if metadata is None:
        return lines
    for candidate in (
        _format_mastering_display_line(metadata),
        _format_hdr_line(metadata),
        _format_dolby_vision_line(metadata.dolby_vision)
        if metadata.dolby_vision is not None
        else None,
        _format_dolby_vision_l1_line(metadata.dolby_vision)
        if metadata.dolby_vision is not None
        else None,
        _format_dolby_vision_l5_line(metadata.dolby_vision)
        if metadata.dolby_vision is not None
        else None,
        _format_dolby_vision_l6_line(metadata.dolby_vision)
        if metadata.dolby_vision is not None
        else None,
        _format_range_line(metadata),
        _format_measurement_line(metadata.measurement)
        if metadata.measurement is not None
        else None,
    ):
        if candidate:
            lines.append(candidate)
    return lines


def _compose_overlay_text(config: OverlayConfig, mode: OverlayMode) -> str | None:
    width, height = config.resolution
    overlay_lines = compose_overlay_text_lines(
        mode=mode,
        base_text=config.base_text,
        width=width,
        height=height,
        selection_type=_resolve_selection_label(config),
        diagnostic_lines=_diagnostic_lines(config, mode),
        resolution_summary=config.resolution_summary,
    )
    if not overlay_lines:
        return None
    return "\n".join(overlay_lines)


def apply_overlay(
    image: Image.Image | np.ndarray | None,
    config: OverlayConfig,
) -> Image.Image:
    """
    Apply text overlay to image.

    Legacy-style behavior:
    - NONE: no-op (return image unchanged; numpy inputs are converted to PIL without drawing).
    - MINIMAL: label-only block at (10, 10).
    - STANDARD/DIAGNOSTIC: frame-info block at (10, 10) and overlay-text block below it.
    - No background box; outlined white text (black stroke) via multiline_text.

    Return value:
    - NONE preserves the input image mode (true no-op).
    - Other modes return an RGBA image.
    """
    normalized_image = _normalize_image(image)
    mode = _resolve_mode(config.mode)

    # No overlay drawn.
    if mode == OverlayMode.NONE:
        return _to_pil_image(normalized_image)

    pil_image = _to_pil_image(normalized_image)

    # Work on a copy and normalize to RGBA to support stroke/alpha consistently.
    canvas = pil_image.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    font = _load_font(config)
    label_position = _label_position(config)

    frame_info_text = _compose_frame_info_text(config, mode)
    details_y = _DEFAULT_DETAILS_Y
    if frame_info_text is not None:
        _draw_text_block(draw, label_position, frame_info_text, font)
        details_y = _resolve_details_y(draw, label_position, frame_info_text, font)

    if mode == OverlayMode.MINIMAL:
        return canvas

    overlay_text = _compose_overlay_text(config, mode)
    if overlay_text is not None:
        _draw_text_block(draw, (label_position[0], details_y), overlay_text, font)

    return canvas
