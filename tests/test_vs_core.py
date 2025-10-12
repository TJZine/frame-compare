import math
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import vs_core
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
