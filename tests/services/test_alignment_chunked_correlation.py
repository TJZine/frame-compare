"""Tests for the pure-numeric chunked GCC-PHAT audio estimator."""

from __future__ import annotations

import math

import numpy as np
import pytest

from frame_compare.services.alignment_correlation import (
    ANALYSIS_SAMPLE_RATE,
    ChunkedAudioEstimate,
    ChunkedAudioOutcome,
    ChunkedCorrelation,
    _chunk_psr,
    comparison_window,
    plan_audio_chunks,
)
from frame_compare.services.errors import AudioAlignmentError
from tests.services.alignment_synthetic_audio import (
    downmix_program,
    drift_program,
    dub_program,
    insert_program,
    intro_program,
    make_program,
    make_stems,
    mix_stems,
    noisy_program,
    prepend_silence,
    quiet_program,
    remaster_program,
    shift_signal,
)

SEED = 11
POSITIVE_SHIFT = 1668
NEGATIVE_SHIFT = -1001


def run_estimate(
    reference: np.ndarray,
    comparison: np.ndarray,
    max_offset_seconds: float = 30.0,
) -> ChunkedAudioEstimate:
    """Drive the accumulator the way streaming decode will: chunk by chunk."""
    plan = plan_audio_chunks(len(reference), len(comparison), max_offset_seconds)
    accumulator = ChunkedCorrelation(plan)
    for index, (start, count) in enumerate(plan.chunks):
        window = comparison_window(comparison, start, count, plan.lag_samples)
        accumulator.add(index, reference[start : start + count], window)
    return accumulator.finish()


def _variant_base(name: str, duration: float) -> np.ndarray:
    if name == "same":
        return make_program(SEED, duration)
    if name == "remix":
        dialogue, music, effects = make_stems(SEED, duration)
        return mix_stems(dialogue, 0.4 * music, effects)
    if name == "downmix":
        return downmix_program(SEED, duration)
    if name == "remaster":
        return remaster_program(SEED, duration)
    if name == "dub":
        return dub_program(SEED, duration, dialogue_seed=999)
    if name == "noisy":
        return noisy_program(SEED, duration, noise_seed=4242)
    raise AssertionError(f"unknown variant {name}")


def test_lag_sign_convention_pinned() -> None:
    """lag = i_ref - i_cmp: content later in the comparison gives a negative lag."""
    reference = make_program(SEED, 120.0)
    comparison = shift_signal(reference, POSITIVE_SHIFT)
    estimate = run_estimate(reference, comparison)
    assert estimate.global_lag == -POSITIVE_SHIFT
    assert estimate.outcome == "agreed"

    leading = shift_signal(reference, NEGATIVE_SHIFT)
    estimate = run_estimate(reference, leading)
    assert estimate.global_lag == -NEGATIVE_SHIFT
    assert estimate.outcome == "agreed"


@pytest.mark.parametrize("variant", ["same", "remix", "downmix", "remaster", "dub", "noisy"])
@pytest.mark.parametrize("shift", [POSITIVE_SHIFT, NEGATIVE_SHIFT])
def test_matrix_positives_agree(variant: str, shift: int) -> None:
    """Mix/master/downmix/dub/noise changes never break timing agreement."""
    reference = make_program(SEED, 120.0)
    comparison = shift_signal(_variant_base(variant, 120.0), shift)
    estimate = run_estimate(reference, comparison)
    assert estimate.outcome == "agreed"
    assert estimate.global_lag is not None
    assert abs(estimate.global_lag + shift) <= 1
    if variant in ("same", "remix", "downmix", "dub"):
        assert estimate.global_lag == -shift
    active = [item for item in estimate.observations if item.active]
    assert active
    assert all(item.credible for item in active)
    assert estimate.agreeing_count == estimate.credible_count == len(active)


def test_matrix_long_intro_agrees() -> None:
    """A 20 s foreign intro shifts every chunk by exactly the intro length."""
    reference = make_program(SEED, 150.0)
    comparison = intro_program(SEED, 150.0, intro_seed=777)
    estimate = run_estimate(reference, comparison)
    assert estimate.outcome == "agreed"
    assert estimate.global_lag == -20 * ANALYSIS_SAMPLE_RATE
    active = [item for item in estimate.observations if item.active]
    assert active
    assert all(item.credible for item in active)
    assert estimate.agreeing_count == estimate.credible_count == len(active)


