"""Audio alignment correlation estimators."""

from __future__ import annotations

import math
import statistics
import threading
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

from frame_compare.services.errors import AudioAlignmentError, raise_if_alignment_cancelled
from frame_compare.services.types import AlignmentConfig, AlignmentCorrelationMode

FloatArray = npt.NDArray[np.float64]

# Legacy array callers remain bounded. Production alignment uses a stricter
# per-window FFT and total-work budget in alignment_audio.
ALIGNMENT_ANALYSIS_SAMPLE_LIMIT = 1 << 21
ALIGNMENT_ESTIMATOR_POLICY = (
    "continuous-origin-qualified-channel-corroboration-2097152-v2-temporal-invariants-20260922"
)

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
        raise AudioAlignmentError(
            "empty audio signal prevents correlation",
            category="insufficient_signal",
            stage="correlation",
        )
    if not bool(np.all(np.isfinite(array))):
        raise AudioAlignmentError(
            f"{name} audio signal contains non-finite samples",
            category="non_finite_signal",
            stage="correlation",
            role="reference" if name == "reference" else "comparison",
        )
    return array


def _preprocess_signal(signal: FloatArray, *, mode: str) -> FloatArray:
    if mode == "none":
        return signal
    if mode != "standard":
        raise AudioAlignmentError(f"unsupported alignment preprocessing mode: {mode}")

    centered = signal - float(np.mean(signal))
    rms = float(np.sqrt(np.mean(centered * centered)))
    if rms <= _EPSILON:
        raise AudioAlignmentError(
            "zero-norm audio signal prevents correlation",
            category="insufficient_signal",
            stage="correlation",
        )
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
    cancellation: threading.Event | None = None,
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
        raise AudioAlignmentError(
            "zero-norm audio signal prevents correlation",
            category="insufficient_signal",
            stage="correlation",
        )

    raise_if_alignment_cancelled(cancellation)
    correlation = _linear_correlation(
        reference_signal,
        comparison_signal,
        mode=correlation_mode,
    )
    # NumPy's native FFT is not interruptible; this is its bounded safe boundary.
    raise_if_alignment_cancelled(cancellation)
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
        raise AudioAlignmentError(
            "insufficient aligned overlap prevents correlation",
            category="insufficient_overlap",
            stage="correlation",
        )
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


def refine_aligned_score(
    reference: npt.ArrayLike,
    comparison: npt.ArrayLike,
    *,
    preprocessing_mode: str,
    correction_bounds_samples: tuple[int, int],
    cancellation: threading.Event | None = None,
) -> tuple[int, float]:
    """Refine a coarse-aligned pair over a small bounded integer neighborhood."""
    reference_signal = _preprocess_signal(
        _as_finite_signal(reference, name="reference"),
        mode=preprocessing_mode,
    )
    comparison_signal = _preprocess_signal(
        _as_finite_signal(comparison, name="comparison"),
        mode=preprocessing_mode,
    )
    lower_correction, upper_correction = correction_bounds_samples
    if lower_correction > upper_correction:
        raise AudioAlignmentError("requested-rate correction bounds are inverted")
    scored: list[tuple[int, float]] = []
    for correction in range(lower_correction, upper_correction + 1):
        raise_if_alignment_cancelled(cancellation)
        score = _normalized_overlap_score(
            reference_signal,
            comparison_signal,
            offset=float(-correction),
        )
        if score is not None:
            scored.append((correction, score))
    if not scored:
        raise AudioAlignmentError(
            "insufficient aligned overlap prevents correlation",
            category="insufficient_overlap",
            stage="scoring",
        )
    return max(scored, key=lambda item: item[1])


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
    cancellation: threading.Event | None,
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
        raise_if_alignment_cancelled(cancellation)
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
    cancellation: threading.Event | None = None,
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
        cancellation=cancellation,
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
        cancellation=cancellation,
    )
    return CorrelationEstimate(
        -refined.sample_offset,
        refined.score,
        refined.peak_ratio,
        -refined.subsample_offset if refined.subsample_offset is not None else None,
    )


