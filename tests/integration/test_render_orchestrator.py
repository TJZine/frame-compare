from pathlib import Path

import pytest
from PIL import Image

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.render.batch.orchestrator import (
    render_screenshots_from_batch,
    render_screenshots_from_batch_detailed,
)
from frame_compare.render.types import BatchRenderOptions, ScreenshotBatchRequest
from frame_compare.utils.media_facts import ActivePictureFacts, SourceSignalFacts
from frame_compare.utils.subproc import run_subprocess


class _NonBatchingFFmpegRunner(DefaultFFmpegRunner):
    """Force the compatibility path so parity tests retain a real per-frame baseline."""

    pass


@pytest.fixture
def integration_config() -> ConfigSchema:
    """Config with tonemap disabled for FFmpeg-only integration tests."""
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


def _request(
    clip_path: Path,
    label: str,
    frames: list[int],
    *,
    is_hdr: bool = False,
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
        signal=SourceSignalFacts(
            is_hdr=is_hdr,
            primaries=9 if is_hdr else 1,
            transfer=16 if is_hdr else 1,
            matrix=9 if is_hdr else 1,
        ),
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
def test_ffmpeg_one_pass_batch_matches_per_frame_pixels_and_facts(
    mock_video_path: Path, tmp_path: Path, integration_config: ConfigSchema
) -> None:
    request = _request(mock_video_path, "TestLabel", [0, 1, 2])
    batched = render_screenshots_from_batch_detailed(
        [request],
        tmp_path / "batched",
        integration_config,
        BatchRenderOptions(renderer="ffmpeg", parallelism=1),
    )
    per_frame = render_screenshots_from_batch_detailed(
        [request],
        tmp_path / "per-frame",
        integration_config,
        BatchRenderOptions(
            renderer="ffmpeg", parallelism=2, ffmpeg_runner=_NonBatchingFFmpegRunner()
        ),
    )

    batched_paths = batched.screenshots_by_label["TestLabel"]
    per_frame_paths = per_frame.screenshots_by_label["TestLabel"]
    assert [path.read_bytes() for path in batched_paths] == [
        path.read_bytes() for path in per_frame_paths
    ]
    assert batched.frame_facts_by_label == per_frame.frame_facts_by_label


@pytest.mark.integration
def test_ffmpeg_one_pass_batch_matches_per_frame_hdr_pixels_and_facts(
    tmp_path: Path, require_ffmpeg: None, integration_config: ConfigSchema
) -> None:
    fixture = tmp_path / "hdr.mkv"
    run_subprocess(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=100x100:rate=10",
            "-frames:v",
            "3",
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "yuv420p10le",
            "-color_primaries",
            "bt2020",
            "-color_trc",
            "smpte2084",
            "-colorspace",
            "bt2020nc",
            str(fixture),
        ],
        timeout_seconds=20,
    )
    request = _request(fixture, "HDR", [0, 1, 2], is_hdr=True)
    batched = render_screenshots_from_batch_detailed(
        [request],
        tmp_path / "hdr-batched",
        integration_config,
        BatchRenderOptions(renderer="ffmpeg", parallelism=1),
    )
    per_frame = render_screenshots_from_batch_detailed(
        [request],
        tmp_path / "hdr-per-frame",
        integration_config,
        BatchRenderOptions(
            renderer="ffmpeg", parallelism=2, ffmpeg_runner=_NonBatchingFFmpegRunner()
        ),
    )

    batched_paths = batched.screenshots_by_label["HDR"]
    per_frame_paths = per_frame.screenshots_by_label["HDR"]
    assert [path.read_bytes() for path in batched_paths] == [
        path.read_bytes() for path in per_frame_paths
    ]
    assert batched.frame_facts_by_label == per_frame.frame_facts_by_label


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
