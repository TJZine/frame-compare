import logging
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Optional, Sequence, TypedDict, cast

import pytest

from src import screenshot, vs_core
from src.datatypes import ColorConfig, OddGeometryPolicy, RGBDither, ScreenshotConfig
from src.screenshot import GeometryPlan, _compute_requires_full_chroma


class _CapturedWriterCall(TypedDict):
    crop: tuple[int, int, int, int]
    scaled: tuple[int, int]
    pad: tuple[int, int, int, int]
    label: str
    requested: int
    frame: int
    selection_label: Optional[str]
    source: Optional[str]


class FakeClip:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height


def _prepare_fake_vapoursynth_clip(
    monkeypatch: pytest.MonkeyPatch,
    *,
    width: int,
    height: int,
    subsampling_w: int,
    subsampling_h: int,
    bits_per_sample: int,
    color_family: str = "YUV",
    format_name: str | None = None,
) -> tuple[Any, Any, list[dict[str, Any]], list[dict[str, Any]]]:
    """Install a lightweight VapourSynth stub and return a synthetic clip and call logs."""

    writer_calls: list[dict[str, Any]] = []
    resize_calls: list[dict[str, Any]] = []

    fake_vs = types.SimpleNamespace()
    yuv_constant = object()
    rgb_constant = object()

    class _FakeFormat:
        def __init__(
            self,
            *,
            color_family_obj: object,
            bits_per_sample_val: int,
            subsampling_w_val: int,
            subsampling_h_val: int,
            name_val: str,
        ) -> None:
            self.color_family = color_family_obj
            self.bits_per_sample = bits_per_sample_val
            self.subsampling_w = subsampling_w_val
            self.subsampling_h = subsampling_h_val
            self.name = name_val

    class _FakeStd:
        def __init__(self, parent: "_FakeClip") -> None:
            self._parent = parent

        def CropRel(
            self,
            *,
            left: int,
            right: int,
            top: int,
            bottom: int,
        ) -> "_FakeClip":
            new_width = self._parent.width - left - right
            new_height = self._parent.height - top - bottom
            return self._parent._with_dimensions(width=new_width, height=new_height)

        def AddBorders(
            self,
            clip: "_FakeClip",
            *,
            left: int,
            right: int,
            top: int,
            bottom: int,
        ) -> "_FakeClip":
            return clip._with_dimensions(
                width=clip.width + left + right,
                height=clip.height + top + bottom,
            )

        def CopyFrameProps(self, clip: "_FakeClip", _src: "_FakeClip") -> "_FakeClip":
            return clip

        def SetFrameProps(self, **_: Any) -> "_FakeClip":
            return self._parent

    class _FakeClip:
        def __init__(self, width: int, height: int, format_obj: _FakeFormat, core: Any) -> None:
            self.width = width
            self.height = height
            self.format = format_obj
            self.core = core

        def _with_dimensions(
            self,
            *,
            width: int | None = None,
            height: int | None = None,
            format_obj: _FakeFormat | None = None,
        ) -> "_FakeClip":
            return _FakeClip(
                width if width is not None else self.width,
                height if height is not None else self.height,
                format_obj if format_obj is not None else self.format,
                self.core,
            )

        @property
        def std(self) -> _FakeStd:
            return _FakeStd(self)

    class _FakeResize:
        def Point(self, clip: _FakeClip, **kwargs: Any) -> _FakeClip:
            resize_calls.append(kwargs)
            fmt = kwargs.get("format")
            if fmt == fake_vs.YUV444P16:
                promoted_format = _FakeFormat(
                    color_family_obj=yuv_constant,
                    bits_per_sample_val=16,
                    subsampling_w_val=0,
                    subsampling_h_val=0,
                    name_val="YUV444P16",
                )
                return clip._with_dimensions(format_obj=promoted_format)
            if fmt == fake_vs.RGB24:
                rgb_format = _FakeFormat(
                    color_family_obj=rgb_constant,
                    bits_per_sample_val=8,
                    subsampling_w_val=0,
                    subsampling_h_val=0,
                    name_val="RGB24",
                )
                return clip._with_dimensions(format_obj=rgb_format)
            return clip

        def Spline36(self, clip: _FakeClip, **_: Any) -> _FakeClip:
            return clip

    class _FakeFpng:
        def Write(self, _clip: _FakeClip, path: str, **kwargs: Any) -> Any:
            writer_calls.append(kwargs)

            class _Job:
                def get_frame(self, _index: int) -> None:
                    return None

            Path(path).write_text("png", encoding="utf-8")
            return _Job()

    def _core_add_borders(
        clip: _FakeClip,
        *,
        left: int,
        right: int,
        top: int,
        bottom: int,
    ) -> _FakeClip:
        return clip._with_dimensions(
            width=clip.width + left + right,
            height=clip.height + top + bottom,
        )

    fake_core = types.SimpleNamespace(
        resize=_FakeResize(),
        fpng=_FakeFpng(),
        std=types.SimpleNamespace(
            AddBorders=_core_add_borders,
            SetFrameProps=lambda clip, **_: clip,
            CopyFrameProps=lambda clip, _src: clip,
        ),
    )

    fake_vs.VideoNode = _FakeClip
    fake_vs.YUV = yuv_constant
    fake_vs.RGB = rgb_constant
    fake_vs.YUV444P16 = "YUV444P16"
    fake_vs.RGB24 = "RGB24"
    fake_vs.RANGE_FULL = 0
    fake_vs.RANGE_LIMITED = 1
    fake_vs.MATRIX_BT709 = 1
    fake_vs.TRANSFER_BT709 = 1
    fake_vs.PRIMARIES_BT709 = 1
    fake_vs.core = fake_core

    initial_color = yuv_constant if color_family.upper() == "YUV" else rgb_constant
    initial_format = _FakeFormat(
        color_family_obj=initial_color,
        bits_per_sample_val=bits_per_sample,
        subsampling_w_val=subsampling_w,
        subsampling_h_val=subsampling_h,
        name_val=format_name or "SyntheticFormat",
    )

    clip = _FakeClip(width, height, initial_format, fake_core)

    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    return clip, fake_vs, writer_calls, resize_calls

