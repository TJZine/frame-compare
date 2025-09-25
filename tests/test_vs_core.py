import sys
import types

import pytest
import src.vs_core as vs_core

from src.datatypes import ColorConfig
from src.vs_core import (
    ClipInitError,
    ClipProcessError,
    configure,
    init_clip,
    process_clip_for_screenshot,
    set_ram_limit,
    VSSourceUnavailableError,
    VSPluginDepMissingError,
    _normalize_rgb_props,
)


class _FakeStd:
    def __init__(self, owner):
        self._owner = owner
        self.trim_args = None
        self.fps_args = None
        self.set_props_kwargs = None

    def Trim(self, *, first: int, last: int):
        self.trim_args = (first, last)
        return self._owner

    def AssumeFPS(self, *, num: int, den: int):
        self.fps_args = (num, den)
        return self._owner

    def SetFrameProps(self, **kwargs):
        self.set_props_kwargs = kwargs
        return self._owner

    def SetFrameProp(self, clip=None, **kwargs):
        self.set_props_kwargs = kwargs
        return self._owner if clip is None else clip


class _FakeLibplacebo:
    def __init__(self):
        self.called_with = None

    def Tonemap(self, clip, **kwargs):
        self.called_with = (clip, kwargs)
        return clip


class _FakeClip:
    def __init__(self, props=None):
        self.frame_props = props or {}
        self.std = _FakeStd(self)
        self.core = types.SimpleNamespace()
        self.core.libplacebo = _FakeLibplacebo()
        self.core.placebo = self.core.libplacebo
        resize_ns = types.SimpleNamespace()

        def _spline36(target_clip, **kwargs):
            target_clip.last_resize_kwargs = kwargs
            return target_clip

        def _point(target_clip, **kwargs):
            target_clip.last_point_kwargs = kwargs
            return target_clip

        resize_ns.Spline36 = _spline36
        resize_ns.Point = _point
        self.core.resize = resize_ns
        self.slice_history = []
        self.blank_frames = None
        self.num_frames = 10
        self.fps_num = 24
        self.fps_den = 1
        self.width = 1920
        self.height = 1080

    def get_frame_props(self):
        return self.frame_props

    def get_frame(self, idx):
        return types.SimpleNamespace(props=self.frame_props)

    def __getitem__(self, key):
        self.slice_history.append(key)
        return self


class _FailingLWLib:
    @staticmethod
    def LWLibavSource(path: str, **kwargs):
        raise RuntimeError("boom")


class _BrokenDependencyLWLib:
    @staticmethod
    def LWLibavSource(path: str, **kwargs):
        raise RuntimeError(
            "dlopen(/path/to/lsmas.dylib, 0x0001): Library not loaded: "
            "/usr/local/lib/libavcodec.61.dylib"
        )


class _WorkingFFMS:
    @staticmethod
    def Source(path: str, **kwargs):
        clip = _FakeClip()
        clip.opened_path = path
        clip.cachefile = kwargs.get("cachefile")
        return clip


class _FakeCore:
    def __init__(self, source, ffms_source=None):
        self.lsmas = source
        if ffms_source is not None:
            self.ffms2 = ffms_source
        self.std = types.SimpleNamespace(BlankClip=_BlankClip)


class _BlankClip:
    def __init__(self, clip, length: int):
        self.clip = clip
        self.length = length

    def __add__(self, other):
        other.blank_frames = self.length
        return other


@pytest.fixture(autouse=True)
def _stub_vs_module(monkeypatch):
    module_core = types.SimpleNamespace()

    def _spline36(target_clip, **kwargs):
        target_clip.last_resize_kwargs = kwargs
        return target_clip

    def _point(target_clip, **kwargs):
        target_clip.last_point_kwargs = kwargs
        return target_clip

    module_core.resize = types.SimpleNamespace(Spline36=_spline36, Point=_point)
    module_core.libplacebo = _FakeLibplacebo()

    fake_vs = types.SimpleNamespace(
        RGB48=object(),
        RGB24=object(),
        RANGE_LIMITED=1,
        RANGE_FULL=0,
        core=module_core,
        get_core=lambda: module_core,
    )
    monkeypatch.setattr(vs_core, "_get_vapoursynth_module", lambda: fake_vs)


