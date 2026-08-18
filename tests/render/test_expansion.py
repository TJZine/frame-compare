from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import OverlayMode
from frame_compare.render.batch.expansion import (
    expand_batch_render_requests,
    render_batch_results_by_label,
    validate_batch_requests,
)
from frame_compare.render.types import PreparedRenderSource, ScreenshotBatchRequest
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    SourceSignalFacts,
)


def _request(label: str = "ref") -> ScreenshotBatchRequest:
    return ScreenshotBatchRequest(
        clip_path=Path(f"{label}.mkv"),
        label=label,
        source_frames=[10, 20],
        comparison_frames=[12, 22],
        selection_labels=["Dark", "Bright"],
        size_bytes=100,
        source_resolution=(1920, 1080),
        source_total_frames=100,
        signal=SourceSignalFacts(is_hdr=False),
        active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
    )


def _prepared(*, state: PresentationState = PresentationState.SDR) -> PreparedRenderSource:
    original = MagicMock(name="original")
    return PreparedRenderSource(
        diagnostic_source=original,
        prepared_clip=MagicMock(name="prepared"),
        source_dimensions=(1920, 1080),
        source_total_frames=101,
        source_is_hdr=state != PresentationState.SDR,
        presentation_state=state,
        tonemap_settings=None,
    )


def test_validate_batch_requests_rejects_duplicate_labels_and_outputs() -> None:
    with pytest.raises(ValueError, match="Duplicate label"):
        validate_batch_requests([_request(), _request()])

    duplicate = replace(_request(), comparison_frames=[12, 12])
    with pytest.raises(ValueError, match="Duplicate screenshot output"):
        validate_batch_requests([duplicate])


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expansion_preserves_source_mapping_and_prepared_source(
    mock_prepare: MagicMock,
) -> None:
    prepared = _prepared()
    mock_prepare.return_value = prepared
    batch = _request()
    requests, ranges, facts = expand_batch_render_requests(
        [batch],
        output_dir=Path("out"),
        config=ConfigSchema(),
        overlay_mode=OverlayMode.NONE,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )

    assert [request.frame_number for request in requests] == [10, 20]
    assert [request.output_path.name for request in requests] == [
        "12 - ref.png",
        "22 - ref.png",
    ]
    assert all(request.diagnostic_source is prepared.diagnostic_source for request in requests)
    assert all(request.clip is prepared.prepared_clip for request in requests)
    assert mock_prepare.call_args.kwargs["source_is_hdr"] is False
    assert ranges == {"ref": range(0, 2)}
    assert facts["ref"].source_total_frames == 101
    assert facts["ref"].presentation_state is PresentationState.SDR


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expansion_uses_actual_preparation_state_and_overlay_facts(
    mock_prepare: MagicMock,
) -> None:
    prepared = _prepared(state=PresentationState.HDR_TONEMAP_OFF)
    mock_prepare.return_value = prepared
    batch = _request()
    batch = replace(batch, signal=SourceSignalFacts(is_hdr=True))
    requests, _, facts = expand_batch_render_requests(
        [batch],
        output_dir=Path("out"),
        config=ConfigSchema(),
        overlay_mode=OverlayMode.DIAGNOSTIC,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    assert facts["ref"].presentation_state is PresentationState.HDR_TONEMAP_OFF
    assert requests[0].overlay is not None
    assert requests[0].overlay.presentation_state is PresentationState.HDR_TONEMAP_OFF
    assert requests[0].overlay.source_frame == 10
    assert requests[0].overlay.comparison_frame == 12


def test_render_batch_results_by_label_preserves_order() -> None:
    requests = [_request("a"), _request("b")]
    paths = [Path("a0"), Path("a1"), Path("b0"), Path("b1")]
    assert render_batch_results_by_label(requests, paths, {"a": range(0, 2), "b": range(2, 4)}) == {
        "a": paths[:2],
        "b": paths[2:],
    }
