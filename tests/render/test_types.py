import typing
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from frame_compare.config.schema import OverlayMode
from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.render.types import (
    BatchRenderOptions,
    EncoderSettings,
    OverlayConfig,
    RenderedBatchResult,
    RenderedClipFacts,
    Renderer,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
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
        tonemap_settings=None,
        geometry=_geometry(),
    )


def test_overlay_mode_string_values() -> None:
    assert {mode.value for mode in OverlayMode} == {"minimal", "standard", "diagnostic", "none"}


def test_encoder_settings_defaults() -> None:
    settings = EncoderSettings()
    assert settings.format == "png"
    assert settings.compression == 6
    assert settings.bit_depth == 8
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
        tonemap_settings=None,
        geometry=_geometry(),
        font_path=None,
    )
    assert config.comparison_frame == 1
    assert config.source_frame == 3
    with pytest.raises(FrozenInstanceError):
        config.label = "changed"  # type: ignore[misc]


def test_rendered_batch_requires_identical_labels_and_counts() -> None:
    with pytest.raises(ValueError, match="identical label sets"):
        RenderedBatchResult(screenshots_by_label={"ref": []})

    with pytest.raises(ValueError, match="count mismatch"):
        RenderedBatchResult(
            screenshots_by_label={"ref": [Path("frame.png")]},
            frame_facts_by_label={"ref": []},
            clip_facts_by_label={"ref": _clip_facts()},
        )


def test_rendered_batch_accepts_one_to_one_exact_frame_facts() -> None:
    result = RenderedBatchResult(
        screenshots_by_label={"ref": [Path("frame.png")]},
        frame_facts_by_label={"ref": [RenderedFrameFacts(source_frame=3, picture_type="B")]},
        clip_facts_by_label={"ref": _clip_facts()},
    )
    assert result.frame_facts_by_label["ref"][0].source_frame == 3


def test_renderer_literal_values() -> None:
    assert typing.get_args(Renderer) == ("vapoursynth", "ffmpeg", "auto")


def test_batch_render_options_defaults() -> None:
    options = BatchRenderOptions()
    assert options.renderer == "auto"
    assert options.overlay_mode == OverlayMode.STANDARD
    assert options.reporter is None
    assert options.ffmpeg_runner is None
