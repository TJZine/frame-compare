"""Pure edge cases shared by audio decision, video scoring, and review projection."""

from fractions import Fraction

from frame_compare.services.alignment_correlation import ChunkObservation, ChunkRun
from frame_compare.services.alignment_decision import (
    classify_audio_observations,
    competing_run_center,
)
from frame_compare.utils.alignment_policy import confirmed_offset


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