# ─── Whole-track chunked GCC-PHAT estimator (pure numeric) ────────────────────
#
# Estimates one constant frame offset by tiling 30 s chunks over the whole track,
# correlating each against the comparison with GCC-PHAT, judging chunks by peak
# prominence (PSR), and requiring chunks to agree on the lag. Operates on
# in-memory arrays at ANALYSIS_SAMPLE_RATE; streaming decode feeds it later.

ANALYSIS_SAMPLE_RATE = 8000

_MAX_CHUNK_SECONDS = 30
_MIN_CHUNK_SECONDS = 5
_MAX_CHUNK_FFT_POINTS = 2**22
_ACTIVITY_FLOOR_DBFS = -50
_PSR_EXCLUSION_SAMPLES = 160
_CREDIBLE_PSR = 25.0
_AGREEMENT_SAMPLES = 16
_REQUIRED_AGREEING = 3

_ACTIVITY_FLOOR = 10.0 ** (_ACTIVITY_FLOOR_DBFS / 20)

ChunkedAudioOutcome = Literal["agreed", "no_single_offset", "search_edge", "no_usable_audio"]


@dataclass(frozen=True)
class ChunkPlan:
    """Chunking of the reference stream plus the symmetric lag search radius."""

    chunk_samples: int
    lag_samples: int
    chunks: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ChunkObservation:
    """Per-chunk result. ``agrees`` is resolved by ``finish()`` against the global lag."""

    index: int
    reference_start: int
    reference_count: int
    active: bool
    lag: int | None
    psr: float | None
    credible: bool
    agrees: bool


@dataclass(frozen=True)
class ChunkRun:
    """Contiguous credible chunks sharing one lag (edit/drift diagnosis)."""

    first_index: int
    last_index: int
    lag: int
    chunk_count: int


@dataclass(frozen=True)
class ChunkedAudioEstimate:
    """Decision over all planned chunks."""

    outcome: ChunkedAudioOutcome
    global_lag: int | None
    observations: tuple[ChunkObservation, ...]
    runs: tuple[ChunkRun, ...]
    active_count: int
    credible_count: int
    agreeing_count: int


