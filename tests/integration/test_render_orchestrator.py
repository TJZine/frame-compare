from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.batch.orchestrator import (
    render_screenshots_from_batch_detailed,
)
from frame_compare.render.types import ScreenshotBatchRequest
from frame_compare.utils.media_facts import ActivePictureFacts, SourceSignalFacts
from frame_compare.vs.env import detect_plugins
from tests.render_test_support import paths_by_label, selections

vs = pytest.importorskip("vapoursynth")
if isinstance(vs, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)
if not detect_plugins(vs.core).get("lsmas", False):
    pytest.skip("lsmas plugin not available", allow_module_level=True)


@pytest.fixture
def integration_config() -> ConfigSchema:
    """Config for screenshot integration tests with tonemapping disabled."""
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


def _request(
    clip_path: Path,
    label: str,
    frames: list[int],
    *,
    size: tuple[int, int] = (100, 100),
) -> ScreenshotBatchRequest:
    return ScreenshotBatchRequest(
        clip_path=clip_path,
        label=label,
        frames=selections(frames, frames, [None] * len(frames)),
        size_bytes=clip_path.stat().st_size,
        source_resolution=size,
        source_total_frames=3,
        signal=SourceSignalFacts(is_hdr=False, primaries=1, transfer=1, matrix=1),
        active_picture=ActivePictureFacts(0, 0, *size, "full_frame", True),
        filename_label=clip_path.stem,
    )


@pytest.mark.integration
def test_render_screenshots_naming_and_output(
    mock_video_path: Path, integration_output_dir: Path, integration_config: ConfigSchema
):
    """Verify canonical batch rendering naming and output mapping."""
    frames = [0, 1]
    output_dir = integration_output_dir

    results = paths_by_label(
        render_screenshots_from_batch_detailed(
            [_request(mock_video_path, "TestLabel", frames)],
            output_dir,
            integration_config,
        )
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
    results = paths_by_label(
        render_screenshots_from_batch_detailed(
            [_request(mock_video_path, "EmptyFrames", [])],
            integration_output_dir,
            integration_config,
        )
    )

    assert results == {"EmptyFrames": []}


@pytest.mark.integration
def test_render_screenshots_from_batch_empty_clips_returns_empty_dict(
    integration_output_dir: Path, integration_config: ConfigSchema
):
    results = paths_by_label(
        render_screenshots_from_batch_detailed([], integration_output_dir, integration_config)
    )

    assert results == {}


@pytest.mark.integration
def test_render_screenshots_from_batch_uses_supplied_label(
    mock_video_path: Path, integration_output_dir: Path, integration_config: ConfigSchema
):
    results = paths_by_label(
        render_screenshots_from_batch_detailed(
            [_request(mock_video_path, mock_video_path.stem, [])],
            integration_output_dir,
            integration_config,
        )
    )

    assert results == {mock_video_path.stem: []}
