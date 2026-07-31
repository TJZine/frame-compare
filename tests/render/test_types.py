import typing

from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.render.types import (
    BatchRenderOptions,
    EncoderSettings,
    OverlayConfig,
    OverlayMode,
    Renderer,
)


def test_overlay_mode_string_values() -> None:
    assert {mode.value for mode in OverlayMode} == {"minimal", "standard", "diagnostic", "none"}


def test_encoder_settings_defaults() -> None:
    settings = EncoderSettings()
    assert settings.format == "png"
    assert settings.compression == 6
    assert settings.bit_depth == 8
    assert settings.vs_writer == VsScreenshotWriter.AUTO


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
    assert config.base_text is None
    assert config.resolution_summary is None


def test_renderer_literal_values() -> None:
    assert typing.get_args(Renderer) == ("vapoursynth", "ffmpeg", "auto")


def test_batch_render_options_defaults() -> None:
    options = BatchRenderOptions()
    assert options.renderer == "auto"
    assert options.overlay_mode == OverlayMode.STANDARD
    assert options.reporter is None
    assert options.ffmpeg_runner is None
