"""Opt-in production resource proof for continuous audio alignment."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import threading
import time
import weakref
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from frame_compare.orchestration import execution, phase_alignment
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    ExecutionState,
    RunArtifacts,
)
from frame_compare.services import (
    alignment,
    alignment_audio,
    alignment_consensus,
    alignment_streaming,
)
from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.alignment_audio import (
    AudioAnalysisBudgetExceeded,
    AudioAnalysisPlan,
    AudioStreamInfo,
    AudioStreamTimeline,
)
from frame_compare.services.alignment_correlation import plan_audio_chunks
from frame_compare.services.alignment_streaming import (
    ContinuousAudioCollection,
    PairedAudioCollection,
    PairedAudioCollectionFailure,
    PairedAudioCollectionResult,
    collect_paired_audio_chunks,
    paired_collection_timeout_seconds,
    paired_output_limit_samples,
)
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig, AlignmentResult
from tests.orchestration.phase_task_helpers import _clip, _context
from tests.services.alignment_request_test_support import alignment_request

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
        self.child_started = threading.Event()

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
            self.child_started.set()
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


def _generate_container(path: Path, *, sample_rate: int, duration_seconds: int) -> None:
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
            f"color=c=black:s=160x90:r=1:d={duration_seconds}",
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=pink:sample_rate={sample_rate}:duration={duration_seconds}:seed=6106",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "ffv1",
            "-c:a",
            "pcm_s16le",
            "-shortest",
            str(path),
        ],
        check=True,
        timeout=120,
    )


@pytest.fixture(scope="module")
def production_pairs(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, tuple[Path, Path]]:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.fail("ffmpeg/ffprobe are required for the opted-in resource gate")
    root = tmp_path_factory.mktemp("alignment-production-resources")
    pairs: dict[str, tuple[Path, Path]] = {}
    for label, rate, duration in (("verification", 44_100, 150), ("long", 8_000, 7_200)):
        reference = root / f"{label}-reference.mkv"
        comparison = root / f"{label}-comparison.mkv"
        _generate_container(reference, sample_rate=rate, duration_seconds=duration)
        shutil.copyfile(reference, comparison)
        pairs[label] = reference, comparison
    return pairs


def _install_tracker(monkeypatch: pytest.MonkeyPatch) -> _ProcessTracker:
    tracker = _ProcessTracker(subprocess.Popen)
    monkeypatch.setattr(alignment_streaming.subprocess, "Popen", tracker.popen)
    return tracker


def _run_pair(
    reference: Path,
    comparison: Path,
    *,
    sample_rate: int,
    generated_dir: Path,
) -> AlignmentResult:
    config = AlignmentConfig(
        sample_rate=sample_rate,
        max_offset_seconds=30,
        cache_results=False,
    )
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=generated_dir,
    )
    return asyncio.run(align_clips_from_request(request, config, reference_fps=Fraction(24)))[0]


def _stream(duration_seconds: int) -> AudioStreamInfo:
    return AudioStreamInfo(
        audio_stream_index=0,
        absolute_stream_index=1,
        codec_name="aac",
        channels=2,
        channel_layout="stereo",
        sample_rate=48_000,
        language="eng",
        is_default=True,
        is_original=False,
        is_commentary=False,
        timeline=AudioStreamTimeline(
            start_time=Fraction(0),
            duration=Fraction(duration_seconds),
            time_base=Fraction(1, 48_000),
            duration_basis="duration_ts",
        ),
    )


def _assert_resource_result(
    result: AlignmentResult,
    measurement: _RssMeasurement,
    *,
    expected_collections: int,
) -> None:
    assert result.applied
    assert result.frame_offset == 0
    assert result.audio_attempt is not None
    attempt = result.audio_attempt
    assert attempt.decision.state == "trusted_automatic"
    assert attempt.decision.primary_reason == "accepted"
    assert attempt.planned_window_count == 5
    assert len(attempt.collection_summaries) == expected_collections
    assert all(summary.elapsed_seconds < 120 for summary in attempt.collection_summaries)
    assert all(summary.cleanup_failure_count == 0 for summary in attempt.collection_summaries)
    assert measurement.peak_incremental_bytes <= _RSS_LIMIT_BYTES
    assert measurement.maximum_active_children == 1
    assert measurement.child_sample_count > 0
    assert measurement.sample_count >= 2
    assert measurement.maximum_gap_seconds <= 0.1


def _print_measurement(
    case: str,
    result: AlignmentResult,
    measurement: _RssMeasurement,
    elapsed: float,
) -> None:
    assert result.audio_attempt is not None
    print(
        {
            "case": case,
            "elapsed_seconds": elapsed,
            "rss": measurement,
            "collections": [
                {
                    "phase": summary.phase,
                    "role": summary.role,
                    "rate": summary.output_rate,
                    "horizon": summary.requested_horizon,
                    "retained_bytes": summary.retained_byte_count,
                    "elapsed_seconds": summary.elapsed_seconds,
                    "end": summary.end_category,
                }
                for summary in result.audio_attempt.collection_summaries
            ],
        }
    )


def test_five_window_48khz_verification_pair_stays_within_resource_contract(
    production_pairs: dict[str, tuple[Path, Path]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = production_pairs["verification"]
    tracker = _install_tracker(monkeypatch)
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    real_collect = alignment_audio.collect_continuous_audio
    discovery_arrays: list[weakref.ReferenceType[Any]] = []

    def observe_phase_lifetime(*args: Any, **kwargs: Any):
        argv = list(args[0])
        audio_filter = argv[argv.index("-af") + 1]
        rate = int(audio_filter.split("aresample=")[1].split(",")[0])
        if rate == 48_000:
            assert discovery_arrays
            assert all(reference() is None for reference in discovery_arrays)
        result = real_collect(*args, **kwargs)
        if rate == 8_000 and isinstance(result, ContinuousAudioCollection):
            discovery_arrays.extend(weakref.ref(interval.samples) for interval in result.intervals)
        return result

    monkeypatch.setattr(alignment_audio, "collect_continuous_audio", observe_phase_lifetime)

    result, measurement, elapsed = _measure_call(
        tracker,
        lambda: _run_pair(
            reference,
            comparison,
            sample_rate=48_000,
            generated_dir=tmp_path,
        ),
    )

    _assert_resource_result(result, measurement, expected_collections=4)
    assert result.audio_attempt is not None
    summaries = result.audio_attempt.collection_summaries
    assert {summary.output_rate for summary in summaries} == {8_000, 48_000}
    retained_by_phase = {
        phase: sum(summary.retained_byte_count for summary in summaries if summary.phase == phase)
        for phase in ("discovery", "verification")
    }
    assert retained_by_phase["discovery"] <= 19_200_000
    assert retained_by_phase["verification"] <= 57_600_240
    assert elapsed < 4 * 120
    assert not list(tmp_path.rglob("*.pcm"))
    assert not list(tmp_path.rglob("*.raw"))
    _print_measurement("verification", result, measurement, elapsed)


def test_two_hour_pair_has_bounded_plateau_and_production_decision(
    production_pairs: dict[str, tuple[Path, Path]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = production_pairs["long"]
    tracker = _install_tracker(monkeypatch)
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)

    result, measurement, elapsed = _measure_call(
        tracker,
        lambda: _run_pair(
            reference,
            comparison,
            sample_rate=8_000,
            generated_dir=tmp_path,
        ),
    )

    _assert_resource_result(result, measurement, expected_collections=2)
    assert len(measurement.within_child_plateau_sample_counts) == 2
    assert all(count >= 6 for count in measurement.within_child_plateau_sample_counts)
    assert measurement.maximum_within_child_plateau_growth_bytes <= 64 * _MIB
    assert result.audio_attempt is not None
    summaries = result.audio_attempt.collection_summaries
    assert sum(summary.retained_byte_count for summary in summaries) <= 19_200_000
    assert all(summary.requested_horizon >= 7_200 * 8_000 - 30 * 8_000 for summary in summaries)
    assert elapsed < 2 * 120
    assert reference.stat().st_size >= 100 * _MIB
    assert comparison.stat().st_size >= 100 * _MIB
    assert not list(tmp_path.rglob("*.pcm"))
    assert not list(tmp_path.rglob("*.raw"))
    _print_measurement("two-hour", result, measurement, elapsed)


def test_maximum_admitted_plan_and_rejected_neighbors_are_explicit() -> None:
    maximum = alignment_audio.plan_audio_analysis(
        _stream(7_200),
        _stream(7_200),
        config=AlignmentConfig(sample_rate=48_000, max_offset_seconds=102),
    )

    assert isinstance(maximum, AudioAnalysisPlan)
    assert maximum.sample_rate == 4_000
    assert maximum.peak_fft_points <= 2_097_152
    assert maximum.total_fft_points <= 16_777_216
    assert maximum.verification_reserved_samples <= 15_000_000
    assert maximum.score_evaluations_per_window <= 512
    assert maximum.scored_positions <= 536_870_912

    neighbors = (
        (
            AlignmentConfig(sample_rate=48_000, window_length_seconds=32),
            "requested_rate_scoring_exceeds_peak_budget",
        ),
        (
            AlignmentConfig(
                sample_rate=48_000,
                window_length_seconds=30,
                window_stride_seconds=30,
                minimum_valid_windows=6,
            ),
            "requested_rate_scoring_exceeds_total_budget",
        ),
        (
            AlignmentConfig(
                max_offset_seconds=1,
                window_length_seconds=1,
                window_stride_seconds=1,
                minimum_valid_windows=17,
            ),
            "minimum_valid_windows_exceeds_work_budget",
        ),
    )
    for config, reason in neighbors:
        rejected = alignment_audio.plan_audio_analysis(
            _stream(180),
            _stream(180),
            config=config,
        )
        assert isinstance(rejected, AudioAnalysisBudgetExceeded)
        assert rejected.reason == reason


def test_outer_task_cancellation_reaps_the_active_production_child(
    production_pairs: dict[str, tuple[Path, Path]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, comparison = production_pairs["long"]
    tracker = _install_tracker(monkeypatch)
    config = AlignmentConfig(sample_rate=8_000, max_offset_seconds=30, cache_results=True)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )

    async def cancel_active_alignment() -> float:
        task = asyncio.create_task(
            align_clips_from_request(request, config, reference_fps=Fraction(24))
        )
        started = time.monotonic()
        assert await asyncio.to_thread(tracker.child_started.wait, 30)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return time.monotonic() - started

    elapsed = asyncio.run(cancel_active_alignment())

    print(
        {
            "case": "outer-cancellation",
            "elapsed_seconds": elapsed,
            "active": tracker.active_pids(),
            "terminate_requests": tracker.terminate_requests,
            "kill_requests": tracker.kill_requests,
        }
    )
    assert elapsed < 10
    assert tracker.active_pids() == ()
    assert tracker.returncodes()
    assert all(returncode is not None and returncode != 0 for returncode in tracker.returncodes())
    assert tracker.terminate_requests == 1
    if elapsed >= 2:
        assert tracker.kill_requests == 1
    assert not (tmp_path / "alignment_diagnostics").exists()
    assert not (tmp_path / "shared-alignment" / "alignment_reuse.toml").exists()


def test_timed_alignment_phase_cancellation_has_no_application_side_effects(
    production_pairs: dict[str, tuple[Path, Path]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference, first_comparison = production_pairs["long"]
    _, next_comparison = production_pairs["verification"]
    tracker = _install_tracker(monkeypatch)

    def probed_clip(path: Path, *, label: str, num_frames: int):
        clip = _clip(path, label=label, num_frames=num_frames)
        stat = path.stat()
        return replace(
            clip,
            probe=replace(
                clip.probe,
                fingerprint=replace(
                    clip.probe.fingerprint,
                    size_bytes=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                ),
            ),
        )

    ctx = _context(
        tmp_path,
        comparisons=[
            probed_clip(first_comparison, label="First", num_frames=7_200 * 24),
            probed_clip(next_comparison, label="Next", num_frames=150 * 24),
        ],
    )
    ctx.reference = probed_clip(reference, label="Reference", num_frames=7_200 * 24)
    ctx.analysis_clip = ctx.reference
    ctx.config = ctx.config.model_copy(
        update={
            "audio_alignment": ctx.config.audio_alignment.model_copy(
                update={
                    "sample_rate": 8_000,
                    "max_offset_seconds": 30,
                    "use_vsview": True,
                    "cache_results": True,
                    "correlation_mode": "raw_fft",
                    "preprocessing_mode": "none",
                    "channel_strategy": "mono_downmix",
                    "window_length_seconds": 0.0,
                    "window_stride_seconds": 0.0,
                    "minimum_valid_windows": 1,
                    "consensus_minimum_ratio": 1.0,
                    "refinement_mode": "disabled",
                    "refinement_sample_rate": None,
                    "reference_stream": None,
                    "comparison_streams": {},
                }
            )
        }
    )
    monkeypatch.setattr(alignment_consensus, "_AUTOMATIC_AUTHORITY_HELD", False)
    state = ExecutionState(artifacts=RunArtifacts(), selected_frames=[0, 1])
    applied_outputs: list[object] = []
    diagnostic_writes: list[object] = []
    review_launches: list[object] = []
    cache_writes: list[object] = []

    def observe_call(bucket: list[object]):
        def observe(*args: Any, **kwargs: Any) -> None:
            bucket.append((args, kwargs))

        return observe

    monkeypatch.setattr(execution, "apply_phase_output", observe_call(applied_outputs))
    monkeypatch.setattr(alignment, "write_alignment_diagnostic", observe_call(diagnostic_writes))
    monkeypatch.setattr(alignment, "maybe_launch_alignment_vsview", observe_call(review_launches))
    monkeypatch.setattr(alignment, "save_reusable_offsets", observe_call(cache_writes))
    original_reference = ctx.reference
    original_comparisons = list(ctx.comparisons)
    phase_outputs: list[object] = []

    async def run_real_phase(phase_ctx: RunContext) -> AlignPhaseOutput:
        output = await phase_alignment.run_align_phase(
            phase_ctx,
            selected_frames=state.selected_frames,
        )
        phase_outputs.append(output)
        return output

    phase = execution._create_timed_phase(
        "align",
        "align",
        None,
        run_real_phase,
        state,
        time.monotonic,
        state.phase_timings,
        state.warnings,
    )

    async def cancel_active_phase() -> float:
        async def execute_phase() -> None:
            await phase.execute(ctx)

        task = asyncio.create_task(execute_phase())
        started = time.monotonic()
        assert await asyncio.to_thread(tracker.child_started.wait, 30)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return time.monotonic() - started

    elapsed = asyncio.run(cancel_active_phase())

    print(
        {
            "case": "timed-phase-cancellation",
            "elapsed_seconds": elapsed,
            "active": tracker.active_pids(),
            "terminate_requests": tracker.terminate_requests,
            "kill_requests": tracker.kill_requests,
        }
    )
    assert elapsed < 10
    assert tracker.active_pids() == ()
    assert tracker.returncodes()
    assert all(returncode is not None and returncode != 0 for returncode in tracker.returncodes())
    assert tracker.terminate_requests == 1
    if elapsed >= 2:
        assert tracker.kill_requests == 1
    assert all(str(next_comparison) not in command for command in tracker.commands())
    assert phase_outputs == []
    assert applied_outputs == []
    assert diagnostic_writes == []
    assert review_launches == []
    assert cache_writes == []
    assert ctx.reference is original_reference
    assert ctx.comparisons == original_comparisons
    assert state.selected_frames == [0, 1]
    assert state.warnings == []
    assert state.phase_timings["align"] >= 0
    assert ctx.workspace.alignment_diagnostics_dir is not None
    assert not ctx.workspace.alignment_diagnostics_dir.exists()
    assert not (ctx.workspace.shared_alignment_cache_dir / "alignment_reuse.toml").exists()


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
    """Real FFmpeg decode to 8 kHz mono float32, as U3 will request it."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        str(_PAIRED_SAMPLE_RATE),
        "-f",
        "f32le",
        "-",
    ]


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
    consumer = _CountingConsumer()
    lag_samples = _PAIRED_CHUNK_SECONDS * _PAIRED_SAMPLE_RATE

    def cancel_soon() -> None:
        assert tracker.child_started.wait(timeout=60)
        time.sleep(2.0)
        cancellation.set()

    waiter = threading.Thread(target=cancel_soon, daemon=True)
    waiter.start()
    started = time.monotonic()
    result = _paired_call(
        reference,
        comparison,
        consumer,
        lag_samples=lag_samples,
        cancellation=cancellation,
    )
    elapsed = time.monotonic() - started
    waiter.join(timeout=10)

    assert isinstance(result, PairedAudioCollectionFailure)
    assert result.category == "cancelled"
    assert result.reference_cleanup.completed
    assert result.comparison_cleanup.completed
    assert elapsed < 60
    assert tracker.active_pids() == ()
    assert tracker.terminate_requests == 2
    print(
        {
            "case": "paired-cancellation",
            "elapsed_seconds": elapsed,
            "terminate_requests": tracker.terminate_requests,
            "kill_requests": tracker.kill_requests,
        }
    )
