from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import (
    OverlayMode,
    ScreenshotActiveRectDetection,
    ScreenshotGeometryMode,
)
from frame_compare.config.schema_models import ScreenshotsConfig
from frame_compare.render.batch.expansion import expand_batch_render_requests
from frame_compare.render.types import PreparedRenderSource, ScreenshotBatchRequest
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    SourceSignalFacts,
)


def _batch(
    label: str,
    width: int,
    height: int,
    *,
    active: ActivePictureFacts | None = None,
) -> ScreenshotBatchRequest:
    return ScreenshotBatchRequest(
        clip_path=Path(f"{label}.mkv"),
        label=label,
        source_frames=[10],
        comparison_frames=[10],
        selection_labels=[None],
        size_bytes=1,
        source_resolution=(width, height),
        source_total_frames=100,
        signal=SourceSignalFacts(is_hdr=False),
        active_picture=active or ActivePictureFacts(0, 0, width, height, "full_frame", True),
    )


def _prepared(width: int, height: int) -> PreparedRenderSource:
    return PreparedRenderSource(
        diagnostic_source=MagicMock(name="source"),
        prepared_clip=MagicMock(name="prepared"),
        source_dimensions=(width, height),
        source_total_frames=100,
        source_is_hdr=False,
        presentation_state=PresentationState.SDR,
        tonemap=None,
    )


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_geometry_facts_preserve_native_active_picture_without_transform(
    mock_prepare: MagicMock,
) -> None:
    mock_prepare.return_value = _prepared(1920, 1080)
    supplied = ActivePictureFacts(0, 140, 1920, 800, "content_derived", False)
    requests, _, clip_facts = expand_batch_render_requests(
        [_batch("ref", 1920, 1080, active=supplied)],
        output_dir=Path("out"),
        config=ConfigSchema(
            screenshots=ScreenshotsConfig(geometry_mode=ScreenshotGeometryMode.NATIVE)
        ),
        overlay_mode=OverlayMode.DIAGNOSTIC,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    facts = clip_facts["ref"].geometry
    assert facts.active_picture == supplied
    assert facts.is_noop
    assert facts.source_size == (1920, 1080)
    assert facts.cropped_size == (1920, 1080)
    assert facts.scaled_size == (1920, 1080)
    assert facts.final_canvas_size == (1920, 1080)
    assert requests[0].overlay is not None
    assert requests[0].overlay.geometry is facts


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_geometry_facts_capture_aligned_active_picture_and_canvas(mock_prepare: MagicMock) -> None:
    mock_prepare.side_effect = [_prepared(1920, 1080), _prepared(1440, 1080)]
    config = ConfigSchema(
        screenshots=ScreenshotsConfig(geometry_mode=ScreenshotGeometryMode.ALIGNED)
    )
    requests, _, facts = expand_batch_render_requests(
        [_batch("wide", 1920, 1080), _batch("narrow", 1440, 1080)],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    assert all(request.geometry_plan is not None for request in requests)
    assert facts["wide"].geometry.final_canvas_size == (1920, 1080)
    assert facts["wide"].geometry.is_noop is True
    assert facts["narrow"].geometry.final_canvas_size == (1920, 1080)
    assert facts["narrow"].geometry.is_noop is False
    assert requests[0].overlay is not None
    assert requests[0].overlay.geometry.final_canvas_size == (1920, 1080)


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_supplied_active_picture_wins_over_config_detection(mock_prepare: MagicMock) -> None:
    mock_prepare.side_effect = [_prepared(1920, 1080), _prepared(1440, 1080)]
    supplied = ActivePictureFacts(160, 0, 1600, 1080, "explicit", False)
    config = ConfigSchema(
        screenshots=ScreenshotsConfig(
            active_rect_detection=ScreenshotActiveRectDetection.ASPECT_RATIO,
            geometry_mode=ScreenshotGeometryMode.ALIGNED,
        )
    )
    requests, _, facts = expand_batch_render_requests(
        [
            _batch("wide", 1920, 1080, active=supplied),
            _batch("narrow", 1440, 1080),
        ],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    geometry = facts["wide"].geometry
    assert geometry.active_picture == supplied
    assert geometry.final_canvas_size == (1600, 1080)
    assert requests[0].geometry_plan is not None
    assert requests[0].geometry_plan.provenance == "explicit"


def test_prepared_dimensions_cannot_silently_replace_active_picture_bounds() -> None:
    from frame_compare.render.errors import RenderError

    request = _batch("oversized", 1920, 1080)
    with (
        patch(
            "frame_compare.render.batch.expansion.prepare_clip_for_render",
            return_value=_prepared(1280, 720),
        ),
        pytest.raises(RenderError, match="outside prepared source dimensions"),
    ):
        expand_batch_render_requests(
            [request],
            output_dir=Path("out"),
            config=ConfigSchema(),
            overlay_mode=OverlayMode.NONE,
            renderer="vapoursynth",
            ffmpeg_runner=MagicMock(),
        )
