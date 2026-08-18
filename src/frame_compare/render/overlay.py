"""Draw supplied overlay presentation facts onto rendered images."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from frame_compare.render.overlay_text import compose_overlay_text_lines
from frame_compare.render.types import OverlayConfig
from frame_compare.utils.media_facts import RenderedFrameFacts


def apply_overlay(
    image: Image.Image,
    config: OverlayConfig,
    frame_facts: RenderedFrameFacts,
) -> Image.Image:
    """Draw a compositional overlay without collecting or inferring metadata."""
    lines = compose_overlay_text_lines(config, frame_facts)
    if not lines:
        return image
    font = _load_font(config)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y = config.origin or (10, 10)
    spacing = max(4, config.font_size // 5)
    text = "\n".join(lines)
    bounds = draw.multiline_textbbox((x, y), text, font=font, spacing=spacing)
    padding = max(4, config.font_size // 4)
    draw.rounded_rectangle(
        (
            bounds[0] - padding,
            bounds[1] - padding,
            bounds[2] + padding,
            bounds[3] + padding,
        ),
        radius=padding,
        fill=(0, 0, 0, 180),
    )
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=(255, 255, 255),
        spacing=spacing,
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )

    composited = Image.alpha_composite(image.convert("RGBA"), overlay)
    if image.mode != "RGBA":
        composited = composited.convert(image.mode)
    image.paste(composited)
    return image


def _load_font(config: OverlayConfig) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if config.font_path is not None:
        return ImageFont.truetype(str(config.font_path), config.font_size)
    try:
        return ImageFont.truetype("DejaVuSans.ttf", config.font_size)
    except OSError:
        return ImageFont.load_default(size=config.font_size)


__all__ = ["apply_overlay"]
