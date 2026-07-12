"""Tests for overlay population during batch-request expansion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema, ScreenshotsConfig
from frame_compare.config.schema_enums import ScreenshotGeometryMode
from frame_compare.render.batch.expansion import expand_batch_render_requests
from frame_compare.render.types import (
    OverlayDiagnosticMetadata,
    OverlayDolbyVisionMetadata,
    OverlayFrameMeasurement,
    OverlayMode,
    OverlaySelectionDetail,
    ScreenshotBatchRequest,
)


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_populates_overlay_config(mock_prepare: MagicMock) -> None:
    detail = OverlaySelectionDetail(
        frame_index=10,
        label="User",
        source="analysis",
        timecode="00:00:00.417",
        clip_role="analyze",
    )
    diagnostic_metadata = OverlayDiagnosticMetadata(
        max_cll=1000,
        color_range="limited",
        dolby_vision=OverlayDolbyVisionMetadata(rpu_present=True),
        measurement=OverlayFrameMeasurement(avg_nits=150.0, max_nits=150.0, category="User"),
    )
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="Reference",
        source_frames=[10],
        display_frames=[10],
        selection_labels=["A"],
        selection_details=[detail],
        diagnostic_metadata=[diagnostic_metadata],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
        filename_label="ref",
    )

    source_info = MagicMock()
    source_info.width = 1920
    source_info.height = 1080
    source_info.num_frames = 100
    source_info.is_hdr = True
    mock_prepare.return_value = (MagicMock(name="clip"), None, "HDR10", source_info)
    config = ConfigSchema(color=ColorConfig(enable_tonemap=True))
    ffmpeg_runner = MagicMock()

    none_requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.NONE,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )
    assert none_requests[0].overlay is None

    standard_requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )
    overlay = standard_requests[0].overlay

    assert overlay is not None
    assert overlay.mode == OverlayMode.STANDARD
    assert overlay.label == "Reference"
    assert overlay.burn_in_label == "ref"
    assert overlay.frame_number == 10
    assert overlay.display_frame_number == 10
    assert overlay.selection_label == "User"
    assert overlay.selection_detail == detail
    assert overlay.diagnostic_metadata == diagnostic_metadata
    assert overlay.resolution == (1920, 1080)
    assert overlay.resolution_summary == "1920 × 1080  (native)"
    assert overlay.hdr_info == "HDR10"
    assert overlay.base_text == "Tonemapping Algorithm: bt2390 dpd = 1 dst = 100 nits"
    assert overlay.num_frames == 100
    assert overlay.include_frame_number is True


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests(mock_prepare: MagicMock) -> None:
    config = ConfigSchema(
        screenshots=ScreenshotsConfig(geometry_mode=ScreenshotGeometryMode.NATIVE)
    )
    ffmpeg_runner = MagicMock()

    ref_clip = MagicMock(name="ref_clip")
    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = True
    enc_clip = MagicMock(name="enc_clip")
    mock_prepare.side_effect = [
        (ref_clip, None, "HDR10", ref_source_info),
        (enc_clip, None, None, None),
    ]
    ref_details = [
        OverlaySelectionDetail(
            frame_index=10,
            label="User",
            source="analysis",
            timecode="00:00:00.417",
            clip_role="analyze",
        ),
        OverlaySelectionDetail(
            frame_index=20,
            label="Cached",
            source="analysis",
            timecode="00:00:00.833",
            clip_role="analyze",
        ),
    ]
    ref_diagnostics = [
        OverlayDiagnosticMetadata(
            max_cll=1000,
            color_range="limited",
            measurement=OverlayFrameMeasurement(avg_nits=150.0, max_nits=150.0, category="User"),
        ),
        OverlayDiagnosticMetadata(
            max_cll=900,
            color_range="limited",
            measurement=OverlayFrameMeasurement(avg_nits=120.0, max_nits=120.0, category="Cached"),
        ),
    ]
    enc_detail = OverlaySelectionDetail(
        frame_index=30,
        label="Motion",
        source="analysis",
        timecode="00:00:01.250",
        clip_role="analyze",
    )
    enc_diagnostic = OverlayDiagnosticMetadata(
        max_cll=600,
        color_range="full",
        measurement=OverlayFrameMeasurement(avg_nits=80.0, max_nits=80.0, category="Motion"),
    )

    req1 = ScreenshotBatchRequest(
        clip_path=Path("video1.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=["A", "B"],
        selection_details=ref_details,
        diagnostic_metadata=ref_diagnostics,
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=True,
        filename_label="ref",
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("video2.mkv"),
        label="Encode 1",
        source_frames=[30],
        display_frames=[30],
        selection_labels=["C"],
        selection_details=[enc_detail],
        diagnostic_metadata=[enc_diagnostic],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
        filename_label="enc",
    )

    requests, label_to_range = expand_batch_render_requests(
        [req1, req2],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    assert len(requests) == 3
    assert label_to_range == {
        "Reference": range(0, 2),
        "Encode 1": range(2, 3),
    }
    prepared_paths = [args[0] for args, _kwargs in mock_prepare.call_args_list]
    assert prepared_paths == [Path("video1.mkv"), Path("video2.mkv")]
    assert all(
        kwargs["ffmpeg_runner"] is ffmpeg_runner for _args, kwargs in mock_prepare.call_args_list
    )

    # Verify requests
    assert requests[0].clip is ref_clip
    assert requests[0].frame_number == 10
    assert requests[0].output_path == Path("out/10 - ref.png")
    first_overlay = requests[0].overlay
    assert first_overlay is not None
    assert first_overlay.label == "Reference"
    assert first_overlay.burn_in_label == "ref"
    assert first_overlay.frame_number == 10
    assert first_overlay.display_frame_number == 10
    assert first_overlay.selection_label == "User"
    assert first_overlay.selection_detail == ref_details[0]
    assert first_overlay.diagnostic_metadata == ref_diagnostics[0]
    assert first_overlay.resolution == (1920, 1080)
    assert first_overlay.resolution_summary == "1920 × 1080  (native)"
    assert first_overlay.origin is None
    assert first_overlay.hdr_info == "HDR10"
    assert first_overlay.base_text == "Tonemapping Algorithm: bt2390 dpd = 1 dst = 100 nits"
    assert first_overlay.num_frames == 150
    assert requests[0].geometry_plan is None

    assert requests[1].frame_number == 20
    assert requests[1].output_path == Path("out/20 - ref.png")
    second_overlay = requests[1].overlay
    assert second_overlay is not None
    assert second_overlay.selection_label == "Cached"
    assert second_overlay.selection_detail == ref_details[1]
    assert second_overlay.diagnostic_metadata == ref_diagnostics[1]
    assert second_overlay.base_text == "Tonemapping Algorithm: bt2390 dpd = 1 dst = 100 nits"

    assert requests[2].clip is enc_clip
    assert requests[2].frame_number == 30
    assert requests[2].output_path == Path("out/30 - enc.png")
    third_overlay = requests[2].overlay
    assert third_overlay is not None
    assert third_overlay.label == "Encode 1"
    assert third_overlay.burn_in_label == "enc"
    assert third_overlay.frame_number == 30
    assert third_overlay.display_frame_number == 30
    assert third_overlay.selection_label == "Motion"
    assert third_overlay.selection_detail == enc_detail
    assert third_overlay.diagnostic_metadata == enc_diagnostic
    assert third_overlay.resolution == (req2.probe_width, req2.probe_height)
    assert third_overlay.resolution_summary == "1920 × 1080  (native)"
    assert third_overlay.origin is None
    assert third_overlay.hdr_info is None
    assert third_overlay.base_text is None
    assert third_overlay.num_frames == req2.probe_num_frames
    assert requests[2].geometry_plan is None


@pytest.mark.parametrize(
    ("source_is_hdr", "tonemap_enabled", "expected_base_text"),
    [
        (True, True, "Tonemapping Algorithm: bt2390 dpd = 1 dst = 100 nits"),
        (False, True, None),
        (True, False, None),
    ],
)
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_sets_base_text_only_for_hdr_tonemap(
    mock_prepare: MagicMock,
    source_is_hdr: bool,
    tonemap_enabled: bool,
    expected_base_text: str | None,
) -> None:
    source_info = MagicMock()
    source_info.width = 1920
    source_info.height = 1080
    source_info.num_frames = 100
    source_info.is_hdr = source_is_hdr
    mock_prepare.return_value = (MagicMock(name="clip"), None, "HDR10", source_info)
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="Reference",
        source_frames=[10],
        display_frames=[10],
        selection_labels=["User"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=source_is_hdr,
    )

    requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=ConfigSchema(color=ColorConfig(enable_tonemap=tonemap_enabled)),
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=MagicMock(),
    )

    assert requests[0].overlay is not None
    assert requests[0].overlay.base_text == expected_base_text
