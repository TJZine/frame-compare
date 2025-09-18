import sys
import types

import pytest
import src.vs_core as vs_core

from src.datatypes import TonemapConfig
from src.vs_core import (
    ClipInitError,
    ClipProcessError,
    configure,
    init_clip,
    process_clip_for_screenshot,
    set_ram_limit,
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
        self.core = types.SimpleNamespace(libplacebo=_FakeLibplacebo())
        self.slice_history = []
        self.blank_frames = None

    def get_frame_props(self):
        return self.frame_props

    def __getitem__(self, key):
        self.slice_history.append(key)
        return self


class _FailingLWLib:
    @staticmethod
    def LWLibavSource(path: str, **kwargs):
        raise RuntimeError("boom")


class _FakeCore:
    def __init__(self, source):
        self.lsmas = source
        self.std = types.SimpleNamespace(BlankClip=_BlankClip)


class _BlankClip:
    def __init__(self, clip, length: int):
        self.clip = clip
        self.length = length

    def __add__(self, other):
        other.blank_frames = self.length
        return other


def test_sdr_pass_through():
    clip = _FakeClip(
        props={"_Primaries": 1, "_Transfer": 1}
    )
    result = process_clip_for_screenshot(clip, "file.mkv", cfg=types.SimpleNamespace())
    assert result is clip
    assert clip.core.libplacebo.called_with is None
    assert clip.std.set_props_kwargs == {
        '_Matrix': 1,
        '_Primaries': 1,
        '_Transfer': 1,
        '_ColorRange': 0,
    }


def test_hdr_triggers_tonemap():
    clip = _FakeClip(
        props={"_Primaries": "bt2020", "_Transfer": "st2084"}
    )
    cfg = TonemapConfig(dst_max=120.0)
    result = process_clip_for_screenshot(clip, "file.mkv", cfg)
    assert clip.core.libplacebo.called_with is not None
    tonemap_clip, kwargs = clip.core.libplacebo.called_with
    assert tonemap_clip is clip
    assert kwargs["dst_max"] == 120.0
    assert kwargs["tone_mapping"] == "bt2390"
    assert kwargs["dynamic_peak_detection"] == 0
    assert kwargs["gamut_mapping"] == "clip"
    assert kwargs["scene_threshold_low"] == pytest.approx(0.12)
    assert kwargs["scene_threshold_high"] == pytest.approx(0.32)
    assert kwargs["dst_csp"] == "bt709"
    assert kwargs["dst_prim"] == "bt709"
    assert kwargs["dst_tf"] == "bt1886"
    assert kwargs["use_dovi"] is True
    assert clip.std.set_props_kwargs == {
        "_Matrix": 1,
        "_Primaries": 1,
        "_Transfer": 1,
        "_ColorRange": 0,
    }
    assert result is clip


def test_init_clip_errors_raise():
    fake_core = _FakeCore(source=_FailingLWLib())
    with pytest.raises(ClipInitError):
        init_clip("video.mkv", core=fake_core)


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
