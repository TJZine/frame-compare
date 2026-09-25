"""Seeded synthetic audio generated directly at 8 kHz for alignment tests.

No FFmpeg, no files: three deterministic stems (dialogue, music, effects) mixed
to mono, plus small helpers to build shifted/remixed/processed comparison
variants. Everything is pure NumPy.
"""

from __future__ import annotations

import numpy as np

from frame_compare.services.alignment_correlation import ANALYSIS_SAMPLE_RATE

SAMPLE_RATE = ANALYSIS_SAMPLE_RATE

_DEFAULT_GAINS = (1.0, 0.8, 0.9)
_DOWNMIX_GAINS = (0.7, 1.0, 0.5)


def _band_limit(noise: np.ndarray, low_hz: float, high_hz: float) -> np.ndarray:
    spectrum = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(noise.size, 1.0 / SAMPLE_RATE)
    spectrum *= (freqs >= low_hz) & (freqs <= high_hz)
    return np.fft.irfft(spectrum, noise.size)


def dialogue_stem(seed: int, duration_seconds: float) -> np.ndarray:
    """Band-limited noise (250-3500 Hz) with syllable and phrase envelopes."""
    n = int(duration_seconds * SAMPLE_RATE)
    rng = np.random.default_rng(seed)
    voice = _band_limit(rng.standard_normal(n), 250.0, 3500.0)
    envelope = np.zeros(n)
    t = 0.0
    while t < duration_seconds:
        for _ in range(int(rng.integers(4, 10))):
            syllable = float(rng.uniform(0.09, 0.28))
            gap = float(rng.uniform(0.02, 0.12))
            start = int(t * SAMPLE_RATE)
            stop = min(n, int((t + syllable) * SAMPLE_RATE))
            if stop > start:
                shape = np.hanning(max(stop - start, 3))
                envelope[start:stop] = shape * float(rng.uniform(0.5, 1.0))
            t += syllable + gap
            if t >= duration_seconds:
                break
        t += float(rng.uniform(0.4, 1.2))
    stem = voice * envelope
    rms = float(np.sqrt(np.mean(stem * stem)))
    return stem * (0.25 / rms) if rms > 0 else stem


def music_stem(seed: int, duration_seconds: float) -> np.ndarray:
    """Harmonic melody notes over a bass line."""
    n = int(duration_seconds * SAMPLE_RATE)
    rng = np.random.default_rng(seed)
    stem = np.zeros(n)
    scale = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]
    degree = 5
    t = 0.0
    while t < duration_seconds:
        degree = int(np.clip(degree + rng.integers(-3, 4), 0, len(scale) - 1))
        freq = 220.0 * 2.0 ** (scale[degree] / 12.0)
        length = float(rng.uniform(0.3, 0.6))
        stop = min(n, int((t + length) * SAMPLE_RATE))
        span = np.arange(int(t * SAMPLE_RATE), stop) / SAMPLE_RATE - t
        decay = np.exp(-span * 6.0)
        for harmonic, gain in ((1, 1.0), (2, 0.35), (3, 0.12)):
            stem[int(t * SAMPLE_RATE) : stop] += (
                gain * np.sin(2.0 * np.pi * freq * harmonic * span) * decay
            )
        t += 0.4
    bass_t = 0.0
    while bass_t < duration_seconds:
        freq = float(rng.choice([55.0, 65.41, 73.42, 82.41, 98.0, 110.0]))
        length = min(1.5, duration_seconds - bass_t)
        stop = min(n, int((bass_t + length) * SAMPLE_RATE))
        span = np.arange(int(bass_t * SAMPLE_RATE), stop) / SAMPLE_RATE - bass_t
        stem[int(bass_t * SAMPLE_RATE) : stop] += (
            0.8 * np.sin(2.0 * np.pi * freq * span) * np.exp(-span * 2.5)
        )
        bass_t += 1.6
    rms = float(np.sqrt(np.mean(stem * stem)))
    return stem * (0.22 / rms) if rms > 0 else stem


def effects_stem(seed: int, duration_seconds: float) -> np.ndarray:
    """Sparse decaying noise bursts."""
    n = int(duration_seconds * SAMPLE_RATE)
    rng = np.random.default_rng(seed)
    stem = np.zeros(n)
    for _ in range(int(duration_seconds * 0.6)):
        start = int(rng.uniform(0, duration_seconds) * SAMPLE_RATE)
        length = int(rng.uniform(0.05, 0.5) * SAMPLE_RATE)
        stop = min(n, start + length)
        if stop > start:
            span = np.arange(start, stop) - start
            burst = rng.standard_normal(stop - start) * np.exp(-span / (0.15 * SAMPLE_RATE))
            stem[start:stop] += burst * float(rng.uniform(0.4, 1.0))
    rms = float(np.sqrt(np.mean(stem * stem)))
    return stem * (0.18 / rms) if rms > 0 else stem