def test_matrix_insert_gives_two_runs() -> None:
    """A 4 s insert at the 60 s chunk boundary splits chunks into two runs."""
    reference = make_program(SEED, 120.0)
    inserted = insert_program(SEED, 120.0, foreign_seed=555)
    comparison = prepend_silence(inserted, POSITIVE_SHIFT)
    estimate = run_estimate(reference, comparison)
    assert estimate.outcome == "no_single_offset"
    assert estimate.global_lag is not None
    assert len(estimate.runs) == 2
    assert estimate.runs[0].lag == -POSITIVE_SHIFT
    assert (estimate.runs[0].first_index, estimate.runs[0].last_index) == (0, 1)
    assert estimate.runs[0].chunk_count == 2
    assert estimate.runs[1].lag == -(POSITIVE_SHIFT + 4 * ANALYSIS_SAMPLE_RATE)
    assert (estimate.runs[1].first_index, estimate.runs[1].last_index) == (2, 3)
    assert estimate.runs[1].chunk_count == 2
    assert estimate.global_lag in (estimate.runs[0].lag, estimate.runs[1].lag)


@pytest.mark.parametrize("comparison_kind", ["drift", "unrelated"])
def test_matrix_negatives_never_agree(comparison_kind: str) -> None:
    """Drift and unrelated audio must not produce an applicable offset."""
    reference = make_program(SEED, 120.0)
    if comparison_kind == "drift":
        comparison = drift_program(SEED, 120.0)
    else:
        comparison = make_program(31337, 120.0)
    estimate = run_estimate(reference, comparison)
    assert estimate.outcome == "no_single_offset"
    assert estimate.active_count > 0
    assert estimate.credible_count == 0
    assert estimate.global_lag is not None


@pytest.mark.parametrize("comparison_kind", ["silence", "quiet"])
def test_matrix_no_usable_audio(comparison_kind: str) -> None:
    """Silence and -70 dBFS audio leave every chunk inactive."""
    reference = make_program(SEED, 120.0)
    if comparison_kind == "silence":
        comparison = np.zeros_like(reference)
    else:
        comparison = quiet_program(SEED, 120.0)
    estimate = run_estimate(reference, comparison)
    assert estimate.outcome == "no_usable_audio"
    assert estimate.global_lag is None
    assert estimate.active_count == 0


def _lag_window(reference: np.ndarray, lag: int, lag_samples: int) -> np.ndarray:
    """Embed a chunk at an exact lag inside its comparison window."""
    window = np.zeros(reference.size + 2 * lag_samples)
    window[lag_samples - lag : lag_samples - lag + reference.size] = reference
    return window


@pytest.mark.parametrize(
    ("agreeing", "disagreeing", "expected"),
    [(80, 20, "agreed"), (79, 21, "no_single_offset")],
)
def test_agreement_boundary_79_vs_80_percent(
    agreeing: int, disagreeing: int, expected: ChunkedAudioOutcome
) -> None:
    """Exactly 80% agreement passes; 79% fails (integer-compared, no float edge)."""
    chunk_samples = 5 * ANALYSIS_SAMPLE_RATE
    total = agreeing + disagreeing
    plan = plan_audio_chunks(
        total * chunk_samples, 15 * ANALYSIS_SAMPLE_RATE, max_offset_seconds=1.0
    )
    assert len(plan.chunks) == total
    lag_samples = plan.lag_samples
    rng = np.random.default_rng(7)
    chunk = rng.standard_normal(chunk_samples)
    accumulator = ChunkedCorrelation(plan)
    for index in range(total):
        lag = 0 if index < agreeing else 1000
        accumulator.add(index, chunk, _lag_window(chunk, lag, lag_samples))
    estimate = accumulator.finish()
    assert estimate.credible_count == total
    assert estimate.agreeing_count == agreeing
    assert estimate.outcome == expected


