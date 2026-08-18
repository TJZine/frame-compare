import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.render.encoders import (
    _clip_to_rgb24_for_pillow,
    _map_fpng_compression,
    _maybe_expand_tonemapped_video_range,
    apply_overlay_to_file,
    render_frame,
    render_frame_detailed,
)
from frame_compare.render.errors import EncodingError, FrameExtractionError, RenderError
from frame_compare.render.geometry import (
    GeometryMargins,
    GeometryRect,
    RenderGeometryPlan,
    SourceGeometry,
)
from frame_compare.render.types import EncoderSettings, OverlayConfig, OverlayMode, RenderRequest
from frame_compare.utils.ffmpeg_errors import FFmpegNotFoundError
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
    normalize_picture_type,
)
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
    mock.return_value = RenderedFrameFacts(source_frame=100)
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


def _overlay(mode: OverlayMode = OverlayMode.MINIMAL, *, frame: int = 0) -> OverlayConfig:
    resolution = (1920, 1080)
    return OverlayConfig(
        mode=mode,
        label="Label",
        comparison_frame=frame,
        source_frame=frame,
        source_total_frames=None,
        include_frame_number=True,
        selection_label=None,
        file_size_bytes=0,
        source_resolution=resolution,
        signal=SourceSignalFacts(is_hdr=False),
        presentation_state=PresentationState.SDR,
        tonemap_settings=None,
        geometry=RenderedGeometryFacts(
            source_size=resolution,
            active_picture=ActivePictureFacts(0, 0, *resolution, "full_frame", True),
            cropped_size=resolution,
            scaled_size=resolution,
            final_canvas_size=resolution,
            is_noop=True,
        ),
        font_path=None,
    )


class _FakeFpngJob:
    def __init__(self) -> None:
        self.frames: list[int] = []

    def get_frame(self, index: int) -> object:
        self.frames.append(index)
        return object()


class _FakeFpngNamespace:
    def __init__(self, job: _FakeFpngJob) -> None:
        self.job = job
        self.calls: list[tuple[object, str, int, bool]] = []

    def Write(  # noqa: N802
        self,
        clip: object,
        filename: str,
        *,
        compression: int,
        overwrite: bool,
    ) -> _FakeFpngJob:
        self.calls.append((clip, filename, compression, overwrite))
        return self.job


class _FakeVsStd:
    def __init__(self, clip: "_FakeFpngClip") -> None:
        self._clip = clip

    def CropRel(  # noqa: N802
        self,
        *,
        left: int,
        right: int,
        top: int,
        bottom: int,
    ) -> "_FakeFpngClip":
        return self._clip.with_op(
            ("crop", {"left": left, "right": right, "top": top, "bottom": bottom})
        )

    def AddBorders(  # noqa: N802
        self,
        *,
        left: int,
        right: int,
        top: int,
        bottom: int,
    ) -> "_FakeFpngClip":
        return self._clip.with_op(
            ("pad", {"left": left, "right": right, "top": top, "bottom": bottom})
        )

    def SetFrameProps(self, **_props: object) -> "_FakeFpngClip":  # noqa: N802
        return self._clip


class _FakeVsResize:
    def __init__(self, clip: "_FakeFpngClip") -> None:
        self._clip = clip

    def Spline36(self, *, width: int, height: int) -> "_FakeFpngClip":  # noqa: N802
        return self._clip.with_op(("resize", {"width": width, "height": height}))


class _FakeFpngFrame:
    def __init__(self, props: dict[str, object]) -> None:
        self.props = props


class _FakeFpngClip:
    def __init__(
        self,
        *,
        props: dict[str, object] | None = None,
        ops: list[tuple[str, dict[str, int]]] | None = None,
        frame_reads: list[int] | None = None,
    ) -> None:
        self._props = props or {}
        self.ops = list(ops or [])
        self.frame_reads = frame_reads if frame_reads is not None else []
        self.format = SimpleNamespace(id=1, color_family=2)
        self.std = _FakeVsStd(self)
        self.resize = _FakeVsResize(self)

    def with_op(self, op: tuple[str, dict[str, int]]) -> "_FakeFpngClip":
        return _FakeFpngClip(
            props=self._props,
            ops=[*self.ops, op],
            frame_reads=self.frame_reads,
        )

    def get_frame(self, index: int) -> _FakeFpngFrame:
        self.frame_reads.append(index)
        return _FakeFpngFrame(self._props)


