from __future__ import annotations

from typing import Never

import pytest
from PIL import Image, ImageFont

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


def test_minimal_draws_translucent_background(monkeypatch: pytest.MonkeyPatch) -> None:
    font = ImageFont.load_default(size=24)
    monkeypatch.setattr("frame_compare.render.overlay._load_font", lambda _config: font)
    image = Image.new("RGB", (400, 200), color=(100, 120, 140))
    before = image.tobytes()

    result = apply_overlay(image, _config(OverlayMode.MINIMAL), RenderedFrameFacts(12, "I"))

    assert result is image
    assert result.size == image.size
    assert result.tobytes() != before
    assert result.getpixel((20, 12)) == (29, 35, 41)


def test_default_font_fallback_uses_configured_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_font = ImageFont.load_default(size=24)
    observed_sizes: list[int | None] = []

    def _raise_missing_font(*_args: object, **_kwargs: object) -> Never:
        raise OSError("font unavailable")

    def _load_default(*, size: int | None = None) -> ImageFont.ImageFont:
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
