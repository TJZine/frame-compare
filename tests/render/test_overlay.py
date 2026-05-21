import numpy as np
import pytest
from PIL import Image, ImageDraw

from frame_compare.render.overlay import apply_overlay
from frame_compare.render.overlay_text import (
    compose_frame_info_lines,
    compose_overlay_text_lines,
)
from frame_compare.render.types import OverlayConfig, OverlayMode


@pytest.fixture
def captured_draw_calls(monkeypatch):
    """
    Monkeypatch ImageDraw.multiline_text and ImageDraw.rectangle to capture calls.
    """
    calls: dict[str, list[object]] = {"multiline_text": [], "rectangle": [], "text": []}

    def mock_multiline_text(self, xy, text, *args, **kwargs):
        calls["multiline_text"].append((xy, text, kwargs))
        return None

    def mock_multiline_textbbox(self, xy, text, *args, **kwargs):
        lines = str(text).splitlines() if text else [""]
        height = len(lines) * 20
        x, y = xy
        return (x, y, x + 200, y + height)

    def mock_rectangle(self, xy, *args, **kwargs):
        calls["rectangle"].append(xy)
        return None

    def mock_text(self, xy, text, *args, **kwargs):
        calls["text"].append((xy, text, kwargs))
        raise AssertionError("apply_overlay must use multiline_text (not text)")

    monkeypatch.setattr(ImageDraw.ImageDraw, "multiline_text", mock_multiline_text)
    monkeypatch.setattr(ImageDraw.ImageDraw, "multiline_textbbox", mock_multiline_textbbox)
    monkeypatch.setattr(ImageDraw.ImageDraw, "rectangle", mock_rectangle)
    monkeypatch.setattr(ImageDraw.ImageDraw, "text", mock_text)

    return calls


def test_apply_overlay_minimal_mode(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.MINIMAL,
        label="Source",
        frame_number=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert captured_draw_calls["rectangle"] == []
    assert len(captured_draw_calls["multiline_text"]) == 1

    xy, text, kwargs = captured_draw_calls["multiline_text"][0]
    assert xy == (10, 10)
    assert text == "Source"
    assert kwargs["stroke_width"] == 2
    assert kwargs["stroke_fill"] == (0, 0, 0, 255)


def test_apply_overlay_none_mode_is_noop(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.NONE,
        label="NoOverlay",
        frame_number=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100), color=(1, 2, 3))
    before = img.tobytes()

    result = apply_overlay(img, config)

    assert result.mode == img.mode
    assert result.size == img.size
    assert result.tobytes() == before
    assert captured_draw_calls["multiline_text"] == []
    assert captured_draw_calls["rectangle"] == []
    assert captured_draw_calls["text"] == []


