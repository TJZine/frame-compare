from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.batch.orchestrator import render_screenshots
from frame_compare.render.types import ScreenshotRenderOptions


@pytest.fixture
def default_config() -> ConfigSchema:
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


def test_render_screenshots_builds_canonical_batch_request(
    tmp_path: Path, default_config: ConfigSchema
) -> None:
    with patch(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        return_value={"vid1": [tmp_path / "1.png", tmp_path / "2.png"]},
    ) as render_batch:
        result = render_screenshots(
            [Path("vid1.mkv")],
            [1, 2],
            tmp_path,
            default_config,
            ScreenshotRenderOptions(
                renderer="ffmpeg",
                display_frames=[101, 102],
                selection_labels=["first", None],
            ),
        )

    assert result == {"vid1": [tmp_path / "1.png", tmp_path / "2.png"]}
    request = render_batch.call_args.kwargs["batch_requests"][0]
    assert request.source_frames == [1, 2]
    assert request.comparison_frames == [101, 102]
    assert request.selection_labels == ["first", None]
    assert request.source_resolution == (0, 0)
    assert request.source_total_frames is None
    assert request.signal.is_hdr is False
    assert request.active_picture.is_full_frame is True


def test_render_screenshots_rejects_mismatched_display_frames(
    tmp_path: Path, default_config: ConfigSchema
) -> None:
    with pytest.raises(ValueError, match="display_frames must have the same length"):
        render_screenshots(
            [Path("vid1.mkv")],
            [1, 2],
            tmp_path,
            default_config,
            ScreenshotRenderOptions(display_frames=[1]),
        )


def test_render_screenshots_rejects_mismatched_selection_labels(
    tmp_path: Path, default_config: ConfigSchema
) -> None:
    with pytest.raises(ValueError, match="selection_labels must have the same length"):
        render_screenshots(
            [Path("vid1.mkv")],
            [1, 2],
            tmp_path,
            default_config,
            ScreenshotRenderOptions(selection_labels=["only-one"]),
        )


def test_render_screenshots_preserves_clip_order(
    tmp_path: Path, default_config: ConfigSchema
) -> None:
    with patch(
        "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
        return_value={"b": [tmp_path / "b.png"], "a": [tmp_path / "a.png"]},
    ):
        result = render_screenshots(
            [Path("b.mkv"), Path("a.mkv")],
            [1],
            tmp_path,
            default_config,
            ScreenshotRenderOptions(renderer="ffmpeg"),
        )
    assert list(result) == ["b", "a"]


def test_render_screenshots_constructs_configured_default_ffmpeg_runner(tmp_path: Path) -> None:
    config = ConfigSchema(
        color=ColorConfig(enable_tonemap=False),
        screenshots={"use_ffmpeg": True, "ffmpeg_timeout_seconds": 47.0},
    )
    configured_runner = MagicMock()
    with (
        patch(
            "frame_compare.render.batch.expansion.DefaultFFmpegRunner",
            return_value=configured_runner,
        ) as default_runner,
        patch(
            "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
            return_value={},
        ),
    ):
        render_screenshots([Path("clip.mkv")], [1], tmp_path, config)
    default_runner.assert_called_once_with(extraction_timeout_seconds=47.0)


def test_render_screenshots_preserves_injected_ffmpeg_runner(tmp_path: Path) -> None:
    config = ConfigSchema(
        color=ColorConfig(enable_tonemap=False),
        screenshots={"use_ffmpeg": True, "ffmpeg_timeout_seconds": 47.0},
    )
    injected_runner = MagicMock()
    with (
        patch("frame_compare.render.batch.expansion.DefaultFFmpegRunner") as default_runner,
        patch(
            "frame_compare.render.batch.orchestrator.render_screenshots_from_batch",
            return_value={},
        ) as render_batch,
    ):
        render_screenshots(
            [Path("clip.mkv")],
            [1],
            tmp_path,
            config,
            ScreenshotRenderOptions(ffmpeg_runner=injected_runner),
        )
    default_runner.assert_not_called()
    assert render_batch.call_args.kwargs["options"].ffmpeg_runner is injected_runner
