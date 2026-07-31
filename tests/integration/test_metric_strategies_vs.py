from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from frame_compare.analysis.metric_strategies import calculate_metric_strategy
from frame_compare.config.schema import AnalysisConfig

vs = pytest.importorskip("vapoursynth")
if isinstance(vs, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)


def _source(clip: object) -> SimpleNamespace:
    return SimpleNamespace(clip=clip)


@pytest.mark.vs_required
def test_performance_strategy_black_clip_has_zero_luminance_and_motion() -> None:
    clip = vs.core.std.BlankClip(width=16, height=16, length=3, format=vs.GRAY8, color=0)

    result = calculate_metric_strategy(
        _source(clip),
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.luminance == pytest.approx([0.0])
    assert result.motion == pytest.approx([0.0])
    assert result.sampled_source_frames == (1,)


@pytest.mark.vs_required
def test_performance_strategy_one_frame_clip_uses_real_planestats() -> None:
    clip = vs.core.std.BlankClip(width=16, height=16, length=1, format=vs.GRAY8, color=64)

    result = calculate_metric_strategy(
        _source(clip),
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.luminance == pytest.approx([64 / 255])
    assert result.motion == pytest.approx([0.0])
    assert result.sampled_source_frames == (0,)


@pytest.mark.vs_required
def test_performance_strategy_white_clip_has_full_luminance_and_zero_motion() -> None:
    clip = vs.core.std.BlankClip(width=16, height=16, length=3, format=vs.GRAY8, color=255)

    result = calculate_metric_strategy(
        _source(clip),
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.luminance == pytest.approx([1.0])
    assert result.motion == pytest.approx([0.0])
    assert result.sampled_source_frames == (1,)


@pytest.mark.vs_required
def test_performance_strategy_black_to_white_motion_is_at_current_frame() -> None:
    black = vs.core.std.BlankClip(width=16, height=16, length=1, format=vs.GRAY8, color=0)
    white = vs.core.std.BlankClip(width=16, height=16, length=3, format=vs.GRAY8, color=255)
    clip = black + white

    result = calculate_metric_strategy(
        _source(clip),
        AnalysisConfig(performance_mode="performance"),
        reporter=None,
    )

    assert result.luminance == pytest.approx([1.0])
    assert result.motion[0] > 0.0
    assert result.sampled_source_frames == (1,)


@pytest.mark.vs_required
def test_performance_strategy_repeated_runs_are_identical() -> None:
    clip = vs.core.std.BlankClip(width=16, height=16, length=4, format=vs.GRAY8, color=64)
    config = AnalysisConfig(performance_mode="performance")

    first = calculate_metric_strategy(_source(clip), config, reporter=None)
    second = calculate_metric_strategy(_source(clip), config, reporter=None)

    assert first.luminance == pytest.approx([64 / 255])
    assert first.motion == pytest.approx([0.0])
    assert first.sampled_source_frames == (1,)
    assert second.luminance == first.luminance
    assert second.motion == first.motion
