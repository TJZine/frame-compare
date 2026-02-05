import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.errors import (
    FFmpegNotFoundError,
    FrameExtractionError,
    RenderError,
    SourceLoadError,
)
from frame_compare.render.encoders import _probe_fps, _render_ffmpeg, render_frame
from frame_compare.render.types import EncoderSettings, OverlayConfig, OverlayMode, RenderRequest


@pytest.fixture
def mock_run_subprocess(monkeypatch):
    mock = MagicMock()
    # Default behavior: success with empty stdout/stderr
    mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
    monkeypatch.setattr("frame_compare.render.encoders.run_subprocess", mock)
    return mock


@pytest.fixture
def mock_render_vs(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("frame_compare.render.encoders._render_vs", mock)
    return mock


@pytest.fixture
def mock_render_ffmpeg(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("frame_compare.render.encoders._render_ffmpeg", mock)
    return mock


@pytest.fixture
def mock_apply_overlay_file(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("frame_compare.render.encoders._apply_overlay_to_file", mock)
    return mock


class FakeClip:
    """Mock for vs.VideoNode"""

    pass


def test_render_frame_vs_dispatch(mock_render_vs):
    clip = FakeClip()
    request = RenderRequest(
        clip=clip,  # type: ignore
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="auto")
    mock_render_vs.assert_called_once()


def test_render_frame_ffmpeg_dispatch(mock_render_ffmpeg):
    request = RenderRequest(
        clip=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="auto")
    mock_render_ffmpeg.assert_called_once()


def test_render_frame_mismatch_error():
    # Path but renderer="vapoursynth"
    request = RenderRequest(
        clip=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )
    with pytest.raises(FrameExtractionError, match="Failed to extract frame 100"):
        render_frame(request, renderer="vapoursynth")


def test_render_frame_overlay_integration(mock_render_vs):
    # VS Path: pass overlay to _render_vs
    clip = FakeClip()
    overlay = OverlayConfig(OverlayMode.MINIMAL, "Label", 100, (1920, 1080), None, None)
    request = RenderRequest(
        clip=clip,  # type: ignore
        frame_number=100,
        output_path=Path("out.png"),
        overlay=overlay,
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="auto")

    mock_render_vs.assert_called_once()
    # Check args
    call_args = mock_render_vs.call_args
    # signature: (clip, frame, output, settings, overlay=...)
    assert call_args[1]["overlay"] == overlay


def test_render_frame_overlay_integration_ffmpeg(mock_render_ffmpeg, mock_apply_overlay_file):
    # FFmpeg Path
    request = RenderRequest(
        clip=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=OverlayConfig(OverlayMode.MINIMAL, "Label", 100, (1920, 1080), None, None),
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="ffmpeg")
    mock_render_ffmpeg.assert_called_once()
    mock_apply_overlay_file.assert_called_once()


def test_ffmpeg_seek_calculation(mock_run_subprocess):
    # Setup probe response: 24000/1001 fps
    mock_run_subprocess.return_value.stdout = b"24000/1001\n"

    _render_ffmpeg(
        video_path=Path("test.mp4"),
        frame=100,
        output=Path("out.png"),
        settings=EncoderSettings(),
    )

    # 100 / (24000/1001) = 4.17083...
    # floor(4170.83) = 4170 -> 4.170

    # Check calls
    # Call 1: probe
    # Call 2: ffmpeg
    assert mock_run_subprocess.call_count == 2

    # Check probe call
    probe_call = mock_run_subprocess.call_args_list[0]
    probe_cmd = probe_call[0][0]
    assert "stream=avg_frame_rate" in probe_cmd

    # Check ffmpeg call
    ffmpeg_call = mock_run_subprocess.call_args_list[1]
    cmd = ffmpeg_call[0][0]

    assert "-ss" in cmd
    idx = cmd.index("-ss")
    assert cmd[idx + 1] == "4.170"

    # Check SSOT compliance (-q:v 1)
    assert "-q:v" in cmd
    idx_q = cmd.index("-q:v")
    assert cmd[idx_q + 1] == "1"


def test_error_wrapping(mock_render_ffmpeg):
    mock_render_ffmpeg.side_effect = FFmpegNotFoundError()

    request = RenderRequest(
        clip=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )

    with pytest.raises(RenderError) as excinfo:
        render_frame(request, renderer="ffmpeg")

    assert isinstance(excinfo.value.__cause__, FFmpegNotFoundError)


def test_probe_fps_logic(mock_run_subprocess):
    mock_run_subprocess.return_value.stdout = b"24000/1001\n"
    fps = _probe_fps(Path("test.mp4"))
    assert fps == pytest.approx(23.976023, rel=1e-6)

    mock_run_subprocess.return_value.stdout = b"30\n"
    fps = _probe_fps(Path("test.mp4"))
    assert fps == 30.0


def test_probe_fps_failure(mock_run_subprocess):
    mock_run_subprocess.return_value.stdout = b"invalid"
    with pytest.raises(SourceLoadError):
        _probe_fps(Path("test.mp4"))


def test_probe_fps_zero_denominator_raises_source_load_error(mock_run_subprocess):
    mock_run_subprocess.return_value.stdout = b"0/0\n"
    with pytest.raises(SourceLoadError, match="Invalid avg_frame_rate"):
        _probe_fps(Path("test.mp4"))
