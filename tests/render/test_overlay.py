import numpy as np
import pytest
from PIL import Image, ImageDraw

from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import OverlayConfig, OverlayMode

# Mock calculate_overlay_position to return fixed coordinates
# This ensures we don't depend on geometry logic implementation details here
MOCK_POS = (100, 200)


@pytest.fixture
def mock_geometry(monkeypatch):
    monkeypatch.setattr(
        "frame_compare.render.overlay.calculate_overlay_position",
        lambda *args, **kwargs: MOCK_POS,
    )


@pytest.fixture
def captured_draw_calls(monkeypatch):
    """
    Monkeypatch ImageDraw.text and ImageDraw.rectangle to capture calls.
    Returns a list of calls.
    """
    calls = {"text": [], "rectangle": []}

    original_text = ImageDraw.ImageDraw.text
    original_rectangle = ImageDraw.ImageDraw.rectangle

    def mock_text(self, xy, text, *args, **kwargs):
        calls["text"].append((xy, text))
        return original_text(self, xy, text, *args, **kwargs)

    def mock_rectangle(self, xy, *args, **kwargs):
        calls["rectangle"].append(xy)
        return original_rectangle(self, xy, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", mock_text)
    monkeypatch.setattr(ImageDraw.ImageDraw, "rectangle", mock_rectangle)

    return calls


def test_apply_overlay_minimal_mode(mock_geometry, captured_draw_calls):
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

    texts = [call[1] for call in captured_draw_calls["text"]]
    assert any("Source" in t for t in texts)
    # Ensure minimal mode doesn't contain extra info
    assert not any("|" in t for t in texts)


def test_apply_overlay_none_mode_is_noop(mock_geometry, captured_draw_calls):
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
    assert captured_draw_calls["text"] == []
    assert captured_draw_calls["rectangle"] == []


def test_apply_overlay_standard_mode(mock_geometry, captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Ref",
        frame_number=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    texts = [call[1] for call in captured_draw_calls["text"]]
    expected = "Ref | Frame 00100 | 1920x1080"
    assert any(t == expected for t in texts)


def test_apply_overlay_diagnostic_with_hdr(mock_geometry, captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.DIAGNOSTIC,
        label="Encode",
        frame_number=200,
        resolution=(3840, 2160),
        hdr_info="PQ / BT.2020",
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    texts = [call[1] for call in captured_draw_calls["text"]]
    assert any("PQ / BT.2020" in t for t in texts)


def test_apply_overlay_diagnostic_sdr(mock_geometry, captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.DIAGNOSTIC,
        label="SDR_Test",
        frame_number=50,
        resolution=(1280, 720),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    texts = [call[1] for call in captured_draw_calls["text"]]
    assert any("SDR" in t for t in texts)


def test_apply_overlay_returns_pil_image(mock_geometry):
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


def test_apply_overlay_accepts_numpy(mock_geometry):
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


def test_apply_overlay_calls_position_function(monkeypatch):
    # We want to verify arguments passed to calculate_overlay_position
    captured_args = []

    def mock_calc(image_size, overlay_size, position):
        captured_args.append((image_size, overlay_size, position))
        return (0, 0)

    monkeypatch.setattr(
        "frame_compare.render.overlay.calculate_overlay_position",
        mock_calc,
    )

    config = OverlayConfig(
        mode=OverlayMode.MINIMAL,
        label="PosTest",
        frame_number=1,
        resolution=(100, 100),
        hdr_info=None,
        font_path=None,
        position="bottom-right",
    )
    img = Image.new("RGB", (100, 100))
    apply_overlay(img, config)

    assert len(captured_args) == 1
    assert captured_args[0][2] == "bottom-right"


def test_apply_overlay_draws_rectangle(mock_geometry, captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.MINIMAL,
        label="RectTest",
        frame_number=1,
        resolution=(100, 100),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))
    apply_overlay(img, config)

    assert len(captured_draw_calls["rectangle"]) >= 1
