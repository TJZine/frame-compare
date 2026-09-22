"""Opt-in R6C evidence for fixed corresponding-channel corroboration."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from frame_compare.services.alignment_correlation import correlate_audio, refine_aligned_score
from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.errors import AudioAlignmentError

from .alignment_oracle import BASE_PEAK_RATIO_FLOOR, BASE_SCORE_FLOOR, deterministic_signal

_OPT_IN = os.environ.get("FRAME_COMPARE_CHANNEL_CORROBORATION") == "1"
_RATE = 8_000
_FPS = Fraction(24_000, 1001)
_WINDOW_SAMPLES = 9 * _RATE
_WINDOW_COUNT = 3
_SEARCH_SAMPLES = 30 * _RATE
_CORRECTION_RADIUS = round(0.005 * _RATE)
_SCORE_CAP = 65_536
_CHANNELS = ("FL", "FR", "FC")
_RSS_LIMIT_BYTES = 512 * 1024 * 1024

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(not _OPT_IN, reason="set FRAME_COMPARE_CHANNEL_CORROBORATION=1"),
]


@dataclass(frozen=True, slots=True)
class _ViewResult:
    view: str
    lag: int | None
    frame: int | None
    score_capped: float | None
    score_full: float | None
    peak_ratio: float | None
    capped_lag: int | None
    full_lag: int | None
    top_three_lags: tuple[int, ...]
    activity_valid: bool
    coverage_valid: bool
    base_credible: bool
    rejection: str | None


@dataclass(frozen=True, slots=True)
class _WindowResult:
    index: int
    mono: _ViewResult
    views: tuple[_ViewResult, ...]
    corroborated: bool
    frame: int | None
    contradiction: bool
    reason: str


class _Resources:
    def __init__(self) -> None:
        self.decode_count = 0
        self.peak_combined_rss = 0
        self.baseline_rss = _rss_bytes(os.getpid())

    def run(self, argv: list[str], *, decode: bool = False) -> bytes:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
        if decode:
            self.decode_count += 1
        samples: list[int] = []
        stopped = threading.Event()

        def sample() -> None:
            while not stopped.is_set():
                samples.append(_rss_bytes(os.getpid()) + _rss_bytes(process.pid))
                stopped.wait(0.02)

        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        try:
            try:
                stdout, stderr = process.communicate(timeout=180)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
                raise
        finally:
            stopped.set()
            sampler.join(timeout=2)
        if process.returncode != 0:
            raise AssertionError(stderr.decode(errors="replace")[-2000:])
        self.peak_combined_rss = max((self.peak_combined_rss, *samples))
        return stdout


def _rss_bytes(pid: int) -> int:
    if platform.system() == "Linux":
        try:
            status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
        except (FileNotFoundError, ProcessLookupError):
            return 0
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
        return 0
    completed = subprocess.run(  # noqa: S603
        ["ps", "-o", "rss=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
        timeout=2,
    )
    return int(completed.stdout.strip() or 0) * 1024


def _shift(signal: np.ndarray, offset: int) -> np.ndarray:
    shifted = np.zeros_like(signal)
    if offset > 0:
        shifted[offset:] = signal[:-offset]
    elif offset < 0:
        shifted[:offset] = signal[-offset:]
    else:
        shifted[:] = signal
    return shifted


def _program(seed: int) -> np.ndarray:
    duration = _WINDOW_COUNT * _WINDOW_SAMPLES // _RATE
    channels = [
        deterministic_signal(seed=seed + index, sample_rate=_RATE, duration_seconds=duration)
        for index in range(6)
    ]
    return np.column_stack(channels).astype(np.float32)


def _positive(reference: np.ndarray, offset: int) -> np.ndarray:
    comparison = np.column_stack([_shift(reference[:, index], offset) for index in range(6)])
    comparison[:, 1] *= -0.7
    comparison[:, 2] *= 0.45
    comparison[:, 3:] *= -0.8
    return comparison.astype(np.float32)


def _matrix() -> tuple[tuple[str, np.ndarray, np.ndarray, int | None, bool], ...]:
    programs = [_program(seed) for seed in (6100, 6200, 6300)]
    positive = [
        ("seed-6100-zero-remix", programs[0], _positive(programs[0], 0), 0, True),
        ("seed-6200-positive-remix", programs[1], _positive(programs[1], 1_600), 1_600, True),
        ("seed-6300-negative-remix", programs[2], _positive(programs[2], -1_600), -1_600, True),
    ]
    unrelated = _program(7100)
    low_information = np.zeros_like(programs[0])
    repeated = np.column_stack(
        [
            np.sin(2 * np.pi * (90 + index * 10) * np.arange(programs[0].shape[0]) / _RATE)
            for index in range(6)
        ]
    ).astype(np.float32)
    permuted = programs[0][:, (1, 2, 0, 4, 5, 3)]
    conflicting = np.column_stack(
        [_shift(programs[1][:, index], 1_600 if index < 2 else -1_600) for index in range(6)]
    ).astype(np.float32)
    localized = programs[2].copy()
    for window in range(_WINDOW_COUNT):
        start = window * _WINDOW_SAMPLES
        middle = start + _WINDOW_SAMPLES // 2
        end = start + _WINDOW_SAMPLES
        localized[start:middle, 0] = _shift(programs[2][:, 0], 1_600)[start:middle]
        localized[middle:end, 0] = unrelated[middle:end, 0]
        localized[start:middle, 1] = _shift(programs[2][:, 1], -1_600)[start:middle]
        localized[middle:end, 1] = unrelated[middle:end, 1]
        localized[start:end, 2] = unrelated[start:end, 2]
    negative = [
        ("unrelated-programs", programs[0], unrelated, None, False),
        ("silence-low-information", programs[0], low_information, None, False),
        ("repeated-structure", repeated, np.roll(repeated, 800, axis=0), None, False),
        ("incompatible-permuted-channels", programs[0], permuted, None, False),
        ("conflicting-channel-offsets", programs[1], conflicting, None, False),
        ("localized-mix-cut-track-mismatch", programs[2], localized, None, False),
    ]
    return tuple(positive + negative)


def _write_media(resources: _Resources, path: Path, samples: np.ndarray) -> None:
    raw = path.with_suffix(".f32le")
    raw.write_bytes(np.asarray(samples, dtype="<f4").tobytes())
    resources.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "f32le",
            "-ar",
            str(_RATE),
            "-ac",
            "6",
            "-channel_layout",
            "5.1",
            "-i",
            str(raw),
            "-c:a",
            "pcm_f32le",
            str(path),
        ]
    )


def _assert_layout(resources: _Resources, path: Path) -> None:
    payload = json.loads(
        resources.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=channels,channel_layout",
                "-of",
                "json",
                str(path),
            ]
        )
    )
    assert payload["streams"] == [{"channels": 6, "channel_layout": "5.1"}]


def _decode(resources: _Resources, path: Path, *, views: bool) -> np.ndarray:
    filters = ["-af", "pan=3c|c0=FL|c1=FR|c2=FC"] if views else ["-ac", "1"]
    raw = resources.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            *filters,
            "-ar",
            str(_RATE),
            "-f",
            "f32le",
            "-",
        ],
        decode=True,
    )
    channels = 3 if views else 1
    return np.frombuffer(raw, dtype="<f4").reshape(-1, channels)


def _raw_candidates(reference: np.ndarray, comparison: np.ndarray) -> tuple[tuple[int, ...], float]:
    reference = reference.astype(np.float64) - float(np.mean(reference))
    comparison = comparison.astype(np.float64) - float(np.mean(comparison))
    if np.linalg.norm(reference) <= 1e-12 or np.linalg.norm(comparison) <= 1e-12:
        return (), 0.0
    size = reference.size + comparison.size - 1
    fft_size = 1 << (size - 1).bit_length()
    raw = np.fft.irfft(
        np.fft.rfft(reference, fft_size) * np.conj(np.fft.rfft(comparison, fft_size)), fft_size
    )
    correlation = np.concatenate((raw[-(comparison.size - 1) :], raw[: reference.size]))
    center = comparison.size - 1
    radius = min(_SEARCH_SAMPLES, reference.size - 1, comparison.size - 1)
    search = correlation[center - radius : center + radius + 1].copy()
    peaks: list[float] = []
    lags: list[int] = []
    exclusion = round(0.004 * _RATE)
    for _ in range(3):
        index = int(np.argmax(search))
        peaks.append(float(search[index]))
        lags.append(radius - index)
        search[max(0, index - exclusion) : index + exclusion + 1] = -np.inf
    ratio = float("inf") if peaks[1] <= 1e-12 else peaks[0] / peaks[1]
    return tuple(lags), ratio


def _score(
    reference: np.ndarray, comparison: np.ndarray, lag: int, *, capped: bool
) -> float | None:
    if lag > 0:
        reference, comparison = reference[:-lag], comparison[lag:]
    elif lag < 0:
        reference, comparison = reference[-lag:], comparison[:lag]
    if reference.size < 3:
        return None
    if capped and reference.size > _SCORE_CAP:
        indices = np.linspace(0, reference.size - 1, _SCORE_CAP, dtype=np.int64)
        reference, comparison = reference[indices], comparison[indices]
    reference = reference.astype(np.float64) - float(np.mean(reference))
    comparison = comparison.astype(np.float64) - float(np.mean(comparison))
    denominator = float(np.linalg.norm(reference) * np.linalg.norm(comparison))
    return None if denominator <= 1e-12 else float(np.dot(reference, comparison) / denominator)


def _view(view: str, reference: np.ndarray, comparison: np.ndarray) -> _ViewResult:
    top_three, peak_ratio = _raw_candidates(reference, comparison)
    activity_valid = bool(np.linalg.norm(reference) > 1e-12 and np.linalg.norm(comparison) > 1e-12)
    try:
        estimate = correlate_audio(
            reference,
            comparison,
            max_offset_samples=_SEARCH_SAMPLES,
            correlation_mode="raw_fft",
            preprocessing_mode="standard",
        )
    except AudioAlignmentError:
        return _ViewResult(
            view,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (),
            False,
            True,
            False,
            "insufficient_activity",
        )
    lag = estimate.sample_offset
    assert top_three[0] == lag
    correction, capped_score = refine_aligned_score(
        reference,
        comparison,
        preprocessing_mode="standard",
        correction_bounds_samples=(-lag - _CORRECTION_RADIUS, -lag + _CORRECTION_RADIUS),
    )
    capped_lag = -correction
    neighborhood = range(lag - _CORRECTION_RADIUS, lag + _CORRECTION_RADIUS + 1)
    full_scores = [
        (candidate, _score(reference, comparison, candidate, capped=False))
        for candidate in neighborhood
    ]
    full_lag, full_score = max(
        (item for item in full_scores if item[1] is not None), key=lambda item: item[1]
    )
    peak_ratio = estimate.peak_ratio
    frame = samples_to_frames(lag, _RATE, _FPS)
    base_credible = capped_score >= BASE_SCORE_FLOOR and peak_ratio >= BASE_PEAK_RATIO_FLOOR
    rejection = None
    if peak_ratio < BASE_PEAK_RATIO_FLOOR:
        rejection = "peak_floor"
    elif capped_score < BASE_SCORE_FLOOR:
        rejection = "waveform_floor"
    return _ViewResult(
        view,
        lag,
        frame,
        capped_score,
        full_score,
        peak_ratio,
        capped_lag,
        full_lag,
        top_three,
        activity_valid,
        True,
        base_credible,
        rejection,
    )


def _window(index: int, mono: _ViewResult, views: tuple[_ViewResult, ...]) -> _WindowResult:
    if mono.score_capped is None or mono.lag is None or mono.score_capped >= BASE_SCORE_FLOOR:
        return _WindowResult(index, mono, views, False, None, False, "mono_not_eligible")
    valid = [
        view
        for view in views
        if view.activity_valid
        and view.coverage_valid
        and view.peak_ratio is not None
        and view.peak_ratio >= BASE_PEAK_RATIO_FLOOR
        and view.lag is not None
        and abs(view.lag - mono.lag) <= _CORRECTION_RADIUS
    ]
    credible_frames = {
        view.frame
        for view in views
        if view.activity_valid and view.coverage_valid and view.base_credible
    }
    groups: dict[int, list[_ViewResult]] = {}
    for view in valid:
        assert view.frame is not None
        groups.setdefault(view.frame, []).append(view)
    eligible = [
        (frame, members)
        for frame, members in groups.items()
        if len(members) >= 2 and any(member.base_credible for member in members)
    ]
    if len(credible_frames) > 1:
        return _WindowResult(index, mono, views, False, None, True, "credible_cross_frame_veto")
    if len(eligible) != 1:
        return _WindowResult(
            index, mono, views, False, None, bool(credible_frames), "no_unique_corroboration"
        )
    frame, members = eligible[0]
    contradiction = any(value != frame for value in credible_frames)
    return _WindowResult(
        index,
        mono,
        views,
        not contradiction,
        frame,
        contradiction,
        "corroborated" if not contradiction else "credible_cross_frame_veto",
    )


def test_predeclared_corresponding_channel_corroboration_matrix(tmp_path: Path) -> None:
    resources = _Resources()
    started = time.monotonic()
    cases: list[dict[str, object]] = []
    matrix = _matrix()
    for case_id, reference_samples, comparison_samples, expected_lag, positive in matrix:
        reference_path = tmp_path / f"{case_id}-reference.wav"
        comparison_path = tmp_path / f"{case_id}-comparison.wav"
        _write_media(resources, reference_path, reference_samples)
        _write_media(resources, comparison_path, comparison_samples)
        _assert_layout(resources, reference_path)
        _assert_layout(resources, comparison_path)
        reference_mono = _decode(resources, reference_path, views=False)[:, 0]
        comparison_mono = _decode(resources, comparison_path, views=False)[:, 0]
        reference_views = _decode(resources, reference_path, views=True)
        comparison_views = _decode(resources, comparison_path, views=True)
        windows: list[_WindowResult] = []
        for index in range(_WINDOW_COUNT):
            start = index * _WINDOW_SAMPLES
            end = start + _WINDOW_SAMPLES
            mono = _view("production_mono", reference_mono[start:end], comparison_mono[start:end])
            views = tuple(
                _view(
                    name, reference_views[start:end, channel], comparison_views[start:end, channel]
                )
                for channel, name in enumerate(_CHANNELS)
            )
            windows.append(_window(index + 1, mono, views))
        if positive:
            expected_frame = samples_to_frames(expected_lag or 0, _RATE, _FPS)
            assert all(window.corroborated and window.frame == expected_frame for window in windows)
            assert len(windows) >= 3  # channel views never add independent temporal support
        else:
            assert not any(window.corroborated for window in windows)
        for window in windows:
            for view in (window.mono, *window.views):
                if view.capped_lag is not None:
                    assert samples_to_frames(view.capped_lag, _RATE, _FPS) == samples_to_frames(
                        view.full_lag, _RATE, _FPS
                    )
                    assert (view.score_capped >= BASE_SCORE_FLOOR) == (
                        view.score_full >= BASE_SCORE_FLOOR
                    )
        cases.append(
            {
                "case": case_id,
                "positive": positive,
                "expected_lag": expected_lag,
                "windows": [asdict(window) for window in windows],
            }
        )
    elapsed = time.monotonic() - started
    retained_bytes = sum(array.nbytes for item in matrix for array in item[1:3])
    assert resources.decode_count == len(cases) * 4
    assert resources.peak_combined_rss - resources.baseline_rss <= _RSS_LIMIT_BYTES
    report = {
        "platform": platform.platform(),
        "ffmpeg": subprocess.run(
            ["ffmpeg", "-version"], check=True, capture_output=True, text=True, timeout=5
        ).stdout.splitlines()[0],  # noqa: S603
        "rule": "fixed FL/FR/FC intersection; two peak-valid same-frame views; one waveform-valid; credible cross-frame veto",
        "sample_rate": _RATE,
        "frame_rate": str(_FPS),
        "search_seconds": 30,
        "correction_radius_samples": _CORRECTION_RADIUS,
        "top_candidate_budget": 3,
        "score_floor": BASE_SCORE_FLOOR,
        "peak_floor": BASE_PEAK_RATIO_FLOOR,
        "decode_count": resources.decode_count,
        "retained_bytes": retained_bytes,
        "elapsed_seconds": elapsed,
        "rss": {
            "baseline_bytes": resources.baseline_rss,
            "peak_combined_bytes": resources.peak_combined_rss,
            "peak_incremental_bytes": resources.peak_combined_rss - resources.baseline_rss,
        },
        "cases": cases,
    }
    if result_path := os.environ.get("R6C_RESULT_PATH"):
        Path(result_path).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print("R6C_RESULT=" + json.dumps(report, separators=(",", ":"), sort_keys=True))
