from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Never

import pytest
from PIL import Image, ImageDraw, ImageFont

from frame_compare.config.schema_enums import OverlayMode
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import OverlayConfig
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)


def _config(mode: OverlayMode) -> OverlayConfig:
    return OverlayConfig(
        mode=mode,
        label="Source",
        comparison_frame=12,
        source_frame=12,
        source_total_frames=100,
        include_frame_number=True,
        selection_label=None,
        file_size_bytes=1024**3,
        source_resolution=(1920, 1080),
        signal=SourceSignalFacts(is_hdr=False),
        presentation_state=PresentationState.SDR,
        tonemap_settings=None,
        geometry=RenderedGeometryFacts(
            source_size=(1920, 1080),
            active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
            cropped_size=(1920, 1080),
            scaled_size=(1920, 1080),
            final_canvas_size=(1920, 1080),
            is_noop=True,
        ),
        font_path=None,
    )


def test_none_mode_is_a_true_noop() -> None:
    image = Image.new("RGB", (100, 100), color=(1, 2, 3))
    before = image.tobytes()
    result = apply_overlay(image, _config(OverlayMode.NONE), RenderedFrameFacts(12, "I"))
    assert result is image
    assert result.tobytes() == before


def test_minimal_uses_outlined_text_without_background(monkeypatch: pytest.MonkeyPatch) -> None:
    font = ImageFont.load_default(size=24)
    monkeypatch.setattr("frame_compare.render.overlay._load_font", lambda _config: font)
    monkeypatch.setattr("frame_compare.render.overlay._display_text", lambda text, _font: text)
    draw_calls: list[dict[str, object]] = []
    original_multiline_text = ImageDraw.ImageDraw.multiline_text

    def _record_multiline_text(
        self: ImageDraw.ImageDraw,
        xy: tuple[int, int],
        text: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        draw_calls.append({"xy": xy, "text": text, **kwargs})
        original_multiline_text(self, xy, text, *args, **kwargs)  # type: ignore[arg-type]

    def _reject_background(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("legacy overlay style must not draw a background panel")

    monkeypatch.setattr(ImageDraw.ImageDraw, "multiline_text", _record_multiline_text)
    monkeypatch.setattr(ImageDraw.ImageDraw, "rounded_rectangle", _reject_background)
    image = Image.new("RGB", (400, 200), color=(100, 120, 140))
    before = image.tobytes()

    result = apply_overlay(image, _config(OverlayMode.MINIMAL), RenderedFrameFacts(12, "I"))

    assert result is image
    assert result.size == image.size
    assert result.tobytes() != before
    assert draw_calls == [
        {
            "xy": (10, 10),
            "text": "Source\nFrame 12 • I-frame • 1.00 GiB",
            "font": font,
            "fill": (255, 255, 255),
            "stroke_width": 2,
            "stroke_fill": (0, 0, 0),
        }
    ]


def test_font_falls_back_from_missing_configured_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_font = ImageFont.load_default(size=24)
    attempts: list[str] = []

    def _load_font(path: str, _size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        attempts.append(path)
        if path == "missing.ttf":
            raise OSError("font unavailable")
        return fallback_font

    monkeypatch.setattr(ImageFont, "truetype", _load_font)
    config = replace(_config(OverlayMode.MINIMAL), font_path=Path("missing.ttf"))

    apply_overlay(Image.new("RGB", (400, 200)), config, RenderedFrameFacts(12, "I"))

    assert attempts[:2] == ["missing.ttf", "segoeui.ttf"]


def test_missing_unicode_glyphs_fall_back_to_readable_ascii() -> None:
    class MissingGlyphFont:
        def getbbox(self, text: str) -> tuple[int, int, int, int]:
            return (0, 0, 10, 10) if not text.isascii() else (0, 0, 5, 5)

        def getlength(self, text: str) -> float:
            return 10.0 if not text.isascii() else 5.0

    from frame_compare.render.overlay import _display_text

    assert _display_text("A • B → 3×2 – done", MissingGlyphFont()) == "A | B -> 3x2 - done"  # type: ignore[arg-type]


def test_default_font_fallback_uses_configured_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_font = ImageFont.load_default(size=24)
    observed_sizes: list[int | None] = []

    def _raise_missing_font(*_args: object, **_kwargs: object) -> Never:
        raise OSError("font unavailable")

    def _load_default(*, size: int | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        observed_sizes.append(size)
        return fallback_font

    monkeypatch.setattr(ImageFont, "truetype", _raise_missing_font)
    monkeypatch.setattr(ImageFont, "load_default", _load_default)

    apply_overlay(
        Image.new("RGB", (400, 200), color=(100, 120, 140)),
        _config(OverlayMode.MINIMAL),
        RenderedFrameFacts(12, "I"),
    )

    assert observed_sizes == [24]


def test_overlay_rejects_mismatched_frame_facts() -> None:
    image = Image.new("RGB", (100, 100))
    with pytest.raises(ValueError, match="do not match"):
        apply_overlay(image, _config(OverlayMode.STANDARD), RenderedFrameFacts(13, "I"))