def test_render_frame_vs_dispatch(mock_render_vs):
    clip = FakeClip()
    request = RenderRequest(
        clip=clip,  # type: ignore
        diagnostic_source=clip,  # type: ignore
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
        diagnostic_source=Path("test.mp4"),
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
        diagnostic_source=Path("test.mp4"),
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
    overlay = _overlay(frame=100)
    request = RenderRequest(
        clip=clip,  # type: ignore
        diagnostic_source=clip,  # type: ignore
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
        diagnostic_source=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=_overlay(frame=100),
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="ffmpeg")
    mock_ffmpeg_runner.assert_called_once()
    mock_apply_overlay_file.assert_called_once()


@pytest.mark.parametrize(
    ("png_level", "fpng_level"),
    [(0, 0), (3, 0), (4, 1), (6, 1), (7, 2), (9, 2)],
)
def test_map_fpng_compression_maps_public_png_range(png_level: int, fpng_level: int) -> None:
    assert _map_fpng_compression(png_level) == fpng_level


def test_map_fpng_compression_rejects_out_of_contract_values() -> None:
    with pytest.raises(ValueError, match="between 0 and 9"):
        _map_fpng_compression(10)


def test_render_frame_vs_auto_uses_fpng_for_geometry_without_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _FakeFpngJob()
    fpng = _FakeFpngNamespace(job)
    monkeypatch.setitem(
        sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2, core=SimpleNamespace(fpng=fpng))
    )
    clip = _FakeFpngClip()
    output = tmp_path / "out.png"

    render_frame(
        RenderRequest(
            clip=clip,  # type: ignore[arg-type]
            diagnostic_source=clip,  # type: ignore[arg-type]
            frame_number=3,
            output_path=output,
            overlay=None,
            encoder_settings=EncoderSettings(compression=8, vs_writer=VsScreenshotWriter.AUTO),
            geometry_plan=_geometry_plan(
                scaled_size=(4, 4),
                final_canvas_size=(6, 4),
                pad=GeometryMargins(left=1, right=1),
            ),
        ),
        renderer="vapoursynth",
    )

    assert len(fpng.calls) == 1
    written_clip, filename, compression, overwrite = fpng.calls[0]
    assert filename == str(output)
    assert compression == 2
    assert overwrite is True
    assert isinstance(written_clip, _FakeFpngClip)
    assert [name for name, _kwargs in written_clip.ops] == ["crop", "resize", "pad"]
    assert written_clip.ops[-1][1]["left"] == 1
    assert written_clip.ops[-1][1]["right"] == 1
    assert job.frames == [3]
    assert clip.frame_reads == [3, 0, 3]


def test_render_frame_vs_auto_preserves_pillow_for_native_geometry_without_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _FakeFpngJob()
    fpng = _FakeFpngNamespace(job)
    monkeypatch.setitem(
        sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2, core=SimpleNamespace(fpng=fpng))
    )
    clip = _FakeFpngClip()
    pillow = MagicMock()
    monkeypatch.setattr("frame_compare.render.encoders._render_vs_pillow", pillow)

    render_frame(
        RenderRequest(
            clip=clip,  # type: ignore[arg-type]
            diagnostic_source=clip,  # type: ignore[arg-type]
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.AUTO),
            geometry_plan=None,
        ),
        renderer="vapoursynth",
    )

    assert fpng.calls == []
    pillow.assert_called_once()


def test_render_frame_vs_auto_falls_back_to_pillow_when_overlay_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _FakeFpngJob()
    fpng = _FakeFpngNamespace(job)
    monkeypatch.setitem(
        sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2, core=SimpleNamespace(fpng=fpng))
    )
    clip = _FakeFpngClip()
    pillow = MagicMock()
    monkeypatch.setattr("frame_compare.render.encoders._render_vs_pillow", pillow)
    overlay = _overlay(frame=3)

    render_frame(
        RenderRequest(
            clip=clip,  # type: ignore[arg-type]
            diagnostic_source=clip,  # type: ignore[arg-type]
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=overlay,
            encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.AUTO),
        ),
        renderer="vapoursynth",
    )

    assert fpng.calls == []
    pillow.assert_called_once()


def test_render_frame_vs_pillow_writer_ignores_available_fpng(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _FakeFpngJob()
    fpng = _FakeFpngNamespace(job)
    monkeypatch.setitem(
        sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2, core=SimpleNamespace(fpng=fpng))
    )
    clip = _FakeFpngClip()
    pillow = MagicMock()
    monkeypatch.setattr("frame_compare.render.encoders._render_vs_pillow", pillow)

    render_frame(
        RenderRequest(
            clip=clip,  # type: ignore[arg-type]
            diagnostic_source=clip,  # type: ignore[arg-type]
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.PILLOW),
        ),
        renderer="vapoursynth",
    )

    assert fpng.calls == []
    pillow.assert_called_once()


