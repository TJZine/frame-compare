from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema, ScreenshotsConfig
from frame_compare.render.batch.orchestrator import (
    render_screenshots_from_batch_detailed,
)
from frame_compare.render.types import (
    BatchRenderOptions,
    EncoderSettings,
    PreparedClipRender,
    RenderedClip,
    RenderedClipFacts,
    RenderedFrameResult,
    RenderedScreenshot,
    RenderRequest,
    ScreenshotBatchRequest,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.vs.errors import TonemapRequiresVapourSynthError
from tests.render_test_support import facts_by_label, paths_by_label, selections


def _batch_request(
    path: str,
    label: str,
    source_frames: list[int],
    comparison_frames: list[int] | None = None,
    *,
    width: int = 1920,
    height: int = 1080,
    total_frames: int | None = 240,
    is_hdr: bool = False,
) -> ScreenshotBatchRequest:
    return ScreenshotBatchRequest(
        clip_path=Path(path),
        label=label,
        frames=selections(
            source_frames, comparison_frames or source_frames, [None] * len(source_frames)
        ),
        size_bytes=0,
        source_resolution=(width, height),
        source_total_frames=total_frames,
        signal=SourceSignalFacts(is_hdr=is_hdr),
        active_picture=ActivePictureFacts(0, 0, width, height, "full_frame", True),
    )


def _clip_facts(width: int = 1920, height: int = 1080) -> RenderedClipFacts:
    geometry = RenderedGeometryFacts(
        source_size=(width, height),
        active_picture=ActivePictureFacts(0, 0, width, height, "full_frame", True),
        cropped_size=(width, height),
        scaled_size=(width, height),
        final_canvas_size=(width, height),
        is_noop=True,
    )
    return RenderedClipFacts(
        size_bytes=0,
        source_resolution=(width, height),
        source_total_frames=240,
        signal=SourceSignalFacts(is_hdr=False),
        presentation_state=PresentationState.SDR,
        tonemap=None,
        geometry=geometry,
    )


def _expanded(
    tmp_path: Path, batches: list[ScreenshotBatchRequest]
) -> tuple[PreparedClipRender, ...]:
    return tuple(
        PreparedClipRender(
            batch.label,
            _clip_facts(*batch.source_resolution),
            batch.frames,
            tuple(
                RenderRequest(
                    clip=batch.clip_path,
                    diagnostic_source=batch.clip_path,
                    frame_number=selection.source_frame,
                    output_path=tmp_path / f"{batch.label}-{selection.source_frame}.png",
                    overlay=None,
                    encoder_settings=EncoderSettings(),
                )
                for selection in batch.frames
            ),
        )
        for batch in batches
    )


def _rendered(jobs: tuple[PreparedClipRender, ...]) -> tuple[RenderedClip, ...]:
    return tuple(
        RenderedClip(
            job.label,
            job.clip_facts,
            tuple(
                RenderedScreenshot(
                    selection,
                    RenderedFrameResult(
                        request.output_path, RenderedFrameFacts(selection.source_frame)
                    ),
                )
                for selection, request in zip(job.frames, job.requests, strict=True)
            ),
        )
        for job in jobs
    )


def test_render_screenshots_from_batch_happy_path(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    requests = [
        _batch_request("vid1.mkv", "label1", [10, 20]),
        _batch_request("vid2.mkv", "label2", [30], width=1280, height=720),
    ]
    expanded = _expanded(tmp_path, requests)
    with (
        patch(
            "frame_compare.render.batch.orchestrator.expand_batch_render_requests",
            return_value=expanded,
        ),
        patch(
            "frame_compare.render.batch.orchestrator.render_clip_jobs",
            return_value=_rendered(expanded),
        ) as render_batch,
    ):
        result = paths_by_label(
            render_screenshots_from_batch_detailed(
                requests,
                tmp_path,
                config,
                BatchRenderOptions(renderer="ffmpeg", ffmpeg_runner=MagicMock()),
            )
        )
    assert result == {
        "label1": [tmp_path / "label1-10.png", tmp_path / "label1-20.png"],
        "label2": [tmp_path / "label2-30.png"],
    }
    assert render_batch.call_args.kwargs["parallelism"] == 1


def test_render_screenshots_from_batch_detailed_preserves_fact_slices_and_clip_mapping(
    tmp_path: Path,
) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    requests = [
        _batch_request("vid1.mkv", "label1", [10, 20]),
        _batch_request("vid2.mkv", "label2", [30], width=1280, height=720),
    ]
    expanded = _expanded(tmp_path, requests)
    with (
        patch(
            "frame_compare.render.batch.orchestrator.expand_batch_render_requests",
            return_value=expanded,
        ),
        patch(
            "frame_compare.render.batch.orchestrator.render_frame_detailed",
            side_effect=lambda request: RenderedFrameResult(
                request.output_path, RenderedFrameFacts(request.frame_number, "B")
            ),
        ),
    ):
        result = render_screenshots_from_batch_detailed(requests, tmp_path, config)

    assert [fact.source_frame for fact in facts_by_label(result)["label1"]] == [10, 20]
    assert [fact.source_frame for fact in facts_by_label(result)["label2"]] == [30]
    assert {clip.label: clip.clip_facts for clip in result} == {
        job.label: job.clip_facts for job in expanded
    }


@pytest.mark.parametrize("parallelism, expected", [(2, 2), (0, 1)])
def test_render_screenshots_from_batch_passes_clamped_parallelism(
    tmp_path: Path, parallelism: int, expected: int
) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    request = _batch_request("vid.mkv", "label", [10])
    expanded = _expanded(tmp_path, [request])
    with (
        patch(
            "frame_compare.render.batch.orchestrator.expand_batch_render_requests",
            return_value=expanded,
        ),
        patch(
            "frame_compare.render.batch.orchestrator.render_clip_jobs",
            return_value=_rendered(expanded),
        ) as render_batch,
    ):
        render_screenshots_from_batch_detailed(
            [request],
            tmp_path,
            config,
            BatchRenderOptions(
                renderer="ffmpeg", ffmpeg_runner=MagicMock(), parallelism=parallelism
            ),
        )
    assert render_batch.call_args.kwargs["parallelism"] == expected
    assert render_batch.call_args.args[0] == expanded


def test_render_screenshots_from_batch_constructs_configured_default_runner(
    tmp_path: Path,
) -> None:
    config = ConfigSchema(
        color=ColorConfig(enable_tonemap=False),
        screenshots=ScreenshotsConfig(ffmpeg_timeout_seconds=47.0),
    )
    request = _batch_request("clip.mkv", "clip", [1])
    expanded = _expanded(tmp_path, [request])
    with (
        patch(
            "frame_compare.render.batch.expansion.DefaultFFmpegRunner",
            return_value=MagicMock(),
        ) as default_runner,
        patch(
            "frame_compare.render.batch.orchestrator.expand_batch_render_requests",
            return_value=expanded,
        ) as expand_batch,
        patch(
            "frame_compare.render.batch.orchestrator.render_clip_jobs",
            return_value=_rendered(expanded),
        ),
    ):
        render_screenshots_from_batch_detailed([request], tmp_path, config)
    default_runner.assert_called_once_with(extraction_timeout_seconds=47.0)
    assert expand_batch.call_args.kwargs["ffmpeg_runner"] is default_runner.return_value


def test_render_screenshots_from_batch_preserves_injected_runner(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    request = _batch_request("clip.mkv", "clip", [1])
    expanded = _expanded(tmp_path, [request])
    injected = MagicMock()
    with (
        patch("frame_compare.render.batch.expansion.DefaultFFmpegRunner") as default_runner,
        patch(
            "frame_compare.render.batch.orchestrator.expand_batch_render_requests",
            return_value=expanded,
        ),
        patch(
            "frame_compare.render.batch.orchestrator.render_clip_jobs",
            return_value=_rendered(expanded),
        ),
    ):
        render_screenshots_from_batch_detailed(
            [request], tmp_path, config, BatchRenderOptions(ffmpeg_runner=injected)
        )
    default_runner.assert_not_called()


def test_render_screenshots_from_batch_rejects_hdr_ffmpeg_tonemap(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=True))
    request = _batch_request("vid.mkv", "vid", [42], is_hdr=True)
    with pytest.raises(TonemapRequiresVapourSynthError):
        render_screenshots_from_batch_detailed(
            [request], tmp_path, config, BatchRenderOptions(renderer="ffmpeg")
        )


def test_render_screenshots_from_batch_requires_positive_source_facts(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    request = _batch_request("vid.mkv", "vid", [42])
    request = replace(
        request,
        source_resolution=(0, 0),
        active_picture=ActivePictureFacts(0, 0, 1, 1, "full_frame", False),
    )
    with pytest.raises(ValueError, match="requires positive source dimensions"):
        render_screenshots_from_batch_detailed([request], tmp_path, config)


def test_real_ffmpeg_batch_result_is_paired_with_selected_source_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PIL import Image

    from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
    from frame_compare.render.batch.orchestrator import render_clip_jobs
    from tests.render_test_support import prepared_jobs

    calls: list[list[int]] = []

    def extract(_self, _video, frames, output_dir, **_kwargs):
        calls.append(frames)
        for index in range(len(frames)):
            Image.new("RGB", (2, 2)).save(output_dir / f"{index:09d}.png")
        return [
            RenderedFrameFacts(source_frame=99, picture_type="I"),
            RenderedFrameFacts(source_frame=2, picture_type="P"),
        ]

    monkeypatch.setattr(DefaultFFmpegRunner, "extract_frames", extract)
    runner = DefaultFFmpegRunner()
    requests = tuple(
        RenderRequest(
            Path("clip.mkv"),
            Path("clip.mkv"),
            frame,
            tmp_path / f"{frame}.png",
            None,
            EncoderSettings(),
            runner,
        )
        for frame in (1, 2)
    )
    with pytest.raises(ValueError, match="rendered source frame differs"):
        render_clip_jobs(prepared_jobs(requests))
    assert calls == [[1, 2]]
    assert not list(tmp_path.glob(".frame-compare-ffmpeg-*"))
