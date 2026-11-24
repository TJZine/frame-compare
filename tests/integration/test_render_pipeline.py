from pathlib import Path

import pytest
from PIL import Image

from frame_compare.render.batch.orchestrator import render_clip_jobs
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import (
    OverlayConfig,
    OverlayMode,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)


def _overlay_config() -> OverlayConfig:
    geometry = RenderedGeometryFacts(
        source_size=(100, 100),
        active_picture=ActivePictureFacts(0, 0, 100, 100, "full_frame", True),
        cropped_size=(100, 100),
        scaled_size=(100, 100),
        final_canvas_size=(100, 100),
        is_noop=True,
    )
    return OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Test",
        comparison_frame=1,
        source_frame=1,
        source_total_frames=10,
        include_frame_number=True,
        selection_label="Selected",
        file_size_bytes=1024,
        source_resolution=(100, 100),
        signal=SourceSignalFacts(is_hdr=False),
        presentation_state=PresentationState.SDR,
        tonemap=None,
        geometry=geometry,
        font_path=None,
        font_size=24,
    )


@pytest.mark.integration
def test_overlay_application_adds_visible_content(sample_image_path: Path):
    with Image.open(sample_image_path) as img:
        config = _overlay_config()

        result = apply_overlay(img, config, RenderedFrameFacts(source_frame=1, picture_type="I"))

        pixel_data = result.get_flattened_data()
        assert len(set(pixel_data)) > 1


@pytest.mark.integration
def test_render_batch_empty_requests_returns_empty() -> None:
    assert render_clip_jobs(()) == ()
