from fractions import Fraction

import pytest

from frame_compare.analysis.errors import SelectionError
from frame_compare.analysis.selection import preferred_frame_gap, select_frames
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


def make_sparse_metrics(
    luminance: list[float],
    motion: list[float],
    source_frames: tuple[int, ...],
    *,
    start: int = 100,
    end_exclusive: int = 140,
) -> FrameMetrics:
    return FrameMetrics(
        luminance=luminance,
        motion=motion,
        metadata=MetricsMetadata(
            frame_count=len(luminance),
            fps=Fraction(24),
            config_fingerprint="fp",
            clips=[],
            source_frame_count=200,
            metric_source_start=start,
            metric_source_end_exclusive=end_exclusive,
            performance_mode="performance",
        ),
        sampled_source_frames=source_frames,
    )


LUMINANCE_100 = [i / 100.0 for i in range(100)]
MOTION_100 = [1.0 if i in {50, 60, 70, 80, 90} else 0.1 for i in range(100)]


@pytest.mark.parametrize(
    ("fps", "expected_gap"),
    [
        (Fraction(24), 12),
        (Fraction(24000, 1001), 12),
        (Fraction(25), 13),
        (Fraction(60), 30),
    ],
)
def test_preferred_frame_gap_ceil_half_second_exactly(fps: Fraction, expected_gap: int) -> None:
    assert preferred_frame_gap(fps) == expected_gap


def test_preferred_frame_gap_keeps_one_frame_minimum() -> None:
    assert preferred_frame_gap(Fraction(1, 2)) == 1


def test_selection_uses_supplied_selection_domain_fps_for_spacing() -> None:
    motion = [0.0] * 40
    motion[20] = 1.0
    motion[30] = 0.9

    result = select_frames(
        make_metrics([0.5] * 40, motion),
        AnalysisConfig(
            user_frames=[0],
            random_frame_count=0,
            motion_frame_count=1,
        ),
        selection_fps=Fraction(60),
    )

    assert result.breakdown.motion == [30]


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

    assert result.frames == [0, 20, 50, 70, 90]


def test_motion_prefers_farther_frame_over_higher_ranked_close_bright_frame() -> None:
    luminance = [0.5] * 40
    luminance[10] = 1.0
    luminance[12] = 0.9
    motion = [0.0] * 40
    motion[12] = 1.0
    motion[25] = 0.9

    result = select_frames(
        make_metrics(luminance, motion),
        AnalysisConfig(
            random_frame_count=0,
            bright_frame_count=1,
            motion_frame_count=1,
        ),
    )

    assert result.breakdown.quantile_bright == [10]
    assert result.breakdown.motion == [25]
    assert abs(result.breakdown.motion[0] - result.breakdown.quantile_bright[0]) >= 12


def test_progressive_spacing_backfill_uses_greatest_attainable_gap() -> None:
    motion = [0.0] * 22
    motion[19] = 1.0
    motion[9] = 0.9
    motion[8] = 0.8

    result = select_frames(
        make_metrics([0.5] * 22, motion),
        AnalysisConfig(
            user_frames=[0],
            random_frame_count=0,
            motion_frame_count=2,
        ),
    )

    assert result.breakdown.motion == [9, 19]
    assert (
        min(
            abs(frame - other)
            for frame in result.frames
            for other in result.frames
            if frame != other
        )
        == 9
    )


def test_progressive_spacing_finally_selects_close_unique_frame() -> None:
    result = select_frames(
        make_metrics([0.5, 0.5], [0.0, 1.0]),
        AnalysisConfig(
            user_frames=[0],
            random_frame_count=0,
            motion_frame_count=1,
        ),
    )

    assert result.frames == [0, 1]
    assert result.breakdown.motion == [1]


def test_very_high_selection_fps_completes_with_small_frame_domain() -> None:
    motion = [0.0, 1.0, 0.9, 0.8]
    config = AnalysisConfig(
        user_frames=[0],
        random_frame_count=0,
        motion_frame_count=3,
    )

    result1 = select_frames(
        make_metrics([0.5] * 4, motion),
        config,
        selection_fps=Fraction(10**12),
    )
    result2 = select_frames(
        make_metrics([0.5] * 4, motion),
        config,
        selection_fps=Fraction(10**12),
    )

    assert result1.frames == [0, 1, 2, 3]
    assert result1.frames == result2.frames
    assert len(result1.frames) == 4
    assert len(set(result1.frames)) == 4