def make_stems(seed: int, duration_seconds: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return the (dialogue, music, effects) stems for one program seed."""
    return (
        dialogue_stem(seed * 3 + 1, duration_seconds),
        music_stem(seed * 3 + 2, duration_seconds),
        effects_stem(seed * 3 + 3, duration_seconds),
    )


def mix_stems(
    dialogue: np.ndarray,
    music: np.ndarray,
    effects: np.ndarray,
    gains: tuple[float, float, float] = _DEFAULT_GAINS,
) -> np.ndarray:
    """Mix stems to mono with per-stem gains, normalizing the peak to 0.8."""
    mix = gains[0] * dialogue + gains[1] * music + gains[2] * effects
    peak = float(np.max(np.abs(mix)))
    return mix * (0.8 / peak) if peak > 0 else mix


def make_program(seed: int, duration_seconds: float) -> np.ndarray:
    """Seeded mono program at 8 kHz."""
    return mix_stems(*make_stems(seed, duration_seconds))


def downmix_program(seed: int, duration_seconds: float) -> np.ndarray:
    """Same stems with different mono mixing coefficients."""
    return mix_stems(*make_stems(seed, duration_seconds), gains=_DOWNMIX_GAINS)


def dub_program(seed: int, duration_seconds: float, dialogue_seed: int) -> np.ndarray:
    """Same music/effects, dialogue from another seed."""
    _, music, effects = make_stems(seed, duration_seconds)
    dialogue = dialogue_stem(dialogue_seed, duration_seconds)
    return mix_stems(dialogue, music, effects)


def remaster_program(seed: int, duration_seconds: float) -> np.ndarray:
    """Spectral tilt, tanh limiting, and seeded noise."""
    signal = make_program(seed, duration_seconds)
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(signal.size, 1.0 / SAMPLE_RATE)
    response = np.interp(freqs, [0.0, 120.0, 3000.0, 4000.0], [2.0, 2.0, 0.4, 0.4])
    tilted = np.fft.irfft(spectrum * response, signal.size)
    limited = np.tanh(2.0 * tilted) / np.tanh(1.6)
    rng = np.random.default_rng(seed * 7 + 5)
    return limited + 0.01 * rng.standard_normal(signal.size)


def noisy_program(seed: int, duration_seconds: float, noise_seed: int) -> np.ndarray:
    """Same program with white noise at about -15 dB SNR."""
    signal = make_program(seed, duration_seconds)
    rms = float(np.sqrt(np.mean(signal * signal)))
    rng = np.random.default_rng(noise_seed)
    return signal + (rms / 10.0 ** (15.0 / 20.0)) * rng.standard_normal(signal.size)


def shift_signal(signal: np.ndarray, shift: int) -> np.ndarray:
    """Shift content later (shift > 0) or earlier, keeping the length."""
    out = np.zeros_like(signal)
    if shift >= 0:
        out[shift:] = signal[: signal.size - shift]
    else:
        out[: signal.size + shift] = signal[-shift:]
    return out


def prepend_silence(signal: np.ndarray, samples: int) -> np.ndarray:
    """Prepend silence, growing the array (no truncation)."""
    return np.concatenate((np.zeros(samples), signal))


def intro_program(seed: int, duration_seconds: float, intro_seed: int) -> np.ndarray:
    """Twenty seconds of another program prepended, truncated to length."""
    intro = make_program(intro_seed, 20.0)
    return np.concatenate((intro, make_program(seed, duration_seconds)))[
        : int(duration_seconds * SAMPLE_RATE)
    ]


def insert_program(seed: int, duration_seconds: float, foreign_seed: int) -> np.ndarray:
    """Four seconds of another program inserted mid-track (output grows by 4 s)."""
    signal = make_program(seed, duration_seconds)
    foreign = make_program(foreign_seed, 4.0)
    at = signal.size // 2
    return np.concatenate((signal[:at], foreign, signal[at:]))


def drift_program(seed: int, duration_seconds: float) -> np.ndarray:
    """Resample by 1.001 via index mapping, keeping the length."""
    signal = make_program(seed, duration_seconds)
    positions = np.arange(signal.size) * 1.001
    return np.interp(positions, np.arange(signal.size), signal, left=0.0, right=0.0)


def quiet_program(seed: int, duration_seconds: float) -> np.ndarray:
    """Same program scaled to a -70 dBFS peak (below the activity floor)."""
    signal = make_program(seed, duration_seconds)
    peak = float(np.max(np.abs(signal)))
    return signal * (10.0 ** (-70.0 / 20.0) / peak) if peak > 0 else signal