def test_sdr_pass_through():
    clip = _FakeClip(
        props={"_Primaries": "bt709", "_Transfer": "bt1886"}
    )
    color_cfg = ColorConfig(enable_tonemap=True, overlay_enabled=False, verify_enabled=False)
    result = process_clip_for_screenshot(
        clip,
        "file.mkv",
        color_cfg,
        enable_overlay=False,
        enable_verification=False,
    )
    assert result.clip is clip
    assert result.tonemap.applied is False
    assert result.overlay_text is None
    assert result.tonemap.reason in {"SDR source", "Tonemap disabled", "Tonemap bypass"}


def test_hdr_triggers_tonemap(monkeypatch):
    clip = _FakeClip(
        props={"_Primaries": 9, "_Transfer": 16}
    )
    tonemapped = _FakeClip()
    recorded = {}

    def fake_tonemap(core, rgb_clip, **kwargs):
        recorded["clip"] = rgb_clip
        recorded["kwargs"] = kwargs
        return tonemapped

    monkeypatch.setattr(vs_core, "_tonemap_with_retries", fake_tonemap)

    color_cfg = ColorConfig(
        enable_tonemap=True,
        overlay_enabled=False,
        verify_enabled=False,
        preset="custom",
        tone_curve="mobius",
        target_nits=120.0,
        dynamic_peak_detection=False,
    )

    result = process_clip_for_screenshot(
        clip,
        "file.mkv",
        color_cfg,
        enable_overlay=False,
        enable_verification=False,
    )

    assert recorded["clip"] is clip
    assert pytest.approx(recorded["kwargs"]["target_nits"], rel=1e-6) == 120.0
    assert recorded["kwargs"]["dpd"] == 0
    assert recorded["kwargs"]["tone_curve"] == "mobius"
    assert result.clip is tonemapped
    assert result.tonemap.applied is True
    assert result.tonemap.tone_curve == "mobius"


def test_overlay_template_respects_overrides(monkeypatch):
    clip = _FakeClip(props={"_Primaries": 9, "_Transfer": 16})
    tonemapped = _FakeClip()

    monkeypatch.setattr(vs_core, "_tonemap_with_retries", lambda *args, **kwargs: tonemapped)

    color_cfg = ColorConfig(
        enable_tonemap=True,
        overlay_enabled=True,
        preset="reference",
        tone_curve="mobius",
        target_nits=203.0,
        dynamic_peak_detection=False,
        overlay_text_template="curve={tone_curve} dpd={dynamic_peak_detection_bool} nits={target_nits}",
        verify_enabled=False,
    )
    setattr(
        color_cfg,
        "_provided_keys",
        {"preset", "tone_curve", "target_nits", "dynamic_peak_detection", "overlay_text_template"},
    )

    result = process_clip_for_screenshot(
        clip,
        "file.mkv",
        color_cfg,
        enable_overlay=True,
        enable_verification=False,
    )

    assert result.overlay_text == "curve=mobius dpd=False nits=203"
    assert result.tonemap.tone_curve == "mobius"
    assert result.tonemap.target_nits == 203.0
    assert result.tonemap.dpd == 0


def test_normalize_rgb_props_handles_bound_method():
    clip = _FakeClip(props={"_Primaries": 9, "_Transfer": 16})

    class _BoundStd:
        def __init__(self, owner):
            self.owner = owner
            self.calls = []

        def SetFrameProp(self, *args, **kwargs):
            if args:
                raise TypeError("clip argument not expected")
            self.calls.append(kwargs)
            return self.owner

    clip.std = _BoundStd(clip)

    result = _normalize_rgb_props(clip, transfer=16, primaries=9)

    assert result is clip
    assert clip.std.calls[0]["prop"] == "_Matrix"
    assert clip.std.calls[-1]["prop"] == "_Primaries"


def test_process_clip_uses_global_core_when_clip_missing_core(monkeypatch):
    clip = _FakeClip(props={"_Primaries": 9, "_Transfer": 16})
    clip.core = None

    tonemapped = _FakeClip()

    monkeypatch.setattr(vs_core, "_tonemap_with_retries", lambda *args, **kwargs: tonemapped)

    color_cfg = ColorConfig(
        enable_tonemap=True,
        overlay_enabled=False,
        verify_enabled=False,
        preset="custom",
    )

    result = process_clip_for_screenshot(
        clip,
        "file.mkv",
        color_cfg,
        enable_overlay=False,
        enable_verification=False,
    )

    assert result.clip is tonemapped


