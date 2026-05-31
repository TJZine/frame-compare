from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from frame_compare.render.overlay import apply_overlay
from frame_compare.render.overlay_text import (
    compose_frame_info_lines,
    compose_overlay_text_lines,
)
from frame_compare.render.types import (
    OverlayConfig,
    OverlayDiagnosticMetadata,
    OverlayDolbyVisionMetadata,
    OverlayFrameMeasurement,
    OverlayMode,
    OverlaySelectionDetail,
)


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


def test_apply_overlay_prefers_explicit_font_path(monkeypatch, captured_draw_calls) -> None:
    captured: list[tuple[str, int]] = []

    def mock_truetype(path: str, size: int):
        captured.append((path, size))
        return "configured-font"

    monkeypatch.setattr("frame_compare.render.overlay.ImageFont.truetype", mock_truetype)

    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Font",
        frame_number=1,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=Path("custom.ttf"),
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert captured == [("custom.ttf", 24)]
    assert captured_draw_calls["multiline_text"]


def test_apply_overlay_uses_first_available_system_font(monkeypatch, captured_draw_calls) -> None:
    attempts: list[tuple[str, int]] = []
    missing_fonts = {"segoeui.ttf", "arial.ttf"}

    def mock_truetype(path: str, size: int):
        attempts.append((path, size))
        if path in missing_fonts:
            raise OSError("missing font")
        return "system-font"

    def mock_load_default(*, size: int):
        raise AssertionError(f"load_default should not run when a system font is available: {size}")

    monkeypatch.setattr("frame_compare.render.overlay.ImageFont.truetype", mock_truetype)
    monkeypatch.setattr("frame_compare.render.overlay.ImageFont.load_default", mock_load_default)

    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Font",
        frame_number=1,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert attempts == [
        ("segoeui.ttf", 24),
        ("arial.ttf", 24),
        ("tahoma.ttf", 24),
    ]
    assert captured_draw_calls["multiline_text"]


def test_apply_overlay_falls_back_when_explicit_font_path_is_unavailable(
    monkeypatch, captured_draw_calls
) -> None:
    attempts: list[tuple[str, int]] = []

    def mock_truetype(path: str, size: int):
        attempts.append((path, size))
        if path == "missing.ttf":
            raise OSError("configured font missing")
        return "system-font"

    def mock_load_default(*, size: int):
        raise AssertionError(f"load_default should not run when a system font is available: {size}")

    monkeypatch.setattr("frame_compare.render.overlay.ImageFont.truetype", mock_truetype)
    monkeypatch.setattr("frame_compare.render.overlay.ImageFont.load_default", mock_load_default)

    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Font",
        frame_number=1,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=Path("missing.ttf"),
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert attempts == [("missing.ttf", 24), ("segoeui.ttf", 24)]
    assert captured_draw_calls["multiline_text"]


def test_apply_overlay_falls_back_to_pillow_default_when_system_fonts_unavailable(
    monkeypatch, captured_draw_calls
) -> None:
    attempts: list[tuple[str, int]] = []

    def mock_truetype(path: str, size: int):
        attempts.append((path, size))
        raise OSError("missing font")

    def mock_load_default(*, size: int):
        return ("default-font", size)

    monkeypatch.setattr("frame_compare.render.overlay.ImageFont.truetype", mock_truetype)
    monkeypatch.setattr("frame_compare.render.overlay.ImageFont.load_default", mock_load_default)

    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Font",
        frame_number=1,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert attempts == [
        ("segoeui.ttf", 24),
        ("arial.ttf", 24),
        ("tahoma.ttf", 24),
        ("calibri.ttf", 24),
        ("verdana.ttf", 24),
    ]
    assert captured_draw_calls["multiline_text"]


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
        origin=(26, 14),
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert len(calls) == 2
    assert calls[0][0] == (26, 14)
    assert calls[1][0] == (26, 144)


