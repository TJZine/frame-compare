"""Tests for render expansion utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema, OverlayMode, ScreenshotsConfig
from frame_compare.config.schema_enums import ScreenshotGeometryMode, VsScreenshotWriter
from frame_compare.render.batch.expansion import (
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
from frame_compare.render.geometry import GeometryMargins, GeometryRect
from frame_compare.render.types import (
    OverlayDiagnosticMetadata,
    OverlayDolbyVisionMetadata,
    OverlayFrameMeasurement,
    OverlaySelectionDetail,
    ScreenshotBatchRequest,
)
from frame_compare.vs.errors import TonemapRequiresVapourSynthError


def _dovi_l5_metadata(
    *,
    left: int | None,
    right: int | None,
    top: int | None,
    bottom: int | None,
) -> OverlayDiagnosticMetadata:
    return OverlayDiagnosticMetadata(
        dolby_vision=OverlayDolbyVisionMetadata(
            rpu_present=True,
            l5_left=left,
            l5_right=right,
            l5_top=top,
            l5_bottom=bottom,
        )
    )


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
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
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
        diagnostic_metadata_trusted_for_geometry=True,
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
    assert (
        requests[0].overlay.resolution_summary == "1920 × 1080 → 1440 × 1080  (original → target)"
    )
    assert requests[0].overlay.origin == ref_plan.overlay_origin

    enc_plan = requests[2].geometry_plan
    assert enc_plan is not None
    assert enc_plan.source.width == 1440
    assert enc_plan.source.height == 1080
    assert enc_plan.final_canvas_size == (1440, 1080)
    assert requests[2].overlay is not None
    assert requests[2].overlay.resolution == (1440, 1080)
    assert requests[2].overlay.resolution_summary == "1440 × 1080  (native)"
    assert requests[2].overlay.origin == enc_plan.overlay_origin


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_maps_aligned_config_to_geometry_options(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(
        screenshots={
            "geometry_mode": "aligned",
            "active_rect_detection": "aspect_ratio",
            "aligned_scale_policy": "smallest_active",
        }
    )
    ffmpeg_runner = MagicMock()
    source_infos = []
    for width, height in ((1920, 800), (1920, 800), (3840, 2160)):
        source_info = MagicMock()
        source_info.width = width
        source_info.height = height
        source_info.num_frames = 100
        source_info.is_hdr = False
        source_infos.append(source_info)
    mock_prepare.side_effect = [
        (MagicMock(name="fhd_a"), None, None, source_infos[0]),
        (MagicMock(name="fhd_b"), None, None, source_infos[1]),
        (MagicMock(name="uhd"), None, None, source_infos[2]),
    ]
    batch_requests = [
        ScreenshotBatchRequest(
            clip_path=Path(f"{label}.mkv"),
            label=label,
            source_frames=[10],
            display_frames=[10],
            selection_labels=[None],
            probe_width=width,
            probe_height=height,
            probe_num_frames=100,
            probe_is_hdr=False,
        )
        for label, width, height in (
            ("FHD A", 1920, 800),
            ("FHD B", 1920, 800),
            ("UHD", 3840, 2160),
        )
    ]

    requests, _ = expand_batch_render_requests(
        batch_requests,
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    plans = [request.geometry_plan for request in requests]
    assert all(plan is not None for plan in plans)
    assert [plan.final_canvas_size for plan in plans if plan is not None] == [(1920, 800)] * 3
    assert plans[2] is not None
    assert plans[2].active_rect_source == "aspect-ratio-derived"
    assert plans[2].active_rect == GeometryRect(0, 280, 3840, 1600)
    assert requests[2].overlay is not None
    assert requests[2].overlay.resolution == (1920, 800)
    assert requests[2].overlay.resolution_summary == "3840 × 2160 → 1920 × 800  (original → target)"


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_marks_same_canvas_aligned_transform_as_target(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(
        screenshots={
            "geometry_mode": "aligned",
            "active_rect_detection": "aspect_ratio",
            "aligned_scale_policy": "explicit_size",
            "aligned_target_width": 3840,
            "aligned_target_height": 2160,
        }
    )
    ffmpeg_runner = MagicMock()
    source_infos = []
    for width, height in ((1920, 800), (1920, 800), (3840, 2160)):
        source_info = MagicMock()
        source_info.width = width
        source_info.height = height
        source_info.num_frames = 100
        source_info.is_hdr = False
        source_infos.append(source_info)
    mock_prepare.side_effect = [
        (MagicMock(name="fhd_a"), None, None, source_infos[0]),
        (MagicMock(name="fhd_b"), None, None, source_infos[1]),
        (MagicMock(name="uhd"), None, None, source_infos[2]),
    ]
    batch_requests = [
        ScreenshotBatchRequest(
            clip_path=Path(f"{label}.mkv"),
            label=label,
            source_frames=[10],
            display_frames=[10],
            selection_labels=[None],
            probe_width=width,
            probe_height=height,
            probe_num_frames=100,
            probe_is_hdr=False,
        )
        for label, width, height in (
            ("FHD A", 1920, 800),
            ("FHD B", 1920, 800),
            ("UHD", 3840, 2160),
        )
    ]

    requests, _ = expand_batch_render_requests(
        batch_requests,
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    uhd_plan = requests[2].geometry_plan
    assert uhd_plan is not None
    assert uhd_plan.final_canvas_size == (3840, 2160)
    assert uhd_plan.crop == GeometryMargins(top=280, bottom=280)
    assert requests[2].overlay is not None
    assert (
        requests[2].overlay.resolution_summary == "3840 × 2160 → 3840 × 2160  (original → target)"
    )


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_aligns_mixed_dimensions_with_explicit_active_rects(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()

    source_infos = []
    for width, height, num_frames in ((1920, 1080, 180), (1440, 800, 160), (1280, 720, 140)):
        source_info = MagicMock()
        source_info.width = width
        source_info.height = height
        source_info.num_frames = num_frames
        source_info.is_hdr = False
        source_infos.append(source_info)
    clips = [MagicMock(name=f"clip_{idx}") for idx in range(3)]
    mock_prepare.side_effect = [
        (clips[0], None, "HDR10", source_infos[0]),
        (clips[1], None, None, source_infos[1]),
        (clips[2], None, None, source_infos[2]),
    ]
    requests_in = [
        ScreenshotBatchRequest(
            clip_path=Path("reference.mkv"),
            label="Reference",
            source_frames=[10],
            display_frames=[0],
            selection_labels=["Dark"],
            probe_width=1920,
            probe_height=1080,
            probe_num_frames=180,
            probe_is_hdr=True,
            active_rect=GeometryRect(240, 140, 1440, 800),
            filename_label="reference",
        ),
        ScreenshotBatchRequest(
            clip_path=Path("encode-a.mkv"),
            label="Encode 1",
            source_frames=[20],
            display_frames=[0],
            selection_labels=["Dark"],
            probe_width=1440,
            probe_height=800,
            probe_num_frames=160,
            probe_is_hdr=False,
            active_rect=GeometryRect(0, 0, 1440, 800),
            filename_label="encode-a",
        ),
        ScreenshotBatchRequest(
            clip_path=Path("encode-b.mkv"),
            label="Encode 2",
            source_frames=[30],
            display_frames=[0],
            selection_labels=["Dark"],
            probe_width=1280,
            probe_height=720,
            probe_num_frames=140,
            probe_is_hdr=False,
            active_rect=GeometryRect(0, 0, 1280, 720),
            filename_label="encode-b",
        ),
    ]

    requests, label_to_range = expand_batch_render_requests(
        requests_in,
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    assert [(request.clip, request.frame_number, request.output_path) for request in requests] == [
        (clips[0], 10, Path("out/0 - reference.png")),
        (clips[1], 20, Path("out/0 - encode-a.png")),
        (clips[2], 30, Path("out/0 - encode-b.png")),
    ]
    assert label_to_range == {
        "Reference": range(0, 1),
        "Encode 1": range(1, 2),
        "Encode 2": range(2, 3),
    }

    plans = [request.geometry_plan for request in requests]
    assert all(plan is not None for plan in plans)
    assert [
        (
            plan.active_rect,
            plan.active_rect_source,
            plan.crop,
            plan.scaled_size,
            plan.pad,
            plan.final_canvas_size,
        )
        for plan in plans
        if plan is not None
    ] == [
        (
            GeometryRect(240, 140, 1440, 800),
            "explicit",
            GeometryMargins(left=240, top=140, right=240, bottom=140),
            (1440, 800),
            GeometryMargins(),
            (1440, 800),
        ),
        (
            GeometryRect(0, 0, 1440, 800),
            "explicit",
            GeometryMargins(),
            (1440, 800),
            GeometryMargins(),
            (1440, 800),
        ),
        (
            GeometryRect(0, 0, 1280, 720),
            "explicit",
            GeometryMargins(),
            (1422, 800),
            GeometryMargins(left=9, right=9),
            (1440, 800),
        ),
    ]
    assert [
        (
            request.overlay.resolution if request.overlay is not None else None,
            request.overlay.resolution_summary if request.overlay is not None else None,
            request.overlay.base_text if request.overlay is not None else None,
            request.overlay.origin if request.overlay is not None else None,
            request.overlay.hdr_info if request.overlay is not None else None,
            request.overlay.num_frames if request.overlay is not None else None,
        )
        for request in requests
    ] == [
        (
            (1440, 800),
            "1920 × 1080 → 1440 × 800  (original → target)",
            None,
            (10, 10),
            "HDR10",
            180,
        ),
        (
            (1440, 800),
            "1440 × 800  (native)",
            None,
            (10, 10),
            None,
            160,
        ),
        (
            (1440, 800),
            "1280 × 720 → 1440 × 800  (original → target)",
            None,
            (19, 10),
            None,
            140,
        ),
    ]


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


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_ignores_overlay_metadata_for_geometry_without_trust(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=[
            _dovi_l5_metadata(left=160, right=160, top=0, bottom=0),
            _dovi_l5_metadata(left=160, right=160, top=0, bottom=0),
        ],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1440,
        probe_height=1080,
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
        warnings=warnings,
    )

    ref_plan = requests[0].geometry_plan
    assert ref_plan is not None
    assert ref_plan.active_rect_source == "dimension-derived"
    assert ref_plan.active_rect == GeometryRect(240, 0, 1440, 1080)
    assert warnings == []


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_explicit_active_rect_beats_metadata_rect(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    source_info = MagicMock()
    source_info.width = 1920
    source_info.height = 1080
    source_info.num_frames = 150
    source_info.is_hdr = False
    mock_prepare.return_value = (MagicMock(name="clip"), None, None, source_info)
    req = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        diagnostic_metadata=[
            _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
        ],
        diagnostic_metadata_trusted_for_geometry=True,
        active_rect=GeometryRect(160, 0, 1600, 1080),
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

    plan = requests[0].geometry_plan
    assert plan is not None
    assert plan.active_rect_source == "explicit"
    assert plan.active_rect == GeometryRect(160, 0, 1600, 1080)
    assert plan.crop == GeometryMargins(left=160, right=160)


@pytest.mark.parametrize(
    ("diagnostic_metadata", "expected_reason"),
    [
        (
            [
                _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
                _dovi_l5_metadata(left=120, right=120, top=0, bottom=0),
            ],
            "selected-frame Dolby Vision L5 margins were inconsistent",
        ),
        (
            [
                _dovi_l5_metadata(left=240, right=None, top=0, bottom=0),
                _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
            ],
            "one or more selected-frame entries had partial Dolby Vision L5 margins",
        ),
        (
            [
                _dovi_l5_metadata(left=1200, right=1200, top=0, bottom=0),
                _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
            ],
            "one or more selected-frame entries had invalid Dolby Vision L5 margins",
        ),
        (
            [
                OverlayDiagnosticMetadata(
                    dolby_vision=OverlayDolbyVisionMetadata(rpu_present=True)
                ),
                _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
            ],
            "one or more selected-frame entries had no Dolby Vision L5 margins",
        ),
    ],
)
@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_rejected_trusted_metadata_falls_back_with_warning(
    mock_prepare: MagicMock,
    diagnostic_metadata: list[OverlayDiagnosticMetadata],
    expected_reason: str,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=diagnostic_metadata,
        diagnostic_metadata_trusted_for_geometry=True,
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1440,
        probe_height=1080,
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
        warnings=warnings,
    )

    ref_plan = requests[0].geometry_plan
    assert ref_plan is not None
    assert ref_plan.active_rect_source == "dimension-derived"
    assert ref_plan.active_rect == GeometryRect(240, 0, 1440, 1080)
    assert len(warnings) == 1
    assert "Dolby Vision L5 active rect metadata" in warnings[0]
    assert "Reference" in warnings[0]
    assert expected_reason in warnings[0]


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_rejected_trusted_metadata_falls_back_to_explicit_with_warning(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    source_info = MagicMock()
    source_info.width = 1920
    source_info.height = 1080
    source_info.num_frames = 150
    source_info.is_hdr = False
    mock_prepare.return_value = (MagicMock(name="clip"), None, None, source_info)
    req = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=[
            _dovi_l5_metadata(left=240, right=240, top=0, bottom=0),
            _dovi_l5_metadata(left=120, right=120, top=0, bottom=0),
        ],
        diagnostic_metadata_trusted_for_geometry=True,
        active_rect=GeometryRect(160, 0, 1600, 1080),
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
        warnings=warnings,
    )

    plan = requests[0].geometry_plan
    assert plan is not None
    assert plan.active_rect_source == "explicit"
    assert plan.active_rect == GeometryRect(160, 0, 1600, 1080)
    assert len(warnings) == 1
    assert "Dolby Vision L5 active rect metadata" in warnings[0]
    assert "Reference" in warnings[0]
    assert "inconsistent" in warnings[0]
    assert "explicit active rect override" in warnings[0]


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_trusted_metadata_without_l5_candidate_falls_back_quietly(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    warnings: list[str] = []
    ref_source_info = MagicMock()
    ref_source_info.width = 1920
    ref_source_info.height = 1080
    ref_source_info.num_frames = 150
    ref_source_info.is_hdr = False
    enc_source_info = MagicMock()
    enc_source_info.width = 1440
    enc_source_info.height = 1080
    enc_source_info.num_frames = 150
    enc_source_info.is_hdr = False
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, ref_source_info),
        (MagicMock(name="enc_clip"), None, None, enc_source_info),
    ]
    req1 = ScreenshotBatchRequest(
        clip_path=Path("wide.mkv"),
        label="Reference",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=[None, None],
        diagnostic_metadata=[
            OverlayDiagnosticMetadata(dolby_vision=OverlayDolbyVisionMetadata(rpu_present=True)),
            OverlayDiagnosticMetadata(max_cll=1000),
        ],
        diagnostic_metadata_trusted_for_geometry=True,
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )
    req2 = ScreenshotBatchRequest(
        clip_path=Path("active.mkv"),
        label="Encode",
        source_frames=[10],
        display_frames=[10],
        selection_labels=[None],
        probe_width=1440,
        probe_height=1080,
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
        warnings=warnings,
    )

    ref_plan = requests[0].geometry_plan
    assert ref_plan is not None
    assert ref_plan.active_rect_source == "dimension-derived"
    assert ref_plan.active_rect == GeometryRect(240, 0, 1440, 1080)
    assert warnings == []


@pytest.mark.unit
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests_attaches_aligned_geometry_for_three_sources(
    mock_prepare: MagicMock,
) -> None:
    config = ConfigSchema(screenshots={"geometry_mode": "aligned"})
    ffmpeg_runner = MagicMock()
    source_infos = []
    for width in (1920, 1600, 1440):
        source_info = MagicMock()
        source_info.width = width
        source_info.height = 1080
        source_info.num_frames = 150
        source_info.is_hdr = False
        source_infos.append(source_info)
    mock_prepare.side_effect = [
        (MagicMock(name="ref_clip"), None, None, source_infos[0]),
        (MagicMock(name="enc_a_clip"), None, None, source_infos[1]),
        (MagicMock(name="enc_b_clip"), None, None, source_infos[2]),
    ]
    batch_requests = [
        ScreenshotBatchRequest(
            clip_path=Path(f"video-{index}.mkv"),
            label=label,
            source_frames=[10, 20],
            display_frames=[10, 20],
            selection_labels=[None, None],
            probe_width=width,
            probe_height=1080,
            probe_num_frames=100,
            probe_is_hdr=False,
        )
        for index, (label, width) in enumerate(
            (("Reference", 1920), ("Encode 1", 1600), ("Encode 2", 1440))
        )
    ]

    requests, label_to_range = expand_batch_render_requests(
        batch_requests,
        output_dir=Path("out"),
        config=config,
        overlay_mode=OverlayMode.STANDARD,
        renderer="ffmpeg",
        ffmpeg_runner=ffmpeg_runner,
    )

    assert label_to_range == {
        "Reference": range(0, 2),
        "Encode 1": range(2, 4),
        "Encode 2": range(4, 6),
    }
    assert len(requests) == 6
    plans = [request.geometry_plan for request in requests]
    assert plans[0] is plans[1]
    assert plans[2] is plans[3]
    assert plans[4] is plans[5]
    assert [plans[index].active_rect for index in (0, 2, 4) if plans[index] is not None] == [
        GeometryRect(240, 0, 1440, 1080),
        GeometryRect(80, 0, 1440, 1080),
        GeometryRect(0, 0, 1440, 1080),
    ]
    for request in requests:
        assert request.geometry_plan is not None
        assert request.geometry_plan.final_canvas_size == (1440, 1080)
        assert request.overlay is not None
        assert request.overlay.resolution == (1440, 1080)


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
    source_info.is_hdr = False
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
