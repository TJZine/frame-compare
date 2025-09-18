from __future__ import annotations

import types

import pytest

from src.cli.args import parse_tonemap_args
from src.tonemap.config import TMConfig
from src.tonemap.core import apply_tonemap, TonemapResult
from src.tonemap.detect import is_hdr
from src.tonemap.exceptions import HDRDetectError, TonemapConfigError


def test_is_hdr_detects_pq_transfer() -> None:
    props = {"_Transfer": 16, "_Primaries": "bt2020"}
    assert is_hdr(props) is True


def test_is_hdr_detects_metadata_when_transfer_missing() -> None:
    props = {"_MaxCLL": 1000, "_MaxFALL": 400}
    assert is_hdr(props) is True


def test_is_hdr_false_for_sdr() -> None:
    props = {"_Primaries": "bt709", "_Transfer": "bt1886"}
    assert is_hdr(props) is False


def test_is_hdr_raises_when_props_missing() -> None:
    with pytest.raises(HDRDetectError):
        is_hdr(None)  # type: ignore[arg-type]


def test_tmconfig_aliases_and_resolution() -> None:
    cfg = TMConfig.from_mapping({"tone_mapping": "hable", "target_nits": 140.0})
    resolved = cfg.resolved()
    assert resolved.func == "hable"
    assert resolved.dst_max == 140.0
    assert resolved.preset == "reference"


def test_tmconfig_invalid_field_raises() -> None:
    with pytest.raises(TonemapConfigError):
        TMConfig.from_mapping({"unknown": 5})


def test_parse_tonemap_args_boolean_overrides() -> None:
    overrides, remainder = parse_tonemap_args(["--tm-overlay", "--no-tm-verify", "--tm-dst-max", "120"])
    assert remainder == []
    assert overrides["overlay"] is True
    assert overrides["verify"] is False
    assert overrides["dst_max"] == 120.0


class _CountingTonemap:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def Tonemap(self, clip, **kwargs):  # noqa: N802 - VapourSynth style
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise RuntimeError("first attempt fails")
        return clip


class _DummyStd:
    def __init__(self, owner):
        self.owner = owner
        self.last_props = None

    def SetFrameProps(self, **kwargs):
        self.last_props = kwargs
        return self.owner


class _DummyResize:
    def __init__(self, owner):
        self.owner = owner

    def Bicubic(self, clip, **kwargs):  # noqa: N802
        self.owner.last_resize_kwargs = kwargs
        return clip


class _DummyClip:
    def __init__(self, props: dict[str, object]):
        self.frame_props = props
        self.std = _DummyStd(self)
        self.core = types.SimpleNamespace()
        self.core.libplacebo = _CountingTonemap()
        self.core.resize = _DummyResize(self)
        self.last_resize_kwargs = None

    def get_frame_props(self):
        return self.frame_props


def test_apply_tonemap_retries_with_hints() -> None:
    clip = _DummyClip({"_Matrix": "bt2020nc", "_Primaries": "bt2020", "_Transfer": "st2084"})
    cfg = TMConfig(dst_max=120.0)
    result = apply_tonemap(clip, cfg)
    assert isinstance(result, TonemapResult)
    assert clip.core.libplacebo.calls  # ensure tonemap attempted
    # Second attempt should carry source hints
    assert clip.core.libplacebo.calls[-1]["src_matrix"] == "bt2020nc"
    assert clip.core.libplacebo.calls[-1]["src_prim"] == "bt2020"
    assert clip.core.libplacebo.calls[-1]["src_tf"] == "st2084"
    assert clip.std.last_props["_Primaries"] == "bt709"


class _FallbackClip:
    def __init__(self, props: dict[str, object]):
        self.frame_props = props
        self.std = _DummyStd(self)
        self.core = types.SimpleNamespace()
        self.core.libplacebo = None
        self.core.resize = _DummyResize(self)
        self.last_resize_kwargs = None

    def get_frame_props(self):
        return self.frame_props


def test_apply_tonemap_uses_fallback_when_placebo_missing() -> None:
    clip = _FallbackClip({"_Transfer": "st2084", "_Primaries": "bt2020"})
    cfg = TMConfig()
    result = apply_tonemap(clip, cfg, force=True)
    assert isinstance(result, TonemapResult)
    assert result.used_libplacebo is False
    assert clip.std.last_props["_Transfer"] == "bt1886"
