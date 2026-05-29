import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from frame_compare.render.encoders import (
    _clip_to_rgb24_for_pillow,
    _maybe_expand_tonemapped_video_range,
    _picture_type_from_frame_props,
    _render_vs,
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
    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.DefaultFFmpegRunner.extract_frame", mock
    )
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
        self.std = MagicMock()
        self.std.SetFrameProps = MagicMock(return_value="props")
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


def test_clip_to_rgb24_for_pillow_expands_marked_limited_tonemap(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=2)
    clip = _FakeClip(fmt=fmt, props={"_Tonemapped": 1, "_FrameCompareExpandRange": 1})
    clip.resize.Point = MagicMock(return_value=clip)

    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "props"
    clip.resize.Point.assert_called_once_with(format=1)
    clip.std.SetFrameProps.assert_called_once_with(_FrameCompareExpandRange=1)


def test_clip_to_rgb24_for_pillow_does_not_expand_marked_full_tonemap(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=2)
    clip = _FakeClip(fmt=fmt, props={"_Tonemapped": 1})

    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "point"
    assert clip.resize.calls[0] == ("Point", {"format": 1})


def test_maybe_expand_tonemapped_video_range_requires_internal_expand_marker() -> None:
    array = np.full((2, 2, 3), 32, dtype=np.uint8)

    result = _maybe_expand_tonemapped_video_range(array, {"_Tonemapped": 1})

    assert result is array


def test_maybe_expand_tonemapped_video_range_expands_marked_limited_video_range() -> None:
    array = np.array(
        [
            [[16, 16, 16], [32, 32, 32], [90, 90, 90]],
            [[18, 18, 18], [48, 48, 48], [120, 120, 120]],
        ],
        dtype=np.uint8,
    )

    result = _maybe_expand_tonemapped_video_range(
        array, {"_Tonemapped": 1, "_FrameCompareExpandRange": 1}
    )

    assert result.dtype == np.uint8
    assert result[0, 0, 0] == 0
    assert result[1, 2, 0] > array[1, 2, 0]


@pytest.mark.parametrize(
    ("prop_value", "expected"),
    [
        (b"I", "I"),
        (" p ", "P"),
        (b"IDR", "I"),
        ("", None),
        (b"\x00", None),
        ("unknown", None),
        (123, None),
    ],
)
def test_picture_type_from_frame_props_normalizes_supported_values(
    prop_value: object, expected: str | None
) -> None:
    assert _picture_type_from_frame_props({"_PictType": prop_value}) == expected


def test_render_vs_populates_overlay_picture_type_from_frame_props(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    captured_picture_types: list[str | None] = []

    def _capture_overlay(image: object, overlay: OverlayConfig) -> object:
        captured_picture_types.append(overlay.picture_type)
        return image

    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay", _capture_overlay)

    class _FrameWithPictureType:
        def __init__(self) -> None:
            self.props = {"_PictType": b"b"}
            self.format = SimpleNamespace(num_planes=1)
            self._plane = np.zeros((2, 2), dtype=np.uint8)

        def __getitem__(self, index: int) -> np.ndarray:
            assert index == 0
            return self._plane

    class _ClipWithPictureType:
        def __init__(self) -> None:
            self.format = SimpleNamespace(id=1, color_family=2)
            self._frame = _FrameWithPictureType()

        def get_frame(self, _index: int) -> _FrameWithPictureType:
            return self._frame

    overlay = OverlayConfig(OverlayMode.STANDARD, "Label", 0, (2, 2), None, None)

    _render_vs(
        _ClipWithPictureType(),  # type: ignore[arg-type]
        0,
        tmp_path / "out.png",
        EncoderSettings(),
        overlay=overlay,
    )

    assert captured_picture_types == ["B"]
    assert overlay.picture_type == "B"


def test_render_vs_clears_overlay_picture_type_when_prop_is_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    captured_picture_types: list[str | None] = []

    def _capture_overlay(image: object, overlay: OverlayConfig) -> object:
        captured_picture_types.append(overlay.picture_type)
        return image

    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay", _capture_overlay)

    class _FrameWithoutSupportedPictureType:
        def __init__(self) -> None:
            self.props = {"_PictType": "unknown"}
            self.format = SimpleNamespace(num_planes=1)
            self._plane = np.zeros((2, 2), dtype=np.uint8)

        def __getitem__(self, index: int) -> np.ndarray:
            assert index == 0
            return self._plane

    class _ClipWithoutSupportedPictureType:
        def __init__(self) -> None:
            self.format = SimpleNamespace(id=1, color_family=2)
            self._frame = _FrameWithoutSupportedPictureType()

        def get_frame(self, _index: int) -> _FrameWithoutSupportedPictureType:
            return self._frame

    overlay = OverlayConfig(
        OverlayMode.STANDARD,
        "Label",
        0,
        (2, 2),
        None,
        None,
        picture_type="I",
    )

    _render_vs(
        _ClipWithoutSupportedPictureType(),  # type: ignore[arg-type]
        0,
        tmp_path / "out.png",
        EncoderSettings(),
        overlay=overlay,
    )

    assert captured_picture_types == [None]
    assert overlay.picture_type is None
