import typing
from pathlib import Path

from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    OverlayMode,
    Renderer,
    RenderRequest,
    ScreenshotResult,
)


def test_overlay_mode_values() -> None:
    assert set(OverlayMode) == {
        OverlayMode.MINIMAL,
        OverlayMode.STANDARD,
        OverlayMode.DIAGNOSTIC,
        OverlayMode.NONE,
    }


def test_overlay_mode_string_values() -> None:
    assert OverlayMode.MINIMAL.value == "minimal"
    assert OverlayMode.STANDARD.value == "standard"
    assert OverlayMode.DIAGNOSTIC.value == "diagnostic"
    assert OverlayMode.NONE.value == "none"


def test_encoder_settings_defaults() -> None:
    settings = EncoderSettings()
    assert settings.format == "png"
    assert settings.compression == 6
    assert settings.bit_depth == 8


def test_encoder_settings_custom() -> None:
    settings = EncoderSettings(format="webp", compression=9, bit_depth=16)
    assert settings.format == "webp"
    assert settings.compression == 9
    assert settings.bit_depth == 16


def test_overlay_config_defaults() -> None:
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Test",
        frame_number=1,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    assert config.font_size == 24
    assert config.position == "top-left"


def test_overlay_config_optional_none() -> None:
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Test",
        frame_number=1,
        resolution=(1920, 1080),
        hdr_info=None,
        font_path=None,
    )
    assert config.hdr_info is None
    assert config.font_path is None


def test_render_request_optional_overlay() -> None:
    request = RenderRequest(
        clip=Path("video.mp4"),
        frame_number=0,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )
    assert request.overlay is None


def test_screenshot_result_creation() -> None:
    paths = [Path("a.png")]
    result = ScreenshotResult(label="label", paths=paths, frame_count=1)
    assert result.label == "label"
    assert result.paths == paths
    assert result.frame_count == 1


def test_renderer_literal_values() -> None:
    assert typing.get_args(Renderer) == ("vapoursynth", "ffmpeg", "auto")
