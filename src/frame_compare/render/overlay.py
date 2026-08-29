"""Draw supplied overlay presentation facts onto rendered images."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from frame_compare.render.overlay_text import compose_overlay_text_lines
from frame_compare.render.types import OverlayConfig
from frame_compare.utils.media_facts import RenderedFrameFacts

type Font = ImageFont.ImageFont | ImageFont.FreeTypeFont

_FILL = (255, 255, 255)
_STROKE_FILL = (0, 0, 0)
_STROKE_WIDTH = 2
_ASCII_GLYPH_FALLBACKS = {"•": "|", "→": "->", "×": "x", "–": "-"}
_BUNDLED_FONT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Inter-Regular.ttf"
)
_DEFAULT_FONT_CANDIDATES = (
    "segoeui.ttf",
    "Arial.ttf",
    "arial.ttf",
    "Tahoma.ttf",
    "tahoma.ttf",
    "Calibri.ttf",
    "calibri.ttf",
    "Verdana.ttf",
    "verdana.ttf",
    "DejaVuSans.ttf",
)


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
    text = _display_text("\n".join(lines), font)
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=_FILL,
        stroke_width=_STROKE_WIDTH,
        stroke_fill=_STROKE_FILL,
    )
    composited = Image.alpha_composite(image.convert("RGBA"), overlay)
    if image.mode != "RGBA":
        composited = composited.convert(image.mode)
    image.paste(composited)
    return image


def _load_font(config: OverlayConfig) -> Font:
    if config.font_path is not None:
        try:
            return ImageFont.truetype(str(config.font_path), config.font_size)
        except OSError:
            pass
    try:
        return ImageFont.truetype(str(_BUNDLED_FONT_PATH), config.font_size)
    except OSError:
        pass
    for font_name in _DEFAULT_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(font_name, config.font_size)
        except OSError:
            continue
    return ImageFont.load_default(size=config.font_size)


def _display_text(text: str, font: Font) -> str:
    missing_glyph = (font.getbbox("\u0378"), font.getlength("\u0378"))
    replacements = {
        ord(glyph): fallback
        for glyph, fallback in _ASCII_GLYPH_FALLBACKS.items()
        if (font.getbbox(glyph), font.getlength(glyph)) == missing_glyph
    }
    return text.translate(replacements)


__all__ = ["apply_overlay"]
