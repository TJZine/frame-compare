import typing
from pathlib import Path

from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.render.types import (
    BatchRenderOptions,
    EncoderSettings,
    OverlayConfig,
    OverlayDiagnosticMetadata,
    OverlayDolbyVisionMetadata,
    OverlayFrameMeasurement,
    OverlayMode,
    OverlaySelectionDetail,
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
    assert settings.vs_writer == VsScreenshotWriter.AUTO


def test_encoder_settings_custom() -> None:
    settings = EncoderSettings(
        format="webp",
        compression=9,
        bit_depth=16,
        vs_writer=VsScreenshotWriter.FPNG,
    )
    assert settings.format == "webp"
    assert settings.compression == 9
    assert settings.bit_depth == 16
    assert settings.vs_writer == VsScreenshotWriter.FPNG


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
    assert config.burn_in_label is None
    assert config.selection_detail is None
    assert config.diagnostic_metadata is None
    assert config.base_text is None
    assert config.resolution_summary is None


def test_overlay_selection_detail_creation() -> None:
    detail = OverlaySelectionDetail(
        frame_index=1,
        label="User",
        source="analysis",
        timecode=None,
        score=0.3,
        clip_role="analyze",
        notes="user_override",
    )
    assert detail.label == "User"
    assert detail.source == "analysis"
    assert detail.timecode is None


def test_overlay_diagnostic_metadata_creation() -> None:
    measurement = OverlayFrameMeasurement(avg_nits=180.0, max_nits=180.0, category="Motion")
    dovi = OverlayDolbyVisionMetadata(rpu_present=True, l1_average=12.5, l1_maximum=450.0)
    metadata = OverlayDiagnosticMetadata(
        mastering_display="G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L(1000.0,0.0050)",
        max_cll=1000,
        max_fall=400,
        color_range="limited",
        dolby_vision=dovi,
        measurement=measurement,
    )
    assert metadata.max_cll == 1000
    assert metadata.color_range == "limited"
    assert metadata.dolby_vision == dovi
    assert metadata.measurement == measurement


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


def test_batch_render_options_defaults() -> None:
    options = BatchRenderOptions()
    assert options.renderer == "auto"
    assert options.overlay_mode == OverlayMode.STANDARD
    assert options.reporter is None
    assert options.ffmpeg_runner is None
