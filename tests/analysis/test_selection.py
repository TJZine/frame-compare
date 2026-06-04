from fractions import Fraction

import pytest

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.selection import MIN_GAP, select_frames
from frame_compare.analysis.types import ClipIdentity, FrameMetrics, MetricsMetadata
from frame_compare.config.schema import AnalysisConfig


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


LUMINANCE_100 = [i / 100.0 for i in range(100)]
MOTION_100 = [1.0 if i in {50, 60, 70, 80, 90} else 0.1 for i in range(100)]


def test_explicit_dark_and_bright_counts_return_luminance_extremes() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = AnalysisConfig(random_frame_count=0, dark_frame_count=5, bright_frame_count=5)

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


def test_quantile_thresholds_affect_selection_when_pool_is_larger_than_needed() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = AnalysisConfig(
        random_frame_count=0,
        dark_frame_count=5,
        bright_frame_count=5,
        dark_quantile=0.2,
        bright_quantile=0.8,
    )

    result = select_frames(metrics, config)

    assert max(result.breakdown.quantile_dark) > 4
    assert min(result.breakdown.quantile_bright) < 95


def test_motion_count_returns_high_motion() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = AnalysisConfig(random_frame_count=0, motion_frame_count=5)

    result = select_frames(metrics, config)

    assert result.frames == [50, 60, 70, 80, 90]


def test_random_count_same_seed_deterministic() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = AnalysisConfig(random_frame_count=10, random_seed=42)

    result1 = select_frames(metrics, config)
    result2 = select_frames(metrics, config)

    assert result1.frames == result2.frames


def test_random_count_different_seed_changes_output() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)

    result42 = select_frames(metrics, AnalysisConfig(random_frame_count=10, random_seed=42))
    result123 = select_frames(metrics, AnalysisConfig(random_frame_count=10, random_seed=123))

    assert result42.frames != result123.frames
    assert len(result42.frames) == 10
    assert len(result123.frames) == 10
    assert len(set(result42.frames)) == 10
    assert len(set(result123.frames)) == 10


def test_explicit_counts_are_combined_without_mode_allocation() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = AnalysisConfig(
        random_frame_count=2,
        dark_frame_count=2,
        bright_frame_count=2,
        motion_frame_count=4,
    )

    result = select_frames(metrics, config)

    assert len(result.breakdown.quantile_dark) == 2
    assert len(result.breakdown.quantile_bright) == 2
    assert len(result.breakdown.motion) == 4
    assert len(result.breakdown.random) == 2
    assert len(result.frames) == 10


def test_user_frames_have_label_precedence_over_metric_categories() -> None:
    lum = [0.0 if i == 0 else (1.0 if i == 99 else 0.5) for i in range(100)]
    mot = [1.0 if i in {0, 99, 10, 20, 30, 40} else 0.1 for i in range(100)]
    metrics = make_metrics(lum, mot)
    config = AnalysisConfig(
        user_frames=[0, 99],
        random_frame_count=2,
        dark_frame_count=2,
        bright_frame_count=2,
        motion_frame_count=2,
    )

    result = select_frames(metrics, config)

    assert result.selection_details[0].label == "User"
    assert result.selection_details[99].label == "User"
    assert len(set(result.frames)) == len(result.frames)


def test_insufficient_candidates_raises() -> None:
    metrics = make_metrics([0.1] * 5, [0.1] * 5)
    config = AnalysisConfig(random_frame_count=0, dark_frame_count=10)

    with pytest.raises(SelectionError) as exc:
        select_frames(metrics, config)

    assert exc.value.code == "FC-4012"
    assert exc.value.context.details == {
        "reason": "insufficient_candidates",
        "requested": 10,
        "found": 5,
    }


def test_empty_metrics_raises() -> None:
    metrics = make_metrics([], [])
    config = AnalysisConfig(random_frame_count=10)

    with pytest.raises(SelectionError) as exc:
        select_frames(metrics, config)

    assert exc.value.code == "FC-4012"
    assert exc.value.context.details == {"reason": "empty_metrics", "requested": 10, "found": 0}


def test_motion_selection_respects_min_gap() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = AnalysisConfig(random_frame_count=0, motion_frame_count=5)

    frames = select_frames(metrics, config).frames

    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            assert abs(frames[i] - frames[j]) >= MIN_GAP


def test_random_selection_respects_min_gap() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = AnalysisConfig(random_frame_count=10)

    frames = select_frames(metrics, config).frames

    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            assert abs(frames[i] - frames[j]) >= MIN_GAP
