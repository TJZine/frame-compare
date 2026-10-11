"""Opt-in resource proof for paired whole-track audio collection."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from frame_compare.services import alignment_audio, alignment_streaming
from frame_compare.services.alignment_correlation import plan_audio_chunks
from frame_compare.services.alignment_streaming import (
    PairedAudioCollection,
    PairedAudioCollectionFailure,
    PairedAudioCollectionResult,
    collect_paired_audio_chunks,
    paired_collection_timeout_seconds,
    paired_output_limit_samples,
)
from frame_compare.services.errors import AudioAlignmentError

_RESOURCE_OPT_IN = os.environ.get("FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES") == "1"
_MIB = 1024 * 1024
_RSS_LIMIT_BYTES = 512 * _MIB
_SAMPLE_PERIOD_SECONDS = 0.02

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(
        not _RESOURCE_OPT_IN,
        reason="set FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1",
    ),
]


@dataclass(frozen=True, slots=True)
class _RssMeasurement:
    method: str
    baseline_bytes: int
    peak_combined_bytes: int
    peak_incremental_bytes: int
    sample_count: int
    child_sample_count: int
    maximum_gap_seconds: float
    maximum_active_children: int
    peak_parent_bytes: int
    peak_child_bytes: int
    maximum_within_child_plateau_growth_bytes: int
    within_child_plateau_sample_counts: tuple[int, ...]


class _ProcessTracker:
    def __init__(self, real_popen: Any) -> None:
        self._lock = threading.Lock()
        self._processes: list[subprocess.Popen[Any]] = []
        self._commands_by_pid: dict[int, tuple[str, ...]] = {}
        self._real_popen = real_popen
        self.terminate_requests = 0
        self.kill_requests = 0

    def popen(self, *args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        process = self._real_popen(*args, **kwargs)
        argv = args[0] if args else kwargs.get("args", ())
        if "f32le" in argv:
            real_terminate = process.terminate
            real_kill = process.kill

            def terminate() -> None:
                self.terminate_requests += 1
                real_terminate()

            def kill() -> None:
                self.kill_requests += 1
                real_kill()

            process.terminate = terminate
            process.kill = kill
            with self._lock:
                self._processes.append(process)
                self._commands_by_pid[process.pid] = tuple(str(part) for part in argv)
        return process

    def active_pids(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(process.pid for process in self._processes if process.poll() is None)

    def returncodes(self) -> tuple[int | None, ...]:
        with self._lock:
            return tuple(process.poll() for process in self._processes)

    def commands(self) -> tuple[tuple[str, ...], ...]:
        with self._lock:
            return tuple(self._commands_by_pid.values())


def _linux_rss_bytes(pids: tuple[int, ...]) -> int:
    total = 0
    for pid in pids:
        try:
            status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
        except (FileNotFoundError, ProcessLookupError):
            continue
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                total += int(line.split()[1]) * 1024
                break
    return total


def _darwin_rss_bytes(pids: tuple[int, ...]) -> int:
    completed = subprocess.run(  # noqa: S603 - fixed platform measurement command
        ["ps", "-o", "rss=", "-p", ",".join(str(pid) for pid in pids)],
        check=True,
        capture_output=True,
        text=True,
        timeout=2,
    )
    return sum(int(value) * 1024 for value in completed.stdout.split())


def _rss_reader() -> tuple[str, Any]:
    if platform.system() == "Linux" and Path("/proc/self/status").is_file():
        return "linux-proc-status-vmrss", _linux_rss_bytes
    if platform.system() == "Darwin" and shutil.which("ps") is not None:
        return "darwin-ps-rss", _darwin_rss_bytes
    pytest.fail("combined parent/child RSS measurement is unavailable on this platform")


def _measure_call(
    tracker: _ProcessTracker,
    call: Any,
) -> tuple[Any, _RssMeasurement, float]:
    method, read_rss = _rss_reader()
    parent_pid = os.getpid()
    baseline = read_rss((parent_pid,))
    samples: list[tuple[float, int, int, int, tuple[int, ...]]] = []
    stopped = threading.Event()

    def sample() -> None:
        while not stopped.is_set():
            started = time.monotonic()
            child_pids = tracker.active_pids()
            combined_rss = read_rss((parent_pid, *child_pids))
            parent_rss = read_rss((parent_pid,))
            child_rss = max(0, combined_rss - parent_rss)
            samples.append((started, combined_rss, parent_rss, child_rss, child_pids))
            stopped.wait(max(0.0, _SAMPLE_PERIOD_SECONDS - (time.monotonic() - started)))

    sampler = threading.Thread(target=sample, name="alignment-rss-sampler", daemon=True)
    sampler.start()
    started = time.monotonic()
    try:
        result = call()
    finally:
        elapsed = time.monotonic() - started
        stopped.set()
        sampler.join(timeout=2)
    assert not sampler.is_alive()
    assert samples
    gaps = [right[0] - left[0] for left, right in zip(samples, samples[1:], strict=False)]
    peak = max(sample[1] for sample in samples)
    child_samples = [sample for sample in samples if sample[4]]
    samples_by_child = {
        pid: [sample for sample in child_samples if pid in sample[4]]
        for pid in {pid for sample in child_samples for pid in sample[4]}
    }
    plateau_growth: list[int] = []
    plateau_counts: list[int] = []
    for child_pid in sorted(samples_by_child):
        child_series = samples_by_child[child_pid]
        settled = child_series[len(child_series) // 3 :]
        split = len(settled) // 2
        if split == 0:
            continue
        early_peak = max(sample[1] for sample in settled[:split])
        late_peak = max(sample[1] for sample in settled[split:])
        plateau_growth.append(max(0, late_peak - early_peak))
        plateau_counts.append(len(settled))
    measurement = _RssMeasurement(
        method=method,
        baseline_bytes=baseline,
        peak_combined_bytes=peak,
        peak_incremental_bytes=max(0, peak - baseline),
        sample_count=len(samples),
        child_sample_count=len(child_samples),
        maximum_gap_seconds=max(gaps, default=0.0),
        maximum_active_children=max(len(sample[4]) for sample in samples),
        peak_parent_bytes=max(sample[2] for sample in samples),
        peak_child_bytes=max(sample[3] for sample in samples),
        maximum_within_child_plateau_growth_bytes=max(plateau_growth, default=0),
        within_child_plateau_sample_counts=tuple(plateau_counts),
    )
    return result, measurement, elapsed


def _install_tracker(monkeypatch: pytest.MonkeyPatch) -> _ProcessTracker:
    tracker = _ProcessTracker(subprocess.Popen)
    monkeypatch.setattr(alignment_streaming.subprocess, "Popen", tracker.popen)
    return tracker


_PAIRED_SAMPLE_RATE = 8_000
_PAIRED_CHUNK_SECONDS = 30
_PAIRED_MEDIA_SECONDS = 10_800


class _CountingConsumer:
    """Trivial paired consumer: proves delivery order without retaining PCM."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, index: int, reference: Any, window: Any) -> None:
        del reference, window
        assert index == self.count
        self.count += 1