def test_apply_overlay_uses_explicit_origin_for_frame_and_detail_blocks(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Ref",
        frame_number=100,
        display_frame_number=12,
        num_frames=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
        origin=(26, 14),
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    (xy1, text1, _kwargs1) = captured_draw_calls["multiline_text"][0]
    (xy2, _text2, _kwargs2) = captured_draw_calls["multiline_text"][1]
    expected_frame_info_height = len(str(text1).splitlines()) * 20
    assert xy1 == (26, 14)
    assert xy2 == (26, 14 + expected_frame_info_height + 10)


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


def test_apply_overlay_standard_omits_picture_type_line_when_unavailable(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Ref",
        frame_number=100,
        display_frame_number=12,
        num_frames=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
        picture_type=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    _, text1, _ = captured_draw_calls["multiline_text"][0]
    assert text1.splitlines() == ["Frame 12 of 100", "Ref"]
    assert all(not line.startswith("Picture type:") for line in text1.splitlines())


def test_apply_overlay_uses_burn_in_label_when_present(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Encode 1",
        burn_in_label="encode-file",
        frame_number=100,
        display_frame_number=12,
        num_frames=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    assert len(captured_draw_calls["multiline_text"]) == 2
    _, text1, _ = captured_draw_calls["multiline_text"][0]
    assert text1 == "\n".join(
        compose_frame_info_lines(
            mode=OverlayMode.STANDARD,
            label="encode-file",
            display_frame_number=12,
            num_frames=100,
            picture_type=None,
            selection_label=None,
        )
    )
    assert "Encode 1" not in text1


def test_apply_overlay_selection_detail_label_overrides_selection_label(captured_draw_calls):
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
        selection_detail=OverlaySelectionDetail(
            frame_index=12,
            label="User",
            source="analysis",
            timecode="00:00:00.500",
            clip_role="analyze",
        ),
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    _, text1, _ = captured_draw_calls["multiline_text"][0]
    assert text1 == "\n".join(
        compose_frame_info_lines(
            mode=OverlayMode.STANDARD,
            label="Ref",
            display_frame_number=12,
            num_frames=100,
            picture_type=None,
            selection_label="User",
        )
    )

    _, text2, _ = captured_draw_calls["multiline_text"][1]
    assert text2 == "\n".join(
        compose_overlay_text_lines(
            mode=OverlayMode.STANDARD,
            base_text=None,
            width=1920,
            height=1080,
            selection_type="User",
            diagnostic_lines=[],
        )
    )


def test_apply_overlay_standard_renders_picture_type_line_when_present(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Ref",
        frame_number=100,
        display_frame_number=12,
        num_frames=100,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
        picture_type="B",
    )
    img = Image.new("RGB", (100, 100))

    apply_overlay(img, config)

    _, text1, _ = captured_draw_calls["multiline_text"][0]
    assert text1.splitlines() == ["Frame 12 of 100", "Picture type: B", "Ref"]


def test_apply_overlay_diagnostic_with_hdr(captured_draw_calls):
    config = OverlayConfig(
        mode=OverlayMode.DIAGNOSTIC,
        label="Encode",
        frame_number=200,
        display_frame_number=20,
        num_frames=100,
        resolution=(3840, 2160),
        hdr_info="HDR (native, no tonemap)",
        font_path=None,
        selection_detail=OverlaySelectionDetail(
            frame_index=20,
            label="Motion",
            source="analysis",
            timecode="00:00:00.833",
            score=0.9,
            clip_role="analyze",
        ),
        diagnostic_metadata=OverlayDiagnosticMetadata(
            mastering_display=(
                "G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L(1000.0,0.0050)"
            ),
            max_cll=900,
            max_fall=300,
            color_range="limited",
            dolby_vision=OverlayDolbyVisionMetadata(
                rpu_present=True,
                block_index=2,
                block_total=10,
                target_nits=800.0,
                l2_target_nits=800.0,
                l1_average=12.5,
                l1_maximum=450.0,
                l5_left=1,
                l5_right=2,
                l5_top=3,
                l5_bottom=4,
                l6_max_cll=900.0,
                l6_max_fall=300.0,
            ),
            measurement=OverlayFrameMeasurement(
                avg_nits=180.0,
                max_nits=180.0,
                category="Motion",
            ),
        ),
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
            selection_label="Motion",
        )
    )

    _, text2, _ = captured_draw_calls["multiline_text"][1]
    assert text2 == "\n".join(
        compose_overlay_text_lines(
            mode=OverlayMode.DIAGNOSTIC,
            base_text=None,
            width=3840,
            height=2160,
            selection_type="Motion",
            diagnostic_lines=[
                "HDR (native, no tonemap)",
                "MDL: min: 0.005 cd/m², max: 1000.0 cd/m²",
                "HDR: MaxCLL 900 / MaxFALL 300",
                "DoVi: on (Target: 800nits) L2 2/10 target 800 nits",
                "DV RPU Level 1 MAX/AVG: 450nits / 12.5nits",
                "DV L5 Active Area: L:1 R:2 T:3 B:4",
                "DV L6 Metadata: MaxCLL 900 / MaxFALL 300",
                "Range: Limited",
                "Measurement MAX/AVG: 180nits / 180nits (Motion)",
            ],
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
