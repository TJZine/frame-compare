from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.batch.orchestrator import (
    render_screenshots_from_batch,
    render_screenshots_from_batch_detailed,
)
from frame_compare.render.types import (
    BatchRenderOptions,
    EncoderSettings,
    RenderedBatchResult,
    RenderedClipFacts,
    RenderedFrameResult,
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
        source_frames=source_frames,
        comparison_frames=comparison_frames or source_frames,
        selection_labels=[None] * len(source_frames),
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
        tonemap_settings=None,
        geometry=geometry,
    )


def _expanded(
    tmp_path: Path, requests: list[ScreenshotBatchRequest]
) -> tuple[list[RenderRequest], dict[str, range], dict[str, RenderedClipFacts]]:
    render_requests: list[RenderRequest] = []
    ranges: dict[str, range] = {}
    facts: dict[str, RenderedClipFacts] = {}
    offset = 0
    for request in requests:
        ranges[request.label] = range(offset, offset + len(request.source_frames))
        facts[request.label] = _clip_facts(*request.source_resolution)
        for frame in request.source_frames:
            render_requests.append(
                RenderRequest(
                    clip=request.clip_path,
                    diagnostic_source=request.clip_path,
                    frame_number=frame,
                    output_path=tmp_path / f"{request.label}-{frame}.png",
                    overlay=None,
                    encoder_settings=EncoderSettings(),
                )
            )
        offset += len(request.source_frames)
    return render_requests, ranges, facts


def _rendered(requests: list[RenderRequest]) -> list[RenderedFrameResult]:
    return [
        RenderedFrameResult(
            path=request.output_path,
            facts=RenderedFrameFacts(source_frame=request.frame_number),
        )
        for request in requests
    ]


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
            "frame_compare.render.batch.orchestrator.render_batch_detailed",
            return_value=_rendered(expanded[0]),
        ) as render_batch,
    ):
        result = render_screenshots_from_batch(
            requests,
            tmp_path,
            config,
            BatchRenderOptions(renderer="ffmpeg", ffmpeg_runner=MagicMock()),
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
    rendered = _rendered(expanded[0])
    with (
        patch(
            "frame_compare.render.batch.orchestrator.expand_batch_render_requests",
            return_value=expanded,
        ),
        patch(
            "frame_compare.render.batch.orchestrator.render_batch_detailed",
            return_value=rendered,
        ),
    ):
        result = render_screenshots_from_batch_detailed(requests, tmp_path, config)

    assert [fact.source_frame for fact in result.frame_facts_by_label["label1"]] == [10, 20]
    assert [fact.source_frame for fact in result.frame_facts_by_label["label2"]] == [30]
    assert result.clip_facts_by_label == expanded[2]


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
            "frame_compare.render.batch.orchestrator.render_batch_detailed",
            return_value=_rendered(expanded[0]),
        ) as render_batch,
    ):
        render_screenshots_from_batch(
            [request],
            tmp_path,
            config,
            BatchRenderOptions(
                renderer="ffmpeg", ffmpeg_runner=MagicMock(), parallelism=parallelism
            ),
        )
    assert render_batch.call_args.kwargs["parallelism"] == expected
    assert render_batch.call_args.kwargs["work_unit_ranges"] == [range(0, 1)]


def test_render_screenshots_from_batch_constructs_configured_default_runner(
    tmp_path: Path,
) -> None:
    config = ConfigSchema(
        color=ColorConfig(enable_tonemap=False),
        screenshots={"ffmpeg_timeout_seconds": 47.0},
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
            "frame_compare.render.batch.orchestrator.render_batch_detailed",
            return_value=_rendered(expanded[0]),
        ),
    ):
        render_screenshots_from_batch([request], tmp_path, config)
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
            "frame_compare.render.batch.orchestrator.render_batch_detailed",
            return_value=_rendered(expanded[0]),
        ),
    ):
        render_screenshots_from_batch(
            [request], tmp_path, config, BatchRenderOptions(ffmpeg_runner=injected)
        )
    default_runner.assert_not_called()


def test_render_screenshots_from_batch_rejects_hdr_ffmpeg_tonemap(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=True))
    request = _batch_request("vid.mkv", "vid", [42], is_hdr=True)
    with pytest.raises(TonemapRequiresVapourSynthError):
        render_screenshots_from_batch(
            [request], tmp_path, config, BatchRenderOptions(renderer="ffmpeg")
        )


def test_render_screenshots_from_batch_rejects_mismatched_lengths(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    request = _batch_request("vid.mkv", "vid", [42], comparison_frames=[42, 43])
    with pytest.raises(ValueError, match="list lengths differ"):
        render_screenshots_from_batch([request], tmp_path, config)


def test_render_screenshots_from_batch_requires_positive_source_facts(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    request = _batch_request("vid.mkv", "vid", [42])
    request = replace(
        request,
        source_resolution=(0, 0),
        active_picture=ActivePictureFacts(0, 0, 1, 1, "full_frame", False),
    )
    with pytest.raises(ValueError, match="requires positive source dimensions"):
        render_screenshots_from_batch([request], tmp_path, config)


def test_render_screenshots_from_batch_rejects_duplicate_labels(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    requests = [_batch_request("a.mkv", "same", [1]), _batch_request("b.mkv", "same", [2])]
    with pytest.raises(ValueError, match="Duplicate label 'same'"):
        render_screenshots_from_batch(requests, tmp_path, config)


def test_render_screenshots_from_batch_empty_returns_empty(tmp_path: Path) -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    assert render_screenshots_from_batch([], tmp_path, config) == {}
    assert render_screenshots_from_batch_detailed([], tmp_path, config) == RenderedBatchResult()
