"""Text overlay rendering for screenshots."""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from frame_compare.render.geometry import calculate_overlay_position
from frame_compare.render.types import OverlayConfig, OverlayMode


def apply_overlay(
    image: Image.Image | np.ndarray,
    config: OverlayConfig,
) -> Image.Image:
    """
    Apply text overlay to image.

    Algorithm:
    1. Convert input to PIL.Image.Image if numpy array is provided.
    2. Generate text string based on config.mode.
    3. Load font and measure text.
    4. Calculate overlay position.
    5. Draw semi-transparent background rectangle.
    6. Draw text with shadow then white foreground.
    """
    # Runtime check for None, even if types say no
    if image is None:  # type: ignore
        raise ValueError("image must not be None")

    # Runtime check for enum
    if not isinstance(config.mode, OverlayMode):  # type: ignore
        raise ValueError("invalid overlay mode")

    # No overlay drawn.
    if config.mode == OverlayMode.NONE:
        return Image.fromarray(image) if isinstance(image, np.ndarray) else image

    # 1. Convert input to PIL.Image.Image if numpy array
    pil_image = Image.fromarray(image) if isinstance(image, np.ndarray) else image

    # Ensure we are working on a copy to avoid modifying original
    # and ensure it's RGBA for transparency
    canvas = pil_image.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # 2. Generate text string
    if config.mode == OverlayMode.MINIMAL:
        text = f"{config.label}"
    elif config.mode == OverlayMode.STANDARD:
        w, h = config.resolution
        text = f"{config.label} | Frame {config.frame_number:05d} | {w}x{h}"
    else:  # DIAGNOSTIC
        w, h = config.resolution
        hdr = config.hdr_info or "SDR"
        text = f"{config.label} | Frame {config.frame_number:05d} | {w}x{h} | {hdr}"

    # 3. Load font
    font_size = config.font_size
    if config.font_path:
        try:
            font = ImageFont.truetype(str(config.font_path), size=font_size)
        except OSError:
            raise
    else:
        font = ImageFont.load_default(size=font_size)

    # Measure text
    # textbbox returns (left, top, right, bottom)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_width = right - left
    text_height = bottom - top

    # 4. Calculate overlay position
    _PADDING = 8
    overlay_width = int(text_width + (_PADDING * 2))
    overlay_height = int(text_height + (_PADDING * 2))

    x, y = calculate_overlay_position(
        image_size=pil_image.size,
        overlay_size=(overlay_width, overlay_height),
        position=config.position,
    )

    # 5. Draw semi-transparent background rectangle
    # RGBA: 0, 0, 0, 180
    rect_coords = (x, y, x + overlay_width, y + overlay_height)
    draw.rectangle(rect_coords, fill=(0, 0, 0, 180))

    # 6. Draw text with shadow (1px offset, black) then white foreground
    text_x = x + _PADDING
    text_y = y + _PADDING

    # Shadow
    draw.text((text_x + 1, text_y + 1), text, font=font, fill=(0, 0, 0))

    # Foreground
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))

    return canvas
