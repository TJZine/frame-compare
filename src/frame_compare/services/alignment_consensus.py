"""Windowed consensus and gating for computed audio alignment."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from fractions import Fraction

import numpy as np
import numpy.typing as npt

from frame_compare.services.alignment_audio import AudioAnalysisPlan, AudioWindow, AudioWindowSpec
from frame_compare.services.alignment_correlation import (
    ALIGNMENT_ANALYSIS_SAMPLE_LIMIT,
    CorrelationEstimate,
    estimate_alignment_offset,
    refine_aligned_score,
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
    array = np.asarray(signal).reshape(-1)[:ALIGNMENT_ANALYSIS_SAMPLE_LIMIT]
    array = np.asarray(array, dtype=np.float64)
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


def rejected_analysis(
    diagnostic: str,
    *,
    config: AlignmentConfig,
    fps: Fraction,
) -> AlignmentConsensus:
    """Return a typed non-applied result before any windows can be analyzed."""
    stability = classify_alignment_stability((), sample_rate=config.sample_rate, fps=fps)
    return _reject(
        diagnostic,
        score=0.0,
        valid_windows=0,
        consensus_windows=0,
        consensus_ratio=0.0,
        ambiguity_ratio=None,
        window_evidence=(),
        stability=stability,
    )


def analysis_budget_exceeded(*, config: AlignmentConfig, fps: Fraction) -> AlignmentConsensus:
    """Return the typed non-applied outcome for a request outside fixed work limits."""
    return rejected_analysis("analysis_budget_exceeded", config=config, fps=fps)


def _finish_consensus(
    candidates: list[CorrelationEstimate],
    evidence: list[AlignmentWindowEvidence],
    *,
    config: AlignmentConfig,
    fps: Fraction,
) -> AlignmentConsensus:
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

    counts = Counter(candidate.sample_offset for candidate in candidates)
    winner_count = max(counts.values())
    tied_offsets = [offset for offset, count in counts.items() if count == winner_count]
    winner_offset = max(
        tied_offsets,
        key=lambda offset: max(
            candidate.score for candidate in candidates if candidate.sample_offset == offset
        ),
    )
    consensus_ratio = winner_count / len(candidates)
    winning_scores = [
        candidate.score for candidate in candidates if candidate.sample_offset == winner_offset
    ]
    score = float(np.median(winning_scores))
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


def estimate_streaming_consensus_offset(
    windows: Iterable[AudioWindow],
    *,
    plan: AudioAnalysisPlan,
    config: AlignmentConfig,
    fps: Fraction,
) -> AlignmentConsensus:
    """Correlate every selected window sequentially and select the majority offset."""
    local_config = replace(config, sample_rate=plan.sample_rate)
    margin = math.ceil(config.max_offset_seconds * plan.sample_rate)
    candidates: list[CorrelationEstimate] = []
    evidence: list[AlignmentWindowEvidence] = []
    for window in windows:
        origin_delta = window.reference_start_sample - window.comparison_start_sample
        local_bounds = (-margin - origin_delta, margin - origin_delta)
        try:
            local_estimate = estimate_alignment_offset(
                window.reference,
                window.comparison,
                config=local_config,
                alignment_offset_bounds_samples=local_bounds,
            )
        except AudioAlignmentError:
            continue
        local_offset = (
            local_estimate.subsample_offset
            if local_estimate.subsample_offset is not None
            else local_estimate.sample_offset
        )
        global_analysis_offset = local_offset + origin_delta
        requested_offset = round(
            global_analysis_offset * plan.requested_sample_rate / plan.sample_rate
        )
        estimate = CorrelationEstimate(
            sample_offset=requested_offset,
            score=local_estimate.score,
            peak_ratio=local_estimate.peak_ratio,
        )
        candidates.append(estimate)
        valid = _valid_evidence(
            estimate,
            start=round(
                window.reference_start_sample * plan.requested_sample_rate / plan.sample_rate
            ),
            end=round(
                (window.reference_start_sample + window.reference.size)
                * plan.requested_sample_rate
                / plan.sample_rate
            ),
            config=config,
        )
        if valid is not None:
            evidence.append(valid)
    return _finish_consensus(candidates, evidence, config=config, fps=fps)


def estimate_planned_consensus_offset(
    *,
    plan: AudioAnalysisPlan,
    config: AlignmentConfig,
    fps: Fraction,
    analysis_window_loader: Callable[[AudioWindowSpec], AudioWindow],
    scoring_window_loader: Callable[[AudioWindowSpec, int], AudioWindow],
) -> AlignmentConsensus:
    """Analyze planned windows sequentially and score fallback lags at the requested rate."""
    local_config = replace(config, sample_rate=plan.sample_rate)
    margin = math.ceil(config.max_offset_seconds * plan.sample_rate)
    requested_limit = int(config.max_offset_seconds * plan.requested_sample_rate)
    candidates: list[CorrelationEstimate] = []
    evidence: list[AlignmentWindowEvidence] = []
    for spec in plan.windows:
        try:
            window = analysis_window_loader(spec)
            origin_delta = window.reference_start_sample - window.comparison_start_sample
            local_estimate = estimate_alignment_offset(
                window.reference,
                window.comparison,
                config=local_config,
                alignment_offset_bounds_samples=(
                    -margin - origin_delta,
                    margin - origin_delta,
                ),
            )
            local_offset = (
                local_estimate.subsample_offset
                if local_estimate.subsample_offset is not None
                else local_estimate.sample_offset
            )
            global_analysis_offset = local_offset + origin_delta
            del window

            score = local_estimate.score
            if plan.sample_rate != plan.requested_sample_rate:
                scoring_window = scoring_window_loader(spec, round(global_analysis_offset))
                scoring_origin_delta = (
                    scoring_window.reference_start_sample - scoring_window.comparison_start_sample
                )
                correction_radius = math.ceil(plan.requested_sample_rate / plan.sample_rate)
                correction, score = refine_aligned_score(
                    scoring_window.reference,
                    scoring_window.comparison,
                    preprocessing_mode=config.preprocessing_mode,
                    correction_bounds_samples=(
                        max(-correction_radius, -requested_limit - scoring_origin_delta),
                        min(correction_radius, requested_limit - scoring_origin_delta),
                    ),
                )
                requested_offset = scoring_origin_delta + correction
                del scoring_window
            else:
                requested_offset = round(global_analysis_offset)
        except AudioAlignmentError:
            continue

        if abs(requested_offset) > requested_limit:
            continue

        estimate = CorrelationEstimate(
            sample_offset=requested_offset,
            score=score,
            peak_ratio=local_estimate.peak_ratio,
        )
        candidates.append(estimate)
        valid = _valid_evidence(
            estimate,
            start=round(
                spec.reference_start_sample * plan.requested_sample_rate / plan.sample_rate
            ),
            end=round(
                (spec.reference_start_sample + spec.reference_sample_count)
                * plan.requested_sample_rate
                / plan.sample_rate
            ),
            config=config,
        )
        if valid is not None:
            evidence.append(valid)
    return _finish_consensus(candidates, evidence, config=config, fps=fps)


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

    return _finish_consensus(candidates, evidence, config=config, fps=fps)
