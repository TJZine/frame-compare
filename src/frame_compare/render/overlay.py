"""Text overlay rendering for screenshots."""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from frame_compare.render.overlay_text import (
    compose_frame_info_lines,
    compose_overlay_text_lines,
)
from frame_compare.render.types import OverlayConfig, OverlayMode

type Font = ImageFont.ImageFont | ImageFont.FreeTypeFont
type ImageInput = Image.Image | np.ndarray | None

_LABEL_POSITION = (10, 10)
_BLOCK_GAP_PX = 10
_DEFAULT_DETAILS_Y = 140
_FILL = (255, 255, 255, 255)
_STROKE_FILL = (0, 0, 0, 255)
_STROKE_WIDTH = 2


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
        return ImageFont.truetype(str(config.font_path), size=config.font_size)
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
        return _DEFAULT_DETAILS_Y
    return int(bbox[3]) + _BLOCK_GAP_PX


def _resolve_display_frame_number(config: OverlayConfig) -> int:
    if config.display_frame_number is not None:
        return config.display_frame_number
    return config.frame_number


def _compose_frame_info_text(config: OverlayConfig, mode: OverlayMode) -> str | None:
    frame_info_lines = compose_frame_info_lines(
        mode=mode,
        label=config.label,
        display_frame_number=_resolve_display_frame_number(config),
        num_frames=config.num_frames,
        picture_type=config.picture_type,
        selection_label=config.selection_label,
    )
    if not frame_info_lines:
        return None
    return "\n".join(frame_info_lines)


def _diagnostic_lines(config: OverlayConfig, mode: OverlayMode) -> list[str]:
    if mode == OverlayMode.DIAGNOSTIC and config.hdr_info:
        return [config.hdr_info]
    return []


def _compose_overlay_text(config: OverlayConfig, mode: OverlayMode) -> str | None:
    width, height = config.resolution
    overlay_lines = compose_overlay_text_lines(
        mode=mode,
        base_text=None,
        width=width,
        height=height,
        selection_type=config.selection_label,
        diagnostic_lines=_diagnostic_lines(config, mode),
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

    frame_info_text = _compose_frame_info_text(config, mode)
    details_y = _DEFAULT_DETAILS_Y
    if frame_info_text is not None:
        _draw_text_block(draw, _LABEL_POSITION, frame_info_text, font)
        details_y = _resolve_details_y(draw, _LABEL_POSITION, frame_info_text, font)

    if mode == OverlayMode.MINIMAL:
        return canvas

    overlay_text = _compose_overlay_text(config, mode)
    if overlay_text is not None:
        _draw_text_block(draw, (_LABEL_POSITION[0], details_y), overlay_text, font)

    return canvas
