from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Never

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFont

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


def test_overlay_supports_grayscale_images() -> None:
    image = Image.new("L", (400, 200), color=128)
    before = image.tobytes()

    result = apply_overlay(image, _config(OverlayMode.MINIMAL), RenderedFrameFacts(12, "I"))

    assert result is image
    assert result.mode == "L"
    assert result.tobytes() != before


def test_minimal_uses_outlined_text_without_background() -> None:
    background = (100, 120, 140)
    image = Image.new("RGB", (400, 200), color=background)
    before = image.copy()

    result = apply_overlay(image, _config(OverlayMode.MINIMAL), RenderedFrameFacts(12, "I"))

    assert result is image
    assert result.size == image.size
    assert ImageChops.difference(before, result).getbbox() is not None
    assert result.getpixel((5, 40)) == background

    colors = result.getcolors(maxcolors=result.width * result.height)
    assert colors is not None
    rendered_colors = {color for _, color in colors}
    assert (255, 255, 255) in rendered_colors
    assert (0, 0, 0) in rendered_colors


def test_font_falls_back_from_missing_configured_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_font = ImageFont.load_default(size=24)
    attempts: list[str] = []

    def _fake_truetype(path: str, _size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        attempts.append(path)
        if path == "missing.ttf":
            raise OSError("font unavailable")
        return fallback_font

    monkeypatch.setattr(ImageFont, "truetype", _fake_truetype)
    config = replace(_config(OverlayMode.MINIMAL), font_path=Path("missing.ttf"))

    apply_overlay(Image.new("RGB", (400, 200)), config, RenderedFrameFacts(12, "I"))

    assert attempts[0] == "missing.ttf"
    assert Path(attempts[1]).name == "Inter-Regular.ttf"


def test_unsupported_generated_punctuation_falls_back_to_readable_ascii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_font = ImageFont.load_default(size=24)

    def _raise_external_font(
        path: object,
        *_args: object,
        **_kwargs: object,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if isinstance(path, str):
            raise OSError("font unavailable")
        return fallback_font

    monkeypatch.setattr(ImageFont, "truetype", _raise_external_font)
    image = Image.new("RGB", (400, 200), color=(100, 120, 140))

    result = apply_overlay(image, _config(OverlayMode.MINIMAL), RenderedFrameFacts(12, "I"))

    expected = Image.new("RGB", image.size, color=(100, 120, 140))
    ImageDraw.Draw(expected).multiline_text(
        (10, 10),
        "Source\nFrame 12 | I-frame | 1.00 GiB",
        font=fallback_font,
        fill=(255, 255, 255),
        stroke_width=2,
        stroke_fill=(0, 0, 0),
    )
    assert ImageChops.difference(expected, result).getbbox() is None


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
