"""Tests for batch-expansion validation and dispatch utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema, ScreenshotsConfig
from frame_compare.config.schema_enums import VsScreenshotWriter
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
from frame_compare.render.types import (
    OverlayDiagnosticMetadata,
    OverlayFrameMeasurement,
    OverlayMode,
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
    assert (
        resolve_batch_ffmpeg_runner(custom_runner, extraction_timeout_seconds=47.0) is custom_runner
    )

    with patch("frame_compare.render.batch.expansion.DefaultFFmpegRunner") as default_runner_class:
        default_runner = default_runner_class.return_value

        assert resolve_batch_ffmpeg_runner(None, extraction_timeout_seconds=47.0) is default_runner
        default_runner_class.assert_called_once_with(extraction_timeout_seconds=47.0)


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
