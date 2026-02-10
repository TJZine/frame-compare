"""Text overlay rendering for screenshots."""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from frame_compare.render.types import OverlayConfig, OverlayMode


def apply_overlay(
    image: Image.Image | np.ndarray,
    config: OverlayConfig,
) -> Image.Image:
    """
    Apply text overlay to image.

    Legacy-style behavior:
    - NONE: no-op (return image unchanged; numpy inputs are converted to PIL without drawing).
    - MINIMAL: label-only block at (10, 10).
    - STANDARD/DIAGNOSTIC: two blocks at (10, 10) and (10, 140).
    - No background box; outlined white text (black stroke) via multiline_text.
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

    # Work on a copy and normalize to RGBA to support stroke/alpha consistently.
    canvas = pil_image.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # 2. Load font
    font_size = config.font_size
    if config.font_path:
        try:
            font = ImageFont.truetype(str(config.font_path), size=font_size)
        except OSError:
            raise
    else:
        font = ImageFont.load_default(size=font_size)

    # 3. Draw legacy-style overlay blocks (outlined text, no background box).
    label_pos = (10, 10)
    details_pos = (10, 140)

    fill = (255, 255, 255, 255)
    stroke_fill = (0, 0, 0, 255)
    stroke_width = 2

    draw.multiline_text(
        label_pos,
        config.label,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    if config.mode == OverlayMode.MINIMAL:
        return canvas

    display_frame_number = (
        config.display_frame_number
        if config.display_frame_number is not None
        else config.frame_number
    )
    w, h = config.resolution
    details_lines = [f"Frame {display_frame_number:05d}", f"{w}x{h}"]
    if config.mode == OverlayMode.DIAGNOSTIC:
        details_lines.append(config.hdr_info or "SDR")

    draw.multiline_text(
        details_pos,
        "\n".join(details_lines),
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )

    return canvas
