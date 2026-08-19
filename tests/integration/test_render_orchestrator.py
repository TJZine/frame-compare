from pathlib import Path

import pytest
from PIL import Image

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.batch.orchestrator import render_screenshots_from_batch
from frame_compare.render.types import BatchRenderOptions, ScreenshotBatchRequest
from frame_compare.utils.media_facts import ActivePictureFacts, SourceSignalFacts


@pytest.fixture
def integration_config() -> ConfigSchema:
    """Config with tonemap disabled for FFmpeg-only integration tests."""
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


def _request(
    clip_path: Path,
    label: str,
    frames: list[int],
) -> ScreenshotBatchRequest:
    return ScreenshotBatchRequest(
        clip_path=clip_path,
        label=label,
        source_frames=frames,
        comparison_frames=frames,
        selection_labels=[None] * len(frames),
        size_bytes=clip_path.stat().st_size,
        source_resolution=(100, 100),
        source_total_frames=3,
        signal=SourceSignalFacts(is_hdr=False),
        active_picture=ActivePictureFacts(0, 0, 100, 100, "full_frame", True),
        filename_label=clip_path.stem,
    )


@pytest.mark.integration
def test_render_screenshots_naming_and_output(
    mock_video_path: Path, integration_output_dir: Path, integration_config: ConfigSchema
):
    """Verify canonical batch rendering naming and output mapping."""
    frames = [0, 1]
    output_dir = integration_output_dir

    results = render_screenshots_from_batch(
        [_request(mock_video_path, "TestLabel", frames)],
        output_dir,
        integration_config,
        BatchRenderOptions(renderer="ffmpeg"),
    )

    assert "TestLabel" in results
    assert len(results["TestLabel"]) == 2

    # Check filenames (legacy-readable frame + source stem).
    assert results["TestLabel"][0].name == "0 - test.png"
    assert results["TestLabel"][1].name == "1 - test.png"

    # Check existence and validity
    for path in results["TestLabel"]:
        assert path.exists()
        with Image.open(path) as img:
            assert img.format == "PNG"


@pytest.mark.integration
def test_render_screenshots_empty_frames_returns_label_with_empty_list(
    mock_video_path: Path, integration_output_dir: Path, integration_config: ConfigSchema
):
    results = render_screenshots_from_batch(
        [_request(mock_video_path, "EmptyFrames", [])],
        integration_output_dir,
        integration_config,
        BatchRenderOptions(renderer="ffmpeg"),
    )

    assert results == {"EmptyFrames": []}


@pytest.mark.integration
def test_render_screenshots_from_batch_empty_clips_returns_empty_dict(
    integration_output_dir: Path, integration_config: ConfigSchema
):
    results = render_screenshots_from_batch([], integration_output_dir, integration_config)

    assert results == {}


@pytest.mark.integration
def test_render_screenshots_from_batch_uses_supplied_label(
    mock_video_path: Path, integration_output_dir: Path, integration_config: ConfigSchema
):
    results = render_screenshots_from_batch(
        [_request(mock_video_path, mock_video_path.stem, [])],
        integration_output_dir,
        integration_config,
        BatchRenderOptions(renderer="ffmpeg"),
    )

    assert results == {mock_video_path.stem: []}