def _paired_decode_argv(path: Path) -> list[str]:
    """The shipped whole-track collection recipe for the fixture's only stream."""
    return alignment_audio.collection_argv(
        path,
        alignment_audio.probe_streams(path).audio[0],
        channel_strategy="mono_downmix",
        timeline_scale=Fraction(1),
    )


def _generate_long_audio(path: Path, *, duration_seconds: int) -> None:
    subprocess.run(  # noqa: S603 - fixed deterministic test fixture command
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=pink:sample_rate={_PAIRED_SAMPLE_RATE}"
            f":duration={duration_seconds}:seed=6106",
            "-ar",
            str(_PAIRED_SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        check=True,
        timeout=600,
    )


@pytest.fixture(scope="module")
def paired_long_media(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path]:
    if shutil.which("ffmpeg") is None:
        pytest.fail("ffmpeg is required for the opted-in resource gate")
    root = tmp_path_factory.mktemp("alignment-paired-resources")
    reference = root / "paired-reference.wav"
    comparison = root / "paired-comparison.wav"
    _generate_long_audio(reference, duration_seconds=_PAIRED_MEDIA_SECONDS)
    shutil.copyfile(reference, comparison)
    return reference, comparison


def _paired_chunks() -> tuple[tuple[int, int], ...]:
    chunk = _PAIRED_CHUNK_SECONDS * _PAIRED_SAMPLE_RATE
    total = _PAIRED_MEDIA_SECONDS * _PAIRED_SAMPLE_RATE
    return tuple((start, chunk) for start in range(0, total, chunk))


def _print_paired_measurement(
    case: str,
    result: PairedAudioCollection,
    measurement: _RssMeasurement,
    elapsed: float,
) -> None:
    print(
        {
            "case": case,
            "elapsed_seconds": elapsed,
            "rss": measurement,
            "chunks_delivered": result.chunks_delivered,
            "reference_emitted_samples": result.reference_facts.emitted_sample_count,
            "comparison_emitted_samples": result.comparison_facts.emitted_sample_count,
            "reference_retained_peak": result.reference_facts.retained_sample_count,
            "comparison_retained_peak": result.comparison_facts.retained_sample_count,
        }
    )


def _assert_paired_resource_result(
    result: PairedAudioCollection,
    measurement: _RssMeasurement,
    *,
    expected_chunks: int,
    max_lag_samples: int,
) -> None:
    chunk = _PAIRED_CHUNK_SECONDS * _PAIRED_SAMPLE_RATE
    spill = alignment_streaming._READ_BYTES // 4 + 1
    assert result.chunks_delivered == expected_chunks
    assert result.reference_cleanup.completed
    assert result.comparison_cleanup.completed
    assert result.reference_facts.retained_sample_count <= chunk + spill
    assert result.comparison_facts.retained_sample_count <= chunk + 2 * max_lag_samples + spill
    assert measurement.peak_incremental_bytes <= _RSS_LIMIT_BYTES
    assert measurement.maximum_active_children == 2
    assert measurement.child_sample_count > 0
    assert measurement.sample_count >= 2
    assert measurement.maximum_gap_seconds <= 0.1
    assert measurement.maximum_within_child_plateau_growth_bytes <= 64 * _MIB


def _paired_call(
    reference: Path,
    comparison: Path,
    consumer: _CountingConsumer,
    *,
    lag_samples: int,
    cancellation: threading.Event | None = None,
) -> PairedAudioCollectionResult:
    duration = float(_PAIRED_MEDIA_SECONDS)
    total_timeout = paired_collection_timeout_seconds(duration, duration)
    reference_limit = paired_output_limit_samples(duration, _PAIRED_SAMPLE_RATE)
    comparison_limit = paired_output_limit_samples(duration, _PAIRED_SAMPLE_RATE)
    assert total_timeout is not None
    assert reference_limit is not None
    assert comparison_limit is not None
    return collect_paired_audio_chunks(
        _paired_decode_argv(reference),
        _paired_decode_argv(comparison),
        chunks=_paired_chunks(),
        lag_samples=lag_samples,
        consumer=consumer,
        reference_limit_samples=reference_limit,
        comparison_limit_samples=comparison_limit,
        total_timeout_seconds=total_timeout,
        cancellation=cancellation,
    )


def test_paired_three_hour_collection_has_flat_rss_plateau(
    paired_long_media: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = paired_long_media
    tracker = _install_tracker(monkeypatch)
    consumer = _CountingConsumer()
    lag_samples = _PAIRED_CHUNK_SECONDS * _PAIRED_SAMPLE_RATE

    result, measurement, elapsed = _measure_call(
        tracker,
        lambda: _paired_call(reference, comparison, consumer, lag_samples=lag_samples),
    )

    assert isinstance(result, PairedAudioCollection)
    _assert_paired_resource_result(
        result, measurement, expected_chunks=360, max_lag_samples=lag_samples
    )
    assert consumer.count == 360
    assert result.reference_facts.emitted_sample_count == 86_400_000
    assert result.comparison_facts.emitted_sample_count == 86_400_000
    assert elapsed < 300
    _print_paired_measurement("paired-three-hour", result, measurement, elapsed)


def test_paired_largest_admitted_lag_stays_within_resource_contract(
    paired_long_media: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    total_samples = _PAIRED_MEDIA_SECONDS * _PAIRED_SAMPLE_RATE
    admitted = plan_audio_chunks(total_samples, total_samples, 247.0)
    assert admitted.lag_samples == 247 * _PAIRED_SAMPLE_RATE
    with pytest.raises(AudioAlignmentError, match="exceeds"):
        plan_audio_chunks(total_samples, total_samples, 248.0)

    reference, comparison = paired_long_media
    tracker = _install_tracker(monkeypatch)
    consumer = _CountingConsumer()

    result, measurement, elapsed = _measure_call(
        tracker,
        lambda: _paired_call(reference, comparison, consumer, lag_samples=admitted.lag_samples),
    )

    assert isinstance(result, PairedAudioCollection)
    _assert_paired_resource_result(
        result,
        measurement,
        expected_chunks=360,
        max_lag_samples=admitted.lag_samples,
    )
    assert consumer.count == 360
    assert elapsed < 300
    _print_paired_measurement("paired-max-lag", result, measurement, elapsed)


def test_paired_mid_run_cancellation_reaps_both_children(
    paired_long_media: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = paired_long_media
    tracker = _install_tracker(monkeypatch)
    cancellation = threading.Event()
    lag_samples = _PAIRED_CHUNK_SECONDS * _PAIRED_SAMPLE_RATE

    class CancelOnFirstChunk(_CountingConsumer):
        def __init__(self) -> None:
            super().__init__()
            self.live_pids_at_cancellation: tuple[int, ...] = ()

        def __call__(self, index: int, reference: Any, window: Any) -> None:
            super().__call__(index, reference, window)
            assert self.count == 1
            self.live_pids_at_cancellation = tracker.active_pids()
            assert len(self.live_pids_at_cancellation) == 2
            cancellation.set()

    consumer = CancelOnFirstChunk()
    started = time.monotonic()
    result = _paired_call(
        reference,
        comparison,
        consumer,
        lag_samples=lag_samples,
        cancellation=cancellation,
    )
    elapsed = time.monotonic() - started

    assert isinstance(result, PairedAudioCollectionFailure)
    assert result.category == "cancelled"
    assert consumer.count == 1
    assert result.reference_cleanup.completed
    assert result.comparison_cleanup.completed
    assert elapsed < 60
    assert tracker.active_pids() == ()
    assert tracker.terminate_requests == 2
    print(
        {
            "case": "paired-cancellation",
            "elapsed_seconds": elapsed,
            "chunks_delivered": consumer.count,
            "live_pids_at_cancellation": consumer.live_pids_at_cancellation,
            "terminate_requests": tracker.terminate_requests,
            "kill_requests": tracker.kill_requests,
        }
    )
