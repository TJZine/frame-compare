"""Shared pure policy for audio/video alignment frame projection and voting."""

from __future__ import annotations

import math
from collections.abc import Sequence
from fractions import Fraction
from statistics import median

from frame_compare.utils.alignment_evidence import AUDIO_ANALYSIS_SAMPLE_RATE

MIN_INFORMATIVE_POSITIONS = 6
INFORMATIVE_MARGIN = 1.1
CONFIRMATION_MARGIN = 1.5
CONFIRMATION_FRACTION = 0.75


def compensated_offset_seconds(
    *,
    global_lag: int | float,
    reference_audio_start: Fraction,
    reference_video_start: Fraction,
    comparison_audio_start: Fraction,
    comparison_video_start: Fraction,
) -> float:
    """Apply container-start compensation to an 8 kHz lag."""
    compensation = (reference_audio_start - reference_video_start) - (
        comparison_audio_start - comparison_video_start
    )
    return global_lag / AUDIO_ANALYSIS_SAMPLE_RATE + float(compensation)


def rounded_frame(offset_seconds: float, fps_reference: Fraction) -> int:
    """Round a compensated time offset to the neighbouring frame."""
    return math.floor(offset_seconds * float(fps_reference) + 0.5)


def compensated_lag_to_frame(
    lag: int | float,
    *,
    compensation_seconds: float,
    fps_reference: Fraction,
) -> int:
    """Project a possibly half-sample lag through compensation and frame rounding."""
    return rounded_frame(
        lag / AUDIO_ANALYSIS_SAMPLE_RATE + compensation_seconds,
        fps_reference,
    )


def sample_to_reference_video_time(
    sample_index: int,
    *,
    audio_start_reference: Fraction,
    video_start_reference: Fraction,
) -> Fraction:
    """Map an 8 kHz reference PCM sample to reference-video time."""
    if sample_index < 0:
        raise ValueError("sample_index must be non-negative")
    return (
        Fraction(sample_index, AUDIO_ANALYSIS_SAMPLE_RATE)
        + audio_start_reference
        - video_start_reference
    )


def sample_to_reference_frame(
    sample_index: int,
    *,
    fps_reference: Fraction,
    audio_start_reference: Fraction,
    video_start_reference: Fraction,
) -> int:
    """Map an 8 kHz reference PCM sample to its raw reference-video frame."""
    return math.floor(
        sample_to_reference_video_time(
            sample_index,
            audio_start_reference=audio_start_reference,
            video_start_reference=video_start_reference,
        )
        * fps_reference
    )


def _margin(scores: Sequence[float], best_index: int) -> float:
    best = scores[best_index]
    runner_up = min(score for index, score in enumerate(scores) if index != best_index)
    if best == 0.0:
        return math.inf if runner_up > 0.0 else 0.0
    return runner_up / best


def position_winner(scores: Sequence[float], offsets: Sequence[int]) -> tuple[int | None, float]:
    """Return the strict local-minimum offset and its informative margin."""
    best_index = min(range(len(scores)), key=scores.__getitem__)
    if best_index == 0 or best_index == len(scores) - 1:
        return None, 0.0
    best = scores[best_index]
    if not best < scores[best_index - 1] or not best < scores[best_index + 1]:
        return None, 0.0
    margin = _margin(scores, best_index)
    if margin == math.inf:
        return offsets[best_index], margin
    if margin < INFORMATIVE_MARGIN:
        return None, 0.0
    return offsets[best_index], margin


def edge_consensus_offset(
    score_rows: Sequence[Sequence[float]], offsets: Sequence[int]
) -> int | None:
    """A neighbouring frame the pictures agree on at a scored edge, for review copy only."""
    votes: list[int] = []
    for scores in score_rows:
        best_index = min(range(len(scores)), key=scores.__getitem__)
        if best_index not in (0, len(scores) - 1):
            continue
        if _margin(scores, best_index) >= CONFIRMATION_MARGIN:
            votes.append(offsets[best_index])
    if len(votes) < MIN_INFORMATIVE_POSITIONS or len(votes) < CONFIRMATION_FRACTION * len(
        score_rows
    ):
        return None
    return votes[0] if all(vote == votes[0] for vote in votes) else None


def confirmed_offset(
    rounded_audio_frame: int,
    winners: Sequence[int | None],
    margins: Sequence[float],
) -> int | None:
    """Apply V5's winner count and winner-only median-margin rule."""
    informative = [
        (winner, margin)
        for winner, margin in zip(winners, margins, strict=True)
        if winner is not None
    ]
    if len(informative) < MIN_INFORMATIVE_POSITIONS:
        return None
    candidates = tuple(range(rounded_audio_frame - 1, rounded_audio_frame + 2))
    counts = {
        candidate: sum(winner == candidate for winner, _ in informative) for candidate in candidates
    }
    best_count = max(counts.values())
    best = [candidate for candidate, count in counts.items() if count == best_count]
    if len(best) != 1 or best_count / len(informative) < CONFIRMATION_FRACTION:
        return None
    winning_margins = [margin for winner, margin in informative if winner == best[0]]
    if median(winning_margins) < CONFIRMATION_MARGIN:
        return None
    return best[0]


__all__ = [
    "CONFIRMATION_MARGIN",
    "compensated_lag_to_frame",
    "compensated_offset_seconds",
    "confirmed_offset",
    "edge_consensus_offset",
    "position_winner",
    "rounded_frame",
    "sample_to_reference_frame",
    "sample_to_reference_video_time",
]
