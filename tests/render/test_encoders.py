import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image
from vapoursynth import VideoNode

from frame_compare.config.schema_enums import VsScreenshotWriter
from frame_compare.render.color import untagged_matrix
from frame_compare.render.encoders import (
    _clip_to_rgb24_for_pillow,
    _map_fpng_compression,
    _maybe_expand_tonemapped_video_range,
    _resolve_matrix_in_s,
    render_frame_detailed,
)
from frame_compare.render.errors import (
    EncodingError,
    OverlayError,
    RenderError,
)
from frame_compare.render.geometry import (
    GeometryMargins,
    GeometryRect,
    RenderGeometryPlan,
    SourceGeometry,
)
from frame_compare.render.types import EncoderSettings, OverlayConfig, OverlayMode, RenderRequest
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedGeometryFacts,
    SourceSignalFacts,
    normalize_picture_type,
)


@pytest.fixture
def mock_render_vs(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("frame_compare.render.encoders._render_vs", mock)
    return mock


class FakeClip:
    width = 4
    height = 4


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
        tonemap=None,
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

    def Write(
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

    def CropRel(
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

    def AddBorders(
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

    def SetFrameProps(self, **_props: object) -> "_FakeFpngClip":
        return self._clip


class _FakeVsResize:
    def __init__(self, clip: "_FakeFpngClip") -> None:
        self._clip = clip

    def Spline36(self, *, width: int, height: int) -> "_FakeFpngClip":
        return self._clip.with_op(("resize", {"width": width, "height": height}))


class _FakeFpngFrame:
    def __init__(self, props: dict[str, object]) -> None:
        self.props = props


class _FakeFpngClip:
    width = 6
    height = 4

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
        clip=cast(VideoNode, clip),
        diagnostic_source=cast(VideoNode, clip),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )
    render_frame_detailed(request)
    mock_render_vs.assert_called_once()


def test_render_frame_overlay_integration(mock_render_vs):
    clip = FakeClip()
    overlay = _overlay(frame=100)
    request = RenderRequest(
        clip=cast(VideoNode, clip),
        diagnostic_source=cast(VideoNode, clip),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=overlay,
        encoder_settings=EncoderSettings(),
    )
    render_frame_detailed(request)

    mock_render_vs.assert_called_once()
    call_args = mock_render_vs.call_args
    assert call_args[1]["overlay"] == overlay


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

    render_frame_detailed(
        RenderRequest(
            clip=cast(VideoNode, clip),
            diagnostic_source=cast(VideoNode, clip),
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
    assert clip.frame_reads == [3, 3]


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

    render_frame_detailed(
        RenderRequest(
            clip=cast(VideoNode, clip),
            diagnostic_source=cast(VideoNode, clip),
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.AUTO),
            geometry_plan=None,
        ),
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

    render_frame_detailed(
        RenderRequest(
            clip=cast(VideoNode, clip),
            diagnostic_source=cast(VideoNode, clip),
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=overlay,
            encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.AUTO),
        ),
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

    render_frame_detailed(
        RenderRequest(
            clip=cast(VideoNode, clip),
            diagnostic_source=cast(VideoNode, clip),
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.PILLOW),
        ),
    )

    assert fpng.calls == []
    pillow.assert_called_once()


def test_render_frame_vs_fpng_requires_plugin_when_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "vapoursynth", SimpleNamespace(RGB24=1, RGB=2))
    clip = _FakeFpngClip()

    with pytest.raises(EncodingError) as exc_info:
        render_frame_detailed(
            RenderRequest(
                clip=cast(VideoNode, clip),
                diagnostic_source=cast(VideoNode, clip),
                frame_number=3,
                output_path=tmp_path / "out.png",
                overlay=None,
                encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.FPNG),
            ),
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
        render_frame_detailed(
            RenderRequest(
                clip=cast(VideoNode, clip),
                diagnostic_source=cast(VideoNode, clip),
                frame_number=3,
                output_path=tmp_path / "out.png",
                overlay=_overlay(frame=3),
                encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.FPNG),
            ),
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

    render_frame_detailed(
        RenderRequest(
            clip=cast(VideoNode, clip),
            diagnostic_source=cast(VideoNode, clip),
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.AUTO),
        ),
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
        render_frame_detailed(
            RenderRequest(
                clip=cast(VideoNode, clip),
                diagnostic_source=cast(VideoNode, clip),
                frame_number=3,
                output_path=tmp_path / "out.png",
                overlay=None,
                encoder_settings=EncoderSettings(vs_writer=VsScreenshotWriter.FPNG),
            ),
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
    source = SourceGeometry(
        width=source_size[0],
        height=source_size[1],
        active_rect=crop_rect,
        provenance="dimension_derived",
    )
    source_rect = GeometryRect(0, 0, source.width, source.height)
    return RenderGeometryPlan(
        source=source,
        source_rect=source_rect,
        active_rect=crop_rect,
        provenance="dimension_derived",
        crop_rect=crop_rect,
        crop=GeometryMargins(left=crop_rect.x, right=source.width - crop_rect.right),
        cropped_size=(crop_rect.width, crop_rect.height),
        scaled_size=scaled_size,
        pad=pad,
        final_canvas_size=final_canvas_size,
        content_origin=(pad.left, pad.top),
        overlay_origin=(pad.left + 10, pad.top + 10),
    )


def test_oversized_padding_never_reaches_vapoursynth_frame_work(tmp_path: Path) -> None:
    clip = MagicMock(width=4, height=4)
    geometry = replace(_geometry_plan(), pad=GeometryMargins(left=10**1000))
    output = tmp_path / "out.png"
    with pytest.raises(RenderError, match="7,680 pixels per axis"):
        render_frame_detailed(
            RenderRequest(
                clip=clip,
                diagnostic_source=clip,
                frame_number=0,
                output_path=output,
                overlay=None,
                encoder_settings=EncoderSettings(),
                geometry_plan=geometry,
            ),
        )
    clip.get_frame.assert_not_called()
    assert not output.exists()


def test_error_wrapping(mock_render_vs):
    error = OverlayError("overlay failed")
    mock_render_vs.side_effect = error
    clip = FakeClip()
    rendered_node = SimpleNamespace(
        width=clip.width,
        height=clip.height,
        format=SimpleNamespace(
            name="RGB24", color_family=2, sample_type=0, bits_per_sample=8, num_planes=3
        ),
    )
    request = RenderRequest(
        clip=cast(VideoNode, rendered_node),
        diagnostic_source=cast(VideoNode, clip),
        frame_number=100,
        output_path=Path("out.png"),
        overlay=None,
        encoder_settings=EncoderSettings(),
    )

    with pytest.raises(RenderError) as excinfo:
        render_frame_detailed(request)

    assert excinfo.value.__cause__ is error
    assert (
        excinfo.value.context.message == f"Final render composition failed: {error.context.message}"
    )
    assert excinfo.value.context.details == {
        "frame": 100,
        "output_path": str(request.output_path),
        "clip_format": "RGB24",
        "color_family": 2,
        "sample_type": 0,
        "bits_per_sample": 8,
        "num_planes": 3,
    }


class _FakeResize:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def Bicubic(self, **kwargs: object) -> str:
        self.calls.append(("Bicubic", dict(kwargs)))
        return "bicubic"

    def Point(self, **kwargs: object) -> str:
        self.calls.append(("Point", dict(kwargs)))
        return "point"


class _FakeFrame:
    def __init__(self, props: dict[str, object]) -> None:
        self.props = props


class _FakeClip:
    def __init__(
        self, *, fmt: object | None, props: dict[str, object], size: tuple[int, int] = (1920, 1080)
    ) -> None:
        self.format = fmt
        self.width, self.height = size
        self.resize = _FakeResize()
        self.std = MagicMock()
        self.get_frame = MagicMock(return_value=_FakeFrame(props))


def test_untagged_matrix_uses_both_coded_dimension_boundaries() -> None:
    cases = [
        ((720, 480), "170m"),
        ((720, 576), "170m"),
        ((704, 576), "170m"),
        ((1024, 576), "170m"),
        ((1025, 576), "709"),
        ((1024, 577), "709"),
        ((1280, 536), "709"),
        ((1920, 540), "709"),
    ]
    assert [untagged_matrix(*size, is_hdr=False) for size, _ in cases] == [
        expected for _, expected in cases
    ]
    for size, expected in cases:
        # The writer must use the same coded-size policy.
        clip = _FakeClip(fmt=None, props={}, size=size)
        assert _resolve_matrix_in_s(cast(VideoNode, clip)) == expected
    assert untagged_matrix(720, 480, is_hdr=True) == "2020ncl"


@pytest.mark.parametrize(
    ("fmt", "size", "props", "source_signal", "expected_matrix"),
    [
        (SimpleNamespace(id=999, color_family=3), (1024, 576), {}, None, "170m"),
        (
            SimpleNamespace(id=999, color_family=3),
            (720, 480),
            {"_Transfer": 16, "_Primaries": 9},
            None,
            "2020ncl",
        ),
        (
            SimpleNamespace(id=999, color_family=3),
            (720, 480),
            {"_Matrix": 1, "_Transfer": 16, "_Primaries": 9},
            SourceSignalFacts(is_hdr=True, matrix=6),
            "709",
        ),
        (None, (1025, 576), {"_Matrix": 2}, None, "709"),
    ],
)
def test_clip_to_rgb24_for_pillow_maps_yuv_matrix_for_pillow(
    monkeypatch,
    fmt: object | None,
    size: tuple[int, int],
    props: dict[str, object],
    source_signal: SourceSignalFacts | None,
    expected_matrix: str,
) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)
    clip = _FakeClip(fmt=fmt, size=size, props=props)

    assert _clip_to_rgb24_for_pillow(cast(VideoNode, clip), source_signal) == "bicubic"
    assert clip.resize.calls[0] == ("Bicubic", {"format": 1, "matrix_in_s": expected_matrix})


def test_clip_to_rgb24_for_pillow_already_rgb24_passthrough(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=1, color_family=2)
    clip = _FakeClip(fmt=fmt, props={"_Matrix": 5})
    result = _clip_to_rgb24_for_pillow(cast(VideoNode, clip))

    assert result is clip
    assert clip.resize.calls == []
    clip.get_frame.assert_not_called()


def test_clip_to_rgb24_for_pillow_rgb_non_24_uses_point(monkeypatch) -> None:
    fake_vs = SimpleNamespace(RGB24=1, RGB=2)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    fmt = SimpleNamespace(id=999, color_family=2)
    clip = _FakeClip(fmt=fmt, props={})
    result = _clip_to_rgb24_for_pillow(cast(VideoNode, clip))

    assert result == "point"
    assert clip.resize.calls[0][0] == "Point"


@pytest.mark.parametrize(
    "range_props",
    [
        {"_Range": 0},
        {"_ColorRange": 1},
    ],
)
def test_clip_to_rgb24_for_pillow_leaves_range_guard_to_selected_frame(
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

    result = _clip_to_rgb24_for_pillow(cast(VideoNode, clip))

    assert result is clip
    clip.resize.Point.assert_called_once_with(format=1)
    clip.get_frame.assert_not_called()
    clip.std.SetFrameProps.assert_not_called()


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

    result = _clip_to_rgb24_for_pillow(cast(VideoNode, clip))

    assert result == "point"
    assert clip.resize.calls[0] == ("Point", {"format": 1})


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
    assert normalize_picture_type(prop_value) == expected


def test_render_vs_reads_picture_type_from_exact_diagnostic_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("frame_compare.render.encoders._render_vs", MagicMock())

    class _Frame:
        def __init__(self, picture_type: str) -> None:
            self.props = {"_PictType": picture_type, "DolbyVisionRPU": b"opaque-rpu"}

    class _Node:
        width = 4
        height = 4

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
            clip=cast(VideoNode, transformed),
            diagnostic_source=cast(VideoNode, source),
            frame_number=7,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
        ),
    )

    assert result.facts.picture_type == "B"
    assert result.facts.dolby_vision_rpu is True
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
        width = 4
        height = 4

        def __init__(self) -> None:
            self.format = SimpleNamespace(id=1, color_family=2)
            self._frame = _RgbFrame()
            self.requested_frames: list[int] = []

        def get_frame(self, index: int) -> _RgbFrame:
            self.requested_frames.append(index)
            return self._frame

    output = tmp_path / "out.png"
    clip = _RgbClip()
    render_frame_detailed(
        RenderRequest(
            clip=cast(VideoNode, clip),
            diagnostic_source=cast(VideoNode, clip),
            frame_number=3,
            output_path=output,
            overlay=None,
            encoder_settings=EncoderSettings(),
            geometry_plan=_geometry_plan(),
        ),
    )

    with Image.open(output) as image:
        assert image.size == (4, 4)
        assert image.getpixel((0, 0)) == (0, 0, 0)
        assert image.getpixel((1, 0)) == (255, 0, 0)
        assert image.getpixel((2, 0)) == (255, 0, 0)
        assert image.getpixel((3, 0)) == (0, 0, 0)
    assert clip.requested_frames[-1] == 3


@pytest.mark.parametrize("source_case", ["invalid", "missing", "raises"])
def test_render_vs_missing_or_invalid_source_property_is_nonfatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_case: str,
) -> None:
    monkeypatch.setattr("frame_compare.render.encoders._render_vs", MagicMock())

    class _Source:
        width = 4
        height = 4

        def get_frame(self, index: int) -> object:
            assert index == 3
            if source_case == "raises":
                raise RuntimeError("frame metadata unavailable")
            props = {"_PictType": "unknown"} if source_case == "invalid" else {}
            return SimpleNamespace(props=props)

    result = render_frame_detailed(
        RenderRequest(
            clip=cast(VideoNode, FakeClip()),
            diagnostic_source=cast(VideoNode, _Source()),
            frame_number=3,
            output_path=tmp_path / "out.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
        ),
    )
    assert result.facts.picture_type is None
    assert result.facts.dolby_vision_rpu is (None if source_case == "raises" else False)


@pytest.mark.parametrize(
    "array, props, brighter",
    [
        pytest.param(
            np.full((2, 2, 3), 32, dtype=np.uint8), {"_Tonemapped": 1}, None, id="requires_marker"
        ),
        pytest.param(
            np.array(
                [
                    [[16, 16, 16], [32, 32, 32], [90, 90, 90]],
                    [[18, 18, 18], [48, 48, 48], [120, 120, 120]],
                ],
                dtype=np.uint8,
            ),
            {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_Range": 0},
            (1, 2, 0),
            id="marked_limited",
        ),
        pytest.param(
            np.full((2, 2, 3), 32, dtype=np.uint8),
            {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_Range": 1},
            None,
            id="marked_full",
        ),
        pytest.param(
            np.array([[[16, 16, 16], [120, 120, 120]]], dtype=np.uint8),
            {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_ColorRange": 1},
            (0, 1, 0),
            id="deprecated_limited",
        ),
        pytest.param(
            np.full((2, 2, 3), 32, dtype=np.uint8),
            {"_Tonemapped": 1, "_FrameCompareExpandRange": 1, "_ColorRange": 0},
            None,
            id="deprecated_full",
        ),
    ],
)
def test_tonemapped_video_range_cases(
    array: NDArray[np.uint8], props: dict[str, object], brighter: tuple[int, int, int] | None
) -> None:
    result = _maybe_expand_tonemapped_video_range(array, props)
    if brighter is None:
        assert result is array
    else:
        assert result.dtype == np.uint8
        assert result[0, 0, 0] == 0
        assert result[brighter] > array[brighter]
