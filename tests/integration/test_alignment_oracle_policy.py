"""Frozen policy regressions retained independently of obsolete seek experiments."""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from frame_compare.services.alignment_math import samples_to_frames

from .alignment_oracle import PolicyObservation, evaluate_predeclared_policy


def _five_windows(
    *,
    offsets: list[int | None],
    scores: list[float | None],
    peaks: list[float | None],
    coverage: list[float] | None = None,
) -> list[PolicyObservation]:
    width = 30 * 48_000
    coverage = coverage or [1.0] * 5
    return [
        PolicyObservation(
            logical_id=f"primary-{index + 1:02d}",
            start_sample=index * width,
            end_sample=(index + 1) * width,
            sample_offset=offset,
            score=score,
            peak_ratio=peak,
            coverage_ratio=coverage[index],
            status="correlated" if offset is not None else "failed",
        )
        for index, (offset, score, peak) in enumerate(zip(offsets, scores, peaks, strict=True))
    ]


def test_tracked_scalar_evidence_preserves_experiment_history() -> None:
    fixture_dir = Path(__file__).parents[1] / "fixtures" / "alignment_oracle"
    evidence = {
        name: json.loads((fixture_dir / name).read_text(encoding="utf-8"))
        for name in ("p3-results.json", "p5-results.json", "p5b-results.json", "p6-results.json")
    }
    raw = json.dumps(evidence)

    assert evidence["p3-results.json"]["disposition"] == (
        "primary_extraction_discrepancy_demonstrated_p5_before_p4"
    )
    assert evidence["p3-results.json"]["matrix"]["weak_dissent"]["false_rejects"] == 0
    assert evidence["p3-results.json"]["matrix"]["localized_edit"]["false_accepts"] == 0
    assert evidence["p5-results.json"]["disposition"].startswith("p5a_ten_second_preroll_failed")
    assert evidence["p5b-results.json"]["disposition"].startswith("STOP")
    assert evidence["p6-results.json"]["decision"]["status"] == "CONDITIONAL"
    assert all(item["schema_version"] == 1 for item in evidence.values())
    assert "/Users/" not in raw
    assert "raw_samples" not in raw


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24_000, 1001)])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("weak_position", range(5))
@pytest.mark.parametrize("holdout_seed", [7701, 7702, 7703, 7704])
def test_policy_accepts_four_strong_windows_and_finite_weak_dissent(
    fps: Fraction,
    sign: int,
    weak_position: int,
    holdout_seed: int,
) -> None:
    offsets = [0] * 5
    scores = [0.99] * 5
    peaks = [2.0] * 5
    offsets[weak_position] = sign * 2400
    scores[weak_position] = 0.20 + (holdout_seed % 4) / 100
    peaks[weak_position] = 1.1

    result = evaluate_predeclared_policy(
        _five_windows(offsets=offsets, scores=scores, peaks=peaks),
        sample_rate=48_000,
        fps=fps,
        duration_seconds=Fraction(150),
    )

    assert result.accepted
    assert result.frame_offset == 0
    assert result.correlated == 5
    assert result.credible == result.voting_qualified == result.winning_qualified == 4
    assert result.independent_support >= 3


@pytest.mark.parametrize("fps", [Fraction(24), Fraction(24_000, 1001)])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("edit_position", range(5))
def test_policy_vetoes_credible_localized_edits(
    fps: Fraction,
    sign: int,
    edit_position: int,
) -> None:
    offsets = [0] * 5
    offsets[edit_position] = sign * 2400
    result = evaluate_predeclared_policy(
        _five_windows(offsets=offsets, scores=[0.99] * 5, peaks=[2.0] * 5),
        sample_rate=48_000,
        fps=fps,
        duration_seconds=Fraction(150),
        confidence_threshold=0.995,
        consensus_minimum_ratio=0.8,
    )

    assert not result.accepted
    assert result.reason == "credible_conflict"


def test_policy_rejects_one_survivor_drift_low_coverage_and_repetition() -> None:
    cases = (
        (
            _five_windows(
                offsets=[0, None, None, None, None],
                scores=[0.99, None, None, None, None],
                peaks=[2.0, None, None, None, None],
            ),
            "insufficient_temporal_support",
        ),
        (
            _five_windows(offsets=[0, 0, 2400, 2400, 4800], scores=[0.99] * 5, peaks=[2.0] * 5),
            "credible_conflict",
        ),
        (
            _five_windows(
                offsets=[0] * 5,
                scores=[0.99] * 5,
                peaks=[2.0] * 5,
                coverage=[1.0, 1.0, 0.89, 0.89, 0.89],
            ),
            "insufficient_temporal_support",
        ),
        (_five_windows(offsets=[0] * 5, scores=[0.99] * 5, peaks=[1.0] * 5), "no_candidate"),
    )
    for observations, reason in cases:
        result = evaluate_predeclared_policy(
            observations,
            sample_rate=48_000,
            fps=Fraction(24),
            duration_seconds=Fraction(150),
        )
        assert not result.accepted
        assert result.reason == reason

    assert samples_to_frames(1000, 48_000, Fraction(24)) == 0
    assert samples_to_frames(1001, 48_000, Fraction(24)) == 1
    assert samples_to_frames(-1000, 48_000, Fraction(24)) == 0
    assert samples_to_frames(-1001, 48_000, Fraction(24)) == -1


def test_policy_accepts_an_explicitly_unbounded_peak() -> None:
    result = evaluate_predeclared_policy(
        [PolicyObservation("primary-01", 0, 300, 0, 1.0, math.inf, 1.0)],
        sample_rate=100,
        fps=Fraction(24),
        duration_seconds=Fraction(3),
    )
    assert result.accepted
    assert result.frame_offset == 0
