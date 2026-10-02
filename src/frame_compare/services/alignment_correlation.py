"""Whole-track chunked GCC-PHAT audio alignment estimator (pure numeric).

Estimates one constant frame offset by tiling chunks over the whole track,
correlating each against the comparison with GCC-PHAT, judging chunks by peak
prominence (PSR), and requiring chunks to agree on the lag. Operates on
in-memory arrays at the shared utils analysis rate; streaming decode feeds it
later.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from frame_compare.services.errors import AudioAlignmentError
from frame_compare.utils.alignment_evidence import (
    AUDIO_ANALYSIS_SAMPLE_RATE,
    MAX_AUDIO_CHUNKS,
    AudioOutcomeStatus,
)

FloatArray = npt.NDArray[np.float64]

_MAX_CHUNK_SECONDS = 30
_MIN_CHUNK_SECONDS = 5
_MAX_CHUNK_FFT_POINTS = 2**22
_ACTIVITY_FLOOR_DBFS = -50
_PSR_EXCLUSION_SAMPLES = 160
_CREDIBLE_PSR = 25.0
_AGREEMENT_SAMPLES = 16
_REQUIRED_AGREEING = 3

_ACTIVITY_FLOOR = 10.0 ** (_ACTIVITY_FLOOR_DBFS / 20)


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
    """Credible chunks sharing one lag, in index order; non-credible gaps are skipped."""

    first_index: int
    last_index: int
    lag: int
    chunk_count: int


@dataclass(frozen=True)
class ChunkedAudioEstimate:
    """Decision over all planned chunks."""

    outcome: AudioOutcomeStatus
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

    min_chunk = _MIN_CHUNK_SECONDS * AUDIO_ANALYSIS_SAMPLE_RATE
    max_chunk = _MAX_CHUNK_SECONDS * AUDIO_ANALYSIS_SAMPLE_RATE
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

    if len(chunks) > MAX_AUDIO_CHUNKS:
        raise AudioAlignmentError(
            f"{len(chunks)} planned chunks exceed the {MAX_AUDIO_CHUNKS} evidence bound",
            category="analysis_budget_exceeded",
            stage="planning",
        )
    lag_samples = int(math.ceil(max_offset_seconds * AUDIO_ANALYSIS_SAMPLE_RATE))
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
            outcome: AudioOutcomeStatus = "no_single_offset"
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
