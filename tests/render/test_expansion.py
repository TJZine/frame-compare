"""Tests for render expansion utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema, OverlayMode, ScreenshotsConfig
from frame_compare.errors import TonemapRequiresVapourSynthError
from frame_compare.render.batch.expansion import (
    _build_overlay_config,
    _validate_batch_request_lengths,
    expand_batch_render_requests,
    render_batch_results_by_label,
    resolve_batch_ffmpeg_runner,
    resolve_target_renderer,
    validate_batch_requests,
    validate_ffmpeg_batch_tonemap_gate,
)
from frame_compare.render.types import ScreenshotBatchRequest


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

    from frame_compare.render.ffmpeg import DefaultFFmpegRunner

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

    with pytest.raises(ValueError, match="Duplicate screenshot output 'ref_00042.png'"):
        validate_batch_requests([req])


def test_validate_batch_requests_rejects_sanitized_output_name_collisions() -> None:
    req1 = ScreenshotBatchRequest(
        clip_path=Path("video1.mkv"),
        label="A B",
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
        label="A_B",
        source_frames=[10],
        display_frames=[42],
        selection_labels=["B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=False,
    )

    with pytest.raises(ValueError, match="Duplicate screenshot output 'A_B_00042.png'"):
        validate_batch_requests([req1, req2])


def test_build_overlay_config() -> None:
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

    # Mode NONE should return None
    assert (
        _build_overlay_config(
            req,
            overlay_mode=OverlayMode.NONE,
            source_frame=10,
            display_frame=10,
            selection_label="A",
            resolution=(1920, 1080),
            hdr_info=None,
            num_frames=100,
        )
        is None
    )

    # Normal mode should populate correctly
    overlay = _build_overlay_config(
        req,
        overlay_mode=OverlayMode.STANDARD,
        source_frame=10,
        display_frame=20,
        selection_label="A",
        resolution=(1920, 1080),
        hdr_info="HDR10",
        num_frames=100,
    )
    assert overlay is not None
    assert overlay.mode == OverlayMode.STANDARD
    assert overlay.label == "ref"
    assert overlay.frame_number == 10
    assert overlay.display_frame_number == 20
    assert overlay.selection_label == "A"
    assert overlay.resolution == (1920, 1080)
    assert overlay.hdr_info == "HDR10"
    assert overlay.num_frames == 100


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expand_batch_render_requests(mock_prepare: MagicMock) -> None:
    config = ConfigSchema()
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

    req1 = ScreenshotBatchRequest(
        clip_path=Path("video1.mkv"),
        label="ref",
        source_frames=[10, 20],
        display_frames=[10, 20],
        selection_labels=["A", "B"],
        probe_width=1920,
        probe_height=1080,
        probe_num_frames=100,
        probe_is_hdr=True,
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
        "ref": range(0, 2),
        "enc": range(2, 3),
    }
    assert mock_prepare.call_args_list == [
        ((Path("video1.mkv"), "ffmpeg", config), {"ffmpeg_runner": ffmpeg_runner}),
        ((Path("video2.mkv"), "ffmpeg", config), {"ffmpeg_runner": ffmpeg_runner}),
    ]

    # Verify requests
    assert requests[0].clip is ref_clip
    assert requests[0].frame_number == 10
    assert requests[0].output_path == Path("out/ref_00010.png")
    first_overlay = requests[0].overlay
    assert first_overlay is not None
    assert first_overlay.label == "ref"
    assert first_overlay.frame_number == 10
    assert first_overlay.display_frame_number == 10
    assert first_overlay.selection_label == "A"
    assert first_overlay.resolution == (1920, 1080)
    assert first_overlay.hdr_info == "HDR10"
    assert first_overlay.num_frames == 150

    assert requests[1].frame_number == 20
    assert requests[1].output_path == Path("out/ref_00020.png")
    second_overlay = requests[1].overlay
    assert second_overlay is not None
    assert second_overlay.selection_label == "B"

    assert requests[2].clip is enc_clip
    assert requests[2].frame_number == 30
    assert requests[2].output_path == Path("out/enc_00030.png")
    third_overlay = requests[2].overlay
    assert third_overlay is not None
    assert third_overlay.label == "enc"
    assert third_overlay.frame_number == 30
    assert third_overlay.display_frame_number == 30
    assert third_overlay.selection_label == "C"
    assert third_overlay.resolution == (req2.probe_width, req2.probe_height)
    assert third_overlay.hdr_info is None
    assert third_overlay.num_frames == req2.probe_num_frames


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
        Path("out/ref_00010.png"),
        Path("out/ref_00020.png"),
        Path("out/enc_00030.png"),
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
        "ref": [Path("out/ref_00010.png"), Path("out/ref_00020.png")],
        "enc": [Path("out/enc_00030.png")],
    }