def test_apply_overlay_standard_mode(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Ref",
        frame_number=100,
        display_frame_number=12,
        num_frames=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert captured_draw_calls["rectangle"] == []
    assert len(captured_draw_calls["multiline_text"]) == 2

    (xy1, text1, kwargs1) = captured_draw_calls["multiline_text"][0]
    (xy2, text2, kwargs2) = captured_draw_calls["multiline_text"][1]

    assert xy1 == (10, 10)
    assert text1 == "\n".join(
        compose_frame_info_lines(
            mode=OverlayMode.STANDARD,
            label="Ref",
            display_frame_number=12,
            num_frames=100,
            picture_type=None,
            selection_label=None,
        )
    )
    assert kwargs1["stroke_width"] == 2
    assert kwargs1["stroke_fill"] == (0, 0, 0, 255)

    expected_frame_info_lines = text1.splitlines()
    expected_frame_info_height = len(expected_frame_info_lines) * 20
    assert xy2 == (10, 10 + expected_frame_info_height + 10)
    assert text2 == "\n".join(
        compose_overlay_text_lines(
            mode=OverlayMode.STANDARD,
            base_text=None,
            width=1920,
            height=1080,
            selection_type=None,
            diagnostic_lines=[],
        )
    )
    assert kwargs2["stroke_width"] == 2
    assert kwargs2["stroke_fill"] == (0, 0, 0, 255)


def test_apply_overlay_standard_uses_fallback_details_y_when_bbox_fails(monkeypatch):
    calls: list[tuple[tuple[int, int], str]] = []

    def mock_multiline_text(self, xy, text, *args, **kwargs):
        calls.append((xy, text))
        return None

    def mock_multiline_textbbox(self, xy, text, *args, **kwargs):
        raise RuntimeError("bbox unavailable")

    monkeypatch.setattr(ImageDraw.ImageDraw, "multiline_text", mock_multiline_text)
    monkeypatch.setattr(ImageDraw.ImageDraw, "multiline_textbbox", mock_multiline_textbbox)

    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Ref",
        frame_number=100,
        display_frame_number=12,
        num_frames=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert len(calls) == 2
    assert calls[0][0] == (10, 10)
    assert calls[1][0] == (10, 140)


def test_apply_overlay_standard_includes_selection_label_when_present(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Ref",
        frame_number=100,
        display_frame_number=12,
        num_frames=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
        selection_label="Dark",
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert len(captured_draw_calls["multiline_text"]) == 2
    _, text1, _ = captured_draw_calls["multiline_text"][0]
    assert text1 == "\n".join(
        compose_frame_info_lines(
            mode=OverlayMode.STANDARD,
            label="Ref",
            display_frame_number=12,
            num_frames=100,
            picture_type=None,
            selection_label="Dark",
        )
    )

    _, text2, _ = captured_draw_calls["multiline_text"][1]
    assert text2 == "\n".join(
        compose_overlay_text_lines(
            mode=OverlayMode.STANDARD,
            base_text=None,
            width=1920,
            height=1080,
            selection_type="Dark",
            diagnostic_lines=[],
        )
    )


def test_apply_overlay_diagnostic_with_hdr(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.DIAGNOSTIC,
        label="Encode",
        frame_number=200,
        display_frame_number=20,
        num_frames=100,
        resolution=(3840, 2160),
        hdr_info="PQ / BT.2020",
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert len(captured_draw_calls["multiline_text"]) == 2
    _, text1, _ = captured_draw_calls["multiline_text"][0]
    assert text1 == "\n".join(
        compose_frame_info_lines(
            mode=OverlayMode.DIAGNOSTIC,
            label="Encode",
            display_frame_number=20,
            num_frames=100,
            picture_type=None,
            selection_label=None,
        )
    )

    _, text2, _ = captured_draw_calls["multiline_text"][1]
    assert text2 == "\n".join(
        compose_overlay_text_lines(
            mode=OverlayMode.DIAGNOSTIC,
            base_text=None,
            width=3840,
            height=2160,
            selection_type=None,
            diagnostic_lines=["PQ / BT.2020"],
        )
    )


def test_apply_overlay_diagnostic_sdr(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.DIAGNOSTIC,
        label="SDR_Test",
        frame_number=50,
        display_frame_number=5,
        num_frames=10,
        resolution=(1280, 720),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert len(captured_draw_calls["multiline_text"]) == 2
    _, text2, _ = captured_draw_calls["multiline_text"][1]
    assert text2 == "\n".join(
        compose_overlay_text_lines(
            mode=OverlayMode.DIAGNOSTIC,
            base_text=None,
            width=1280,
            height=720,
            selection_type=None,
            diagnostic_lines=[],
        )
    )


def test_apply_overlay_returns_pil_image():
    config = OverlayConfig(
        mode=OverlayMode.MINIMAL,
        label="Test",
        frame_number=1,
        resolution=(100, 100),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))
    result = apply_overlay(img, config)
    assert isinstance(result, Image.Image)


def test_apply_overlay_accepts_numpy():
    config = OverlayConfig(
        mode=OverlayMode.MINIMAL,
        label="Test",
        frame_number=1,
        resolution=(100, 100),
        hdr_info=None,
        font_path=None,
    )
    # Create a black image
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    result = apply_overlay(arr, config)
    assert isinstance(result, Image.Image)


def test_apply_overlay_none_image_raises():
    config = OverlayConfig(
        mode=OverlayMode.MINIMAL,
        label="Test",
        frame_number=1,
        resolution=(100, 100),
        hdr_info=None,
        font_path=None,
    )
    with pytest.raises(ValueError, match="image must not be None"):
        apply_overlay(None, config)  # type: ignore


def test_apply_overlay_invalid_mode_raises():
    # Bypass type checking to test runtime validation
    config = OverlayConfig(
        mode="bogus",  # type: ignore
        label="X",
        frame_number=0,
        resolution=(100, 100),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))
    with pytest.raises(ValueError, match="invalid overlay mode"):
        apply_overlay(img, config)
