"""Audio alignment correlation estimators."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentCorrelationMode

FloatArray = npt.NDArray[np.float64]

# Legacy array callers remain bounded. Production alignment uses a stricter
# per-window FFT and total-work budget in alignment_audio.
ALIGNMENT_ANALYSIS_SAMPLE_LIMIT = 1 << 21
ALIGNMENT_ESTIMATOR_POLICY = f"stream-timeline-distributed-{ALIGNMENT_ANALYSIS_SAMPLE_LIMIT}-v4"

_EPSILON = 1e-12
_MIN_OVERLAP_SAMPLES = 3
_MIN_OVERLAP_FRACTION = 0.05
_REFINEMENT_RADIUS_SECONDS = 0.005
_REFINEMENT_MAX_POINTS = 65_536


@dataclass(frozen=True)
class CorrelationEstimate:
    """Correlation estimate in sample units at the coarse extraction sample rate."""

    sample_offset: int
    score: float
    peak_ratio: float
    subsample_offset: float | None = None


def _as_finite_signal(signal: npt.ArrayLike, *, name: str) -> FloatArray:
    array = np.asarray(signal).reshape(-1)[:ALIGNMENT_ANALYSIS_SAMPLE_LIMIT]
    array = np.asarray(array, dtype=np.float64)
    if array.size == 0:
        raise AudioAlignmentError("empty audio signal prevents correlation")
    if not bool(np.all(np.isfinite(array))):
        raise AudioAlignmentError(f"{name} audio signal contains non-finite samples")
    return array


def _preprocess_signal(signal: FloatArray, *, mode: str) -> FloatArray:
    if mode == "none":
        return signal
    if mode != "standard":
        raise AudioAlignmentError(f"unsupported alignment preprocessing mode: {mode}")

    centered = signal - float(np.mean(signal))
    rms = float(np.sqrt(np.mean(centered * centered)))
    if rms <= _EPSILON:
        raise AudioAlignmentError("zero-norm audio signal prevents correlation")
    return centered / rms


def _linear_correlation(
    reference: FloatArray,
    comparison: FloatArray,
    *,
    mode: AlignmentCorrelationMode,
) -> FloatArray:
    correlation_size = reference.size + comparison.size - 1
    fft_size = 1 << (correlation_size - 1).bit_length()

    reference_fft = np.fft.rfft(reference, fft_size)
    comparison_fft = np.fft.rfft(comparison, fft_size)
    cross_power = reference_fft * np.conj(comparison_fft)
    if mode == "gcc_phat":
        magnitude = np.abs(cross_power)
        cross_power = np.divide(
            cross_power,
            magnitude,
            out=np.zeros_like(cross_power),
            where=magnitude > _EPSILON,
        )
    elif mode != "raw_fft":
        raise AudioAlignmentError(f"unsupported alignment correlation mode: {mode}")

    correlation_raw = np.fft.irfft(cross_power, fft_size)
    return np.concatenate(
        (
            correlation_raw[-(comparison.size - 1) :],
            correlation_raw[: reference.size],
        )
    )


def _peak_from_correlation(
    correlation: FloatArray,
    *,
    comparison_size: int,
    max_offset_samples: int | None,
    offset_bounds_samples: tuple[int, int] | None,
) -> tuple[int, float, float]:
    center = comparison_size - 1
    if offset_bounds_samples is not None:
        lower, upper = offset_bounds_samples
        if lower > upper:
            raise AudioAlignmentError("correlation offset bounds are inverted")
        start_idx = max(0, center - upper)
        end_idx = min(correlation.size, center - lower + 1)
        if start_idx >= end_idx:
            raise AudioAlignmentError("offset bounds produced an empty search window")
    elif max_offset_samples is not None:
        bounded = max(0, max_offset_samples)
        start_idx = max(0, center - bounded)
        end_idx = min(correlation.size, center + bounded + 1)
        if start_idx >= end_idx:
            raise AudioAlignmentError("max_offset_seconds produced an empty search window")
    else:
        start_idx = 0
        end_idx = correlation.size

    search = correlation[start_idx:end_idx]
    peak_idx = int(np.argmax(search)) + start_idx
    peak = float(correlation[peak_idx])
    runner_up = _runner_up_peak(
        correlation,
        peak_idx=peak_idx,
        start_idx=start_idx,
        end_idx=end_idx,
    )

    offset = center - peak_idx
    return offset, peak, _peak_ratio(peak, runner_up)


def _runner_up_peak(
    correlation: FloatArray,
    *,
    peak_idx: int,
    start_idx: int,
    end_idx: int,
) -> float | None:
    search_size = end_idx - start_idx
    if search_size <= 1:
        return None

    # Adjacent samples usually belong to the same broad correlation peak. Suppress a
    # small neighborhood and compare against the next distinct candidate peak.
    exclusion_radius = max(1, min(64, search_size // 100))
    candidate = np.array(correlation[start_idx:end_idx], copy=True)
    local_peak_idx = peak_idx - start_idx
    suppress_start = max(0, local_peak_idx - exclusion_radius)
    suppress_end = min(candidate.size, local_peak_idx + exclusion_radius + 1)
    candidate[suppress_start:suppress_end] = -np.inf
    if not bool(np.any(np.isfinite(candidate))):
        return None
    return float(np.max(candidate))


def _peak_ratio(peak: float, runner_up: float | None) -> float:
    if runner_up is None:
        return float("inf")
    if peak <= _EPSILON:
        return 0.0
    if runner_up <= _EPSILON:
        return float("inf")
    return peak / runner_up


def correlate_audio(
    reference: npt.ArrayLike,
    comparison: npt.ArrayLike,
    *,
    max_offset_samples: int | None = None,
    offset_bounds_samples: tuple[int, int] | None = None,
    correlation_mode: AlignmentCorrelationMode = "raw_fft",
    preprocessing_mode: str = "none",
) -> CorrelationEstimate:
    """Estimate sample offset using the requested correlation mode."""
    reference_signal = _preprocess_signal(
        _as_finite_signal(reference, name="reference"),
        mode=preprocessing_mode,
    )
    comparison_signal = _preprocess_signal(
        _as_finite_signal(comparison, name="comparison"),
        mode=preprocessing_mode,
    )

    norm_ref = float(np.linalg.norm(reference_signal))
    norm_comp = float(np.linalg.norm(comparison_signal))
    if norm_ref <= _EPSILON or norm_comp <= _EPSILON:
        raise AudioAlignmentError("zero-norm audio signal prevents correlation")

    correlation = _linear_correlation(
        reference_signal,
        comparison_signal,
        mode=correlation_mode,
    )
    sample_offset, _peak, peak_ratio = _peak_from_correlation(
        correlation,
        comparison_size=comparison_signal.size,
        max_offset_samples=max_offset_samples,
        offset_bounds_samples=offset_bounds_samples,
    )
    score = _normalized_overlap_score(
        reference_signal,
        comparison_signal,
        offset=float(sample_offset),
    )
    if score is None:
        raise AudioAlignmentError("insufficient aligned overlap prevents correlation")
    return CorrelationEstimate(sample_offset=sample_offset, score=score, peak_ratio=peak_ratio)


def _candidate_offsets(
    *,
    coarse_offset: int,
    sample_rate: int,
    refinement_sample_rate: int,
    max_offset_samples: int,
    offset_bounds_samples: tuple[int, int] | None = None,
) -> list[float]:
    radius = min(max_offset_samples, max(1, int(round(sample_rate * _REFINEMENT_RADIUS_SECONDS))))
    ratio = max(1.0, refinement_sample_rate / sample_rate)
    step = 1.0 / ratio
    count_each_side = int(round(radius / step))
    candidates = [
        coarse_offset + (index * step) for index in range(-count_each_side, count_each_side + 1)
    ]
    lower_bound, upper_bound = offset_bounds_samples or (
        -max_offset_samples,
        max_offset_samples,
    )
    return [candidate for candidate in candidates if lower_bound <= candidate <= upper_bound]


def _sample_positions(start: float, stop: float) -> FloatArray:
    sample_count = int(np.floor(stop - start))
    if sample_count <= 1:
        return np.array([], dtype=np.float64)
    if sample_count > _REFINEMENT_MAX_POINTS:
        return np.linspace(start, stop - 1.0, _REFINEMENT_MAX_POINTS, dtype=np.float64)
    return np.arange(start, start + sample_count, dtype=np.float64)


def _normalized_overlap_score(
    reference: FloatArray,
    comparison: FloatArray,
    *,
    offset: float,
) -> float | None:
    start = max(0.0, -offset)
    stop = min(float(reference.size), float(comparison.size) - offset)
    minimum_overlap = max(
        _MIN_OVERLAP_SAMPLES,
        math.ceil(min(reference.size, comparison.size) * _MIN_OVERLAP_FRACTION),
    )
    if math.floor(stop - start) < minimum_overlap:
        return None
    positions = _sample_positions(start, stop)

    reference_values = _interpolate(reference, positions)
    comparison_values = _interpolate(comparison, positions + offset)
    reference_values = reference_values - float(np.mean(reference_values))
    comparison_values = comparison_values - float(np.mean(comparison_values))
    denom = float(np.linalg.norm(reference_values) * np.linalg.norm(comparison_values))
    if denom <= _EPSILON:
        return None
    return float(np.dot(reference_values, comparison_values) / denom)


def normalized_aligned_score(
    reference: npt.ArrayLike,
    comparison: npt.ArrayLike,
    *,
    preprocessing_mode: str,
) -> float:
    """Score an already aligned pair using only its actual shared overlap."""
    reference_signal = _preprocess_signal(
        _as_finite_signal(reference, name="reference"),
        mode=preprocessing_mode,
    )
    comparison_signal = _preprocess_signal(
        _as_finite_signal(comparison, name="comparison"),
        mode=preprocessing_mode,
    )
    score = _normalized_overlap_score(reference_signal, comparison_signal, offset=0.0)
    if score is None:
        raise AudioAlignmentError("insufficient aligned overlap prevents correlation")
    return score


def _interpolate(signal: FloatArray, positions: FloatArray) -> FloatArray:
    lower = np.floor(positions).astype(np.int64)
    upper = np.minimum(lower + 1, signal.size - 1)
    fraction = positions - lower
    return signal[lower] * (1.0 - fraction) + signal[upper] * fraction


def _refine_locally(
    reference: FloatArray,
    comparison: FloatArray,
    *,
    coarse_offset: int,
    coarse_score: float,
    coarse_peak_ratio: float,
    sample_rate: int,
    refinement_sample_rate: int,
    max_offset_samples: int,
    offset_bounds_samples: tuple[int, int] | None,
) -> CorrelationEstimate:
    best_offset = float(coarse_offset)
    best_score = coarse_score
    for candidate in _candidate_offsets(
        coarse_offset=coarse_offset,
        sample_rate=sample_rate,
        refinement_sample_rate=refinement_sample_rate,
        max_offset_samples=max_offset_samples,
        offset_bounds_samples=offset_bounds_samples,
    ):
        score = _normalized_overlap_score(reference, comparison, offset=candidate)
        if score is not None and score > best_score:
            best_offset = candidate
            best_score = score
    return CorrelationEstimate(
        sample_offset=int(round(best_offset)),
        score=best_score,
        peak_ratio=coarse_peak_ratio,
        subsample_offset=best_offset,
    )


def estimate_alignment_offset(
    reference: npt.ArrayLike,
    comparison: npt.ArrayLike,
    *,
    config: AlignmentConfig,
    alignment_offset_bounds_samples: tuple[int, int] | None = None,
) -> CorrelationEstimate:
    """Estimate ``reference - comparison`` alignment from extracted audio."""
    max_offset_samples = int(config.max_offset_seconds * config.sample_rate)
    raw_offset_bounds = (
        (-alignment_offset_bounds_samples[1], -alignment_offset_bounds_samples[0])
        if alignment_offset_bounds_samples is not None
        else None
    )
    estimate = correlate_audio(
        reference,
        comparison,
        max_offset_samples=max_offset_samples,
        offset_bounds_samples=raw_offset_bounds,
        correlation_mode=config.correlation_mode,
        preprocessing_mode=config.preprocessing_mode,
    )
    if config.refinement_mode == "disabled":
        return CorrelationEstimate(-estimate.sample_offset, estimate.score, estimate.peak_ratio)
    if config.refinement_mode != "local":
        raise AudioAlignmentError(
            f"unsupported alignment refinement mode: {config.refinement_mode}"
        )

    reference_signal = _preprocess_signal(
        _as_finite_signal(reference, name="reference"),
        mode=config.preprocessing_mode,
    )
    comparison_signal = _preprocess_signal(
        _as_finite_signal(comparison, name="comparison"),
        mode=config.preprocessing_mode,
    )
    refinement_sample_rate = config.refinement_sample_rate or config.sample_rate
    refined = _refine_locally(
        reference_signal,
        comparison_signal,
        coarse_offset=estimate.sample_offset,
        coarse_score=estimate.score,
        coarse_peak_ratio=estimate.peak_ratio,
        sample_rate=config.sample_rate,
        refinement_sample_rate=refinement_sample_rate,
        max_offset_samples=max_offset_samples,
        offset_bounds_samples=raw_offset_bounds,
    )
    return CorrelationEstimate(
        -refined.sample_offset,
        refined.score,
        refined.peak_ratio,
        -refined.subsample_offset if refined.subsample_offset is not None else None,
    )
