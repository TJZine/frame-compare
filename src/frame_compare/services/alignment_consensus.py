"""Windowed consensus and gating for computed audio alignment."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

import numpy as np
import numpy.typing as npt

from frame_compare.services.alignment_correlation import (
    CorrelationEstimate,
    estimate_alignment_offset,
)
from frame_compare.services.alignment_stability import classify_alignment_stability
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentStabilitySummary,
    AlignmentWindowEvidence,
)

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
    window_evidence: tuple[AlignmentWindowEvidence, ...] = ()
    stability: AlignmentStabilitySummary | None = None


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


def _diagnostic_spans(
    signal_size: int,
    *,
    count: int,
    config: AlignmentConfig,
) -> list[tuple[int, int]]:
    preferred_seconds = min(90.0, max(30.0, 2 * config.max_offset_seconds + 15.0))
    window_size = min(signal_size, int(round(preferred_seconds * config.sample_rate)))
    if window_size <= 0 or window_size >= signal_size:
        return [(0, signal_size)]
    available_start = signal_size - window_size
    divisor = max(1, count - 1)
    indexes = list(range(count))
    if count == 5:
        indexes = [0, 4, 2, 1, 3]
    return list(
        dict.fromkeys(
            (
                round(index * available_start / divisor),
                round(index * available_start / divisor) + window_size,
            )
            for index in indexes
        )
    )


def _valid_evidence(
    estimate: CorrelationEstimate | None,
    *,
    start: int,
    end: int,
    config: AlignmentConfig,
) -> AlignmentWindowEvidence | None:
    if (
        estimate is None
        or estimate.score < config.confidence_threshold
        or estimate.peak_ratio < config.ambiguity_peak_ratio
    ):
        return None
    return AlignmentWindowEvidence(
        start_sample=start,
        end_sample=end,
        sample_offset=estimate.sample_offset,
        score=estimate.score,
        peak_ratio=estimate.peak_ratio,
    )


def _reject(
    diagnostic: str,
    *,
    score: float,
    valid_windows: int,
    consensus_windows: int,
    consensus_ratio: float,
    ambiguity_ratio: float | None,
    window_evidence: tuple[AlignmentWindowEvidence, ...],
    stability: AlignmentStabilitySummary,
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
        window_evidence=window_evidence,
        stability=stability,
    )


def estimate_consensus_offset(
    reference: npt.ArrayLike,
    comparison: npt.ArrayLike,
    *,
    config: AlignmentConfig,
    fps: Fraction,
) -> AlignmentConsensus:
    """Estimate and gate a single computed offset from per-window candidates."""
    reference_signal = _as_signal(reference, name="reference")
    comparison_signal = _as_signal(comparison, name="comparison")
    signal_size = min(reference_signal.size, comparison_signal.size)
    spans = _window_spans(signal_size, config=config)

    candidates: list[CorrelationEstimate] = []
    evidence: list[AlignmentWindowEvidence] = []
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
        valid = _valid_evidence(estimate, start=start, end=end, config=config)
        if valid is not None:
            evidence.append(valid)

    if len(evidence) < 3:
        existing_spans = set(spans)
        for start, end in _diagnostic_spans(
            signal_size,
            count=5,
            config=config,
        ):
            if len(evidence) >= 3:
                break
            if (start, end) in existing_spans:
                continue
            estimate = _window_estimate(
                reference_signal,
                comparison_signal,
                start=start,
                end=end,
                config=config,
            )
            valid = _valid_evidence(estimate, start=start, end=end, config=config)
            if valid is not None:
                evidence.append(valid)

    window_evidence = tuple(sorted(evidence, key=lambda item: item.start_sample))
    stability = classify_alignment_stability(
        window_evidence,
        sample_rate=config.sample_rate,
        fps=fps,
    )

    if len(candidates) < config.minimum_valid_windows:
        return _reject(
            "insufficient_valid_windows",
            score=0.0,
            valid_windows=len(candidates),
            consensus_windows=0,
            consensus_ratio=0.0,
            ambiguity_ratio=None,
            window_evidence=window_evidence,
            stability=stability,
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
            window_evidence=window_evidence,
            stability=stability,
        )

    if consensus_ratio < config.consensus_minimum_ratio:
        return _reject(
            "insufficient_consensus",
            score=score,
            valid_windows=len(candidates),
            consensus_windows=winner_count,
            consensus_ratio=consensus_ratio,
            ambiguity_ratio=ambiguity_ratio,
            window_evidence=window_evidence,
            stability=stability,
        )

    if ambiguity_ratio < config.ambiguity_peak_ratio:
        return _reject(
            "ambiguous_correlation_peak",
            score=score,
            valid_windows=len(candidates),
            consensus_windows=winner_count,
            consensus_ratio=consensus_ratio,
            ambiguity_ratio=ambiguity_ratio,
            window_evidence=window_evidence,
            stability=stability,
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
        window_evidence=window_evidence,
        stability=stability,
    )
