from fractions import Fraction

import pytest

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.selection import MIN_GAP, select_frames
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.config.schema import AnalysisConfig, SelectionMode


def make_metrics(luminance: list[float], motion: list[float]) -> FrameMetrics:
    return FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=len(luminance),
            fps=Fraction(24),
            config_fingerprint="fp",
            clips=[ClipIdentity(path="video.mkv", size=1, mtime=1.0, sha1=None)],
            version=2,
        ),
    )


def make_config(
    *, frame_count: int, selection_mode: SelectionMode, random_seed: int = 42
) -> AnalysisConfig:
    return AnalysisConfig(
        frame_count=frame_count, selection_mode=selection_mode, random_seed=random_seed
    )


LUMINANCE_100 = [i / 100.0 for i in range(100)]
MOTION_100 = [1.0 if i in {50, 60, 70, 80, 90} else 0.1 for i in range(100)]


def test_quantile_mode_returns_luminance_extremes():
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = make_config(frame_count=10, selection_mode=SelectionMode.QUANTILE)
    result = select_frames(metrics, config)
    assert result.frames == [0, 1, 2, 3, 4, 95, 96, 97, 98, 99]
    assert list(result.breakdown.quantile_dark) == [0, 1, 2, 3, 4]
    assert list(result.breakdown.quantile_bright) == [95, 96, 97, 98, 99]
    assert result.selection_details[0].label == "Dark"
    assert result.selection_details[0].source == "analysis"
    assert result.selection_details[0].clip_role == "analyze"
    assert result.selection_details[0].timecode == "00:00:00.000"
    assert result.selection_details[95].label == "Bright"
    assert result.selection_details[95].notes == "quantile_bright"
    assert result.selection_details[95].score == pytest.approx(0.95)


def test_quantile_thresholds_affect_selection_when_pool_is_larger_than_needed():
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = make_config(frame_count=10, selection_mode=SelectionMode.QUANTILE)
    config.dark_quantile = 0.2
    config.bright_quantile = 0.8
    result = select_frames(metrics, config)

    # With larger quantile pools, we should sample across the pool rather than
    # always picking the absolute extremes.
    assert max(result.breakdown.quantile_dark) > 4
    assert min(result.breakdown.quantile_bright) < 95


def test_motion_mode_returns_high_motion():
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = make_config(frame_count=5, selection_mode=SelectionMode.MOTION)
    result = select_frames(metrics, config)
    assert result.frames == [50, 60, 70, 80, 90]


def test_random_mode_same_seed_deterministic():
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = make_config(frame_count=10, selection_mode=SelectionMode.RANDOM, random_seed=42)
    result1 = select_frames(metrics, config)
    result2 = select_frames(metrics, config)
    assert result1.frames == result2.frames


def test_random_mode_different_seed_changes_output():
    metrics = make_metrics(LUMINANCE_100, MOTION_100)

    config42 = make_config(frame_count=10, selection_mode=SelectionMode.RANDOM, random_seed=42)
    result42 = select_frames(metrics, config42)

    config123 = make_config(frame_count=10, selection_mode=SelectionMode.RANDOM, random_seed=123)
    result123 = select_frames(metrics, config123)

    assert result42.frames != result123.frames
    assert len(result42.frames) == 10
    assert len(result123.frames) == 10
    assert len(set(result42.frames)) == 10
    assert len(set(result123.frames)) == 10


def test_mixed_mode_allocation():
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = make_config(frame_count=10, selection_mode=SelectionMode.MIXED)
    result = select_frames(metrics, config)
    # Allocation: 40% Quantile (4 frames: 2 dark, 2 bright), 40% Motion (4 frames), 20% Random (2 frames)
    assert len(result.breakdown.quantile_dark) == 2
    assert len(result.breakdown.quantile_bright) == 2
    assert len(result.breakdown.motion) == 4
    assert len(result.breakdown.random) == 2
    assert len(result.frames) == 10


def test_deduplication_skips_already_selected():
    # Force overlap: peaks at 0 and 99
    lum = [0.0 if i == 0 else (1.0 if i == 99 else 0.5) for i in range(100)]
    mot = [1.0 if i in {0, 99, 10, 20, 30, 40} else 0.1 for i in range(100)]
    metrics = make_metrics(lum, mot)
    # Mode Mixed: 2 dark (0, 1), 2 bright (98, 99)
    # Motion wants peaks: 0, 99, 10, 20, 30, 40. But 0 and 99 are taken.
    config = make_config(frame_count=10, selection_mode=SelectionMode.MIXED)
    result = select_frames(metrics, config)
    assert len(result.frames) == 10
    # Final frames should be unique
    assert len(set(result.frames)) == 10
    assert result.selection_details[0].label == "Dark"


def test_insufficient_candidates_raises():
    # Only 5 frames available, but 10 requested
    metrics = make_metrics([0.1] * 5, [0.1] * 5)
    config = make_config(frame_count=10, selection_mode=SelectionMode.QUANTILE, random_seed=42)
    with pytest.raises(SelectionError) as exc:
        select_frames(metrics, config)
    assert exc.value.code == "FC-4012"
    assert exc.value.context.details == {
        "reason": "insufficient_candidates",
        "requested": 10,
        "found": 5,
    }


def test_empty_metrics_raises():
    metrics = make_metrics([], [])
    config = make_config(frame_count=10, selection_mode=SelectionMode.QUANTILE, random_seed=42)
    with pytest.raises(SelectionError) as exc:
        select_frames(metrics, config)
    assert exc.value.code == "FC-4012"
    assert exc.value.context.details == {"reason": "empty_metrics", "requested": 10, "found": 0}


def test_motion_selection_respects_min_gap():
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = make_config(frame_count=5, selection_mode=SelectionMode.MOTION)
    result = select_frames(metrics, config)
    frames = result.frames
    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            assert abs(frames[i] - frames[j]) >= MIN_GAP


def test_random_selection_respects_min_gap():
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = make_config(frame_count=10, selection_mode=SelectionMode.RANDOM)
    result = select_frames(metrics, config)
    frames = result.frames
    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            assert abs(frames[i] - frames[j]) >= MIN_GAP