def test_search_edge_at_both_bounds() -> None:
    """A true lag within 2 ms of +/-M is reported, never applied."""
    reference = make_program(SEED, 60.0)
    lag_samples = int(1.0 * ANALYSIS_SAMPLE_RATE)
    for shift, expected_lag in (
        (lag_samples - 10, -(lag_samples - 10)),
        (-(lag_samples - 10), lag_samples - 10),
        # Exactly 16 samples inside the bound is still the search edge.
        (lag_samples - 16, -(lag_samples - 16)),
        (-(lag_samples - 16), lag_samples - 16),
    ):
        estimate = run_estimate(reference, shift_signal(reference, shift), 1.0)
        assert estimate.outcome == "search_edge"
        assert estimate.global_lag == expected_lag
    for shift, expected_lag in (
        (lag_samples - 17, -(lag_samples - 17)),
        (-(lag_samples - 17), lag_samples - 17),
    ):
        estimate = run_estimate(reference, shift_signal(reference, shift), 1.0)
        assert estimate.outcome == "agreed"
        assert estimate.global_lag == expected_lag


def test_short_sources() -> None:
    """4 s, 20 s and 60 s sources stay eligible with the planned chunking."""
    shift = 500
    tiny = make_program(SEED, 4.0)
    plan = plan_audio_chunks(len(tiny), len(tiny), 1.0)
    assert plan.chunks == ((0, len(tiny)),)
    estimate = run_estimate(tiny, shift_signal(tiny, shift), 1.0)
    assert estimate.outcome == "agreed"
    assert estimate.global_lag == -shift

    short = make_program(SEED, 20.0)
    plan = plan_audio_chunks(len(short), len(short), 30.0)
    assert plan.chunk_samples == int(20.0 * ANALYSIS_SAMPLE_RATE) // 3
    assert len(plan.chunks) == 3
    estimate = run_estimate(short, shift_signal(short, shift))
    assert estimate.outcome == "agreed"
    assert estimate.global_lag == -shift

    medium = make_program(SEED, 60.0)
    plan = plan_audio_chunks(len(medium), len(medium), 30.0)
    assert plan.chunk_samples == 20 * ANALYSIS_SAMPLE_RATE
    estimate = run_estimate(medium, shift_signal(medium, shift))
    assert estimate.outcome == "agreed"
    assert estimate.global_lag == -shift


def test_partial_final_chunk_boundary() -> None:
    """A final partial chunk is kept at exactly C/2 and dropped just below it."""
    full = 4 * 30 * ANALYSIS_SAMPLE_RATE + 15 * ANALYSIS_SAMPLE_RATE
    plan = plan_audio_chunks(full, full, 30.0)
    assert plan.chunk_samples == 30 * ANALYSIS_SAMPLE_RATE
    assert len(plan.chunks) == 5
    assert plan.chunks[-1][1] == 15 * ANALYSIS_SAMPLE_RATE

    short = full - 1
    plan = plan_audio_chunks(short, short, 30.0)
    assert len(plan.chunks) == 4

    five = plan_audio_chunks(5 * ANALYSIS_SAMPLE_RATE, 5 * ANALYSIS_SAMPLE_RATE, 30.0)
    assert five.chunk_samples == 5 * ANALYSIS_SAMPLE_RATE
    fifteen = plan_audio_chunks(15 * ANALYSIS_SAMPLE_RATE, 15 * ANALYSIS_SAMPLE_RATE, 30.0)
    assert fifteen.chunk_samples == 5 * ANALYSIS_SAMPLE_RATE
    assert len(fifteen.chunks) == 3
    ninety = plan_audio_chunks(90 * ANALYSIS_SAMPLE_RATE, 90 * ANALYSIS_SAMPLE_RATE, 30.0)
    assert ninety.chunk_samples == 30 * ANALYSIS_SAMPLE_RATE
    assert len(ninety.chunks) == 3