def test_metric_categories_choose_best_candidate_per_temporal_stratum() -> None:
    luminance = [0.5] * 40
    motion = [0.1] * 40
    for rank, frame in enumerate((1, 11, 21, 31)):
        luminance[frame] = 0.01 + rank * 0.01
        motion[frame] = 1.0 - rank * 0.01
    for rank, frame in enumerate((8, 18, 28, 38)):
        luminance[frame] = 0.99 - rank * 0.01

    result = select_frames(
        make_metrics(luminance, motion),
        AnalysisConfig(
            random_frame_count=0,
            dark_frame_count=4,
            bright_frame_count=4,
            motion_frame_count=4,
            dark_quantile=0.2,
            bright_quantile=0.8,
        ),
    )

    assert result.breakdown.quantile_dark == [1, 11, 21, 31]
    assert result.breakdown.quantile_bright == [8, 18, 28, 38]
    assert len(result.breakdown.motion) == 4


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


def test_metric_categories_backfill_after_user_collisions() -> None:
    lum = [0.0, 0.1, 0.2, 0.8, 0.9, 1.0]
    mot = [0.0] * len(lum)
    metrics = make_metrics(lum, mot)
    config = AnalysisConfig(
        user_frames=[0, 5],
        random_frame_count=0,
        dark_frame_count=2,
        bright_frame_count=2,
    )

    result = select_frames(metrics, config)

    assert result.breakdown.user == [0, 5]
    assert result.breakdown.quantile_dark == [1, 2]
    assert result.breakdown.quantile_bright == [3, 4]
    assert result.frames == [0, 1, 2, 3, 4, 5]


def test_random_relaxes_spacing_when_short_clip_has_enough_unique_frames() -> None:
    metrics = make_metrics([0.1] * 5, [0.0] * 5)
    config = AnalysisConfig(random_frame_count=2)

    result = select_frames(metrics, config)

    assert len(result.frames) == 2
    assert len(set(result.frames)) == 2


def test_random_selection_uses_every_temporal_stratum() -> None:
    metrics = make_metrics([0.5] * 200, [0.0] * 200)

    frames = select_frames(
        metrics,
        AnalysisConfig(random_frame_count=10, random_seed=42),
    ).breakdown.random

    assert all(any(start <= frame < start + 20 for frame in frames) for start in range(0, 200, 20))


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


def test_motion_selection_respects_preferred_gap_when_candidates_allow_it() -> None:
    metrics = make_metrics(LUMINANCE_100, MOTION_100)
    config = AnalysisConfig(random_frame_count=0, motion_frame_count=5)

    frames = select_frames(metrics, config).frames

    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            assert abs(frames[i] - frames[j]) >= preferred_frame_gap(metrics.metadata.fps)


def test_random_selection_respects_preferred_gap_when_candidates_allow_it() -> None:
    metrics = make_metrics([0.5] * 200, [0.0] * 200)
    config = AnalysisConfig(random_frame_count=10)

    frames = select_frames(metrics, config).frames

    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            assert abs(frames[i] - frames[j]) >= preferred_frame_gap(metrics.metadata.fps)


def test_sparse_selection_uses_source_coordinates_and_full_window_for_user_frames() -> None:
    metrics = make_sparse_metrics(
        [0.1, 0.9, 0.5],
        [0.2, 0.3, 1.0],
        (101, 120, 138),
    )
    config = AnalysisConfig(
        user_frames=[0],
        random_frame_count=0,
        dark_frame_count=1,
        bright_frame_count=1,
        motion_frame_count=1,
    )

    result = select_frames(metrics, config)

    assert result.frames == [0, 1, 20, 38]
    assert result.breakdown.quantile_dark == [1]
    assert result.breakdown.quantile_bright == [20]
    assert result.breakdown.motion == [38]
    assert result.selection_details[1].score == pytest.approx(0.1)
    assert result.selection_details[20].score == pytest.approx(0.9)
    assert result.selection_details[38].score == pytest.approx(1.0)
    assert result.selection_details[38].timecode == "00:00:01.583"


def test_sparse_metric_selection_stratifies_in_source_coordinates() -> None:
    metrics = make_sparse_metrics(
        [0.4, 0.3, 0.2, 0.1],
        [0.7, 0.8, 0.9, 1.0],
        (101, 111, 121, 131),
    )

    result = select_frames(
        metrics,
        AnalysisConfig(random_frame_count=0, motion_frame_count=4),
    )

    assert result.breakdown.motion == [1, 11, 21, 31]
    assert [result.selection_details[frame].score for frame in (1, 11, 21, 31)] == [
        pytest.approx(0.7),
        pytest.approx(0.8),
        pytest.approx(0.9),
        pytest.approx(1.0),
    ]


def test_sparse_selection_reports_insufficient_metric_candidates() -> None:
    metrics = make_sparse_metrics([0.1, 0.2], [0.0, 0.1], (101, 120))

    with pytest.raises(SelectionError) as exc:
        select_frames(
            metrics,
            AnalysisConfig(random_frame_count=0, dark_frame_count=3),
        )

    assert exc.value.context.details == {
        "reason": "insufficient_candidates",
        "requested": 3,
        "found": 2,
    }