@pytest.fixture(autouse=True)
def _stub_process_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace screenshot.vs_core.process_clip_for_screenshot with a test stub that simulates a processed clip.

    This fixture patches the target function so it returns a types.SimpleNamespace containing:
    - clip: the passed-in clip
    - overlay_text: None
    - verification: None
    - tonemap: a vs_core.TonemapInfo indicating an untonemapped SDR source (applied=False, target_nits=100.0, dst_min_nits=0.1, reason="SDR source")
    - source_props: an empty dict

    Parameters:
        monkeypatch: pytest's monkeypatch fixture used to apply the patch.
    """
    def _stub(
        clip: FakeClip,
        file_name: str,
        color_cfg: ColorConfig,
        **kwargs: object,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            clip=clip,
            overlay_text=None,
            verification=None,
            tonemap=vs_core.TonemapInfo(
                applied=False,
                tone_curve=None,
                dpd=0,
                target_nits=100.0,
                dst_min_nits=0.1,
                src_csp_hint=None,
                reason="SDR source",
            ),
            source_props={},
        )

    monkeypatch.setattr(screenshot.vs_core, "process_clip_for_screenshot", _stub)


def test_resolve_source_props_normalises_missing_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_normalise(clip: Any, source_props: Any, **kwargs: Any) -> tuple[str, dict[str, int], tuple[int, int, int, int]]:
        captured["kwargs"] = kwargs
        return "normalized", {"_ColorRange": 1}, (1, 1, 1, 1)

    monkeypatch.setattr(vs_core, "normalise_color_metadata", fake_normalise)

    clip, props = screenshot._resolve_source_props(
        "clip",
        {},
        color_cfg=ColorConfig(),
        file_name="demo.mkv",
    )

    assert clip == "normalized"
    assert props == {"_ColorRange": 1}
    assert captured["kwargs"]["file_name"] == "demo.mkv"


def test_resolve_source_props_skips_normalisation_when_range_present(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_normalise(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal called
        called = True
        return "normalized", {"_ColorRange": 1}, (1, 1, 1, 1)

    monkeypatch.setattr(vs_core, "normalise_color_metadata", fake_normalise)

    clip, props = screenshot._resolve_source_props(
        "original",
        {"_ColorRange": 1},
        color_cfg=ColorConfig(),
        file_name="demo.mkv",
    )

    assert clip == "original"
    assert props == {"_ColorRange": 1}
    assert called is False


def test_sanitise_label_replaces_forbidden_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screenshot.os, "name", "nt")
    raw = 'Group: Episode? 01*<>"| '
    cleaned = screenshot._sanitise_label(raw)
    assert cleaned
    for forbidden in ':?*<>"|':
        assert forbidden not in cleaned
    assert not cleaned.endswith((" ", "."))


def test_sanitise_label_falls_back_when_blank() -> None:
    cleaned = screenshot._sanitise_label("   ")
    assert cleaned == "comparison"


def test_plan_mod_crop_modulus() -> None:
    left, top, right, bottom = screenshot.plan_mod_crop(1919, 1079, mod=4, letterbox_pillarbox_aware=True)
    new_w = 1919 - left - right
    new_h = 1079 - top - bottom
    assert new_w % 4 == 0
    assert new_h % 4 == 0
    assert new_w > 0 and new_h > 0


def test_plan_geometry_letterbox_alignment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(3840, 2160), FakeClip(3840, 1800)]
    cfg = ScreenshotConfig(directory_name="screens", add_frame_info=False)
    color_cfg = ColorConfig()

    captured: list[_CapturedWriterCall] = []

    def fake_writer(
        clip: FakeClip,
        frame_idx: int,
        crop: tuple[int, int, int, int],
        scaled: tuple[int, int],
        pad: tuple[int, int, int, int],
        path: Path,
        cfg: ScreenshotConfig,
        label: str,
        requested_frame: int,
        selection_label: str | None = None,
        **kwargs: object,
    ) -> None:
        captured.append(
            {
                "crop": crop,
                "scaled": scaled,
                "pad": pad,
                "label": str(label),
                "requested": int(requested_frame),
                "frame": int(frame_idx),
                "selection_label": selection_label,
                "source": None,
            }
        )
        Path(path).write_text("data", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_writer)
    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", lambda *args, **kwargs: None)

    frames: list[int] = [0]
    files: list[str] = ["clip_a.mkv", "clip_b.mkv"]
    metadata: list[dict[str, str]] = [{"label": "Clip A"}, {"label": "Clip B"}]

    screenshot.generate_screenshots(
        clips,
        frames,
        files,
        metadata,
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    assert len(captured) == 2
    assert captured[0]["crop"] == (0, 180, 0, 180)
    assert captured[0]["scaled"] == (3840, 1800)
    assert captured[1]["crop"] == (0, 0, 0, 0)
    assert captured[1]["scaled"] == (3840, 1800)


def test_generate_screenshots_debug_color_disables_overlays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clip, fake_vs, _, _ = _prepare_fake_vapoursynth_clip(
        monkeypatch,
        width=1920,
        height=1080,
        subsampling_w=1,
        subsampling_h=1,
        bits_per_sample=8,
        color_family="YUV",
        format_name="YUV420P8",
    )
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)

    cfg = ScreenshotConfig(directory_name="screens", add_frame_info=True, use_ffmpeg=False)
    color_cfg = ColorConfig()
    color_cfg.debug_color = True

    captured: dict[str, Any] = {}

    def fake_writer(
        clip: Any,
        frame_idx: int,
        crop: tuple[int, int, int, int],
        scaled: tuple[int, int],
        pad: tuple[int, int, int, int],
        path: Path,
        cfg: ScreenshotConfig,
        label: str,
        requested_frame: int,
        selection_label: str | None = None,
        *,
        overlay_text: Optional[str] = None,
        debug_state: Any = None,
        frame_info_allowed: bool = True,
        overlays_allowed: bool = True,
        **kwargs: Any,
    ) -> None:
        captured.setdefault("overlay_text", overlay_text)
        captured.setdefault("frame_info_allowed", frame_info_allowed)
        captured.setdefault("overlays_allowed", overlays_allowed)
        Path(path).write_text("data", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_writer)
    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", lambda *args, **kwargs: None)

    artifact = vs_core.ColorDebugArtifacts(
        normalized_clip=clip,
        normalized_props={},
        color_tuple=(1, 1, 1, 1),
    )
    tonemap_info = vs_core.TonemapInfo(
        applied=False,
        tone_curve=None,
        dpd=0,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
        reason="SDR source",
    )

    def fake_process(
        clip_in: Any,
        file_name: str,
        color_cfg_in: ColorConfig,
        **kwargs: Any,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            clip=clip_in,
            overlay_text="should be suppressed",
            verification=None,
            tonemap=tonemap_info,
            source_props={},
            debug=artifact,
        )

    monkeypatch.setattr(screenshot.vs_core, "process_clip_for_screenshot", fake_process)

    screenshot.generate_screenshots(
        [clip],
        [0],
        ["clip.mkv"],
        [{"label": "Debug Clip"}],
        tmp_path,
        cfg,
        color_cfg,
    )

    assert captured["overlay_text"] is None
    assert captured["frame_info_allowed"] is False
    assert captured["overlays_allowed"] is False


def test_plan_geometry_subsamp_safe_rebalance_aligns_modulus() -> None:
    class _Format:
        def __init__(self, subsampling_w: int, subsampling_h: int) -> None:
            self.subsampling_w = subsampling_w
            self.subsampling_h = subsampling_h

    class _ClipWithFormat:
        def __init__(self, width: int, height: int, subsampling_w: int, subsampling_h: int) -> None:
            self.width = width
            self.height = height
            self.format = _Format(subsampling_w, subsampling_h)

    cfg = ScreenshotConfig(
        directory_name="screens",
        add_frame_info=False,
        odd_geometry_policy=OddGeometryPolicy.SUBSAMP_SAFE,
        pad_to_canvas="on",
        mod_crop=4,
        letterbox_pillarbox_aware=True,
        center_pad=True,
        upscale=False,
    )

    clips: list[_ClipWithFormat] = [
        _ClipWithFormat(1919, 720, 1, 1),
        _ClipWithFormat(1920, 1080, 1, 1),
    ]

    plans = screenshot._plan_geometry(clips, cfg)

    first_plan = plans[0]
    assert first_plan["final"][0] % cfg.mod_crop == 0
    assert first_plan["final"][1] % cfg.mod_crop == 0
    assert not first_plan["requires_full_chroma"]
    assert first_plan["promotion_axes"] == "none"


@pytest.mark.parametrize(
    "policy,sub_w,sub_h,crop,pad,expected",
    [
        (OddGeometryPolicy.AUTO, 1, 1, (0, 1, 0, 0), (0, 0, 0, 0), True),
        (OddGeometryPolicy.AUTO, 1, 0, (0, 1, 0, 0), (0, 0, 0, 0), False),
        (OddGeometryPolicy.AUTO, 1, 0, (1, 0, 0, 0), (0, 0, 0, 0), True),
        (OddGeometryPolicy.AUTO, 1, 1, (0, 0, 0, 0), (0, 0, 0, 0), False),
        (OddGeometryPolicy.FORCE_FULL_CHROMA, 0, 0, (0, 0, 0, 0), (0, 0, 0, 0), True),
        (OddGeometryPolicy.SUBSAMP_SAFE, 1, 1, (0, 1, 0, 0), (0, 0, 0, 0), False),
    ],
)
def test_compute_requires_full_chroma_policy_matrix(
    policy: OddGeometryPolicy,
    sub_w: int,
    sub_h: int,
    crop: tuple[int, int, int, int],
    pad: tuple[int, int, int, int],
    expected: bool,
) -> None:
    fmt = types.SimpleNamespace(subsampling_w=sub_w, subsampling_h=sub_h)
    result = _compute_requires_full_chroma(fmt, crop, pad, policy)
    assert result is expected


def test_plan_geometry_aligns_vertical_odds_require_promotion() -> None:
    class _Format:
        def __init__(self, subsampling_w: int, subsampling_h: int) -> None:
            self.subsampling_w = subsampling_w
            self.subsampling_h = subsampling_h

    class _Clip:
        def __init__(self, width: int, height: int, fmt: _Format) -> None:
            self.width = width
            self.height = height
            self.format = fmt

    cfg = ScreenshotConfig(
        odd_geometry_policy=OddGeometryPolicy.AUTO,
        letterbox_pillarbox_aware=True,
        mod_crop=2,
        upscale=False,
    )

    clip_short = _Clip(1920, 1036, _Format(1, 1))
    clip_tall = _Clip(1920, 1038, _Format(1, 1))

    plans = screenshot._plan_geometry([clip_short, clip_tall], cfg)

    assert len(plans) == 2
    assert plans[0]["final"] == plans[1]["final"] == (1920, 1036)
    assert plans[1]["crop"] == (0, 1, 0, 1)
    assert plans[1]["requires_full_chroma"]
    assert not plans[0]["requires_full_chroma"]
    assert plans[1]["promotion_axes"] == "vertical"
    assert plans[0]["promotion_axes"] == "none"


def test_plan_geometry_even_difference_skips_full_chroma() -> None:
    class _Format:
        def __init__(self, subsampling_w: int, subsampling_h: int) -> None:
            self.subsampling_w = subsampling_w
            self.subsampling_h = subsampling_h

    class _Clip:
        def __init__(self, width: int, height: int, fmt: _Format) -> None:
            self.width = width
            self.height = height
            self.format = fmt

    cfg = ScreenshotConfig(
        odd_geometry_policy=OddGeometryPolicy.AUTO,
        letterbox_pillarbox_aware=True,
        mod_crop=2,
        upscale=False,
    )

    clip_short = _Clip(1920, 1036, _Format(1, 1))
    clip_taller = _Clip(1920, 1040, _Format(1, 1))

    plans = screenshot._plan_geometry([clip_short, clip_taller], cfg)

    assert len(plans) == 2
    assert plans[1]["crop"] == (0, 2, 0, 2)
    assert all(not plan["requires_full_chroma"] for plan in plans)
    assert plans[0]["final"] == plans[1]["final"]
    assert all(plan["promotion_axes"] == "none" for plan in plans)


def test_generate_screenshots_filenames(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clip = FakeClip(1280, 720)
    cfg = ScreenshotConfig(directory_name="screens")
    color_cfg = ColorConfig()

    calls: list[_CapturedWriterCall] = []

    def fake_writer(
        clip: FakeClip,
        frame_idx: int,
        crop: tuple[int, int, int, int],
        scaled: tuple[int, int],
        pad: tuple[int, int, int, int],
        path: Path,
        cfg: ScreenshotConfig,
        label: str,
        requested_frame: int,
        selection_label: str | None = None,
        **kwargs: object,
    ) -> None:
        calls.append(
            {
                "frame": int(frame_idx),
                "crop": crop,
                "scaled": scaled,
                "pad": pad,
                "label": str(label),
                "requested": int(requested_frame),
                "selection_label": selection_label,
                "source": None,
            }
        )
        Path(path).write_text("data", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_writer)

    frames: list[int] = [5, 25]
    files: list[str] = ["example_video.mkv"]
    metadata: list[dict[str, str]] = [{"label": "Example Release"}]
    created = screenshot.generate_screenshots(
        [clip],
        frames,
        files,
        metadata,
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0],
    )
    assert len(created) == len(frames)
    expected_names = {f"{frame} - Example Release.png" for frame in frames}
    assert {Path(path).name for path in created} == expected_names
    for entry in calls:
        assert entry["label"] == "Example Release"
        assert entry["requested"] == entry["frame"]

    assert len(calls) == len(frames)


def test_generate_screenshots_reports_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clips = [FakeClip(1280, 720)]
    frames = [0]
    files = ["clip.mkv"]
    metadata = [{}]
    cfg = ScreenshotConfig(directory_name="screens")
    color_cfg = ColorConfig()
    out_dir = tmp_path / "screens"

    path_type = type(out_dir)
    real_mkdir = path_type.mkdir

    def _deny_mkdir(
        self: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if self == out_dir:
            raise PermissionError("denied")
        real_mkdir(self, mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(path_type, "mkdir", _deny_mkdir)

    with pytest.raises(screenshot.ScreenshotError) as excinfo:
        screenshot.generate_screenshots(
            clips,
            frames,
            files,
            metadata,
            out_dir,
            cfg,
            color_cfg,
        )

    assert "Unable to create screenshot directory" in str(excinfo.value)


def _make_plan(
    *,
    width: int = 1920,
    height: int = 1080,
    crop: tuple[int, int, int, int] = (0, 0, 0, 0),
    cropped_w: int = 1920,
    cropped_h: int = 1080,
    scaled: tuple[int, int] = (1920, 1080),
    pad: tuple[int, int, int, int] = (0, 0, 0, 0),
    final: tuple[int, int] = (1920, 1080),
    requires_full_chroma: bool = False,
    promotion_axes: str = "none",
) -> GeometryPlan:
    """
    Builds a rendering plan dictionary describing dimensions, crop, scaling, padding, and final output size.

    Returns:
        dict: A plan mapping with the following keys:
            - "width": source frame width.
            - "height": source frame height.
            - "crop": 4-tuple (left, top, right, bottom) representing pixel crop offsets.
            - "cropped_w": width after cropping.
            - "cropped_h": height after cropping.
            - "scaled": 2-tuple (width, height) after scaling.
            - "pad": 4-tuple (left, top, right, bottom) of pixels added as padding.
            - "final": 2-tuple (width, height) of the final output frame.
            - "promotion_axes": Label describing which axes triggered 4:4:4 promotion.
    """
    plan = cast(
        GeometryPlan,
        {
            "width": width,
            "height": height,
            "crop": crop,
            "cropped_w": cropped_w,
            "cropped_h": cropped_h,
            "scaled": scaled,
            "pad": pad,
            "final": final,
            "requires_full_chroma": requires_full_chroma,
            "promotion_axes": promotion_axes,
        },
    )
    return plan


def test_compose_overlay_text_minimal_adds_resolution_and_selection() -> None:
    color_cfg = ColorConfig(overlay_mode="minimal")
    plan = _make_plan()
    base_text = "Tonemapping Algorithm: bt.2390 dpd = 1 dst = 100 nits"
    tonemap_info = vs_core.TonemapInfo(
        applied=True,
        tone_curve="bt.2390",
        dpd=1,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
    )

    composed = screenshot._compose_overlay_text(
        base_text,
        color_cfg,
        plan,
        selection_label="Dark",
        source_props={},
        tonemap_info=tonemap_info,
    )

    assert composed is not None
    lines = composed.split("\n")
    assert lines[0] == base_text
    assert lines[1] == "1920 × 1080  (native)"
    assert lines[2] == "Frame Selection Type: Dark"


def test_compose_overlay_text_minimal_handles_missing_base_and_label() -> None:
    color_cfg = ColorConfig(overlay_mode="minimal")
    plan = _make_plan()

    composed = screenshot._compose_overlay_text(
        base_text=None,
        color_cfg=color_cfg,
        plan=plan,
        selection_label=None,
        source_props={},
        tonemap_info=None,
    )

    assert composed is not None
    lines = composed.split("\n")
    assert lines[0] == "1920 × 1080  (native)"
    assert lines[1] == "Frame Selection Type: (unknown)"


def test_compose_overlay_text_minimal_ignores_hdr_details() -> None:
    color_cfg = ColorConfig(overlay_mode="minimal")
    plan = _make_plan()
    props = {
        "_MasteringDisplayMinLuminance": 0.0001,
        "_MasteringDisplayMaxLuminance": 1000.0,
    }
    tonemap_info = vs_core.TonemapInfo(
        applied=True,
        tone_curve="bt.2390",
        dpd=1,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
    )

    composed = screenshot._compose_overlay_text(
        base_text=None,
        color_cfg=color_cfg,
        plan=plan,
        selection_label="Dark",
        source_props=props,
        tonemap_info=tonemap_info,
    )

    assert composed is not None
    assert "MDL:" not in composed
    assert composed.endswith("Frame Selection Type: Dark")


def test_compose_overlay_text_diagnostic_appends_required_lines() -> None:
    color_cfg = ColorConfig(overlay_mode="diagnostic")
    plan = _make_plan(
        scaled=(3840, 2160),
        final=(3840, 2160),
    )
    base_text = "Tonemapping Algorithm: bt.2390 dpd = 1 dst = 100 nits"
    tonemap_info = vs_core.TonemapInfo(
        applied=True,
        tone_curve="bt.2390",
        dpd=1,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
    )
    props = {
        "_MasteringDisplayMinLuminance": 0.0001,
        "_MasteringDisplayMaxLuminance": 1000.0,
    }

    composed = screenshot._compose_overlay_text(
        base_text,
        color_cfg,
        plan,
        selection_label="Dark",
        source_props=props,
        tonemap_info=tonemap_info,
    )

    assert composed is not None
    lines = composed.split("\n")
    assert lines[0] == base_text
    assert lines[1] == "1920 × 1080 → 3840 × 2160  (original → target)"
    assert lines[2] == "MDL: min: 0.0001 cd/m², max: 1000.0 cd/m²"
    assert lines[3] == "Frame Selection Type: Dark"


def test_compose_overlay_text_skips_hdr_details_for_sdr() -> None:
    color_cfg = ColorConfig(overlay_mode="diagnostic")
    plan = _make_plan()
    base_text = "Tonemapping Algorithm: bt.2390 dpd = 1 dst = 100 nits"
    tonemap_info = vs_core.TonemapInfo(
        applied=False,
        tone_curve=None,
        dpd=0,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
        reason="SDR source",
    )

    composed = screenshot._compose_overlay_text(
        base_text,
        color_cfg,
        plan,
        selection_label="Cached",
        source_props={},
        tonemap_info=tonemap_info,
    )

    assert composed is not None
    lines = composed.split("\n")
    assert "MDL:" not in composed
    assert "Measurement" not in composed
    assert lines[-1] == "Frame Selection Type: Cached"


def test_compression_flag_passed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clip = FakeClip(1920, 1080)
    cfg = ScreenshotConfig(use_ffmpeg=True, compression_level=2)
    color_cfg = ColorConfig()

    captured: dict[int, int] = {}

    def fake_writer(
        source: Path,
        frame_idx: int,
        crop: tuple[int, int, int, int],
        scaled: tuple[int, int],
        pad: tuple[int, int, int, int],
        path: Path,
        cfg: ScreenshotConfig,
        width: int,
        height: int,
        selection_label: str | None,
        *,
        overlay_text: str | None = None,
        is_sdr: bool = True,
        **_kwargs: Any,
    ) -> None:
        captured[frame_idx] = screenshot._map_ffmpeg_compression(cfg.compression_level)
        path.write_text("ffmpeg", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", fake_writer)

    screenshot.generate_screenshots(
        [clip],
        [10],
        ["video.mkv"],
        [{"label": "video"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0],
    )
    assert captured[10] == 9


def test_ffmpeg_respects_trim_offsets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clip = FakeClip(1920, 1080)
    cfg = ScreenshotConfig(use_ffmpeg=True)
    color_cfg = ColorConfig()

    calls: list[int] = []

    def fake_ffmpeg(
        source,
        frame_idx,
        crop,
        scaled,
        pad,
        path,
        cfg,
        width,
        height,
        selection_label,
        *,
        overlay_text=None,
        is_sdr: bool = True,
        **_kwargs: Any,
    ):
        calls.append(frame_idx)
        Path(path).write_text("ff", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", fake_ffmpeg)
    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", lambda *args, **kwargs: None)

    screenshot.generate_screenshots(
        [clip],
        [0, 5],
        ["video.mkv"],
        [{"label": "video"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[3],
    )

    assert calls == [3, 8]


def test_global_upscale_coordination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(1280, 720), FakeClip(1920, 1080), FakeClip(640, 480)]
    cfg = ScreenshotConfig(upscale=True, use_ffmpeg=False, add_frame_info=False)
    color_cfg = ColorConfig()

    scaled: list[tuple[int, int]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        scaled.append((scaled_dims, pad))
        Path(path).write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)
    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", lambda *args, **kwargs: None)

    metadata: list[dict[str, str]] = [{"label": f"clip{i}"} for i in range(len(clips))]
    screenshot.generate_screenshots(
        clips,
        [0],
        [f"clip{i}.mkv" for i in range(len(clips))],
        metadata,
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0, 0],
    )

    assert [dims for dims, _ in scaled] == [(1920, 1080), (1920, 1080), (1440, 1080)]
    assert all(pad == (0, 0, 0, 0) for _, pad in scaled)


def test_upscale_clamps_letterbox_width(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(3840, 2160), FakeClip(3832, 1384)]
    cfg = ScreenshotConfig(upscale=True, use_ffmpeg=False, add_frame_info=False)
    color_cfg = ColorConfig()

    recorded: list[tuple[int, int]] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        recorded.append((scaled_dims, pad))
        Path(path).write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    metadata: list[dict[str, str]] = [{"label": "hdr"}, {"label": "scope"}]
    screenshot.generate_screenshots(
        clips,
        [0],
        ["hdr.mkv", "scope.mkv"],
        metadata,
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    assert recorded[0][0] == (3840, 2160)
    assert recorded[0][1] == (0, 0, 0, 0)
    expected_height = int(round(1384 * (3840 / 3832)))
    assert recorded[1][0] == (3840, expected_height)
    assert recorded[1][1] == (0, 0, 0, 0)


def test_auto_letterbox_crop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(3840, 2160), FakeClip(3832, 1384)]
    cfg = ScreenshotConfig(
        upscale=False,
        use_ffmpeg=False,
        add_frame_info=False,
        auto_letterbox_crop=True,
    )
    color_cfg = ColorConfig()

    captured: list[_CapturedWriterCall] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append(
            {
                "crop": crop,
                "scaled": scaled_dims,
                "pad": pad,
                "label": str(label),
                "requested": int(requested_frame),
                "frame": int(frame_idx),
                "selection_label": selection_label,
                "source": None,
            }
        )
        Path(path).write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["bars.mkv", "scope.mkv"],
        [{"label": "bars"}, {"label": "scope"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    assert len(captured) == 2
    first_crop = captured[0]["crop"]
    assert isinstance(first_crop, tuple)
    assert first_crop[1] > 0 and first_crop[3] > 0
    assert captured[0]["scaled"] == (3840, 1384)
    assert captured[0]["pad"] == (0, 0, 0, 0)
    assert captured[1]["scaled"] == (3832, 1384)
    assert captured[1]["pad"] == (0, 0, 0, 0)


def test_pad_to_canvas_auto_handles_micro_bars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(3840, 2152), FakeClip(1920, 1080)]
    cfg = ScreenshotConfig(
        upscale=True,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=2160,
        pad_to_canvas="auto",
        letterbox_px_tolerance=8,
    )
    color_cfg = ColorConfig()

    captured: list[_CapturedWriterCall] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append(
            {
                "crop": crop,
                "scaled": scaled_dims,
                "pad": pad,
                "label": str(label),
                "requested": int(requested_frame),
                "frame": int(frame_idx),
                "selection_label": selection_label,
                "source": None,
            }
        )
        Path(path).write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["uhd.mkv", "hd.mkv"],
        [{"label": "UHD"}, {"label": "HD"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["UHD"]["scaled"] == (3840, 2152)
    assert by_label["UHD"]["pad"] == (0, 4, 0, 4)
    assert by_label["HD"]["scaled"] == (3840, 2160)
    assert by_label["HD"]["pad"] == (0, 0, 0, 0)


def test_pad_to_canvas_auto_respects_tolerance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(3840, 2048), FakeClip(1920, 1080)]
    cfg = ScreenshotConfig(
        upscale=True,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=2160,
        pad_to_canvas="auto",
        letterbox_px_tolerance=8,
    )
    color_cfg = ColorConfig()

    captured: list[_CapturedWriterCall] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append(
            {
                "crop": crop,
                "scaled": scaled_dims,
                "pad": pad,
                "label": str(label),
                "requested": int(requested_frame),
                "frame": int(frame_idx),
                "selection_label": selection_label,
                "source": None,
            }
        )
        Path(path).write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["scope.mkv", "hd.mkv"],
        [{"label": "scope"}, {"label": "hd"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["scope"]["pad"] == (0, 0, 0, 0)
    assert by_label["scope"]["scaled"][1] == 2048
    assert by_label["hd"]["pad"] == (0, 0, 0, 0)


def test_pad_to_canvas_on_pillarboxes_narrow_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(1920, 1080), FakeClip(1440, 1080)]
    cfg = ScreenshotConfig(
        upscale=False,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=1080,
        pad_to_canvas="on",
        letterbox_pillarbox_aware=False,
    )
    color_cfg = ColorConfig()

    captured: list[_CapturedWriterCall] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append(
            {
                "crop": crop,
                "scaled": scaled_dims,
                "pad": pad,
                "label": str(label),
                "requested": int(requested_frame),
                "frame": int(frame_idx),
                "selection_label": selection_label,
                "source": None,
            }
        )
        Path(path).write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["widescreen.mkv", "academy.mkv"],
        [{"label": "ws"}, {"label": "academy"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["ws"]["pad"] == (0, 0, 0, 0)
    assert by_label["ws"]["scaled"] == (1920, 1080)
    assert by_label["academy"]["scaled"] == (1440, 1080)
    assert by_label["academy"]["pad"] == (240, 0, 240, 0)


def test_pad_to_canvas_on_without_single_res(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(1920, 1080), FakeClip(1440, 1080)]
    cfg = ScreenshotConfig(
        upscale=False,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=0,
        pad_to_canvas="on",
        letterbox_pillarbox_aware=False,
    )
    color_cfg = ColorConfig()

    captured: list[_CapturedWriterCall] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append(
            {
                "crop": crop,
                "scaled": scaled_dims,
                "pad": pad,
                "label": str(label),
                "requested": int(requested_frame),
                "frame": int(frame_idx),
                "selection_label": selection_label,
                "source": None,
            }
        )
        Path(path).write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["wide.mkv", "narrow.mkv"],
        [{"label": "wide"}, {"label": "narrow"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["wide"]["scaled"] == (1920, 1080)
    assert by_label["wide"]["pad"] == (0, 0, 0, 0)
    assert by_label["narrow"]["scaled"] == (1440, 1080)
    assert by_label["narrow"]["pad"] == (240, 0, 240, 0)


def test_pad_to_canvas_auto_zero_tolerance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(3840, 2152), FakeClip(1920, 1080)]
    cfg = ScreenshotConfig(
        upscale=True,
        use_ffmpeg=False,
        add_frame_info=False,
        single_res=2160,
        pad_to_canvas="auto",
        letterbox_px_tolerance=0,
    )
    color_cfg = ColorConfig()

    captured: list[_CapturedWriterCall] = []

    def fake_vs_writer(
        clip,
        frame_idx,
        crop,
        scaled_dims,
        pad,
        path,
        cfg,
        label,
        requested_frame,
        selection_label=None,
        **kwargs,
    ):
        captured.append(
            {
                "crop": crop,
                "scaled": scaled_dims,
                "pad": pad,
                "label": str(label),
                "requested": int(requested_frame),
                "frame": int(frame_idx),
                "selection_label": selection_label,
                "source": None,
            }
        )
        Path(path).write_text("vs", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", fake_vs_writer)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["uhd.mkv", "hd.mkv"],
        [{"label": "UHD"}, {"label": "HD"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    by_label = {entry["label"]: entry for entry in captured}
    assert by_label["UHD"]["scaled"] == (3840, 2152)
    assert by_label["UHD"]["pad"] == (0, 0, 0, 0)
    assert by_label["HD"]["scaled"] == (3840, 2160)
    assert by_label["HD"]["pad"] == (0, 0, 0, 0)


def test_ffmpeg_writer_receives_padding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clips = [FakeClip(1920, 1080), FakeClip(1440, 1080)]
    cfg = ScreenshotConfig(
        use_ffmpeg=True,
        add_frame_info=False,
        single_res=1080,
        pad_to_canvas="on",
        letterbox_pillarbox_aware=False,
        mod_crop=2,
    )
    color_cfg = ColorConfig()

    calls: list[_CapturedWriterCall] = []

    def fake_ffmpeg(
        source,
        frame_idx,
        crop,
        scaled,
        pad,
        path,
        cfg,
        width,
        height,
        selection_label,
        *,
        overlay_text=None,
        is_sdr: bool = True,
        **_kwargs: Any,
    ):
        calls.append(
            {
                "crop": crop,
                "scaled": scaled,
                "pad": pad,
                "label": "ffmpeg",
                "requested": int(frame_idx),
                "frame": int(frame_idx),
                "selection_label": selection_label,
                "source": str(source),
            }
        )
        Path(path).write_text("ff", encoding="utf-8")

    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", fake_ffmpeg)
    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", lambda *args, **kwargs: None)

    screenshot.generate_screenshots(
        clips,
        [0],
        ["wide.mkv", "narrow.mkv"],
        [{"label": "wide"}, {"label": "narrow"}],
        tmp_path,
        cfg,
        color_cfg,
        trim_offsets=[0, 0],
    )

    assert len(calls) == 2
    wide_call = next(call for call in calls if call["source"] is not None and call["source"].endswith("wide.mkv"))
    narrow_call = next(call for call in calls if call["source"] is not None and call["source"].endswith("narrow.mkv"))
    assert wide_call["source"] is not None
    assert narrow_call["source"] is not None
    assert wide_call["scaled"] == (1920, 1080)
    assert wide_call["pad"] == (0, 0, 0, 0)
    assert narrow_call["scaled"] == (1440, 1080)
    assert narrow_call["pad"] == (240, 0, 240, 0)
def test_placeholder_logging(tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    clip = FakeClip(1280, 720)
    cfg = ScreenshotConfig(use_ffmpeg=False)
    color_cfg = ColorConfig()

    def failing_writer(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(screenshot, "_save_frame_with_fpng", failing_writer)
    monkeypatch.setattr(screenshot, "_save_frame_with_ffmpeg", lambda *args, **kwargs: None)

    with caplog.at_level("WARNING"):
        created = screenshot.generate_screenshots(
            [clip],
            [0],
            ["clip.mkv"],
            [{"label": "clip"}],
            tmp_path,
            cfg,
            color_cfg,
            trim_offsets=[0],
        )

    assert any("Falling back to placeholder" in message for message in caplog.messages)
    placeholder = Path(created[0])
    assert placeholder.read_bytes() == b"placeholder\n"


def test_compose_overlay_text_omits_selection_detail_lines() -> None:
    color_cfg = ColorConfig(overlay_mode="diagnostic")
    plan = _make_plan()
    base_text = "Tonemapping Algorithm: bt.2390 dpd = 1 dst = 100 nits"
    selection_detail = {"timecode": "00:00:05.000", "score": 0.42, "notes": "motion"}
    composed = screenshot._compose_overlay_text(
        base_text,
        color_cfg,
        plan,
        selection_label="Motion",
        source_props={},
        tonemap_info=None,
        selection_detail=selection_detail,
    )
    assert composed is not None
    assert "Selection Timecode" not in composed
    assert "Selection Score" not in composed
    assert "Selection Notes" not in composed
    assert "Frame Selection Type: Motion" in composed


def test_overlay_state_warning_helpers_roundtrip() -> None:
    state = screenshot._new_overlay_state()
    screenshot._append_overlay_warning(state, "first")
    screenshot._append_overlay_warning(state, "second")
    assert screenshot._get_overlay_warnings(state) == ["first", "second"]


def test_save_frame_with_ffmpeg_honours_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = ScreenshotConfig(ffmpeg_timeout_seconds=37.5)
    recorded: dict[str, object] = {}

    def fake_run(cmd: Sequence[str], **kwargs: Any):  # type: ignore[override]
        recorded.update(kwargs)
        recorded["cmd"] = cmd

        class _Result:
            returncode = 0
            stderr = b""

        return _Result()

    monkeypatch.setattr(screenshot.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(screenshot.subprocess, "run", fake_run)

    screenshot._save_frame_with_ffmpeg(
        source="video.mkv",
        frame_idx=12,
        crop=(0, 0, 0, 0),
        scaled=(1920, 1080),
        pad=(0, 0, 0, 0),
        path=tmp_path / "frame.png",
        cfg=cfg,
        width=1920,
        height=1080,
        selection_label=None,
        frame_info_allowed=True,
        overlays_allowed=True,
    )

    cmd = recorded.get("cmd")
    assert isinstance(cmd, list)
    assert "-nostdin" in cmd
    assert recorded.get("stdin") is subprocess.DEVNULL
    assert recorded.get("stdout") is subprocess.DEVNULL
    assert recorded.get("stderr") is subprocess.PIPE
    assert recorded.get("timeout") == pytest.approx(37.5)


def test_save_frame_with_ffmpeg_disables_timeout_when_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = ScreenshotConfig(ffmpeg_timeout_seconds=0.0)
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[override]
        recorded.update(kwargs)

        class _Result:
            returncode = 0
            stderr = b""

        return _Result()

    monkeypatch.setattr(screenshot.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(screenshot.subprocess, "run", fake_run)

    screenshot._save_frame_with_ffmpeg(
        source="video.mkv",
        frame_idx=3,
        crop=(0, 0, 0, 0),
        scaled=(1920, 1080),
        pad=(0, 0, 0, 0),
        path=tmp_path / "frame.png",
        cfg=cfg,
        width=1920,
        height=1080,
        selection_label=None,
        frame_info_allowed=True,
        overlays_allowed=True,
    )

    assert "timeout" not in recorded or recorded.get("timeout") is None


def test_save_frame_with_ffmpeg_inserts_full_chroma_filters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = ScreenshotConfig(rgb_dither=RGBDither.ERROR_DIFFUSION)
    plan = _make_plan(
        crop=(1, 0, 2, 0),
        pad=(0, 1, 0, 1),
        requires_full_chroma=True,
        promotion_axes="horizontal+vertical",
    )
    recorded_cmd: list[str] = []
    pivot_notes: list[str] = []

    def fake_run(cmd: Sequence[str], **_kwargs: Any):  # type: ignore[override]
        recorded_cmd[:] = list(cmd)

        class _Result:
            returncode = 0
            stderr = b""

        return _Result()

    monkeypatch.setattr(screenshot.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(screenshot.subprocess, "run", fake_run)

    screenshot._save_frame_with_ffmpeg(
        source="video.mkv",
        frame_idx=7,
        crop=(1, 0, 2, 0),
        scaled=(1917, 1080),
        pad=(0, 1, 0, 1),
        path=tmp_path / "frame.png",
        cfg=cfg,
        width=1920,
        height=1080,
        selection_label=None,
        geometry_plan=plan,
        pivot_notifier=pivot_notes.append,
        frame_info_allowed=True,
        overlays_allowed=True,
    )

    assert recorded_cmd
    vf_index = recorded_cmd.index("-vf")
    filter_chain = recorded_cmd[vf_index + 1]
    filters = filter_chain.split(",")
    assert "format=yuv444p16" in filters
    assert any(entry.startswith("format=rgb24") for entry in filters)
    assert filters[-1].endswith("dither=ordered")
    assert any("Full-chroma pivot" in note for note in pivot_notes)


def test_save_frame_with_ffmpeg_raises_on_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = ScreenshotConfig(ffmpeg_timeout_seconds=5.0)

    def fake_run(*args: object, **kwargs: Any):  # type: ignore[override]
        timeout_value = float(kwargs.get("timeout", 0.0) or 0.0)
        cmd_arg = cast(Any, args[0])
        raise subprocess.TimeoutExpired(cmd=cmd_arg, timeout=timeout_value)

    monkeypatch.setattr(screenshot.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(screenshot.subprocess, "run", fake_run)

    with pytest.raises(screenshot.ScreenshotWriterError) as exc_info:
        screenshot._save_frame_with_ffmpeg(
            source="video.mkv",
            frame_idx=99,
            crop=(0, 0, 0, 0),
            scaled=(1280, 720),
            pad=(0, 0, 0, 0),
            path=tmp_path / "frame.png",
            cfg=cfg,
            width=1280,
            height=720,
            selection_label=None,
            frame_info_allowed=True,
            overlays_allowed=True,
        )

    assert "timed out" in str(exc_info.value)


def test_save_frame_with_fpng_promotes_subsampled_sdr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    clip, fake_vs, writer_calls, resize_calls = _prepare_fake_vapoursynth_clip(
        monkeypatch,
        width=1920,
        height=1080,
        subsampling_w=1,
        subsampling_h=1,
        bits_per_sample=10,
        format_name="YUV420P10",
    )

    cfg = ScreenshotConfig(add_frame_info=False, rgb_dither=RGBDither.ORDERED)
    tonemap_info = vs_core.TonemapInfo(
        applied=False,
        tone_curve=None,
        dpd=0,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
        reason="SDR source",
    )
    plan = _make_plan(
        pad=(0, 1, 0, 1),
        requires_full_chroma=True,
        promotion_axes="vertical",
    )
    source_props = {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_ColorRange": 1}

    caplog_any = cast(Any, caplog)
    caplog_any.set_level(logging.INFO)

    pivot_notes: list[str] = []

    screenshot._save_frame_with_fpng(
        clip,
        frame_idx=0,
        crop=plan["crop"],
        scaled=plan["scaled"],
        pad=plan["pad"],
        path=tmp_path / "frame.png",
        cfg=cfg,
        label="Clip",
        requested_frame=0,
        selection_label=None,
        source_props=source_props,
        geometry_plan=plan,
        tonemap_info=tonemap_info,
        pivot_notifier=pivot_notes.append,
        debug_state=None,
        frame_info_allowed=False,
        overlays_allowed=False,
    )

    log_records: Sequence[logging.LogRecord] = list(caplog_any.records)
    assert any("promoting to YUV444P16" in record.getMessage() for record in log_records)
    assert writer_calls, "fpng writer should be invoked"
    assert len(resize_calls) >= 2
    first_call, second_call = resize_calls[0], resize_calls[-1]
    assert first_call.get("format") == fake_vs.YUV444P16
    assert first_call.get("dither_type") == "none"
    assert second_call.get("format") == fake_vs.RGB24
    assert second_call.get("dither_type") == RGBDither.ORDERED.value
    assert any("Full-chroma pivot" in note for note in pivot_notes)


def test_save_frame_with_fpng_skips_promotion_on_even_geometry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    clip, fake_vs, writer_calls, resize_calls = _prepare_fake_vapoursynth_clip(
        monkeypatch,
        width=1920,
        height=1080,
        subsampling_w=1,
        subsampling_h=1,
        bits_per_sample=10,
        format_name="YUV420P10",
    )

    cfg = ScreenshotConfig(add_frame_info=False, rgb_dither=RGBDither.ORDERED)
    tonemap_info = vs_core.TonemapInfo(
        applied=False,
        tone_curve=None,
        dpd=0,
        target_nits=100.0,
        dst_min_nits=0.1,
        src_csp_hint=None,
        reason="SDR source",
    )
    plan = _make_plan(pad=(0, 2, 0, 2), requires_full_chroma=False)
    source_props = {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_ColorRange": 1}

    screenshot._save_frame_with_fpng(
        clip,
        frame_idx=3,
        crop=plan["crop"],
        scaled=plan["scaled"],
        pad=plan["pad"],
        path=tmp_path / "frame.png",
        cfg=cfg,
        label="Clip",
        requested_frame=3,
        selection_label=None,
        source_props=source_props,
        geometry_plan=plan,
        tonemap_info=tonemap_info,
        debug_state=None,
        frame_info_allowed=False,
        overlays_allowed=False,
    )

    assert writer_calls, "fpng writer should be invoked"
    assert not any(call.get("format") == fake_vs.YUV444P16 for call in resize_calls)
    assert any(call.get("format") == fake_vs.RGB24 for call in resize_calls)


def test_ensure_rgb24_applies_rec709_defaults_when_metadata_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    captured_props: dict[str, Any] = {}

    class _DummyStd:
        def __init__(self, parent: "_DummyClip") -> None:
            self._parent = parent

        def SetFrameProps(self, **kwargs: Any) -> "_DummyClip":
            captured_props.update(kwargs)
            return self._parent

    class _DummyClip:
        def __init__(self) -> None:
            self.std = _DummyStd(self)

    def fake_point(clip: Any, **kwargs: Any) -> _DummyClip:
        captured.update(kwargs)
        return _DummyClip()

    fake_core = types.SimpleNamespace(resize=types.SimpleNamespace(Point=fake_point))
    yuv_family = object()
    fake_vs = types.SimpleNamespace(
        RGB24=0,
        RGB=object(),
        YUV=yuv_family,
        RANGE_FULL=0,
        RANGE_LIMITED=1,
        MATRIX_BT709=1,
        TRANSFER_BT709=1,
        PRIMARIES_BT709=1,
    )
    fake_vs.core = fake_core

    class _SourceClip:
        def __init__(self) -> None:
            self.core = fake_core
            self.format = types.SimpleNamespace(color_family=yuv_family, bits_per_sample=8)
            self.height = 1080

        def get_frame(self, idx: int) -> Any:  # type: ignore[override]
            raise AssertionError("get_frame should not be invoked when props are provided")

    patcher = cast(Any, monkeypatch)
    patcher.setitem(sys.modules, "vapoursynth", fake_vs)

    converted = screenshot._ensure_rgb24(
        fake_core,
        _SourceClip(),
        frame_idx=12,
        source_props={},
        rgb_dither=RGBDither.ERROR_DIFFUSION,
    )
    assert isinstance(converted, _DummyClip)
    assert captured.get("matrix_in") == 1
    assert captured.get("transfer_in") == 1
    assert captured.get("primaries_in") == 1
    assert captured.get("range_in") == 1
    assert captured.get("dither_type") == RGBDither.ERROR_DIFFUSION.value
    assert captured_props == {"_Matrix": 0, "_ColorRange": 0}


def test_ensure_rgb24_uses_source_colour_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    captured_props: dict[str, Any] = {}

    class _DummyStd:
        def __init__(self, parent: "_DummyClip") -> None:
            self._parent = parent

        def SetFrameProps(self, **kwargs: Any) -> "_DummyClip":
            captured_props.update(kwargs)
            return self._parent

    class _DummyClip:
        def __init__(self) -> None:
            self.std = _DummyStd(self)

    def fake_point(clip: Any, **kwargs: Any) -> _DummyClip:
        captured.update(kwargs)
        return _DummyClip()

    fake_core = types.SimpleNamespace(resize=types.SimpleNamespace(Point=fake_point))
    yuv_family = object()
    fake_vs = types.SimpleNamespace(
        RGB24=0,
        RGB=object(),
        YUV=yuv_family,
        RANGE_FULL=0,
        RANGE_LIMITED=1,
        MATRIX_BT709=1,
        TRANSFER_BT709=1,
        PRIMARIES_BT709=1,
    )
    fake_vs.core = fake_core

    class _SourceClip:
        def __init__(self) -> None:
            self.core = fake_core
            self.format = types.SimpleNamespace(color_family=yuv_family, bits_per_sample=10)
            self.height = 1080
            self._frame = types.SimpleNamespace(
                props={
                    "_Matrix": 9,
                    "_Transfer": 16,
                    "_Primaries": 9,
                    "_ColorRange": 0,
                }
            )

        def get_frame(self, idx: int) -> Any:  # type: ignore[override]
            raise AssertionError("get_frame should not be called when props are supplied")

    patcher = cast(Any, monkeypatch)
    patcher.setitem(sys.modules, "vapoursynth", fake_vs)

    converted = screenshot._ensure_rgb24(
        fake_core,
        _SourceClip(),
        frame_idx=24,
        source_props={
            "_Matrix": 9,
            "_Transfer": 16,
            "_Primaries": 9,
            "_ColorRange": 0,
        },
        rgb_dither=RGBDither.ORDERED,
    )
    assert isinstance(converted, _DummyClip)
    assert captured.get("matrix_in") == 9
    assert captured.get("transfer_in") == 16
    assert captured.get("primaries_in") == 9
    assert captured.get("range_in") == 0
    assert captured.get("dither_type") == RGBDither.ORDERED.value
    assert captured_props == {
        "_Matrix": 0,
        "_ColorRange": 0,
        "_Primaries": 9,
        "_Transfer": 16,
    }