def test_partial_final_chunk_boundary_uses_ceiling_for_odd_chunks() -> None:
    """With an odd C, a final chunk of ceil(C/2) is kept and floor(C/2) is dropped."""
    comparison = 20 * ANALYSIS_SAMPLE_RATE
    odd_chunk = comparison // 3
    assert odd_chunk % 2 == 1
    kept = plan_audio_chunks(3 * odd_chunk + odd_chunk // 2 + 1, comparison, 1.0)
    assert kept.chunk_samples == odd_chunk
    assert kept.chunks[-1] == (3 * odd_chunk, odd_chunk // 2 + 1)
    dropped = plan_audio_chunks(3 * odd_chunk + odd_chunk // 2, comparison, 1.0)
    assert len(dropped.chunks) == 3


def test_psr_matches_hand_computed_value() -> None:
    """PSR = (peak - median) / (1.4826 * MAD) over lags outside +/-160 of the peak."""
    # Outside the exclusion there are 440 values each of +1 and -1: median 0, MAD 1.
    correlation = np.tile([1.0, -1.0], 601)[:1201]
    peak = 600
    correlation[peak - 160 : peak + 161] = 9.0
    correlation[peak] = 10.0
    assert _chunk_psr(correlation, peak) == pytest.approx(10.0 / 1.4826)


def test_psr_zero_mad_rules() -> None:
    """MAD = 0 gives inf when the peak exceeds the median, otherwise 0."""
    flat = np.zeros(1201)
    raised = flat.copy()
    raised[600] = 1.0
    assert _chunk_psr(raised, 600) == math.inf
    assert _chunk_psr(flat, 600) == 0.0


def test_admission_budget() -> None:
    """Chunk FFTs past 2**22 points refuse before any analysis; just inside plans."""
    samples = 180 * ANALYSIS_SAMPLE_RATE
    with pytest.raises(AudioAlignmentError) as exc_info:
        plan_audio_chunks(samples, samples, 248.0)
    assert exc_info.value.category == "analysis_budget_exceeded"
    assert exc_info.value.stage == "planning"

    plan = plan_audio_chunks(samples, samples, 247.0)
    assert len(plan.chunks) == 6

    with pytest.raises(AudioAlignmentError) as exc_info:
        plan_audio_chunks(0, samples, 30.0)
    assert exc_info.value.category == "insufficient_signal"

    with pytest.raises(AudioAlignmentError) as exc_info:
        plan_audio_chunks(samples, 0, 30.0)
    assert exc_info.value.category == "insufficient_signal"
    for bad_offset in (0.5, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            plan_audio_chunks(samples, samples, bad_offset)


def test_add_contract_errors() -> None:
    """Out-of-order, duplicate and malformed adds fail; finish needs every chunk."""
    samples = 60 * ANALYSIS_SAMPLE_RATE
    plan = plan_audio_chunks(samples, samples, 1.0)
    start, count = plan.chunks[0]
    reference = make_program(SEED, 60.0)
    chunk = reference[start : start + count]
    window = comparison_window(reference, start, count, plan.lag_samples)

    accumulator = ChunkedCorrelation(plan)
    with pytest.raises(ValueError):
        accumulator.add(1, chunk, window)
    accumulator.add(0, chunk, window)
    with pytest.raises(ValueError):
        accumulator.add(0, chunk, window)
    with pytest.raises(ValueError):
        accumulator.finish()

    fresh = ChunkedCorrelation(plan)
    with pytest.raises(AudioAlignmentError) as exc_info:
        fresh.add(0, chunk[:-1], window)
    assert exc_info.value.category == "correlation_failed"
    assert exc_info.value.stage == "correlation"
    with pytest.raises(AudioAlignmentError) as exc_info:
        fresh.add(0, chunk, window[:-1])
    assert exc_info.value.category == "correlation_failed"
    assert exc_info.value.stage == "correlation"
    tiny_plan = plan_audio_chunks(4 * ANALYSIS_SAMPLE_RATE, 4 * ANALYSIS_SAMPLE_RATE, 1.0)
    tiny_count = tiny_plan.chunks[0][1]
    tiny_acc = ChunkedCorrelation(tiny_plan)
    tiny_acc.add(
        0,
        np.zeros(tiny_count),
        np.zeros(tiny_count + 2 * tiny_plan.lag_samples),
    )
    with pytest.raises(ValueError):
        tiny_acc.add(
            1,
            np.zeros(tiny_count),
            np.zeros(tiny_count + 2 * tiny_plan.lag_samples),
        )

    broken = np.array(chunk, copy=True)
    broken[0] = math.inf
    with pytest.raises(AudioAlignmentError) as exc_info:
        fresh.add(0, broken, window)
    assert exc_info.value.category == "non_finite_signal"
    broken_window = np.array(window, copy=True)
    broken_window[0] = math.nan
    with pytest.raises(AudioAlignmentError) as exc_info:
        fresh.add(0, chunk, broken_window)
    assert exc_info.value.category == "non_finite_signal"


def test_comparison_window_edges() -> None:
    """Windows zero-pad past both stream edges and copy exactly in the middle."""
    comparison = np.arange(10000, dtype=np.float64)
    window = comparison_window(comparison, 0, 5000, 8000)
    assert window.size == 5000 + 2 * 8000
    assert np.all(window[:8000] == 0)
    assert np.array_equal(window[8000:18000], comparison[:10000])
    assert np.all(window[18000:] == 0)

    window = comparison_window(comparison, 9000, 1000, 8000)
    assert window.size == 1000 + 2 * 8000
    assert np.array_equal(window[:9000], comparison[1000:])
    assert np.all(window[9000:] == 0)

    window = comparison_window(comparison, 4000, 1000, 100)
    assert np.array_equal(window, comparison[3900:5100])

    with pytest.raises(ValueError):
        comparison_window(comparison, -1, 1000, 100)
    with pytest.raises(ValueError):
        comparison_window(comparison, 4000, 0, 100)


def test_prototype_parity_on_180s_same() -> None:
    """On 30 s-multiple sources the lag and counts equal the benchmark prototype."""

    def prototype(
        reference: np.ndarray, comparison: np.ndarray, lag_range: int, chunk: int
    ) -> tuple[int, int, int]:
        padded = np.concatenate([np.zeros(lag_range), comparison, np.zeros(lag_range + chunk)])
        size = 1 << (chunk + 2 * lag_range - 1).bit_length()
        total = np.zeros(2 * lag_range + 1)
        rows: list[tuple[float, int]] = []
        for start in range(0, len(reference) - ANALYSIS_SAMPLE_RATE, chunk):
            part = reference[start : start + chunk].astype(np.float64)
            segment = padded[start : start + chunk + 2 * lag_range].astype(np.float64)
            if not (
                np.sqrt(np.mean(part * part)) > 10 ** (-50 / 20)
                and np.sqrt(np.mean(segment * segment)) > 10 ** (-50 / 20)
            ):
                continue
            cross = np.conj(np.fft.rfft(part, size)) * np.fft.rfft(segment, size)
            cross /= np.maximum(np.abs(cross), 1e-12)
            curve = np.fft.irfft(cross, size)[: 2 * lag_range + 1]
            peak = int(np.argmax(curve))
            side = np.delete(curve, np.arange(max(0, peak - 160), peak + 161))
            mad = np.median(np.abs(side - np.median(side))) + 1e-15
            psr = (curve[peak] - np.median(side)) / (1.4826 * mad)
            rows.append((psr, lag_range - peak))
            total += curve
        global_lag = lag_range - int(np.argmax(total))
        credible = [row for row in rows if row[0] >= 25.0]
        agreeing = [row for row in credible if abs(row[1] - global_lag) <= 16]
        return global_lag, len(credible), len(agreeing)

    reference = make_program(SEED, 180.0)
    comparison = shift_signal(reference, POSITIVE_SHIFT)
    estimate = run_estimate(reference, comparison)
    assert estimate.outcome == "agreed"
    lag_range = int(30.0 * ANALYSIS_SAMPLE_RATE)
    expected = prototype(reference, comparison, lag_range, 30 * ANALYSIS_SAMPLE_RATE)
    assert expected[0] == -POSITIVE_SHIFT
    assert estimate.global_lag == expected[0]
    assert estimate.credible_count == expected[1]
    assert estimate.agreeing_count == expected[2]