def test_render_frame_vs_fpng_requires_plugin_when_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2))
    clip = _FakeFpngClip()

    with pytest.raises(EncodingError) as exc_info:
        render_frame(
            RenderRequest(
                clip=clip,  # type: ignore[arg-type]
                diagnostic_source=clip,  # type: ignore[arg-type]
                frame_number=3,
                output_path=tmp_path / "out.png",
                overlay=None,
                encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.FPNG),
            ),
            renderer="vapoursynth",
        )

    assert "fpng.Write plugin is unavailable" in exc_info.value.context.message


def test_render_frame_vs_fpng_rejects_overlay_when_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _FakeFpngJob()
    fpng = _FakeFpngNamespace(job)
    monkeypatch.setitem(
        sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2, core=SimpleNamespace(fpng=fpng))
    )
    clip = _FakeFpngClip()

    with pytest.raises(EncodingError) as exc_info:
        render_frame(
            RenderRequest(
                clip=clip,  # type: ignore[arg-type]
                diagnostic_source=clip,  # type: ignore[arg-type]
                frame_number=3,
                output_path=tmp_path / "out.png",
                overlay=_overlay(frame=3),
                encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.FPNG),
            ),
            renderer="vapoursynth",
        )

    assert "cannot preserve overlays yet" in exc_info.value.context.message
    assert fpng.calls == []


def test_render_frame_vs_auto_falls_back_to_pillow_for_tonemapped_limited_rgb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _FakeFpngJob()
    fpng = _FakeFpngNamespace(job)
    monkeypatch.setitem(
        sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2, core=SimpleNamespace(fpng=fpng))
    )
    clip = _FakeFpngClip(props={"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_Range": 0})
    pillow = MagicMock()
    monkeypatch.setattr("frame_compare.render.encoders._render_vs_pillow", pillow)

    render_frame(
        RenderRequest(
            clip=clip,  # type: ignore[arg-type]
            diagnostic_source=clip,  # type: ignore[arg-type]
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.AUTO),
        ),
        renderer="vapoursynth",
    )

    assert fpng.calls == []
    pillow.assert_called_once()


def test_render_frame_vs_fpng_rejects_tonemapped_limited_rgb_when_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _FakeFpngJob()
    fpng = _FakeFpngNamespace(job)
    monkeypatch.setitem(
        sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2, core=SimpleNamespace(fpng=fpng))
    )
    clip = _FakeFpngClip(props={"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_Range": 0})

    with pytest.raises(EncodingError) as exc_info:
        render_frame(
            RenderRequest(
                clip=clip,  # type: ignore[arg-type]
                diagnostic_source=clip,  # type: ignore[arg-type]
                frame_number=3,
                output_path=tmp_path / "out.png",
                overlay=None,
                encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.FPNG),
            ),
            renderer="vapoursynth",
        )

    assert "cannot preserve tonemapped limited-range RGB expansion yet" in (
        exc_info.value.context.message
    )
    assert fpng.calls == []


def _geometry_plan(
    *,
    source_size: tuple[int, int] = (4, 4),
    crop_rect: GeometryRect | None = None,
    scaled_size: tuple[int, int] = (2, 4),
    final_canvas_size: tuple[int, int] = (4, 4),
    pad: GeometryMargins | None = None,
) -> RenderGeometryPlan:
    crop_rect = crop_rect or GeometryRect(1, 0, 2, 4)
    pad = pad or GeometryMargins(left=1, right=1)
    source = SourceGeometry(width=source_size[0], height=source_size[1])
    source_rect = GeometryRect(0, 0, source.width, source.height)
    return RenderGeometryPlan(
        source=source,
        source_rect=source_rect,
        active_rect=crop_rect,
        active_rect_source="dimension-derived",
        crop_rect=crop_rect,
        crop=GeometryMargins(left=crop_rect.x, right=source.width - crop_rect.right),
        cropped_size=(crop_rect.width, crop_rect.height),
        scaled_size=scaled_size,
        pad=pad,
        final_canvas_size=final_canvas_size,
        content_origin=(pad.left, pad.top),
        overlay_origin=(pad.left + 10, pad.top + 10),
        source_overlay_origin=(crop_rect.x + 10, crop_rect.y + 10),
    )


