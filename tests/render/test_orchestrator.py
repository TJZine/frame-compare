from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import pytest
from structlog.testing import capture_logs

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.errors import (
    PluginNotFoundError,
    RenderError,
    SourceLoadError,
    VapourSynthNotFoundError,
)
from frame_compare.render.batch.orchestrator import (
    ProgressReporter,
    render_batch,
    render_screenshots,
    render_screenshots_from_batch,
)
from frame_compare.render.orchestrator import render_batch as legacy_render_batch
from frame_compare.render.types import (
    EncoderSettings,
    RenderRequest,
    ScreenshotBatchRequest,
    ScreenshotRenderOptions,
)


@pytest.fixture
def default_config() -> ConfigSchema:
    """Default config with tonemap disabled for isolated tests."""
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


@pytest.fixture
def mock_render_request(tmp_path):
    return RenderRequest(
        clip=Path("video.mkv"),
        frame_number=42,
        output_path=tmp_path / "out.png",
        overlay=None,
        encoder_settings=EncoderSettings(),
    )


def test_render_batch_sequential(mock_render_request):
    requests = [mock_render_request] * 3
    with patch("frame_compare.render.batch.orchestrator.render_frame") as mock_render:
        mock_render.side_effect = lambda r: r.output_path
        results = render_batch(requests, parallelism=1)
        assert results == [r.output_path for r in requests]
        assert mock_render.call_count == 3


def test_legacy_orchestrator_import_reexports_batch_owner() -> None:
    assert legacy_render_batch is render_batch


def test_render_batch_parallel_order(mock_render_request):
    requests = [
        RenderRequest(
            clip=Path("video.mkv"),
            frame_number=i,
            output_path=Path(f"out_{i}.png"),
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        for i in range(5)
    ]
    with patch("frame_compare.render.batch.orchestrator.render_frame") as mock_render:
        mock_render.side_effect = lambda r: r.output_path
        results = render_batch(requests, parallelism=2)
        assert results == [r.output_path for r in requests]


def test_render_batch_fail_fast(mock_render_request):
    requests = [mock_render_request] * 10
    with patch("frame_compare.render.batch.orchestrator.render_frame") as mock_render:
        # Fail on the 3rd request
        def side_effect(r):
            if r == requests[2]:
                raise RuntimeError("Failed")
            return r.output_path

        mock_render.side_effect = side_effect
        with pytest.raises(RuntimeError, match="Failed"):
            render_batch(requests, parallelism=2)

        # Verify we didn't submit all 10
        assert mock_render.call_count < 10


def test_render_batch_progress(mock_render_request):
    requests = [mock_render_request] * 3
    reporter = MagicMock(spec=ProgressReporter)

    with patch("frame_compare.render.batch.orchestrator.render_frame") as mock_render:
        mock_render.side_effect = lambda r: r.output_path
        render_batch(requests, parallelism=1, reporter=reporter)

        reporter.start_phase.assert_called_once_with("Rendering", 3)
        assert reporter.set_description.call_count == 3
        assert reporter.advance.call_count == 3
        reporter.complete_phase.assert_called_once()


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


def test_render_screenshots_from_batch_rejects_mismatched_frame_metadata(tmp_path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False), screenshots={"use_ffmpeg": True})
    ffmpeg_runner = MagicMock()
    request = ScreenshotBatchRequest(
        clip_path=Path("vid1.mkv"),
        label="vid1",
        source_frames=[42],
        display_frames=[42, 43],
        selection_labels=[None, None],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=240,
        probe_is_hdr=False,
    )

    with pytest.raises(ValueError, match="ScreenshotBatchRequest 'vid1' has mismatched lengths"):
        render_screenshots_from_batch(
            batch_requests=[request],
            output_dir=tmp_path,
            config=config,
            overlay_mode=config.screenshots.overlay_mode,
            ffmpeg_runner=ffmpeg_runner,
        )

    ffmpeg_runner.extract_frame.assert_not_called()


