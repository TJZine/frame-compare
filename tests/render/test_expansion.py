"""Tests for render expansion utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema, OverlayMode, ScreenshotsConfig
from frame_compare.config.schema_enums import ScreenshotGeometryMode, VsScreenshotWriter
from frame_compare.render.batch.expansion import (
    _build_overlay_config,
    _resolve_num_frames,
    _validate_batch_request_lengths,
    _validate_source_frame_range,
    expand_batch_render_requests,
    render_batch_results_by_label,
    resolve_batch_ffmpeg_runner,
    resolve_target_renderer,
    validate_batch_requests,
    validate_ffmpeg_batch_tonemap_gate,
)
from frame_compare.render.types import (
    OverlayDiagnosticMetadata,
    OverlayDolbyVisionMetadata,
    OverlayFrameMeasurement,
    OverlaySelectionDetail,
    ScreenshotBatchRequest,
)
from frame_compare.vs.errors import TonemapRequiresVapourSynthError


def test_validate_batch_request_lengths_valid() -> None:
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=["A", "B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    # Should not raise
    _validate_batch_request_lengths(req)


def test_validate_batch_request_lengths_invalid() -> None:
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10, 20],
        display_frames=[10],
        selection_labels=["A", "B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    with pytest.raises(ValueError, match="mismatched lengths"):
        _validate_batch_request_lengths(req)


def test_validate_batch_request_lengths_invalid_selection_details() -> None:
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=["A", "B"],
        selection_details=[
            OverlaySelectionDetail(
                frame_index=10,
                label="User",
                source="analysis",
                timecode="00:00:00.417",
                clip_role="analyze",
            )
        ],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    with pytest.raises(ValueError, match="mismatched lengths"):
        _validate_batch_request_lengths(req)


def test_validate_batch_request_lengths_invalid_diagnostic_metadata() -> None:
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=["A", "B"],
        diagnostic_metadata=[
            OverlayDiagnosticMetadata(
                max_cll=1000,
                measurement=OverlayFrameMeasurement(avg_nits=100.0, max_nits=100.0),
            )
        ],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    with pytest.raises(ValueError, match="mismatched lengths"):
        _validate_batch_request_lengths(req)


def test_validate_source_frame_range_rejects_known_out_of_range_frame() -> None:
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[100],
        display_frames=[42],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    with pytest.raises(
        ValueError,
        match=(
            "ScreenshotBatchRequest 'ref' requested source frame 100 "
            "outside valid range 0..99 for video.mkv"
        ),
    ):
        _validate_source_frame_range(req, source_frame=100, num_frames=100)


def test_validate_source_frame_range_rejects_negative_frame() -> None:
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[-1],
        display_frames=[42],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    with pytest.raises(ValueError, match="requested source frame -1 outside valid range"):
        _validate_source_frame_range(req, source_frame=-1, num_frames=100)


def test_validate_source_frame_range_allows_unknown_frame_count() -> None:
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10_000],
        display_frames=[42],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=None,
        probe_is_hdr=False,
    )

    _validate_source_frame_range(req, source_frame=10_000, num_frames=None)


def test_resolve_num_frames_falls_back_to_probe_for_malformed_source_value() -> None:
    assert _resolve_num_frames("not-an-int", 100) == 100
    assert _resolve_num_frames(None, 100) == 100
    assert _resolve_num_frames(150, 100) == 150


def test_resolve_target_renderer() -> None:
    # auto + ffmpeg = ffmpeg
    config1 = ConfigSchema(screenshots=ScreenshotsConfig(use_ffmpeg=True))
    assert resolve_target_renderer(config1, "auto") == "ffmpeg"

    # auto + vapoursynth = auto
    config2 = ConfigSchema(screenshots=ScreenshotsConfig(use_ffmpeg=False))
    assert resolve_target_renderer(config2, "auto") == "auto"

    # explicit renderer should be returned as-is
    assert resolve_target_renderer(config1, "vapoursynth") == "vapoursynth"
    assert resolve_target_renderer(config2, "ffmpeg") == "ffmpeg"


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_carries_encoder_settings_from_config(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"png_compression": 9, "vs_writer": "fpng"})
    ffmpeg_runner = MagicMock()
    mock_prepare.return_value = (MagicMock(name="clip"), None, None, None)
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10],
        display_frames=[10],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.NONE,
        renderer="vapoursynth",
        ffmpeg_runner=ffmpeg_runner,
    )

    assert requests[0].encoder_settings.compression == 9
    assert requests[0].encoder_settings.vs_writer == VsScreenshotWriter.FPNG


def test_validate_ffmpeg_batch_tonemap_gate() -> None:
    config = ConfigSchema(color=ColorConfig(enable_tonemap=True))
    hdr_req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10],
        display_frames=[10],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=True,
    )
    sdr_req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10],
        display_frames=[10],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    unknown_hdr_req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10],
        display_frames=[10],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=None,
    )

    # Should raise TonemapRequiresVapourSynthError when renderer is ffmpeg, tonemap is enabled, and any batch is HDR
    with pytest.raises(TonemapRequiresVapourSynthError):
        validate_ffmpeg_batch_tonemap_gate([hdr_req], config, "ffmpeg")

    # Should not raise if renderer is vapoursynth
    validate_ffmpeg_batch_tonemap_gate([hdr_req], config, "vapoursynth")

    # Should not raise if tonemap is disabled
    config_disabled = ConfigSchema(color=ColorConfig(enable_tonemap=False))
    validate_ffmpeg_batch_tonemap_gate([hdr_req], config_disabled, "ffmpeg")

    # Should not raise if no HDR requests
    validate_ffmpeg_batch_tonemap_gate([sdr_req], config, "ffmpeg")

    # Unknown HDR state must fail closed on the FFmpeg + tonemap path.
    with pytest.raises(TonemapRequiresVapourSynthError):
        validate_ffmpeg_batch_tonemap_gate([unknown_hdr_req], config, "ffmpeg")


def test_resolve_batch_ffmpeg_runner() -> None:
    custom_runner = MagicMock()
    assert resolve_batch_ffmpeg_runner(custom_runner) is custom_runner

    from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner

    assert isinstance(resolve_batch_ffmpeg_runner(None), DefaultFFmpegRunner)


def test_validate_batch_requests_rejects_duplicate_labels() -> None:
    req1 = ScreenshotBatchRequest(
        clip_path=Path("video1.mkv"),
        label="ref",
        source_frames=[10],
        display_frames=[10],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("video2.mkv"),
        label="ref",  # Duplicate label
        source_frames=[10],
        display_frames=[10],
        selection_labels=["B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    # Should raise on duplicate labels
    with pytest.raises(ValueError, match="Duplicate label 'ref' detected"):
        validate_batch_requests([req1, req2])


def test_validate_batch_requests_rejects_duplicate_output_name_within_request() -> None:
    req = ScreenshotBatchRequest(
        clip_path=Path("video1.mkv"),
        label="ref",
        source_frames=[10, 11],
        display_frames=[42, 42],
        selection_labels=["A", "B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    with pytest.raises(ValueError, match="Duplicate screenshot output '42 - ref.png'"):
        validate_batch_requests([req])


def test_validate_batch_requests_rejects_sanitized_output_name_collisions() -> None:
    req1 = ScreenshotBatchRequest(
        clip_path=Path("video1.mkv"),
        label="Bad:Name",
        source_frames=[10],
        display_frames=[42],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("video2.mkv"),
        label="Bad?Name",
        source_frames=[10],
        display_frames=[42],
        selection_labels=["B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    with pytest.raises(ValueError, match="Duplicate screenshot output '42 - Bad_Name.png'"):
        validate_batch_requests([req1, req2])


def test_validate_batch_requests_rejects_duplicate_filename_labels_with_distinct_labels() -> None:
    req1 = ScreenshotBatchRequest(
        clip_path=Path("video1.mkv"),
        label="Reference",
        source_frames=[10],
        display_frames=[42],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
        filename_label="same-source",
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("video2.mkv"),
        label="Encode 1",
        source_frames=[10],
        display_frames=[42],
        selection_labels=["B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
        filename_label="same-source",
    )

    with pytest.raises(ValueError, match="Duplicate screenshot output '42 - same-source.png'"):
        validate_batch_requests([req1, req2])


def test_build_overlay_config() -> None:
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

    # Mode NONE should return None
    assert (
        _build_overlay_config(
            req,
            overlay_mode=OverlayMode.NONE,
            source_frame=10,
            display_frame=10,
            selection_label="A",
            selection_detail=detail,
            diagnostic_metadata=diagnostic_metadata,
            resolution=(1920, 1080),
            origin=None,
            hdr_info=None,
            num_frames=100,
            include_frame_number=True,
        )
        is None
    )

    # Normal mode should populate correctly
    overlay = _build_overlay_config(
        req,
        overlay_mode=OverlayMode.STANDARD,
        source_frame=10,
        display_frame=20,
        selection_label="User",
        selection_detail=detail,
        diagnostic_metadata=diagnostic_metadata,
        resolution=(1920, 1080),
        origin=None,
        hdr_info="HDR10",
        num_frames=100,
        include_frame_number=True,
    )
    assert overlay is not None
    assert overlay.mode == OverlayMode.STANDARD
    assert overlay.label == "Reference"
    assert overlay.burn_in_label == "ref"
    assert overlay.frame_number == 10
    assert overlay.display_frame_number == 20
    assert overlay.selection_label == "User"
    assert overlay.selection_detail == detail
    assert overlay.diagnostic_metadata == diagnostic_metadata
    assert overlay.resolution == (1920, 1080)
    assert overlay.hdr_info == "HDR10"
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
    assert mock_prepare.call_args_list == [
        ((Path("video1.mkv"), "ffmpeg", config), {"ffmpeg_runner": ffmpeg_runner}),
        ((Path("video2.mkv"), "ffmpeg", config), {"ffmpeg_runner": ffmpeg_runner}),
    ]

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
    assert first_overlay.origin is None
    assert first_overlay.hdr_info == "HDR10"
    assert first_overlay.num_frames == 150
    assert requests[0].geometry_plan is None

    assert requests[1].frame_number == 20
    assert requests[1].output_path == Path("out/20 - ref.png")
    second_overlay = requests[1].overlay
    assert second_overlay is not None
    assert second_overlay.selection_label == "Cached"
    assert second_overlay.selection_detail == ref_details[1]
    assert second_overlay.diagnostic_metadata == ref_diagnostics[1]

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
    assert third_overlay.origin is None
    assert third_overlay.hdr_info is None
    assert third_overlay.num_frames == req2.probe_num_frames
    assert requests[2].geometry_plan is None


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_attaches_aligned_geometry_after_loading_dimensions(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()

    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]

    ref_metadata = OverlayDiagnosticMetadata(
        dolby_vision=OverlayDolbyVisionMetadata(
            rpu_present=True,
            l5_left=240,
            l5_right=240,
            l5_top=0,
            l5_bottom=0,
        )
    )
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=[ref_metadata, ref_metadata],
        probe_width=3840,
        probe_height=2160,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1280,
        probe_height=720,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req1, req2],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    ref_plan = requests[0].geometry_plan
    assert ref_plan is not None
    assert requests[1].geometry_plan is ref_plan
    assert ref_plan.active_rect_source == "metadata"
    assert ref_plan.crop.left == 240
    assert ref_plan.crop.right == 240
    assert ref_plan.final_canvas_size == (1440, 1080)
    assert requests[0].overlay is not None
    assert requests[0].overlay.resolution == (1440, 1080)
    assert requests[0].overlay.origin == ref_plan.overlay_origin

    enc_plan = requests[2].geometry_plan
    assert enc_plan is not None
    assert enc_plan.source.width == 1440
    assert enc_plan.source.height == 1080
    assert enc_plan.final_canvas_size == (1440, 1080)
    assert requests[2].overlay is not None
    assert requests[2].overlay.resolution == (1440, 1080)
    assert requests[2].overlay.origin == enc_plan.overlay_origin


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_warns_and_uses_native_when_aligned_dimensions_unknown(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    mock_prepare.return_value = (Path("video.mkv"), None, None, None)
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="Reference",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=None,
        probe_height=None,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
        warnings=warnings,
    )

    assert requests[0].geometry_plan is None
    assert requests[0].overlay is not None
    assert requests[0].overlay.origin is None
    assert requests[0].overlay.resolution == (0, 0)
    assert warnings == [
        "Screenshot geometry alignment skipped: source dimensions were unavailable "
        "for Reference; using native screenshot geometry for this batch."
    ]


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_uses_source_info_frame_count_over_probe(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema()
    ffmpeg_runner = MagicMock()

    source_info = MagicMock()
    source_info.width = 1920
    source_info.height = 1080
    source_info.num_frames = 150
    mock_prepare.return_value = (MagicMock(name="clip"), None, None, source_info)
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[120],
        display_frames=[10],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    assert requests[0].frame_number == 120
    assert requests[0].output_path == Path("out/10 - ref.png")


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_preserves_out_of_range_display_frame(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema()
    ffmpeg_runner = MagicMock()
    mock_prepare.return_value = (MagicMock(name="clip"), None, None, None)
    req = ScreenshotBatchRequest(
        clip_path=Path("video.mkv"),
        label="ref",
        source_frames=[10],
        display_frames=[999],
        selection_labels=["A"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    requests, _ = expand_batch_render_requests(
        [req],
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    assert requests[0].frame_number == 10
    assert requests[0].output_path == Path("out/999 - ref.png")
    assert requests[0].overlay is not None
    assert requests[0].overlay.display_frame_number == 999


def test_render_batch_results_by_label() -> None:
    req1 = ScreenshotBatchRequest(
        clip_path=Path("video1.mkv"),
        label="ref",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=["A", "B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("video2.mkv"),
        label="enc",
        source_frames=[30],
        display_frames=[30],
        selection_labels=["C"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    rendered_paths = [
        Path("out/10 - ref.png"),
        Path("out/20 - ref.png"),
        Path("out/30 - enc.png"),
    ]
    label_to_range = {
        "ref": range(0, 2),
        "enc": range(2, 3),
    }

    results = render_batch_results_by_label(
        [req1, req2],
        rendered_paths,
        label_to_range,
    )

    assert results == {
        "ref": [Path("out/10 - ref.png"), Path("out/20 - ref.png")],
        "enc": [Path("out/30 - enc.png")],
    }
