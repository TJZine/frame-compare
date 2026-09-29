"""Pure edge cases shared by audio decision, video scoring, and review projection."""

from dataclasses import replace
from fractions import Fraction

import pytest

from frame_compare.services.alignment_correlation import ChunkObservation, ChunkRun
from frame_compare.services.alignment_decision import (
    classify_audio_observations,
    competing_run_center,
)
from frame_compare.utils.alignment_policy import (
    compensated_offset_seconds,
    confirmed_offset,
    edge_consensus_offset,
)
from tests.services.test_alignment_evidence import stream


def _observation(index: int, lag: int) -> ChunkObservation:
    return ChunkObservation(index, index * 240_000, 240_000, True, lag, 20.0, True, False)


def test_competing_run_uses_true_median_only_for_alternative_centre() -> None:
    observations = (_observation(0, 499), _observation(1, 501))
    run = ChunkRun(0, 1, 499, 2)

    assert competing_run_center(run, observations) == 500.0
    assert competing_run_center(run, (_observation(0, 499), _observation(1, 500))) == 499.5


def test_a4a_run_span_never_exceeds_two_milliseconds() -> None:
    classified = classify_audio_observations(
        observations=tuple(_observation(index, lag) for index, lag in enumerate((1000, 984, 1016))),
        global_lag=0,
        confirmed_offset=0,
        fps_reference=Fraction(24),
        compensation_seconds=0.0,
    )

    assert [(run.first_index, run.last_index) for run in classified.competing_runs] == [(0, 1)]
    assert [item.index for item in classified.credible_disagreements] == [2]


def test_v5_uses_winner_only_margin_population() -> None:
    winners = [0] * 9 + [1] * 3
    margins = [1.1] * 4 + [1.6] * 5 + [1.1] * 3

    assert confirmed_offset(0, winners, margins) == 0


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        pytest.param(
            [(3.0, 2.5, 2.2, 2.0, 1.0)] * 6,
            148,
            id="six-edge-votes-agree",
        ),
        pytest.param(
            [(3.0, 2.5, 2.2, 2.0, 1.0)] * 5,
            None,
            id="five-votes-are-too-few",
        ),
        pytest.param(
            [(3.0, 2.5, 2.2, 2.0, 1.0)] * 6 + [(1.0, 2.0, 2.2, 2.5, 3.0)],
            None,
            id="split-edges-disagree",
        ),
        pytest.param(
            [(3.0, 2.5, 2.2, 2.0, 1.0)] * 6 + [(2.0, 1.0, 0.1, 1.0, 2.0)],
            148,
            id="interior-best-is-ignored",
        ),
    ],
)
def test_edge_consensus_offset(
    rows: list[tuple[float, float, float, float, float]], expected: int | None
) -> None:
    assert edge_consensus_offset(rows, (144, 145, 146, 147, 148)) == expected


def test_retimed_start_uses_the_analysis_timeline() -> None:
    evidence = replace(
        stream("reference"),
        stream_start_num=1,
        stream_start_den=10,
        video_start_num=0,
        video_start_den=1,
        timeline_scale_num=1001,
        timeline_scale_den=1000,
    )

    assert evidence.analysis_audio_start == Fraction(1001, 10000)
    assert compensated_offset_seconds(
        global_lag=0,
        reference_audio_start=evidence.analysis_audio_start,
        reference_video_start=Fraction(0),
        comparison_audio_start=Fraction(0),
        comparison_video_start=Fraction(0),
    ) == pytest.approx(0.1001)
