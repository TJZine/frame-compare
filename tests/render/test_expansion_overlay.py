from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import OverlayMode
from frame_compare.render.batch.expansion import expand_batch_render_requests
from frame_compare.render.types import PreparedRenderSource, ScreenshotBatchRequest
from frame_compare.utils.media_facts import ActivePictureFacts, PresentationState, SourceSignalFacts


def _request() -> ScreenshotBatchRequest:
    return ScreenshotBatchRequest(
        clip_path=Path("source.mkv"),
        label="CtrlHD",
        source_frames=[1855],
        comparison_frames=[1842],
        selection_labels=["Bright"],
        size_bytes=int(17.42 * 1024**3),
        source_resolution=(3840, 2160),
        source_total_frames=143892,
        signal=SourceSignalFacts(is_hdr=False),
        active_picture=ActivePictureFacts(0, 0, 3840, 2160, "full_frame", True),
    )


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_overlay_config_contains_structured_facts_and_original_diagnostic_source(
    mock_prepare: MagicMock,
) -> None:
    original = MagicMock(name="decoded_source")
    prepared_graph = MagicMock(name="prepared_graph")
    mock_prepare.return_value = PreparedRenderSource(
        diagnostic_source=original,
        prepared_clip=prepared_graph,
        source_dimensions=(3840, 2160),
        source_total_frames=143892,
        source_is_hdr=False,
        presentation_state=PresentationState.SDR,
        tonemap_settings=None,
    )
    requests, _, facts = expand_batch_render_requests(
        [_request()],
        output_dir=Path("out"),
        config=ConfigSchema(),
        overlay_mode=OverlayMode.DIAGNOSTIC,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    request = requests[0]
    assert request.clip is prepared_graph
    assert request.diagnostic_source is original
    assert request.overlay is not None
    assert request.overlay.label == "CtrlHD"
    assert request.overlay.comparison_frame == 1842
    assert request.overlay.source_frame == 1855
    assert request.overlay.source_total_frames == 143892
    assert request.overlay.file_size_bytes == int(17.42 * 1024**3)
    assert request.overlay.geometry is facts["CtrlHD"].geometry


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_none_overlay_mode_does_not_create_overlay_config(mock_prepare: MagicMock) -> None:
    source = MagicMock()
    mock_prepare.return_value = PreparedRenderSource(
        diagnostic_source=source,
        prepared_clip=source,
        source_dimensions=(1920, 1080),
        source_total_frames=143892,
        source_is_hdr=False,
        presentation_state=PresentationState.SDR,
        tonemap_settings=None,
    )
    requests, _, _ = expand_batch_render_requests(
        [_request()],
        output_dir=Path("out"),
        config=ConfigSchema(),
        overlay_mode=OverlayMode.NONE,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    assert requests[0].overlay is None
