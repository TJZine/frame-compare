import logging
import math
import sys
import types
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from src import vs_core
from src.datatypes import ColorConfig
from src.vs_core import VerificationResult


def test_pick_verify_frame_warns_when_no_frames() -> None:
    clip = types.SimpleNamespace(num_frames=0)
    cfg = types.SimpleNamespace(
        verify_frame=None,
        verify_auto=True,
        verify_start_seconds=10.0,
        verify_step_seconds=10.0,
        verify_max_seconds=90.0,
        verify_luma_threshold=0.10,
    )
    warnings: list[str] = []

    frame_idx, auto_selected = vs_core._pick_verify_frame(
        clip,
        cfg,
        fps=24.0,
        file_name="clip.mkv",
        warning_sink=warnings,
    )

    assert frame_idx == 0
    assert auto_selected is False
    assert warnings == ["[VERIFY] clip.mkv has no frames; using frame 0"]


def test_resolve_effective_tonemap_uses_preset_defaults() -> None:
    cfg = types.SimpleNamespace(
        preset="contrast",
        tone_curve="bt.2390",
        target_nits=100.0,
        dynamic_peak_detection=True,
        dst_min_nits=0.1,
        _provided_keys={"preset"},
    )

    resolved = vs_core.resolve_effective_tonemap(cfg)

    assert resolved["preset"] == "contrast"
    assert resolved["tone_curve"] == "mobius"
    assert resolved["target_nits"] == 120.0
    assert resolved["dynamic_peak_detection"] is False


class _FakeSampleType:
    def __init__(self, name: str, value: int) -> None:
        self.name = name
        self._value = value

    def __int__(self) -> int:
        return self._value


@dataclass
class _FakeFormat:
    bits_per_sample: int
    sample_type: _FakeSampleType


class _FakeClip:
    def __init__(self, fmt: _FakeFormat) -> None:
        self.format = fmt


class _FakeFrame:
    def __init__(self, props: Dict[str, float]) -> None:
        self.props = props


class _FakeStatsClip:
    def __init__(self, props: Dict[str, float]) -> None:
        self._props = props

    def get_frame(self, index: int) -> _FakeFrame:
        return _FakeFrame(self._props)


class _DetectStatsFrame:
    def __init__(self, props: Dict[str, float]) -> None:
        self.props = props


class _DetectStatsClip:
    def __init__(self, frames: Sequence[Dict[str, float]]) -> None:
        self._frames = [_DetectStatsFrame(item) for item in frames]
        self.num_frames = len(self._frames)

    def get_frame(self, index: int) -> _DetectStatsFrame:
        if not self._frames:
            raise RuntimeError("no frames available")
        clamped = min(max(index, 0), len(self._frames) - 1)
        return self._frames[clamped]


class _DetectStd:
    def __init__(self, frames: Sequence[Dict[str, float]]) -> None:
        self._stats_clip = _DetectStatsClip(frames)

    def PlaneStats(self, clip: Any) -> _DetectStatsClip:
        return self._stats_clip


class _FakeStd:
    def __init__(self, expr_clip: _FakeClip, stats_clip: _FakeStatsClip) -> None:
        self._expr_clip = expr_clip
        self._stats_clip = stats_clip
        self.expr_calls: List[Sequence[Any]] = []

    def Expr(self, clips: Sequence[Any], expr: str) -> _FakeClip:
        self.expr_calls.append(clips)
        return self._expr_clip

    def PlaneStats(self, clip: _FakeClip) -> _FakeStatsClip:
        return self._stats_clip


class _FakeCore:
    def __init__(self, expr_clip: _FakeClip, stats_clip: _FakeStatsClip) -> None:
        self.std = _FakeStd(expr_clip, stats_clip)


def _run_compute_verification(
    fmt: _FakeFormat, props: Dict[str, float]
) -> VerificationResult:
    expr_clip = _FakeClip(fmt)
    stats_clip = _FakeStatsClip(props)
    core = _FakeCore(expr_clip, stats_clip)
    return vs_core._compute_verification(core, object(), object(), 3, auto_selected=False)


