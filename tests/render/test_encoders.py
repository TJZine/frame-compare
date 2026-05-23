import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from frame_compare.render.encoders import (
    _clip_to_rgb24_for_pillow,
    apply_overlay_to_file,
    render_frame,
)
from frame_compare.render.errors import FrameExtractionError, RenderError
from frame_compare.render.types import EncoderSettings, OverlayConfig, OverlayMode, RenderRequest
from frame_compare.utils.ffmpeg_errors import FFmpegNotFoundError
from frame_compare.vs.errors import SourceLoadError


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
def mock_ffmpeg_runner(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("frame_compare.render.ffmpeg.DefaultFFmpegRunner.extract_frame", mock)
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


def test_render_frame_ffmpeg_dispatch(mock_ffmpeg_runner):
    request = RenderRequest(
        clip=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="auto")
    mock_ffmpeg_runner.assert_called_once()


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


def test_render_frame_overlay_integration_ffmpeg(mock_ffmpeg_runner, mock_apply_overlay_file):
    # FFmpeg Path
    request = RenderRequest(
        clip=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=OverlayConfig(OverlayMode.MINIMAL, "Label", 100, (1920, 1080), None, None),
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="ffmpeg")
    mock_ffmpeg_runner.assert_called_once()
    mock_apply_overlay_file.assert_called_once()


def test_apply_overlay_to_file_none_mode_is_noop(monkeypatch) -> None:
    overlay = OverlayConfig(OverlayMode.NONE, "Label", 100, (1920, 1080), None, None)

    def _should_not_call(_path: Path, _config: OverlayConfig) -> None:
        raise AssertionError("_apply_overlay_to_file should not be called for NONE mode")

    monkeypatch.setattr("frame_compare.render.encoders._apply_overlay_to_file", _should_not_call)
    apply_overlay_to_file(Path("does-not-matter.png"), overlay)


def test_render_frame_overlay_none_mode_is_strict_noop_on_ffmpeg(
    mock_ffmpeg_runner, mock_apply_overlay_file
):
    request = RenderRequest(
        clip=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=OverlayConfig(OverlayMode.NONE, "Label", 100, (1920, 1080), None, None),
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="ffmpeg")
    mock_ffmpeg_runner.assert_called_once()
    mock_apply_overlay_file.assert_not_called()


def test_error_wrapping(mock_ffmpeg_runner):
    mock_ffmpeg_runner.side_effect = FFmpegNotFoundError()

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


def test_render_frame_reraises_source_load_error(mock_ffmpeg_runner):
    mock_ffmpeg_runner.side_effect = SourceLoadError(Path("test.mp4"), "ffprobe failed")

    request = RenderRequest(
        clip=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )

    with pytest.raises(SourceLoadError, match="ffprobe failed"):
        render_frame(request, renderer="ffmpeg")


class _FakeResize:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def Bicubic(self, **kwargs: object) -> str:  # noqa: N802
        self.calls.append(("Bicubic", dict(kwargs)))
        return "bicubic"

    def Point(self, **kwargs: object) -> str:  # noqa: N802
        self.calls.append(("Point", dict(kwargs)))
        return "point"


class _FakeFrame:
    def __init__(self, props: dict[str, object]) -> None:
        self.props = props


class _FakeClip:
    def __init__(self, *, fmt: object | None, props: dict[str, object]) -> None:
        self.format = fmt
        self.resize = _FakeResize()
        self._frame = _FakeFrame(props)

    def get_frame(self, _index: int) -> _FakeFrame:
        return self._frame


def test_clip_to_rgb24_for_pillow_uses_709_when_matrix_missing(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=3)
    clip = _FakeClip(fmt=fmt, props={})

    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "bicubic"
    assert clip.resize.calls[0][0] == "Bicubic"
    assert clip.resize.calls[0][1]["matrix_in_s"] == "709"


def test_clip_to_rgb24_for_pillow_uses_hdr_fallback_when_matrix_missing(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=3)
    clip = _FakeClip(fmt=fmt, props={"_Transfer": 16, "_Primaries": 9})

    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "bicubic"
    assert clip.resize.calls[0][1]["matrix_in_s"] == "2020ncl"


def test_clip_to_rgb24_for_pillow_uses_matrix_prop_mapping(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=3)
    clip = _FakeClip(fmt=fmt, props={"_Matrix": 5})

    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "bicubic"
    assert clip.resize.calls[0][1]["matrix_in_s"] == "470bg"


def test_clip_to_rgb24_for_pillow_variable_format(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    clip = _FakeClip(fmt=None, props={})
    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "bicubic"
    assert clip.resize.calls[0][0] == "Bicubic"
    assert clip.resize.calls[0][1]["matrix_in_s"] == "709"


def test_clip_to_rgb24_for_pillow_already_rgb24_passthrough(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=1, color_family=2)
    clip = _FakeClip(fmt=fmt, props={"_Matrix": 5})
    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result is clip
    assert clip.resize.calls == []


def test_clip_to_rgb24_for_pillow_rgb_non_24_uses_point(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=2)
    clip = _FakeClip(fmt=fmt, props={})
    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "point"
    assert clip.resize.calls[0][0] == "Point"