def test_render_frame_ffmpeg_passes_geometry_plan_to_runner() -> None:
    plan = _geometry_plan()
    runner = MagicMock()
    request = RenderRequest(
        clip=Path("test.mp4"),
        diagnostic_source=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
        ffmpeg_runner=runner,
        geometry_plan=plan,
    )

    render_frame(request, renderer="ffmpeg")

    runner.extract_frame.assert_called_once_with(
        Path("test.mp4"),
        100,
        Path("out.png"),
        geometry_plan=plan,
    )


def test_render_frame_ffmpeg_wraps_unrepresentable_geometry_as_render_error() -> None:
    request = RenderRequest(
        clip=Path("test.mp4"),
        diagnostic_source=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
        geometry_plan=_geometry_plan(scaled_size=(0, 4)),
    )

    with pytest.raises(RenderError) as exc_info:
        render_frame(request, renderer="ffmpeg")

    assert "scale dimensions must be positive" in exc_info.value.context.message


def test_apply_overlay_to_file_none_mode_is_noop(monkeypatch) -> None:
    overlay = _overlay(OverlayMode.NONE, frame=100)

    def _should_not_call(_path: Path, _config: OverlayConfig) -> None:
        raise AssertionError("_apply_overlay_to_file should not be called for NONE mode")

    monkeypatch.setattr("frame_compare.render.encoders._apply_overlay_to_file", _should_not_call)
    apply_overlay_to_file(
        Path("does-not-matter.png"), overlay, RenderedFrameFacts(source_frame=100)
    )


def test_render_frame_overlay_none_mode_is_strict_noop_on_ffmpeg(
    mock_ffmpeg_runner, mock_apply_overlay_file
):
    request = RenderRequest(
        clip=Path("test.mp4"),
        diagnostic_source=Path("test.mp4"),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=_overlay(OverlayMode.NONE, frame=100),
        encoder_settings=EncoderSettings(),
    )
    render_frame(request, renderer="ffmpeg")
    mock_ffmpeg_runner.assert_called_once()
    mock_apply_overlay_file.assert_not_called()


def test_error_wrapping(mock_ffmpeg_runner):
    mock_ffmpeg_runner.side_effect = FFmpegNotFoundError()

    request = RenderRequest(
        clip=Path("test.mp4"),
        diagnostic_source=Path("test.mp4"),
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
        diagnostic_source=Path("test.mp4"),
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


@pytest.mark.parametrize(
    ("fmt", "props", "expected_matrix"),
    [
        (SimpleNamespace(id=999, color_family=3), {}, "709"),
        (SimpleNamespace(id=999, color_family=3), {"_Transfer": 16, "_Primaries": 9}, "2020ncl"),
        (SimpleNamespace(id=999, color_family=3), {"_Matrix": 5}, "470bg"),
        (None, {}, "709"),
    ],
)
def test_clip_to_rgb24_for_pillow_maps_yuv_matrix_for_pillow(
    monkeypatch,
    fmt: object | None,
    props: dict[str, object],
    expected_matrix: str,
) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    clip = _FakeClip(fmt=fmt, props=props)

    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "bicubic"
    assert clip.resize.calls[0][0] == "Bicubic"
    assert clip.resize.calls[0][1]["matrix_in_s"] == expected_matrix


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


@pytest.mark.parametrize(
    "range_props",
    [
        {"_Range": 0},
        {"_ColorRange": 1},
    ],
)
def test_clip_to_rgb24_for_pillow_expands_marked_limited_tonemap(
    monkeypatch,
    range_props: dict[str, object],
) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=2)
    clip = _FakeClip(
        fmt=fmt,
        props={"_Tonemapped": 1, "_FrameCompareExpandRange": 1, **range_props},
    )
    clip.resize.Point = MagicMock(return_value=clip)

    result = _clip_to_rgb24_for_pillow(clip)  # type: ignore[arg-type]

    assert result == "props"
    clip.resize.Point.assert_called_once_with(format=1)
    clip.std.SetFrameProps.assert_called_once_with(_FrameCompareExpandRange=1)


