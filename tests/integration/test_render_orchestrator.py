from pathlib import Path

import pytest
from PIL import Image

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render import render_screenshots
from frame_compare.render.types import OverlayMode


@pytest.fixture
def integration_config() -> ConfigSchema:
    """Config with tonemap disabled for FFmpeg-only integration tests."""
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


@pytest.mark.integration
def test_render_screenshots_naming_and_output(
    mock_video_path: Path, integration_output_dir: Path, integration_config: ConfigSchema
):
    """Verify render_screenshots naming convention and output mapping."""
    clips = [mock_video_path]
    frames = [0, 1]
    output_dir = integration_output_dir
    label_map = {mock_video_path: "TestLabel"}

    results = render_screenshots(
        clips,
        frames,
        output_dir,
        integration_config,
        label_map=label_map,
        renderer="ffmpeg",
        overlay_mode=OverlayMode.MINIMAL,
    )

    assert "TestLabel" in results
    assert len(results["TestLabel"]) == 2

    # Check filenames (deterministic padding per SSOT)
    assert results["TestLabel"][0].name == "TestLabel_00000.png"
    assert results["TestLabel"][1].name == "TestLabel_00001.png"

    # Check existence and validity
    for path in results["TestLabel"]:
        assert path.exists()
        with Image.open(path) as img:
            assert img.format == "PNG"
