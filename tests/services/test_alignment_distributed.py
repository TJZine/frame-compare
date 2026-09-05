"""Bounded, timeline-distributed audio alignment regressions."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from frame_compare.services import alignment_audio, alignment_consensus
from frame_compare.services.alignment_audio import (
    AudioAnalysisBudgetExceeded,
    AudioAnalysisPlan,
    AudioStreamInfo,
    AudioStreamTimeline,
    AudioWindow,
    AudioWindowSpec,
)
from frame_compare.services.alignment_correlation import (
    CorrelationEstimate,
    correlate_audio,
    estimate_alignment_offset,
    refine_aligned_score,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig


def _stream(duration: int, *, start: int = 0) -> AudioStreamInfo:
    return AudioStreamInfo(
        audio_stream_index=0,
        absolute_stream_index=1,
        codec_name="aac",
        channels=2,
        channel_layout="stereo",
        sample_rate=48000,
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        timeline=AudioStreamTimeline(
            start_time=Fraction(start),
            duration=Fraction(duration),
            time_base=Fraction(1, 48000),
            duration_basis="duration_ts",
        ),
    )


def _plan(*, rate: int, count: int) -> AudioAnalysisPlan:
    specs = tuple(AudioWindowSpec(index * 100, 200, index * 100, 400) for index in range(count))
    return AudioAnalysisPlan(rate, rate, specs, 1024, count * 1024)


def _estimate_windows(
    windows: list[AudioWindow],
    *,
    config: AlignmentConfig,
) -> alignment_consensus.AlignmentConsensus:
    remaining = iter(windows)
    return alignment_consensus.estimate_planned_consensus_offset(
        plan=_plan(rate=config.sample_rate, count=len(windows)),
        config=config,
        fps=Fraction(24),
        analysis_window_loader=lambda _spec: next(remaining),
        scoring_window_loader=lambda _spec, _offset: (_ for _ in ()).throw(
            AssertionError("requested-rate scoring is not expected")
        ),
    )


@pytest.mark.parametrize(
    ("reference_size", "comparison_size", "reference_index", "comparison_index"),
    [(30, 50, 7, 19), (50, 30, 19, 7)],
)
def test_unequal_length_correlation_uses_the_comparison_zero_lag_axis(
    reference_size: int,
    comparison_size: int,
    reference_index: int,
    comparison_index: int,
) -> None:
    pattern = np.array([1, -2, 4, -3, 2], dtype=np.float32)
    reference = np.zeros(reference_size, dtype=np.float32)
    comparison = np.zeros(comparison_size, dtype=np.float32)
    reference[reference_index : reference_index + pattern.size] = pattern
    comparison[comparison_index : comparison_index + pattern.size] = pattern

    estimate = estimate_alignment_offset(
        reference,
        comparison,
        config=AlignmentConfig(sample_rate=100, max_offset_seconds=1),
    )

    assert estimate.sample_offset == reference_index - comparison_index
    assert estimate.score == pytest.approx(1.0)


def test_confidence_is_normalized_over_the_actual_aligned_overlap() -> None:
    rng = np.random.default_rng(7)
    reference = rng.standard_normal(200).astype(np.float32)
    comparison = np.zeros(400, dtype=np.float32)
    comparison[73:273] = reference

    estimate = correlate_audio(reference, comparison, max_offset_samples=100)

    assert estimate.sample_offset == 73
    assert estimate.score == pytest.approx(1.0)


def test_two_sample_boundary_match_is_not_meaningful_overlap() -> None:
    reference = np.zeros(100, dtype=np.float32)
    comparison = np.zeros(100, dtype=np.float32)
    reference[:2] = [1, -1]
    comparison[-2:] = [1, -1]

    with pytest.raises(AudioAlignmentError, match="insufficient aligned overlap"):
        correlate_audio(reference, comparison, max_offset_samples=100)


def test_requested_rate_score_accepts_full_30_second_overlap() -> None:
    rng = np.random.default_rng(41)
    signal = rng.standard_normal(30 * 48000).astype(np.float32)

    correction, score = refine_aligned_score(
        signal,
        signal,
        preprocessing_mode="none",
        correction_bounds_samples=(0, 0),
    )

    assert correction == 0
    assert score == pytest.approx(1.0)


def test_overlap_confidence_threshold_rejects_without_exposing_an_offset() -> None:
    reference = np.array([0, 1, -2, 3, -1, 0], dtype=np.float32)
    comparison = np.concatenate((np.zeros(2, dtype=np.float32), reference))
    result = _estimate_windows(
        [AudioWindow(reference, comparison, 0, 0)],
        config=AlignmentConfig(
            sample_rate=100,
            max_offset_seconds=1,
            confidence_threshold=1.1,
        ),
    )

    assert not result.applied
    assert result.sample_offset is None
    assert result.diagnostic == "low_confidence"


def test_planned_consensus_uses_majority_before_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    estimates = iter(
        [
            CorrelationEstimate(4, 0.51, 2.0),
            CorrelationEstimate(4, 0.52, 2.0),
            CorrelationEstimate(4, 0.53, 2.0),
            CorrelationEstimate(9, 0.99, 2.0),
            CorrelationEstimate(9, 0.98, 2.0),
        ]
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: next(estimates),
    )
    windows = [
        AudioWindow(np.ones(20), np.ones(20), index * 100, index * 100) for index in range(5)
    ]

    result = _estimate_windows(
        windows,
        config=AlignmentConfig(
            sample_rate=100,
            max_offset_seconds=1,
            consensus_minimum_ratio=0.6,
        ),
    )

    assert result.applied
    assert result.sample_offset == 4
    assert result.consensus_windows == 3


def test_winning_group_uses_representative_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    estimates = iter(
        [
            CorrelationEstimate(4, 0.95, 2.0),
            CorrelationEstimate(4, 0.10, 2.0),
            CorrelationEstimate(4, 0.10, 2.0),
        ]
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: next(estimates),
    )
    windows = [AudioWindow(np.ones(20), np.ones(20), 0, 0) for _ in range(3)]

    result = _estimate_windows(
        windows,
        config=AlignmentConfig(
            sample_rate=100,
            max_offset_seconds=1,
            confidence_threshold=0.9,
        ),
    )

    assert not result.applied
    assert result.diagnostic == "low_confidence"
    assert result.score == pytest.approx(0.1)


def test_coarse_lag_is_scored_at_requested_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = AudioAnalysisPlan(
        sample_rate=8000,
        requested_sample_rate=48000,
        windows=(AudioWindowSpec(0, 100, 0, 100),),
        peak_fft_points=256,
        total_fft_points=256,
    )
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(0, 0.99, 2.0),
    )
    signal = np.linspace(-1, 1, 600, dtype=np.float32)

    result = alignment_consensus.estimate_planned_consensus_offset(
        plan=plan,
        config=AlignmentConfig(
            sample_rate=48000,
            max_offset_seconds=1,
            confidence_threshold=0.9,
        ),
        fps=Fraction(24),
        analysis_window_loader=lambda _spec: AudioWindow(np.ones(100), np.ones(100), 0, 0),
        scoring_window_loader=lambda _spec, _offset: AudioWindow(signal, -signal, 0, 0),
    )

    assert not result.applied
    assert result.diagnostic == "low_confidence"
    assert result.score == pytest.approx(-1.0)


@pytest.mark.parametrize("sign", [-1, 1])
def test_requested_rate_correction_cannot_escape_max_offset(
    monkeypatch: pytest.MonkeyPatch,
    sign: int,
) -> None:
    plan = AudioAnalysisPlan(8000, 48000, (AudioWindowSpec(0, 100, 0, 100),), 256, 256)
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(sign * 8000, 1.0, 2.0),
    )
    seen_bounds: list[tuple[int, int]] = []

    def outward_refinement(*_args: object, **kwargs: Any) -> tuple[int, float]:
        seen_bounds.append(kwargs["correction_bounds_samples"])
        return sign * 6, 1.0

    monkeypatch.setattr(alignment_consensus, "refine_aligned_score", outward_refinement)

    result = alignment_consensus.estimate_planned_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000, max_offset_seconds=1),
        fps=Fraction(24),
        analysis_window_loader=lambda _spec: AudioWindow(np.ones(100), np.ones(100), 0, 0),
        scoring_window_loader=lambda _spec, _offset: AudioWindow(
            np.ones(600),
            np.ones(600),
            48000 if sign > 0 else 0,
            0 if sign > 0 else 48000,
        ),
    )

    assert not result.applied
    assert result.sample_offset is None
    assert seen_bounds == [(-6, 0) if sign > 0 else (0, 6)]


@pytest.mark.parametrize("expected", [-23, 23])
def test_requested_rate_interior_correction_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    expected: int,
) -> None:
    plan = AudioAnalysisPlan(8000, 48000, (AudioWindowSpec(0, 100, 0, 100),), 256, 256)
    coarse = 24 if expected > 0 else -24
    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(coarse // 6, 1.0, 2.0),
    )
    monkeypatch.setattr(
        alignment_consensus,
        "refine_aligned_score",
        lambda *_args, **_kwargs: (expected - coarse, 1.0),
    )

    result = alignment_consensus.estimate_planned_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000, max_offset_seconds=1),
        fps=Fraction(24),
        analysis_window_loader=lambda _spec: AudioWindow(np.ones(100), np.ones(100), 0, 0),
        scoring_window_loader=lambda _spec, _offset: AudioWindow(
            np.ones(600),
            np.ones(600),
            max(0, coarse),
            max(0, -coarse),
        ),
    )

    assert result.applied
    assert result.sample_offset == expected


@pytest.mark.parametrize("expected_offset", [-99, 99])
def test_planned_windows_recover_offsets_near_both_search_bounds(
    expected_offset: int,
) -> None:
    rng = np.random.default_rng(19)
    source = rng.standard_normal(1200).astype(np.float32)
    reference_start = 400
    comparison_start = 300
    reference = source[reference_start : reference_start + 200]
    comparison = source[
        comparison_start + expected_offset : comparison_start + expected_offset + 400
    ]
    window = AudioWindow(reference, comparison, reference_start, comparison_start)

    result = _estimate_windows(
        [window],
        config=AlignmentConfig(sample_rate=100, max_offset_seconds=1),
    )

    assert result.applied
    assert result.sample_offset == expected_offset


def test_weak_intro_does_not_hide_strong_late_content() -> None:
    rng = np.random.default_rng(23)
    strong = rng.standard_normal(200).astype(np.float32)
    windows = [AudioWindow(np.zeros(200), np.zeros(300), 0, 0)]
    windows.extend(
        AudioWindow(strong, np.concatenate((np.zeros(20), strong)), index * 1000, index * 1000)
        for index in range(1, 5)
    )

    result = _estimate_windows(
        windows,
        config=AlignmentConfig(
            sample_rate=100,
            max_offset_seconds=1,
            minimum_valid_windows=3,
        ),
    )

    assert result.applied
    assert result.sample_offset == -20
    assert result.valid_windows == 4


@pytest.mark.parametrize("stride_seconds", [0, 60])
def test_plan_uses_selected_stream_duration_and_configured_window_grid(
    stride_seconds: int,
) -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(7200),
        _stream(300),
        config=AlignmentConfig(
            window_length_seconds=60,
            window_stride_seconds=stride_seconds,
        ),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert all(spec.reference_sample_count == 60 * plan.sample_rate for spec in plan.windows)
    assert [spec.reference_start_sample // plan.sample_rate for spec in plan.windows] == [
        0,
        60,
        120,
        180,
        240,
    ]


@pytest.mark.parametrize("requested_rate", [8000, 48000])
def test_long_request_uses_bounded_distributed_coarse_work(requested_rate: int) -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(7200),
        _stream(7200),
        config=AlignmentConfig(sample_rate=requested_rate),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert plan.sample_rate == 8000
    assert plan.requested_sample_rate == requested_rate
    assert len(plan.windows) == 5
    assert plan.peak_fft_points <= 1 << 21
    assert plan.total_fft_points <= 1 << 24


def test_long_48k_fallback_produces_requested_rate_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(65),
        _stream(65),
        config=AlignmentConfig(sample_rate=48000),
    )
    assert isinstance(plan, AudioAnalysisPlan)
    assert plan.sample_rate == 8000
    signal = np.linspace(-1, 1, 30 * 48000, dtype=np.float32)
    current_origin_delta = 0

    def load_analysis_window(spec: AudioWindowSpec) -> AudioWindow:
        nonlocal current_origin_delta
        current_origin_delta = spec.reference_start_sample - spec.comparison_start_sample
        return AudioWindow(
            np.ones(spec.reference_sample_count),
            np.ones(spec.comparison_sample_count),
            spec.reference_start_sample,
            spec.comparison_start_sample,
        )

    monkeypatch.setattr(
        alignment_consensus,
        "estimate_alignment_offset",
        lambda *_args, **_kwargs: CorrelationEstimate(-current_origin_delta, 0.99, 2.0),
    )

    result = alignment_consensus.estimate_planned_consensus_offset(
        plan=plan,
        config=AlignmentConfig(sample_rate=48000),
        fps=Fraction(24),
        analysis_window_loader=load_analysis_window,
        scoring_window_loader=lambda _spec, _offset: AudioWindow(signal, signal, 0, 0),
    )

    assert result.applied
    assert result.valid_windows == len(plan.windows)
    assert result.score == pytest.approx(1.0)


def test_tiny_stride_on_huge_timeline_plans_without_materializing_the_grid() -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(1_000_000_000),
        _stream(1_000_000_000),
        config=AlignmentConfig(
            window_length_seconds=1,
            window_stride_seconds=1e-12,
        ),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert 1 < len(plan.windows) <= 16
    assert plan.windows[0].reference_start_sample == 0
    assert plan.windows[-1].reference_start_sample > 1_000_000 * plan.sample_rate


@pytest.mark.parametrize(
    "config",
    [
        AlignmentConfig(max_offset_seconds=600),
        AlignmentConfig(max_offset_seconds=3600),
        AlignmentConfig(minimum_valid_windows=10000),
    ],
)
def test_pathological_valid_config_returns_budget_outcome(config: AlignmentConfig) -> None:
    plan = alignment_audio.plan_audio_analysis(_stream(7200), _stream(7200), config=config)

    assert isinstance(plan, AudioAnalysisBudgetExceeded)
    result = alignment_consensus.analysis_budget_exceeded(config=config, fps=Fraction(24))
    assert not result.applied
    assert result.sample_offset is None
    assert result.diagnostic == "analysis_budget_exceeded"


@pytest.mark.parametrize(
    "config",
    [
        AlignmentConfig(max_offset_seconds=float("inf")),
        AlignmentConfig(window_length_seconds=float("inf")),
        AlignmentConfig(window_stride_seconds=float("inf")),
    ],
)
def test_non_finite_internal_config_returns_budget_outcome(config: AlignmentConfig) -> None:
    result = alignment_audio.plan_audio_analysis(_stream(60), _stream(60), config=config)

    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == "non_finite_analysis_config"


def test_window_count_budget_rejects_tiny_work_with_huge_minimum() -> None:
    result = alignment_audio.plan_audio_analysis(
        _stream(7200),
        _stream(7200),
        config=AlignmentConfig(
            max_offset_seconds=1,
            window_length_seconds=1e-6,
            window_stride_seconds=1e-6,
            minimum_valid_windows=10000,
        ),
    )

    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == "minimum_valid_windows_exceeds_work_budget"


def test_short_clip_remains_a_single_complete_window() -> None:
    plan = alignment_audio.plan_audio_analysis(
        _stream(2),
        _stream(2),
        config=AlignmentConfig(),
    )

    assert isinstance(plan, AudioAnalysisPlan)
    assert len(plan.windows) == 1
    assert plan.windows[0].reference_sample_count == 16000


def test_extract_planned_window_decodes_exactly_one_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, int]] = []

    def extract(
        path: Path,
        _stream: AudioStreamInfo,
        *,
        sample_rate: int,
        start_sample: int,
        sample_count: int,
        channel_strategy: str,
    ) -> np.ndarray:
        del sample_rate, channel_strategy
        calls.append((path, start_sample))
        return np.ones(sample_count, dtype=np.float32)

    monkeypatch.setattr(alignment_audio, "extract_audio_window", extract)
    plan = AudioAnalysisPlan(
        100,
        100,
        (
            AudioWindowSpec(0, 10, 0, 20),
            AudioWindowSpec(100, 10, 90, 30),
        ),
        64,
        128,
    )
    window = alignment_audio.extract_planned_window(
        Path("reference.mkv"),
        Path("comparison.mkv"),
        _stream(10),
        _stream(10),
        plan,
        plan.windows[0],
        channel_strategy="mono_downmix",
    )

    assert calls == [(Path("reference.mkv"), 0), (Path("comparison.mkv"), 0)]
    assert window.reference.size == 10
    assert window.comparison.size == 20


def test_stream_probe_prefers_selected_stream_duration_over_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"time_base":"1/48000",'
        b'"duration_ts":1440000,"duration":"30.0"}],"format":{"duration":"600.0"}}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    selected = alignment_audio.select_reference_audio_stream(Path("short-audio.mkv"))

    assert selected.timeline.duration == 30
    assert selected.timeline.duration_basis == "duration_ts"


def test_stream_probe_does_not_substitute_long_container_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"time_base":"1/48000"}],"format":{"duration":"7200.0"}}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    selected = alignment_audio.select_reference_audio_stream(Path("unknown-audio.mkv"))
    result = alignment_audio.plan_audio_analysis(selected, _stream(7200), config=AlignmentConfig())

    assert selected.timeline.duration is None
    assert isinstance(result, AudioAnalysisBudgetExceeded)
    assert result.reason == "selected_audio_timeline_unavailable"


def test_stream_probe_preserves_negative_selected_stream_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"start_time":"-1.25",'
        b'"time_base":"1/48000","duration_ts":192000}]}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    selected = alignment_audio.select_reference_audio_stream(Path("negative-start.mkv"))

    assert selected.timeline.start_time == Fraction(-5, 4)
    assert selected.timeline.duration == 4


def test_stream_probe_ignores_non_finite_timing_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = MagicMock(
        stdout=b'{"streams":[{"index":1,"start_time":"Infinity",'
        b'"duration":"Infinity","time_base":"1/48000"}]}'
    )
    monkeypatch.setattr(alignment_audio, "run_subprocess", lambda *_args, **_kwargs: proc)

    selected = alignment_audio.select_reference_audio_stream(Path("invalid-time.mkv"))

    assert selected.timeline.start_time == 0
    assert selected.timeline.duration is None