@pytest.mark.parametrize(
    "props",
    [
        {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_Range": 1},
        {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_ColorRange": 0},
        {"_Tonemapped": 1},
    ],
)
def test_clip_to_rgb24_for_pillow_skips_expand_when_not_limited_internal_tonemap(
    monkeypatch,
    props: dict[str, object],
) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=2)
    clip = _FakeClip(fmt=fmt, props=props)

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
        array, {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_Range": 0}
    )

    assert result.dtype == np.uint8
    assert result[0, 0, 0] == 0
    assert result[1, 2, 0] > array[1, 2, 0]


def test_maybe_expand_tonemapped_video_range_skips_marked_full_range() -> None:
    array = np.full((2, 2, 3), 32, dtype=np.uint8)

    result = _maybe_expand_tonemapped_video_range(
        array, {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_Range": 1}
    )

    assert result is array


def test_maybe_expand_tonemapped_video_range_expands_deprecated_limited_color_range() -> None:
    array = np.array([[[16, 16, 16], [120, 120, 120]]], dtype=np.uint8)

    result = _maybe_expand_tonemapped_video_range(
        array, {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_ColorRange": 1}
    )

    assert result.dtype == np.uint8
    assert result[0, 0, 0] == 0
    assert result[0, 1, 0] > array[0, 1, 0]


def test_maybe_expand_tonemapped_video_range_skips_deprecated_full_color_range() -> None:
    array = np.full((2, 2, 3), 32, dtype=np.uint8)

    result = _maybe_expand_tonemapped_video_range(
        array, {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_ColorRange": 0}
    )

    assert result is array


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
    # Intentional internal-seam coverage: render_frame tests below prove integration,
    # while this table protects the stable `_PictType` normalization contract.
    assert normalize_picture_type(prop_value) == expected


def test_render_vs_reads_picture_type_from_exact_diagnostic_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("frame_compare.render.encoders._render_vs", MagicMock())

    class _Frame:
        def __init__(self, picture_type: str) -> None:
            self.props = {"_PictType": picture_type}

    class _Node:
        def __init__(self, picture_type: str) -> None:
            self.picture_type = picture_type
            self.requested: list[int] = []

        def get_frame(self, index: int) -> _Frame:
            self.requested.append(index)
            return _Frame(self.picture_type)

    transformed = _Node("P")
    source = _Node("B")
    result = render_frame_detailed(
        RenderRequest(
            clip=transformed,  # type: ignore[arg-type]
            diagnostic_source=source,  # type: ignore[arg-type]
            frame_number=7,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
        ),
        renderer="vapoursynth",
    )

    assert result.facts.picture_type == "B"
    assert source.requested == [7]
    assert transformed.requested == []


def test_render_vs_applies_geometry_plan_before_saving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    class _RgbFrame:
        def __init__(self) -> None:
            self.props = {}
            self.format = SimpleNamespace(num_planes=3)
            self._planes = [
                np.full((4, 4), 255, dtype=np.uint8),
                np.zeros((4, 4), dtype=np.uint8),
                np.zeros((4, 4), dtype=np.uint8),
            ]

        def __getitem__(self, index: int) -> np.ndarray:
            return self._planes[index]

    class _RgbClip:
        def __init__(self) -> None:
            self.format = SimpleNamespace(id=1, color_family=2)
            self._frame = _RgbFrame()
            self.requested_frames: list[int] = []

        def get_frame(self, index: int) -> _RgbFrame:
            self.requested_frames.append(index)
            return self._frame

    output = tmp_path / "out.png"
    clip = _RgbClip()
    render_frame(
        RenderRequest(
            clip=clip,  # type: ignore[arg-type]
            diagnostic_source=clip,  # type: ignore[arg-type]
            frame_number=3,
            output_path=output,
            overlay=None,
            encoder_settings=EncoderSettings(),
            geometry_plan=_geometry_plan(),
        ),
        renderer="vapoursynth",
    )

    with Image.open(output) as image:
        assert image.size == (4, 4)
        assert image.getpixel((0, 0)) == (0, 0, 0)
        assert image.getpixel((1, 0)) == (255, 0, 0)
        assert image.getpixel((2, 0)) == (255, 0, 0)
        assert image.getpixel((3, 0)) == (0, 0, 0)
    assert clip.requested_frames[-1] == 3


def test_render_vs_missing_or_invalid_source_property_is_nonfatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("frame_compare.render.encoders._render_vs", MagicMock())

    class _Source:
        def get_frame(self, index: int) -> object:
            assert index == 3
            return SimpleNamespace(props={"_PictType": "unknown"})

    result = render_frame_detailed(
        RenderRequest(
            clip=object(),  # type: ignore[arg-type]
            diagnostic_source=_Source(),  # type: ignore[arg-type]
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
        ),
        renderer="vapoursynth",
    )
    assert result.facts.picture_type is None
