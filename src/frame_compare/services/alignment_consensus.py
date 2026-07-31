"""Windowed consensus and gating for computed audio alignment."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from frame_compare.services.alignment_correlation import (
    CorrelationEstimate,
    estimate_alignment_offset,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig

FloatArray = npt.NDArray[np.float64]

_EPSILON = 1e-12


@dataclass(frozen=True)
class AlignmentConsensus:
    """Selected computed candidate, or diagnostics for a rejected estimate."""

    sample_offset: int | None
    score: float
    applied: bool
    diagnostic: str
    valid_windows: int
    consensus_windows: int
    consensus_ratio: float
    ambiguity_ratio: float | None


def _as_signal(signal: npt.ArrayLike, *, name: str) -> FloatArray:
    array = np.asarray(signal, dtype=np.float64).reshape(-1)
    if array.size == 0:
        raise AudioAlignmentError("empty audio signal prevents consensus alignment")
    if not bool(np.all(np.isfinite(array))):
        raise AudioAlignmentError(f"{name} audio signal contains non-finite samples")
    return array


def _window_spans(signal_size: int, *, config: AlignmentConfig) -> list[tuple[int, int]]:
    window_size = int(round(config.window_length_seconds * config.sample_rate))
    if window_size <= 0 or window_size >= signal_size:
        return [(0, signal_size)]

    stride = int(round(config.window_stride_seconds * config.sample_rate))
    if stride <= 0:
        stride = window_size

    spans: list[tuple[int, int]] = []
    start = 0
    while start + window_size <= signal_size:
        spans.append((start, start + window_size))
        start += stride
    if spans and spans[-1][1] < signal_size:
        spans.append((signal_size - window_size, signal_size))
    return list(dict.fromkeys(spans))


def _rms(signal: FloatArray) -> float:
    return float(np.sqrt(np.mean(signal * signal)))


def _window_estimate(
    reference: FloatArray,
    comparison: FloatArray,
    *,
    start: int,
    end: int,
    config: AlignmentConfig,
) -> CorrelationEstimate | None:
    reference_window = reference[start:end]
    comparison_window = comparison[start:end]
    if reference_window.size < 2 or comparison_window.size < 2:
        return None
    if _rms(reference_window) <= _EPSILON or _rms(comparison_window) <= _EPSILON:
        return None
    try:
        return estimate_alignment_offset(reference_window, comparison_window, config=config)
    except AudioAlignmentError:
        return None


def _reject(
    diagnostic: str,
    *,
    score: float,
    valid_windows: int,
    consensus_windows: int,
    consensus_ratio: float,
    ambiguity_ratio: float | None,
) -> AlignmentConsensus:
    return AlignmentConsensus(
        sample_offset=None,
        score=score,
        applied=False,
        diagnostic=diagnostic,
        valid_windows=valid_windows,
        consensus_windows=consensus_windows,
        consensus_ratio=consensus_ratio,
        ambiguity_ratio=ambiguity_ratio,
    )


def estimate_consensus_offset(
    reference: npt.ArrayLike,
    comparison: npt.ArrayLike,
    *,
    config: AlignmentConfig,
) -> AlignmentConsensus:
    """Estimate and gate a single computed offset from per-window candidates."""
    reference_signal = _as_signal(reference, name="reference")
    comparison_signal = _as_signal(comparison, name="comparison")
    signal_size = min(reference_signal.size, comparison_signal.size)
    spans = _window_spans(signal_size, config=config)

    candidates: list[CorrelationEstimate] = []
    for start, end in spans:
        estimate = _window_estimate(
            reference_signal,
            comparison_signal,
            start=start,
            end=end,
            config=config,
        )
        if estimate is not None:
            candidates.append(estimate)

    if len(candidates) < config.minimum_valid_windows:
        return _reject(
            "insufficient_valid_windows",
            score=0.0,
            valid_windows=len(candidates),
            consensus_windows=0,
            consensus_ratio=0.0,
            ambiguity_ratio=None,
        )

    offsets = [candidate.sample_offset for candidate in candidates]
    counts = Counter(offsets)
    winner_offset, winner_count = counts.most_common(1)[0]
    consensus_ratio = winner_count / len(candidates)
    winning_scores = [
        candidate.score for candidate in candidates if candidate.sample_offset == winner_offset
    ]
    score = float(max(winning_scores))
    winning_peak_ratios = [
        candidate.peak_ratio for candidate in candidates if candidate.sample_offset == winner_offset
    ]
    ambiguity_ratio = min(winning_peak_ratios)

    if score < config.confidence_threshold:
        return _reject(
            "low_confidence",
            score=score,
            valid_windows=len(candidates),
            consensus_windows=winner_count,
            consensus_ratio=consensus_ratio,
            ambiguity_ratio=ambiguity_ratio,
        )

    if consensus_ratio < config.consensus_minimum_ratio:
        return _reject(
            "insufficient_consensus",
            score=score,
            valid_windows=len(candidates),
            consensus_windows=winner_count,
            consensus_ratio=consensus_ratio,
            ambiguity_ratio=ambiguity_ratio,
        )

    if ambiguity_ratio < config.ambiguity_peak_ratio:
        return _reject(
            "ambiguous_correlation_peak",
            score=score,
            valid_windows=len(candidates),
            consensus_windows=winner_count,
            consensus_ratio=consensus_ratio,
            ambiguity_ratio=ambiguity_ratio,
        )

    return AlignmentConsensus(
        sample_offset=winner_offset,
        score=score,
        applied=True,
        diagnostic="accepted",
        valid_windows=len(candidates),
        consensus_windows=winner_count,
        consensus_ratio=consensus_ratio,
        ambiguity_ratio=ambiguity_ratio,
    )
