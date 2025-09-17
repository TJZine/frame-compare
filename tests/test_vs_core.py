import types

import pytest

from src.vs_core import ClipInitError, ClipProcessError, init_clip, process_clip_for_screenshot


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

    def get_frame_props(self):
        return self.frame_props


class _FailingLWLib:
    @staticmethod
    def LWLibavSource(path: str):
        raise RuntimeError("boom")


class _FakeCore:
    def __init__(self, source):
        self.lsmas = source


def test_sdr_pass_through():
    clip = _FakeClip(
        props={"_Primaries": "bt709", "_Transfer": "bt1886"}
    )
    result = process_clip_for_screenshot(clip, "file.mkv", cfg=types.SimpleNamespace())
    assert result is clip
    assert clip.core.libplacebo.called_with is None
    assert clip.std.set_props_kwargs is None


def test_hdr_triggers_tonemap():
    clip = _FakeClip(
        props={"_Primaries": "bt2020", "_Transfer": "st2084"}
    )
    cfg = types.SimpleNamespace(target_nits=120)
    result = process_clip_for_screenshot(clip, "file.mkv", cfg)
    assert clip.core.libplacebo.called_with is not None
    tonemap_clip, kwargs = clip.core.libplacebo.called_with
    assert tonemap_clip is clip
    assert kwargs["target_nits"] == 120
    assert clip.std.set_props_kwargs == {
        "_Matrix": "bt709",
        "_Primaries": "bt709",
        "_Transfer": "bt1886",
        "_ColorRange": "limited",
    }
    assert result is clip


def test_init_clip_errors_raise():
    fake_core = _FakeCore(source=_FailingLWLib())
    with pytest.raises(ClipInitError):
        init_clip("video.mkv", core=fake_core)


def test_init_clip_applies_trim_and_fps(monkeypatch):
    class _Source:
        @staticmethod
        def LWLibavSource(path: str):
            clip = _FakeClip()
            clip.opened_path = path
            return clip

    fake_core = _FakeCore(source=_Source())
    clip = init_clip(
        "video.mkv",
        trims=(10, 100),
        fps_map=(24000, 1001),
        core=fake_core,
    )
    assert clip.opened_path == "video.mkv"
    assert clip.std.trim_args == (10, 100)
    assert clip.std.fps_args == (24000, 1001)