def test_render_screenshots_from_batch_rejects_duplicate_labels(tmp_path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False), screenshots={"use_ffmpeg": True})
    ffmpeg_runner = MagicMock()
    req1 = ScreenshotBatchRequest(
        clip_path=Path("vid1.mkv"),
        label="duplicate_label",
        source_frames=[42],
        display_frames=[42],
        selection_labels=[None],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=240,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("vid2.mkv"),
        label="duplicate_label",
        source_frames=[42],
        display_frames=[42],
        selection_labels=[None],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=240,
        probe_is_hdr=False,
    )

    with pytest.raises(
        ValueError, match="Duplicate label 'duplicate_label' detected in batch requests"
    ):
        render_screenshots_from_batch(
            batch_requests=[req1, req2],
            output_dir=tmp_path,
            config=config,
            overlay_mode=config.screenshots.overlay_mode,
            ffmpeg_runner=ffmpeg_runner,
        )

    ffmpeg_runner.extract_frame.assert_not_called()


def test_render_batch_parallel_fail_fast_no_wait() -> None:
    import time

    slow_started = Event()
    slow_finished = Event()

    requests = [
        RenderRequest(
            clip=Path("video.mkv"),
            frame_number=0,
            output_path=Path("out_0.png"),
            overlay=None,
            encoder_settings=EncoderSettings(),
        ),
        RenderRequest(
            clip=Path("video.mkv"),
            frame_number=1,
            output_path=Path("out_1.png"),
            overlay=None,
            encoder_settings=EncoderSettings(),
        ),
    ]

    # Let one task block after it starts, then fail from the other worker.
    def side_effect(r):
        if r.frame_number == 0:
            slow_started.set()
            time.sleep(0.5)
            slow_finished.set()
            return r.output_path
        assert slow_started.wait(timeout=1.0)
        raise RuntimeError("Failed immediately")

    with patch("frame_compare.render.batch.orchestrator.render_frame", side_effect=side_effect):
        with pytest.raises(RuntimeError, match="Failed immediately"):
            render_batch(requests, parallelism=2)
        assert slow_started.is_set()
        assert not slow_finished.is_set()


def test_render_screenshots_from_batch_happy_path(tmp_path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False), screenshots={"use_ffmpeg": True})
    ffmpeg_runner = MagicMock()

    req1 = ScreenshotBatchRequest(
        clip_path=Path("vid1.mkv"),
        label="label1",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=240,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("vid2.mkv"),
        label="label2",
        source_frames=[30],
        display_frames=[30],
        selection_labels=[None],
        probe_width=1280,
        probe_height=720,
        probe_num_frames=300,
        probe_is_hdr=False,
    )

    with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
        mock_batch.return_value = [
            tmp_path / "label1_00010.png",
            tmp_path / "label1_00020.png",
            tmp_path / "label2_00030.png",
        ]

        results = render_screenshots_from_batch(
            batch_requests=[req1, req2],
            output_dir=tmp_path,
            config=config,
            overlay_mode=config.screenshots.overlay_mode,
            renderer="ffmpeg",
            ffmpeg_runner=ffmpeg_runner,
        )

        assert "label1" in results
        assert "label2" in results
        assert results["label1"] == [tmp_path / "label1_00010.png", tmp_path / "label1_00020.png"]
        assert results["label2"] == [tmp_path / "label2_00030.png"]
        mock_batch.assert_called_once()


def test_render_screenshots_from_batch_renderer_auto_path(tmp_path) -> None:
    config = ConfigSchema(
        color=ColorConfig(enable_tonemap=False), screenshots={"use_ffmpeg": False}
    )
    ffmpeg_runner = MagicMock()

    req = ScreenshotBatchRequest(
        clip_path=Path("vid1.mkv"),
        label="label1",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=240,
        probe_is_hdr=False,
    )

    with patch("frame_compare.vs.loader.DefaultVSLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        mock_source = MagicMock()
        mock_source.clip = MagicMock()
        mock_source.width = 1920
        mock_source.height = 1080
        mock_source.is_hdr = False
        mock_loader.load.return_value = mock_source

        with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
            mock_batch.return_value = [tmp_path / "label1_00010.png"]

            results = render_screenshots_from_batch(
                batch_requests=[req],
                output_dir=tmp_path,
                config=config,
                overlay_mode=config.screenshots.overlay_mode,
                renderer="auto",
                ffmpeg_runner=ffmpeg_runner,
            )

            assert results["label1"] == [tmp_path / "label1_00010.png"]
            mock_loader.load.assert_called_once_with(Path("vid1.mkv"))