def test_detect_rgb_color_range_identifies_limited(monkeypatch: Any) -> None:
    fake_vs = _install_fake_vs(monkeypatch)
    frames = [
        {"PlaneStatsMin": 4096.0, "PlaneStatsMax": 50200.0},
        {"PlaneStatsMin": 4200.0, "PlaneStatsMax": 49600.0},
    ]
    std = _DetectStd(frames)
    clip = types.SimpleNamespace(
        format=types.SimpleNamespace(
            color_family=getattr(fake_vs, "RGB"),
            sample_type=_FakeSampleType("INTEGER", 0),
            bits_per_sample=16,
        )
    )
    core = types.SimpleNamespace(std=std)

    detected, source = vs_core._detect_rgb_color_range(
        core,
        clip,
        log=logging.getLogger("test"),
        label="limited",
    )

    assert detected == getattr(fake_vs, "RANGE_LIMITED")
    assert source == "plane_stats"


def test_detect_rgb_color_range_identifies_full(monkeypatch: Any) -> None:
    fake_vs = _install_fake_vs(monkeypatch)
    frames = [
        {"PlaneStatsMin": 0.0, "PlaneStatsMax": 65535.0},
        {"PlaneStatsMin": 300.0, "PlaneStatsMax": 64000.0},
    ]
    std = _DetectStd(frames)
    clip = types.SimpleNamespace(
        format=types.SimpleNamespace(
            color_family=getattr(fake_vs, "RGB"),
            sample_type=_FakeSampleType("INTEGER", 0),
            bits_per_sample=16,
        )
    )
    core = types.SimpleNamespace(std=std)

    detected, source = vs_core._detect_rgb_color_range(
        core,
        clip,
        log=logging.getLogger("test"),
        label="full",
    )

    assert detected == getattr(fake_vs, "RANGE_FULL")
    assert source == "plane_stats"


def test_detect_rgb_color_range_detects_undershoot(monkeypatch: Any) -> None:
    fake_vs = _install_fake_vs(monkeypatch)
    frames = [
        {"PlaneStatsMin": 2000.0, "PlaneStatsMax": 42000.0},
        {"PlaneStatsMin": 2100.0, "PlaneStatsMax": 43000.0},
    ]
    std = _DetectStd(frames)
    clip = types.SimpleNamespace(
        format=types.SimpleNamespace(
            color_family=getattr(fake_vs, "RGB"),
            sample_type=_FakeSampleType("INTEGER", 0),
            bits_per_sample=16,
        )
    )
    core = types.SimpleNamespace(std=std)

    detected, source = vs_core._detect_rgb_color_range(
        core,
        clip,
        log=logging.getLogger("test"),
        label="undershoot",
    )

    assert detected == getattr(fake_vs, "RANGE_LIMITED")
    assert source == "plane_stats"


def test_compute_verification_normalizes_integer_clip() -> None:
    fmt = _FakeFormat(bits_per_sample=8, sample_type=_FakeSampleType("INTEGER", 0))
    props = {"PlaneStatsAverage": 25.5, "PlaneStatsMax": 51.0}
    result = _run_compute_verification(fmt, props)
    assert math.isclose(result.average, 0.1)
    assert math.isclose(result.maximum, 0.2)


def test_compute_verification_preserves_float_clip() -> None:
    fmt = _FakeFormat(bits_per_sample=32, sample_type=_FakeSampleType("FLOAT", 1))
    props = {"PlaneStatsAverage": 0.25, "PlaneStatsMax": 0.75}
    result = _run_compute_verification(fmt, props)
    assert math.isclose(result.average, 0.25)
    assert math.isclose(result.maximum, 0.75)


class _DummyStd:
    def __init__(self, clip: "_DummyClip") -> None:
        self._clip = clip
        self.calls: List[Dict[str, int]] = []

    def SetFrameProps(self, clip: Any, **kwargs: int) -> "_DummyClip":
        assert clip is self._clip
        self.calls.append({key: int(value) for key, value in kwargs.items()})
        return self._clip


class _DummyClip:
    def __init__(self, fake_vs: Any, height: int) -> None:
        self.format = types.SimpleNamespace(color_family=getattr(fake_vs, "YUV", object()))
        self.height = height
        self.std = _DummyStd(self)


def _install_fake_vs(monkeypatch: Any, **overrides: int) -> Any:
    yuv_family = object()
    attributes = dict(
        YUV=yuv_family,
        RGB=object(),
        MATRIX_BT709=1,
        MATRIX_SMPTE170M=6,
        PRIMARIES_BT709=1,
        PRIMARIES_SMPTE170M=6,
        TRANSFER_BT709=1,
        TRANSFER_SMPTE170M=6,
        RANGE_LIMITED=1,
        RANGE_FULL=0,
    )
    attributes.update(overrides)
    fake_vs = types.SimpleNamespace(**attributes)
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vs)
    monkeypatch.setattr(vs_core, "_vs_module", fake_vs, raising=False)
    return fake_vs


