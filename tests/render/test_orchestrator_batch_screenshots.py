from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.batch.orchestrator import (
    render_screenshots_from_batch,
)
from frame_compare.render.types import (
    BatchRenderOptions,
    ScreenshotBatchRequest,
)
from frame_compare.vs.errors import (
    TonemapRequiresVapourSynthError,
)


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
            options=BatchRenderOptions(
                overlay_mode=config.screenshots.overlay_mode,
                renderer="ffmpeg",
                ffmpeg_runner=ffmpeg_runner,
            ),
        )

        assert "label1" in results
        assert "label2" in results
        assert results["label1"] == [tmp_path / "label1_00010.png", tmp_path / "label1_00020.png"]
        assert results["label2"] == [tmp_path / "label2_00030.png"]
        mock_batch.assert_called_once()
        assert mock_batch.call_args.kwargs["parallelism"] == 1


def test_render_screenshots_from_batch_passes_internal_parallelism(tmp_path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False), screenshots={"use_ffmpeg": True})
    ffmpeg_runner = MagicMock()

    request = ScreenshotBatchRequest(
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

    with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
        mock_batch.return_value = [tmp_path / "label1_00010.png"]

        render_screenshots_from_batch(
            batch_requests=[request],
            output_dir=tmp_path,
            config=config,
            options=BatchRenderOptions(
                renderer="ffmpeg",
                ffmpeg_runner=ffmpeg_runner,
                parallelism=2,
            ),
        )

        assert mock_batch.call_args.kwargs["parallelism"] == 2


def test_render_screenshots_from_batch_clamps_internal_parallelism_to_one(tmp_path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False), screenshots={"use_ffmpeg": True})
    ffmpeg_runner = MagicMock()

    request = ScreenshotBatchRequest(
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

    with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
        mock_batch.return_value = [tmp_path / "label1_00010.png"]

        render_screenshots_from_batch(
            batch_requests=[request],
            output_dir=tmp_path,
            config=config,
            options=BatchRenderOptions(
                renderer="ffmpeg",
                ffmpeg_runner=ffmpeg_runner,
                parallelism=0,
            ),
        )

        assert mock_batch.call_args.kwargs["parallelism"] == 1


def test_render_screenshots_from_batch_rejects_unknown_hdr_for_ffmpeg_tonemap(
    tmp_path: Path,
) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=True), screenshots={"use_ffmpeg": True})
    ffmpeg_runner = MagicMock()
    request = ScreenshotBatchRequest(
        clip_path=Path("vid1.mkv"),
        label="vid1",
        source_frames=[42],
        display_frames=[42],
        selection_labels=[None],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=240,
        probe_is_hdr=None,
    )

    with pytest.raises(TonemapRequiresVapourSynthError):
        render_screenshots_from_batch(
            batch_requests=[request],
            output_dir=tmp_path,
            config=config,
            options=BatchRenderOptions(
                overlay_mode=config.screenshots.overlay_mode,
                renderer="ffmpeg",
                ffmpeg_runner=ffmpeg_runner,
            ),
        )

    ffmpeg_runner.extract_frame.assert_not_called()


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
                options=BatchRenderOptions(
                    overlay_mode=config.screenshots.overlay_mode,
                    renderer="auto",
                    ffmpeg_runner=ffmpeg_runner,
                ),
            )

            assert results["label1"] == [tmp_path / "label1_00010.png"]
            mock_loader.load.assert_called_once_with(Path("vid1.mkv"))


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
            options=BatchRenderOptions(
                overlay_mode=config.screenshots.overlay_mode,
                ffmpeg_runner=ffmpeg_runner,
            ),
        )

    ffmpeg_runner.extract_frame.assert_not_called()


def test_render_screenshots_from_batch_rejects_known_out_of_range_source_frame(
    tmp_path: Path,
) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False), screenshots={"use_ffmpeg": True})
    ffmpeg_runner = MagicMock()
    request = ScreenshotBatchRequest(
        clip_path=Path("vid1.mkv"),
        label="vid1",
        source_frames=[240],
        display_frames=[999],
        selection_labels=[None],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=240,
        probe_is_hdr=False,
    )

    with patch("frame_compare.render.batch.orchestrator.render_batch") as mock_batch:
        with pytest.raises(
            ValueError,
            match=(
                "ScreenshotBatchRequest 'vid1' requested source frame 240 "
                "outside valid range 0..239 for vid1.mkv"
            ),
        ):
            render_screenshots_from_batch(
                batch_requests=[request],
                output_dir=tmp_path,
                config=config,
                options=BatchRenderOptions(
                    overlay_mode=config.screenshots.overlay_mode,
                    renderer="ffmpeg",
                    ffmpeg_runner=ffmpeg_runner,
                ),
            )

        mock_batch.assert_not_called()
    ffmpeg_runner.extract_frame.assert_not_called()


def test_render_screenshots_from_batch_rejects_duplicate_output_names_after_sanitization(
    tmp_path: Path,
) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False), screenshots={"use_ffmpeg": True})
    ffmpeg_runner = MagicMock()
    req1 = ScreenshotBatchRequest(
        clip_path=Path("vid1.mkv"),
        label="A B",
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
        label="A_B",
        source_frames=[42],
        display_frames=[42],
        selection_labels=[None],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=240,
        probe_is_hdr=False,
    )

    with pytest.raises(ValueError, match="Duplicate screenshot output 'A_B_00042.png'"):
        render_screenshots_from_batch(
            batch_requests=[req1, req2],
            output_dir=tmp_path,
            config=config,
            options=BatchRenderOptions(
                overlay_mode=config.screenshots.overlay_mode,
                ffmpeg_runner=ffmpeg_runner,
            ),
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
            options=BatchRenderOptions(
                overlay_mode=config.screenshots.overlay_mode,
                ffmpeg_runner=ffmpeg_runner,
            ),
        )

    ffmpeg_runner.extract_frame.assert_not_called()
