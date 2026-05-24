from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from structlog.testing import capture_logs

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.batch.orchestrator import (
    render_screenshots,
)
from frame_compare.render.errors import RenderError
from frame_compare.render.types import (
    ScreenshotRenderOptions,
)
from frame_compare.vs.errors import (
    PluginNotFoundError,
    SourceLoadError,
    VapourSynthNotFoundError,
)


@pytest.fixture
def default_config() -> ConfigSchema:
    """Default config with tonemap disabled for isolated tests."""
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


def test_render_screenshots_vs_forced_fail_plugin(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = PluginNotFoundError("lsmas")

        with pytest.raises(PluginNotFoundError):
            render_screenshots(
                clips,
                [1],
                tmp_path,
                default_config,
                ScreenshotRenderOptions(renderer="vapoursynth"),
            )


def test_render_screenshots_overlay_resolution(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_source = MagicMock()
        mock_source.width = 1280
        mock_source.height = 720
        mock_source.is_hdr = False
        mock_loader.load.return_value = mock_source

        with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
            mock_batch.return_value = [tmp_path / "1.png"]
            render_screenshots(
                clips,
                [1],
                tmp_path,
                default_config,
                ScreenshotRenderOptions(renderer="vapoursynth"),
            )

            # Verify resolution in request
            req = mock_batch.call_args[0][0][0]
            assert req.overlay.resolution == (1280, 720)

    # Test fallback resolution (0, 0)
    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = SourceLoadError(Path("vid1.mkv"), "Failed")
        with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
            mock_batch.return_value = [tmp_path / "1.png"]
            render_screenshots(
                clips,
                [1],
                tmp_path,
                default_config,
                ScreenshotRenderOptions(renderer="auto"),
            )
            req = mock_batch.call_args[0][0][0]
            assert req.overlay.resolution == (0, 0)


def test_render_screenshots_vs_forced_fail_vs_not_found(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = VapourSynthNotFoundError()

        with pytest.raises(VapourSynthNotFoundError):
            render_screenshots(
                clips,
                [1],
                tmp_path,
                default_config,
                ScreenshotRenderOptions(renderer="vapoursynth"),
            )


def test_render_screenshots_vs_forced_fail_source(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = SourceLoadError(Path("vid1.mkv"), "Failed")

        with pytest.raises(SourceLoadError):
            render_screenshots(
                clips,
                [1],
                tmp_path,
                default_config,
                ScreenshotRenderOptions(renderer="vapoursynth"),
            )


def test_render_screenshots_dict_order(tmp_path, default_config):
    clips = [Path("b.mkv"), Path("a.mkv")]
    frames = [1, 2]
    with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
        mock_batch.return_value = [Path(f"{i}.png") for i in range(4)]
        results = render_screenshots(
            clips,
            frames,
            tmp_path,
            default_config,
            ScreenshotRenderOptions(renderer="ffmpeg"),
        )

        # Dict keys should preserve clip order
        assert list(results.keys()) == ["b", "a"]
        assert len(results["b"]) == 2
        assert len(results["a"]) == 2


def test_render_screenshots_vs_loading(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    frames = [10, 20]

    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_source = MagicMock()
        mock_source.clip = MagicMock()
        mock_source.width = 1920
        mock_source.height = 1080
        mock_source.is_hdr = False
        mock_loader.load.return_value = mock_source

        with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
            mock_batch.return_value = [tmp_path / "1.png", tmp_path / "2.png"]

            results = render_screenshots(
                clips,
                frames,
                tmp_path,
                default_config,
                ScreenshotRenderOptions(renderer="vapoursynth"),
            )

            assert "vid1" in results
            assert len(results["vid1"]) == 2
            mock_loader.load.assert_called_once_with(Path("vid1.mkv"))


def test_render_screenshots_vs_forced_fail_unknown(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = RuntimeError("Unknown")

        with pytest.raises(RenderError) as exc_info:
            render_screenshots(
                clips,
                [1],
                tmp_path,
                default_config,
                ScreenshotRenderOptions(renderer="vapoursynth"),
            )
        assert exc_info.type is RenderError
        assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_render_screenshots_output_path(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    frames = [42]
    with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
        mock_batch.return_value = [tmp_path / "vid1_000042.png"]
        render_screenshots(
            clips,
            frames,
            tmp_path,
            default_config,
            ScreenshotRenderOptions(renderer="ffmpeg"),
        )

        req = mock_batch.call_args[0][0][0]
        from frame_compare.render.naming import generate_screenshot_path

        expected = generate_screenshot_path(tmp_path, "vid1", 42)
        assert req.output_path == expected


def test_render_screenshots_fallback(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    frames = [10]

    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = SourceLoadError(Path("vid1.mkv"), "Failed")

        with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
            mock_batch.return_value = [tmp_path / "1.png"]

            # Should NOT raise, but log warning (enable_tonemap=False → fallback allowed)
            with capture_logs() as captured:
                results = render_screenshots(
                    clips,
                    frames,
                    tmp_path,
                    default_config,
                    ScreenshotRenderOptions(renderer="auto"),
                )

            assert "vid1" in results
            assert any(log["event"] == "vs_load_failed_falling_back" for log in captured)
            request = mock_batch.call_args.args[0][0]
            assert request.overlay is not None
            assert request.overlay.resolution == (0, 0)
            assert request.overlay.num_frames is None


def test_render_screenshots_fallback_unknown(tmp_path, default_config):
    clips = [Path("vid1.mkv")]
    frames = [10]

    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_loader.load.side_effect = RuntimeError("Unknown")

        with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
            mock_batch.return_value = [tmp_path / "1.png"]

            with pytest.raises(RenderError) as exc_info:
                render_screenshots(
                    clips,
                    frames,
                    tmp_path,
                    default_config,
                    ScreenshotRenderOptions(renderer="auto"),
                )
            assert exc_info.type is RenderError
            assert isinstance(exc_info.value.__cause__, RuntimeError)