def test_resolve_core_uses_get_core(monkeypatch):
    module_core = types.SimpleNamespace()

    fake_vs = types.SimpleNamespace(
        RGB48=object(),
        RGB24=object(),
        RANGE_LIMITED=1,
        RANGE_FULL=0,
        get_core=lambda: module_core,
    )

    monkeypatch.setattr(vs_core, "_get_vapoursynth_module", lambda: fake_vs)

    resolved = vs_core._resolve_core(None)

    assert resolved is module_core


def test_tonemap_uses_placebo_namespace(monkeypatch):
    clip = _FakeClip(props={"_Primaries": 9, "_Transfer": 16})
    tonemapped = _FakeClip()

    # Remove libplacebo namespace to force placebo fallback
    clip.core.libplacebo = None

    capture = {}

    def fake_tonemap(rgb_clip, **kwargs):
        capture["rgb_clip"] = rgb_clip
        return tonemapped

    # monkeypatch placebo namespace to use fake tonemap
    clip.core.placebo = types.SimpleNamespace(Tonemap=fake_tonemap)

    color_cfg = ColorConfig(
        enable_tonemap=True,
        overlay_enabled=False,
        verify_enabled=False,
        preset="custom",
    )

    result = process_clip_for_screenshot(
        clip,
        "file.mkv",
        color_cfg,
        enable_overlay=False,
        enable_verification=False,
    )

    assert result.clip is tonemapped
    assert capture["rgb_clip"] is clip


def test_init_clip_errors_raise():
    fake_core = _FakeCore(source=_FailingLWLib())
    with pytest.raises(ClipInitError):
        init_clip("video.mkv", core=fake_core)


def test_init_clip_falls_back_to_ffms():
    fake_core = _FakeCore(source=_BrokenDependencyLWLib(), ffms_source=_WorkingFFMS())

    clip = init_clip("video.mkv", core=fake_core)

    assert getattr(clip, "opened_path", None) == "video.mkv"
    assert isinstance(clip.cachefile, str) and clip.cachefile.endswith(".ffindex")


def test_init_clip_reports_plugin_errors_when_all_fail():
    fake_core = types.SimpleNamespace(
        lsmas=_BrokenDependencyLWLib(),
        std=types.SimpleNamespace(BlankClip=_BlankClip),
    )

    with pytest.raises(VSSourceUnavailableError) as exc_info:
        init_clip("video.mkv", core=fake_core)

    assert "lsmas" in exc_info.value.errors
    lsmas_error = exc_info.value.errors["lsmas"]
    assert isinstance(lsmas_error, VSPluginDepMissingError)
    assert "libavcodec.61" in str(lsmas_error)


def test_init_clip_applies_trim_and_fps(monkeypatch):
    class _Source:
        @staticmethod
        def LWLibavSource(path: str, **kwargs):
            clip = _FakeClip()
            clip.opened_path = path
            clip.cachefile = kwargs.get("cachefile")
            return clip

    fake_core = _FakeCore(source=_Source())
    clip = init_clip(
        "video.mkv",
        trim_start=10,
        trim_end=100,
        fps_map=(24000, 1001),
        core=fake_core,
    )
    assert clip.opened_path == "video.mkv"
    assert clip.slice_history == [slice(10, None, None), slice(None, 100, None)]
    assert clip.std.fps_args == (24000, 1001)
    assert clip.cachefile.endswith("video.mkv.lwi")


def test_init_clip_handles_negative_trims():
    class _Source:
        @staticmethod
        def LWLibavSource(path: str, **kwargs):
            clip = _FakeClip()
            clip.opened_path = path
            clip.cachefile = kwargs.get("cachefile")
            return clip

    fake_core = _FakeCore(source=_Source())
    clip = init_clip(
        "video.mkv",
        trim_start=-5,
        trim_end=-2,
        core=fake_core,
    )
    assert clip.opened_path == "video.mkv"
    assert clip.blank_frames == 5
    assert clip.slice_history == [slice(None, -2, None)]


def test_set_ram_limit_applies_value():
    fake_core = types.SimpleNamespace(max_cache_size=0)
    set_ram_limit(16, core=fake_core)
    assert fake_core.max_cache_size == 16


def test_configure_registers_search_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(vs_core, "_EXTRA_SEARCH_PATHS", [])
    monkeypatch.setattr(vs_core, "_vs_module", None)
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    configure(search_paths=[str(site_dir)])
    expected = str(site_dir.expanduser().resolve())
    assert expected in sys.path
    assert expected in vs_core._EXTRA_SEARCH_PATHS