def _next_pow2(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def plan_audio_chunks(
    reference_samples: int,
    comparison_samples: int,
    max_offset_seconds: float,
) -> ChunkPlan:
    """Tile the reference stream into chunks searched over ``±M`` lag samples."""
    if reference_samples < 1 or comparison_samples < 1:
        raise AudioAlignmentError(
            "need at least one sample per stream to plan audio chunks",
            category="insufficient_signal",
            stage="planning",
        )
    if not math.isfinite(max_offset_seconds) or max_offset_seconds < 1:
        raise ValueError(f"max_offset_seconds must be finite and >= 1, got {max_offset_seconds!r}")

    min_chunk = _MIN_CHUNK_SECONDS * ANALYSIS_SAMPLE_RATE
    max_chunk = _MAX_CHUNK_SECONDS * ANALYSIS_SAMPLE_RATE
    shorter = min(reference_samples, comparison_samples)
    if shorter < min_chunk:
        chunk_samples = shorter
        chunks = ((0, shorter),)
    else:
        chunk_samples = min(max(shorter // 3, min_chunk), max_chunk)
        kept: list[tuple[int, int]] = []
        start = 0
        while start < reference_samples:
            count = min(chunk_samples, reference_samples - start)
            if count >= -(-chunk_samples // 2):
                kept.append((start, count))
            start += chunk_samples
        chunks = tuple(kept)

    lag_samples = int(math.ceil(max_offset_seconds * ANALYSIS_SAMPLE_RATE))
    largest_fft = max(_next_pow2(count + 2 * lag_samples) for _, count in chunks)
    if largest_fft > _MAX_CHUNK_FFT_POINTS:
        raise AudioAlignmentError(
            f"chunk FFT of {largest_fft} points exceeds the {_MAX_CHUNK_FFT_POINTS} budget",
            category="analysis_budget_exceeded",
            stage="planning",
        )
    return ChunkPlan(chunk_samples=chunk_samples, lag_samples=lag_samples, chunks=chunks)


def comparison_window(
    comparison: npt.ArrayLike,
    reference_start: int,
    reference_count: int,
    lag_samples: int,
) -> FloatArray:
    """Build the comparison window for one chunk, zero-padding past stream edges.

    The window covers comparison samples
    ``[reference_start - lag_samples, reference_start + reference_count + lag_samples)``.
    """
    if reference_start < 0 or reference_count < 1 or lag_samples < 0:
        raise ValueError(
            "comparison window needs reference_start >= 0, reference_count >= 1, lag_samples >= 0"
        )
    signal = np.asarray(comparison, dtype=np.float64).reshape(-1)
    window = np.zeros(reference_count + 2 * lag_samples, dtype=np.float64)
    window_start = reference_start - lag_samples
    copy_start = max(window_start, 0)
    copy_end = min(window_start + window.size, signal.size)
    if copy_end > copy_start:
        window[copy_start - window_start : copy_end - window_start] = signal[copy_start:copy_end]
    return window


def _chunk_psr(correlation: FloatArray, peak: int) -> float:
    side = np.concatenate(
        (
            correlation[: max(0, peak - _PSR_EXCLUSION_SAMPLES)],
            correlation[min(correlation.size, peak + _PSR_EXCLUSION_SAMPLES + 1) :],
        )
    )
    # An empty side has no median; treat it as 0 so the peak test below still applies.
    median = float(np.median(side)) if side.size else 0.0
    mad = float(np.median(np.abs(side - median))) if side.size else 0.0
    if mad == 0:
        return float("inf") if correlation[peak] > median else 0.0
    return float((correlation[peak] - median) / (1.4826 * mad))


class ChunkedCorrelation:
    """Streaming-shaped accumulator: one ``add`` per planned chunk, then ``finish``.

    Keeps only the running global correlation sum plus scalar observations, so
    memory stays bounded independent of track length.
    """

    def __init__(self, plan: ChunkPlan) -> None:
        self._plan = plan
        self._next_index = 0
        self._global = np.zeros(2 * plan.lag_samples + 1, dtype=np.float64)
        self._observations: list[ChunkObservation] = []

    def add(
        self,
        index: int,
        reference: npt.ArrayLike,
        comparison_window: npt.ArrayLike,
    ) -> ChunkObservation:
        """Correlate one chunk. Chunks must be added in plan order, each exactly once."""
        if index != self._next_index or index >= len(self._plan.chunks):
            raise ValueError(
                f"audio chunks must be added in plan order, expected {self._next_index}, got {index}"
            )
        reference_start, reference_count = self._plan.chunks[index]
        lag_samples = self._plan.lag_samples
        reference_signal = np.asarray(reference, dtype=np.float64).reshape(-1)
        window_signal = np.asarray(comparison_window, dtype=np.float64).reshape(-1)
        if reference_signal.size != reference_count:
            raise AudioAlignmentError(
                f"chunk {index} needs {reference_count} reference samples, "
                f"got {reference_signal.size}",
                category="correlation_failed",
                stage="correlation",
            )
        if window_signal.size != reference_count + 2 * lag_samples:
            raise AudioAlignmentError(
                f"chunk {index} needs {reference_count + 2 * lag_samples} comparison "
                f"samples, got {window_signal.size}",
                category="correlation_failed",
                stage="correlation",
            )
        if not bool(np.all(np.isfinite(reference_signal))):
            raise AudioAlignmentError(
                f"chunk {index} reference signal contains non-finite samples",
                category="non_finite_signal",
                stage="correlation",
                role="reference",
            )
        if not bool(np.all(np.isfinite(window_signal))):
            raise AudioAlignmentError(
                f"chunk {index} comparison signal contains non-finite samples",
                category="non_finite_signal",
                stage="correlation",
                role="comparison",
            )

        observation = ChunkObservation(
            index=index,
            reference_start=reference_start,
            reference_count=reference_count,
            active=False,
            lag=None,
            psr=None,
            credible=False,
            agrees=False,
        )
        reference_rms = float(np.sqrt(np.mean(reference_signal * reference_signal)))
        window_rms = float(np.sqrt(np.mean(window_signal * window_signal)))
        if reference_rms <= _ACTIVITY_FLOOR or window_rms <= _ACTIVITY_FLOOR:
            self._observations.append(observation)
            self._next_index += 1
            return observation

        # N >= n + 2M, so no circular wrap affects the searched lags;
        # index m of xc corresponds to lag = M - m.
        size = _next_pow2(reference_count + 2 * lag_samples)
        cross_power = np.conj(np.fft.rfft(reference_signal, size)) * np.fft.rfft(
            window_signal, size
        )
        cross_power /= np.maximum(np.abs(cross_power), 1e-12)
        chunk_correlation = np.fft.irfft(cross_power, size)[: 2 * lag_samples + 1]
        peak = int(np.argmax(chunk_correlation))
        lag = lag_samples - peak
        psr = _chunk_psr(chunk_correlation, peak)
        self._global += chunk_correlation
        observation = ChunkObservation(
            index=index,
            reference_start=reference_start,
            reference_count=reference_count,
            active=True,
            lag=lag,
            psr=psr,
            credible=psr >= _CREDIBLE_PSR,
            agrees=False,
        )
        self._observations.append(observation)
        self._next_index += 1
        return observation

    def finish(self) -> ChunkedAudioEstimate:
        """Decide one global lag from all planned chunks."""
        if self._next_index != len(self._plan.chunks):
            raise ValueError(
                f"need all {len(self._plan.chunks)} chunks before finish, got {self._next_index}"
            )
        lag_samples = self._plan.lag_samples
        active = [item for item in self._observations if item.active]
        if not active:
            return ChunkedAudioEstimate(
                outcome="no_usable_audio",
                global_lag=None,
                observations=tuple(self._observations),
                runs=(),
                active_count=0,
                credible_count=0,
                agreeing_count=0,
            )
        global_lag = lag_samples - int(np.argmax(self._global))
        credible = [item for item in active if item.credible]
        agreeing = [
            item
            for item in credible
            if item.lag is not None and abs(item.lag - global_lag) <= _AGREEMENT_SAMPLES
        ]
        agreeing_count = len(agreeing)
        credible_count = len(credible)
        required = max(1, min(_REQUIRED_AGREEING, len(self._plan.chunks)))
        # agreeing / credible >= 0.8, compared as integers.
        passed = agreeing_count >= required and agreeing_count * 5 >= credible_count * 4
        if not passed:
            outcome: ChunkedAudioOutcome = "no_single_offset"
        elif abs(global_lag) >= lag_samples - _AGREEMENT_SAMPLES:
            outcome = "search_edge"
        else:
            outcome = "agreed"
        agreeing_ids = {item.index for item in agreeing}
        observations = tuple(
            ChunkObservation(
                index=item.index,
                reference_start=item.reference_start,
                reference_count=item.reference_count,
                active=item.active,
                lag=item.lag,
                psr=item.psr,
                credible=item.credible,
                agrees=item.index in agreeing_ids,
            )
            for item in self._observations
        )
        runs = _credible_runs(credible)
        return ChunkedAudioEstimate(
            outcome=outcome,
            global_lag=global_lag,
            observations=observations,
            runs=runs,
            active_count=len(active),
            credible_count=credible_count,
            agreeing_count=agreeing_count,
        )


def _credible_runs(credible: list[ChunkObservation]) -> tuple[ChunkRun, ...]:
    """Group credible chunks into runs sharing one lag (diagnostic, index order)."""
    runs: list[ChunkRun] = []
    member_lags: list[int] = []
    member_indices: list[int] = []

    def close_run() -> None:
        if member_indices:
            runs.append(
                ChunkRun(
                    first_index=member_indices[0],
                    last_index=member_indices[-1],
                    lag=int(statistics.median_low(member_lags)),
                    chunk_count=len(member_indices),
                )
            )

    for item in credible:
        if item.lag is None:
            raise ValueError(f"credible chunk {item.index} is missing its lag")
        if member_indices and abs(item.lag - member_lags[0]) > _AGREEMENT_SAMPLES:
            close_run()
            member_lags = []
            member_indices = []
        member_lags.append(item.lag)
        member_indices.append(item.index)
    close_run()
    return tuple(runs)