def test_normalise_color_metadata_infers_hd_defaults(monkeypatch: Any) -> None:
    fake_vs = _install_fake_vs(monkeypatch)
    clip = _DummyClip(fake_vs, height=1080)

    normalised_clip, props, color_tuple = vs_core.normalise_color_metadata(
        clip,
        {},
        color_cfg=ColorConfig(),
        file_name="clip.mkv",
    )

    assert normalised_clip is clip
    assert color_tuple == (
        int(fake_vs.MATRIX_BT709),
        int(fake_vs.TRANSFER_BT709),
        int(fake_vs.PRIMARIES_BT709),
        int(fake_vs.RANGE_LIMITED),
    )
    assert props["_Matrix"] == int(fake_vs.MATRIX_BT709)
    assert props["_Transfer"] == int(fake_vs.TRANSFER_BT709)
    assert props["_Primaries"] == int(fake_vs.PRIMARIES_BT709)
    assert props["_ColorRange"] == int(fake_vs.RANGE_LIMITED)
    assert clip.std.calls == [
        {
            "_Matrix": int(fake_vs.MATRIX_BT709),
            "_Transfer": int(fake_vs.TRANSFER_BT709),
            "_Primaries": int(fake_vs.PRIMARIES_BT709),
            "_ColorRange": int(fake_vs.RANGE_LIMITED),
        }
    ]


def test_normalise_color_metadata_infers_sd_defaults(monkeypatch: Any) -> None:
    fake_vs = _install_fake_vs(
        monkeypatch,
        MATRIX_SMPTE170M=106,
        PRIMARIES_SMPTE170M=206,
        TRANSFER_SMPTE170M=306,
        RANGE_LIMITED=17,
    )
    clip = _DummyClip(fake_vs, height=480)

    normalised_clip, props, color_tuple = vs_core.normalise_color_metadata(
        clip,
        {},
        color_cfg=ColorConfig(),
        file_name="clip_sd.mkv",
    )

    assert normalised_clip is clip
    assert color_tuple == (106, 306, 206, 17)
    assert props["_Matrix"] == 106
    assert props["_Transfer"] == 306
    assert props["_Primaries"] == 206
    assert props["_ColorRange"] == 17


def test_normalise_color_metadata_honours_overrides(monkeypatch: Any) -> None:
    fake_vs = _install_fake_vs(monkeypatch)
    clip = _DummyClip(fake_vs, height=2160)

    cfg = ColorConfig(
        color_overrides={
            "clip.mkv": {
                "matrix": "bt2020",
                "primaries": "bt2020",
                "transfer": "st2084",
                "range": "full",
            }
        }
    )

    _, props, color_tuple = vs_core.normalise_color_metadata(
        clip,
        {},
        color_cfg=cfg,
        file_name="clip.mkv",
    )

    assert color_tuple == (9, 16, 9, 0)
    assert props["_Matrix"] == 9
    assert props["_Transfer"] == 16
    assert props["_Primaries"] == 9
    assert props["_ColorRange"] == 0


def test_normalise_color_metadata_infers_limited_via_signal(monkeypatch: Any) -> None:
    fake_vs = _install_fake_vs(monkeypatch)
    clip = _DummyClip(fake_vs, height=1080)

    monkeypatch.setattr(vs_core, "_compute_luma_bounds", lambda _: (16.0, 234.0))

    warnings: list[str] = []
    _, props, _ = vs_core.normalise_color_metadata(
        clip,
        {},
        color_cfg=ColorConfig(),
        file_name="clip.mkv",
        warning_sink=warnings,
    )

    assert props["_ColorRange"] == int(fake_vs.RANGE_LIMITED)
    assert warnings  # warning emitted for metadata adjustment


def test_normalise_color_metadata_warns_for_mismatched_limited(monkeypatch: Any) -> None:
    fake_vs = _install_fake_vs(monkeypatch)
    clip = _DummyClip(fake_vs, height=1080)

    monkeypatch.setattr(vs_core, "_compute_luma_bounds", lambda _: (0.0, 255.0))

    warnings: list[str] = []
    _, props, _ = vs_core.normalise_color_metadata(
        clip,
        {"_ColorRange": int(fake_vs.RANGE_LIMITED)},
        color_cfg=ColorConfig(),
        file_name="clip.mkv",
        warning_sink=warnings,
    )

    # Range remains limited but a warning is emitted for the suspicious signal.
    assert props["_ColorRange"] == int(fake_vs.RANGE_LIMITED)
    assert warnings
