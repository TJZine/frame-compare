from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from frame_compare.config.schema import OverlayMode
from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.render.types import (
    BatchRenderOptions,
    EncoderSettings,
    OverlayConfig,
    RenderedClipFacts,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedGeometryFacts,
    SourceSignalFacts,
)


def _geometry() -> RenderedGeometryFacts:
    return RenderedGeometryFacts(
        source_size=(1920, 1080),
        active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
        cropped_size=(1920, 1080),
        scaled_size=(1920, 1080),
        final_canvas_size=(1920, 1080),
        is_noop=True,
    )


def _clip_facts() -> RenderedClipFacts:
    return RenderedClipFacts(
        size_bytes=1024,
        source_resolution=(1920, 1080),
        source_total_frames=10,
        signal=SourceSignalFacts(is_hdr=False),
        presentation_state=PresentationState.SDR,
        tonemap=None,
        geometry=_geometry(),
    )


def test_encoder_settings_defaults() -> None:
    settings = EncoderSettings()
    assert settings.compression == 6
    assert settings.vs_writer == VsScreenshotWriter.AUTO


def test_overlay_config_is_immutable_and_keeps_source_domain() -> None:
    config = OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Test",
        comparison_frame=1,
        source_frame=3,
        source_total_frames=10,
        include_frame_number=True,
        selection_label=None,
        file_size_bytes=1024,
        source_resolution=(1920, 1080),
        signal=SourceSignalFacts(is_hdr=False),
        presentation_state=PresentationState.SDR,
        tonemap=None,
        geometry=_geometry(),
        font_path=None,
    )
    assert config.comparison_frame == 1
    assert config.source_frame == 3
    field = "label"
    with pytest.raises(FrozenInstanceError):
        setattr(config, field, "changed")


def test_batch_render_options_defaults() -> None:
    options = BatchRenderOptions()
    assert options.renderer == "auto"
    assert options.overlay_mode == OverlayMode.STANDARD
    assert options.reporter is None
    assert options.ffmpeg_runner is None


@pytest.mark.parametrize("frames", [(), (3,)])
def test_prepared_clip_rejects_selection_request_disagreement(frames: tuple[int, ...]) -> None:
    from frame_compare.render.types import EncoderSettings, PreparedClipRender, RenderRequest
    from tests.render_test_support import selections

    request = RenderRequest(
        Path("clip.mkv"), Path("clip.mkv"), 1, Path("frame.png"), None, EncoderSettings()
    )
    with pytest.raises(ValueError, match="one request per selected|source frame differs"):
        PreparedClipRender("ref", _clip_facts(), selections(frames), (request,))
