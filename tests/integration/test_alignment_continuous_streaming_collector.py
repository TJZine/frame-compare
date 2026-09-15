"""Test-only feasibility spike for continuous origin-based audio collection."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import time
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from typing import BinaryIO, Literal, cast

import numpy as np
import pytest

from frame_compare.services.alignment_audio import (
    AudioAnalysisPlan,
    AudioStreamInfo,
    extract_audio_window,
    plan_audio_analysis,
    select_reference_audio_stream,
)
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.runtime_contract import media_runtime_fingerprint, runtime_kind
from tests.integration.alignment_oracle import (
    compare_with_oracle,
    continuous_decode,
    continuous_decode_argv,
    deterministic_signal,
    recipe_identity,
    sha256_file,
    write_pcm_wave,
)
from tests.integration.test_alignment_continuous_decode_oracle import _mux_audio

_OUTPUT_SAMPLE_RATE = 8000
_REQUESTED_OUTPUT_SAMPLE_RATE = 48000
_FLOAT32_BYTES = np.dtype("<f4").itemsize
_READ_CHUNK_BYTES = 64 * 1024
_STDERR_CHUNK_BYTES = 4096
_STDERR_CAPTURE_LIMIT = 64 * 1024
_PIPE_QUEUE_SIZE = 8
_PROCESS_CLEANUP_TIMEOUT_SECONDS = 2.0
_READER_JOIN_TIMEOUT_SECONDS = 2.0
_LONG_SOURCE_DEFAULT_SECONDS = 3 * 60 * 60
_LONG_SOURCE_GENERATION_TIMEOUT_SECONDS = 900.0
_LONG_SOURCE_DECODE_TIMEOUT_SECONDS = 900.0
_LONG_SOURCE_WINDOW_LENGTH_SECONDS = 2.0
_LONG_SOURCE_ENV = "FRAME_COMPARE_CONTINUOUS_COLLECTOR_LONG"
_LONG_SOURCE_SECONDS_ENV = "FRAME_COMPARE_CONTINUOUS_COLLECTOR_LONG_SECONDS"
_LONG_SOURCE_TIMEOUT_ENV = "FRAME_COMPARE_CONTINUOUS_COLLECTOR_TIMEOUT_SECONDS"
_EVIDENCE_ENV = "FRAME_COMPARE_P6_EVIDENCE_PATH"


@dataclass(frozen=True, slots=True)
class _SampleInterval:
    start_sample: int
    sample_count: int

    @property
    def end_sample(self) -> int:
        return self.start_sample + self.sample_count


@dataclass(slots=True)
class _StderrCapture:
    total_bytes: int = 0
    truncated: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class _CollectorResult:
    retained: tuple[np.ndarray, ...]
    total_output_bytes: int
    total_output_samples: int
    max_retained_bytes: int
    wall_clock_seconds: float
    returncode: int | None
    timed_out: bool
    cancelled: bool
    termination_requested: bool
    kill_requested: bool
    cleanup_completed: bool
    stderr_bytes: int
    stderr_truncated: bool
    error: str | None


def _read_stdout(
    stream: BinaryIO,
    chunks: Queue[bytes | None],
    stop: threading.Event,
) -> None:
    """Read bounded chunks without letting a full decode accumulate in memory."""
    try:
        while not stop.is_set():
            chunk = stream.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            while not stop.is_set():
                try:
                    chunks.put(chunk, timeout=0.1)
                    break
                except Full:
                    continue
    finally:
        while not stop.is_set():
            try:
                chunks.put(None, timeout=0.1)
                break
            except Full:
                continue


def _drain_stderr(stream: BinaryIO, capture: _StderrCapture) -> None:
    """Drain stderr fully while retaining only bounded diagnostic counters."""
    try:
        while True:
            chunk = stream.read(_STDERR_CHUNK_BYTES)
            if not chunk:
                break
            capture.total_bytes += len(chunk)
            if capture.total_bytes > _STDERR_CAPTURE_LIMIT:
                capture.truncated = True
    except OSError as exc:
        capture.error = f"stderr reader failed: {exc}"


def _retain_chunk(
    payload: bytes,
    *,
    chunk_start_sample: int,
    chunk_sample_count: int,
    intervals: Sequence[_SampleInterval],
    buffers: list[bytearray],
) -> int:
    """Copy only interval intersections from one decoded output chunk."""
    chunk_end_sample = chunk_start_sample + chunk_sample_count
    for index, interval in enumerate(intervals):
        start_sample = max(chunk_start_sample, interval.start_sample)
        end_sample = min(chunk_end_sample, interval.end_sample)
        if start_sample >= end_sample:
            continue
        start_byte = (start_sample - chunk_start_sample) * _FLOAT32_BYTES
        end_byte = (end_sample - chunk_start_sample) * _FLOAT32_BYTES
        buffers[index].extend(payload[start_byte:end_byte])
    return sum(len(buffer) for buffer in buffers)


def _collect_continuous_windows(
    media: Path,
    stream: AudioStreamInfo,
    intervals: Sequence[_SampleInterval],
    *,
    sample_rate: int,
    timeout_seconds: float,
    cancel_after_samples: int | None = None,
) -> _CollectorResult:
    """Decode one stream from origin and retain only the requested sample intervals."""
    if not intervals:
        raise ValueError("continuous collector requires at least one interval")
    if timeout_seconds <= 0:
        raise ValueError("continuous collector timeout must be positive")
    if sample_rate not in (_OUTPUT_SAMPLE_RATE, _REQUESTED_OUTPUT_SAMPLE_RATE):
        raise ValueError("continuous collector supports only 8 kHz and 48 kHz evidence")
    if cancel_after_samples is not None and cancel_after_samples <= 0:
        raise ValueError("continuous collector cancellation point must be positive")
    if any(interval.start_sample < 0 or interval.sample_count <= 0 for interval in intervals):
        raise ValueError("continuous collector intervals must be non-empty and non-negative")

    buffers = [bytearray() for _ in intervals]
    chunks: Queue[bytes | None] = Queue(maxsize=_PIPE_QUEUE_SIZE)
    stop = threading.Event()
    stderr_capture = _StderrCapture()
    process = subprocess.Popen(  # noqa: S603 - fixed test-only FFmpeg argv
        continuous_decode_argv(
            media,
            stream,
            sample_rate=sample_rate,
            channel_strategy="mono_downmix",
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_pipe = process.stdout
    stderr_pipe = process.stderr
    stdout_thread = threading.Thread(
        target=_read_stdout,
        args=(stdout_pipe, chunks, stop),
        name="continuous-collector-stdout",
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_drain_stderr,
        args=(stderr_pipe, stderr_capture),
        name="continuous-collector-stderr",
        daemon=True,
    )
    started = time.monotonic()
    stdout_thread.start()
    stderr_thread.start()

    total_output_bytes = 0
    total_output_samples = 0
    max_retained_bytes = 0
    pending = b""
    stdout_finished = False
    timed_out = False
    cancelled = False
    termination_requested = False
    kill_requested = False
    error: str | None = None

    try:
        while not stdout_finished:
            remaining = timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                timed_out = True
                error = "collector_timeout"
                break
            try:
                chunk = chunks.get(timeout=min(remaining, 0.25))
            except Empty:
                continue
            if chunk is None:
                stdout_finished = True
                continue

            total_output_bytes += len(chunk)
            payload = pending + chunk
            complete_bytes = len(payload) - len(payload) % _FLOAT32_BYTES
            if complete_bytes:
                sample_count = complete_bytes // _FLOAT32_BYTES
                max_retained_bytes = max(
                    max_retained_bytes,
                    _retain_chunk(
                        payload[:complete_bytes],
                        chunk_start_sample=total_output_samples,
                        chunk_sample_count=sample_count,
                        intervals=intervals,
                        buffers=buffers,
                    ),
                )
                total_output_samples += sample_count
            pending = payload[complete_bytes:]
            if cancel_after_samples is not None and total_output_samples >= cancel_after_samples:
                cancelled = True
                error = "collector_cancelled"
                break

        if not timed_out and not cancelled:
            if pending:
                error = "partial_float32_sample"
            elif not stdout_finished:
                error = "stdout_reader_stopped_without_eof"
    finally:
        force_stop = timed_out or cancelled or not stdout_finished
        if process.poll() is None and force_stop:
            termination_requested = True
            with suppress(ProcessLookupError):
                process.terminate()

        try:
            process.wait(timeout=_PROCESS_CLEANUP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            error = error or "collector_process_wait_timeout"
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    process.terminate()
                termination_requested = True
            try:
                process.wait(timeout=_PROCESS_CLEANUP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                if process.poll() is None:
                    kill_requested = True
                    with suppress(ProcessLookupError):
                        process.kill()
                try:
                    process.wait(timeout=_PROCESS_CLEANUP_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    error = error or "collector_process_kill_timeout"

        stop.set()
        stdout_thread.join(timeout=_READER_JOIN_TIMEOUT_SECONDS)
        stderr_thread.join(timeout=_READER_JOIN_TIMEOUT_SECONDS)
        if stdout_thread.is_alive() or stderr_thread.is_alive():
            with suppress(OSError):
                stdout_pipe.close()
            with suppress(OSError):
                stderr_pipe.close()
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)
        else:
            stdout_pipe.close()
            stderr_pipe.close()

        if stderr_capture.error is not None:
            error = error or stderr_capture.error
        if process.returncode not in (None, 0) and not (timed_out or cancelled):
            error = error or f"ffmpeg_exit_{process.returncode}"

    retained = tuple(np.frombuffer(buffer, dtype=np.dtype("<f4")) for buffer in buffers)
    cleanup_completed = (
        process.poll() is not None and not stdout_thread.is_alive() and not stderr_thread.is_alive()
    )
    return _CollectorResult(
        retained=retained,
        total_output_bytes=total_output_bytes,
        total_output_samples=total_output_samples,
        max_retained_bytes=max_retained_bytes,
        wall_clock_seconds=time.monotonic() - started,
        returncode=process.returncode,
        timed_out=timed_out,
        cancelled=cancelled,
        termination_requested=termination_requested,
        kill_requested=kill_requested,
        cleanup_completed=cleanup_completed,
        stderr_bytes=stderr_capture.total_bytes,
        stderr_truncated=stderr_capture.truncated,
        error=error,
    )


def _intervals_for_role(
    plan: AudioAnalysisPlan,
    role: Literal["reference", "comparison"],
) -> tuple[_SampleInterval, ...]:
    if role == "reference":
        return tuple(
            _SampleInterval(spec.reference_start_sample, spec.reference_sample_count)
            for spec in plan.windows
        )
    return tuple(
        _SampleInterval(spec.comparison_start_sample, spec.comparison_sample_count)
        for spec in plan.windows
    )


def _fully_observable_intervals(
    plan: AudioAnalysisPlan,
    role: Literal["reference", "comparison"],
    *,
    max_interval_count: int | None = None,
) -> tuple[_SampleInterval, ...]:
    """Keep a pre-end grid while excluding AAC metadata-padding endpoints."""
    intervals = _intervals_for_role(plan, role)
    assert len(intervals) > 1
    intervals = intervals[:-1]
    if max_interval_count is not None:
        intervals = intervals[:max_interval_count]
    return intervals


def _plan_for_media(
    media: Path,
    *,
    window_length_seconds: float,
    window_stride_seconds: float = 0.0,
    output_sample_rate: int = _OUTPUT_SAMPLE_RATE,
) -> tuple[AudioStreamInfo, AudioAnalysisPlan]:
    stream = select_reference_audio_stream(media)
    plan = plan_audio_analysis(
        stream,
        stream,
        config=AlignmentConfig(
            cache_results=False,
            sample_rate=output_sample_rate,
            max_offset_seconds=1.0,
            window_length_seconds=window_length_seconds,
            window_stride_seconds=window_stride_seconds,
        ),
    )
    assert isinstance(plan, AudioAnalysisPlan)
    assert plan.sample_rate == output_sample_rate
    return stream, plan


def _source_record(
    media: Path,
    stream: AudioStreamInfo,
    *,
    output_sample_rate: int,
) -> dict[str, object]:
    return {
        "media_sha256": sha256_file(media),
        "codec": stream.codec_name,
        "input_sample_rate": stream.sample_rate,
        "stream_start_seconds": float(stream.timeline.start_time),
        "duration_seconds": (
            float(stream.timeline.duration) if stream.timeline.duration is not None else None
        ),
        "duration_basis": stream.timeline.duration_basis,
        "output_sample_rate": output_sample_rate,
    }


def _plan_record(
    plan: AudioAnalysisPlan,
    intervals: Sequence[_SampleInterval],
) -> dict[str, object]:
    return {
        "sample_rate": plan.sample_rate,
        "requested_sample_rate": plan.requested_sample_rate,
        "interval_count": len(intervals),
        "intervals": [
            {
                "start_sample": interval.start_sample,
                "expected_count": interval.sample_count,
            }
            for interval in intervals
        ],
        "peak_fft_points": plan.peak_fft_points,
        "total_fft_points": plan.total_fft_points,
    }


def _collector_record(
    result: _CollectorResult,
    intervals: Sequence[_SampleInterval],
    comparisons: Sequence[dict[str, object]],
) -> dict[str, object]:
    expected_counts = [interval.sample_count for interval in intervals]
    returned_counts = [int(samples.size) for samples in result.retained]
    return {
        "planned_interval_count": len(intervals),
        "expected_counts": expected_counts,
        "returned_counts": returned_counts,
        "counts_correct": returned_counts == expected_counts,
        "total_output_bytes": result.total_output_bytes,
        "total_output_samples": result.total_output_samples,
        "max_retained_bytes": result.max_retained_bytes,
        "planned_retained_bytes": sum(expected_counts) * _FLOAT32_BYTES,
        "wall_clock_decode_seconds": result.wall_clock_seconds,
        "comparisons": list(comparisons),
        "process": {
            "exit_code": result.returncode,
            "timed_out": result.timed_out,
            "cancelled": result.cancelled,
            "termination_requested": result.termination_requested,
            "kill_requested": result.kill_requested,
            "cleanup_completed": result.cleanup_completed,
            "stderr_bytes_drained": result.stderr_bytes,
            "stderr_capture_truncated": result.stderr_truncated,
            "error": result.error,
        },
    }


def _collect_against_oracle(
    media: Path,
    stream: AudioStreamInfo,
    intervals: Sequence[_SampleInterval],
    *,
    sample_rate: int,
    timeout_seconds: float,
) -> tuple[_CollectorResult, list[dict[str, object]]]:
    with continuous_decode(
        media,
        stream,
        sample_rate=sample_rate,
        channel_strategy="mono_downmix",
    ) as oracle:
        result = _collect_continuous_windows(
            media,
            stream,
            intervals,
            sample_rate=sample_rate,
            timeout_seconds=timeout_seconds,
        )
        comparisons: list[dict[str, object]] = []
        for interval, actual in zip(intervals, result.retained, strict=True):
            comparison = compare_with_oracle(
                actual,
                oracle,
                start_sample=interval.start_sample,
                sample_count=interval.sample_count,
            )
            comparisons.append(
                {
                    "start_sample": interval.start_sample,
                    "expected_count": comparison.oracle_count,
                    "returned_count": comparison.bounded_count,
                    "measured_lag_samples": comparison.measured_lag,
                    "correlation": comparison.correlation,
                    "maximum_absolute_delta": comparison.maximum_absolute_delta,
                    "equal_samples": np.array_equal(
                        actual,
                        np.asarray(
                            oracle[
                                interval.start_sample : interval.start_sample
                                + interval.sample_count
                            ]
                        ),
                    ),
                }
            )
    return result, comparisons


def _bounded_oracle_record(
    media: Path,
    stream: AudioStreamInfo,
    *,
    sample_rate: int,
    start_sample: int,
    sample_count: int,
) -> dict[str, object]:
    bounded = extract_audio_window(
        media,
        stream,
        sample_rate=sample_rate,
        start_sample=start_sample,
        sample_count=sample_count,
        channel_strategy="mono_downmix",
    )
    with continuous_decode(
        media,
        stream,
        sample_rate=sample_rate,
        channel_strategy="mono_downmix",
    ) as oracle:
        comparison = compare_with_oracle(
            bounded,
            oracle,
            start_sample=start_sample,
            sample_count=sample_count,
        )
    return {
        "sample_rate": sample_rate,
        "start_sample": start_sample,
        "requested_count": sample_count,
        "bounded_count": comparison.bounded_count,
        "oracle_count": comparison.oracle_count,
        "measured_lag_samples": comparison.measured_lag,
        "correlation": comparison.correlation,
        "maximum_absolute_delta": comparison.maximum_absolute_delta,
    }


def _assert_success(
    result: _CollectorResult,
    intervals: Sequence[_SampleInterval],
    comparisons: Sequence[dict[str, object]],
) -> None:
    expected_counts = [interval.sample_count for interval in intervals]
    assert result.error is None
    assert result.returncode == 0
    assert not result.timed_out
    assert not result.cancelled
    assert result.cleanup_completed
    assert [int(samples.size) for samples in result.retained] == expected_counts
    assert result.max_retained_bytes == sum(expected_counts) * _FLOAT32_BYTES
    assert all(item["equal_samples"] is True for item in comparisons)
    assert all(item["measured_lag_samples"] == 0 for item in comparisons)


def _record_evidence(section: str, payload: dict[str, object]) -> None:
    """Optionally merge scalar evidence for a selected native/runtime run."""
    destination = os.environ.get(_EVIDENCE_ENV)
    if not destination:
        return
    path = Path(destination)
    if path.exists() and path.stat().st_size:
        evidence = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    else:
        evidence = {
            "schema_version": 1,
            "purpose": "p6_continuous_streaming_collector_scalar_evidence",
            "environment": {
                "platform": platform.platform(),
                "runtime_kind": runtime_kind(),
                "alignment_runtime_fingerprint": media_runtime_fingerprint("alignment"),
                "ffmpeg": _version_line("ffmpeg"),
                "ffprobe": _version_line("ffprobe"),
            },
            "experiment": {
                "production_changed": False,
                "public_contract_changed": False,
                "output_sample_rate": _OUTPUT_SAMPLE_RATE,
                "requested_rate_grid": [
                    _OUTPUT_SAMPLE_RATE,
                    _REQUESTED_OUTPUT_SAMPLE_RATE,
                ],
                "collector_argv_recipe": recipe_identity(
                    {
                        "source": "<selected-media>",
                        "argv": continuous_decode_argv(
                            Path("<selected-media>"),
                            AudioStreamInfo(
                                audio_stream_index=0,
                                absolute_stream_index=0,
                                codec_name=None,
                                channels=1,
                                channel_layout="mono",
                                sample_rate=48000,
                                language=None,
                                is_default=True,
                                is_original=False,
                                is_commentary=False,
                            ),
                            sample_rate=_OUTPUT_SAMPLE_RATE,
                            channel_strategy="mono_downmix",
                        ),
                    }
                ),
                "retention_policy": "incremental fixed-size chunks; interval intersections only",
                "peak_rss": {
                    "status": "unavailable",
                    "bytes": None,
                    "reason": (
                        "portable combined parent/child peak RSS requires platform-specific "
                        "sampling or a new dependency; no approximation recorded"
                    ),
                },
            },
            "sections": {},
        }
    sections = cast(dict[str, object], evidence["sections"])
    sections[section] = payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _version_line(executable: str) -> str:
    process = subprocess.run(  # noqa: S603 - fixed test evidence executable
        [executable, "-version"],
        capture_output=True,
        check=True,
        text=True,
        timeout=10,
    )
    return process.stdout.splitlines()[0]


def _encode_synthetic_aac(path: Path, *, duration_seconds: int) -> list[str]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        (f"aevalsrc=0.22*sin(2*PI*(173+5*t)*t)+0.15*sin(2*PI*997*t):s=48000:d={duration_seconds}"),
        "-ac",
        "1",
        "-ar",
        "48000",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        str(path),
    ]
    timeout = _LONG_SOURCE_GENERATION_TIMEOUT_SECONDS if duration_seconds >= 3600 else 120.0
    run_subprocess(command, timeout_seconds=timeout)
    return command


def _long_duration_seconds() -> int:
    raw = os.environ.get(_LONG_SOURCE_SECONDS_ENV)
    if raw is None:
        return _LONG_SOURCE_DEFAULT_SECONDS
    value = int(raw)
    if value < 3600:
        raise ValueError(f"{_LONG_SOURCE_SECONDS_ENV} must be at least one hour")
    return value


def _long_timeout_seconds() -> float:
    raw = os.environ.get(_LONG_SOURCE_TIMEOUT_ENV)
    if raw is None:
        return _LONG_SOURCE_DECODE_TIMEOUT_SECONDS
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{_LONG_SOURCE_TIMEOUT_ENV} must be positive")
    return value


def test_tracked_scalar_evidence_records_collector_scope() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "alignment_oracle" / "p6-results.json"
    raw = path.read_text(encoding="utf-8")
    evidence = json.loads(raw)
    assert evidence["schema_version"] == 1
    assert evidence["purpose"] == "p6_continuous_streaming_collector_scalar_evidence"
    assert evidence["experiment"]["production_changed"] is False
    assert evidence["experiment"]["public_contract_changed"] is False
    assert evidence["experiment"]["peak_rss"]["status"] == "unavailable"
    assert evidence["experiment"]["requested_rate_grid"] == [8000, 48000]
    assert "positive_start_aac_48k_native" in evidence["sections"]
    assert (
        evidence["sections"]["long_compressed_traversal_native"]["source"]["output_sample_rate"]
        == 48000
    )
    assert (
        evidence["sections"]["docker_focused_cases"]["cancellation_cleanup"]["kill_requested"]
        is True
    )
    assert evidence["limitations"]["endpoint_handling"]["status"] == "unresolved"
    assert evidence["limitations"]["retention_and_memory"]["combined_parent_child_peak_rss"] == (
        "Unavailable; no combined RSS claim is made."
    )
    assert "/Users/" not in raw
    assert "raw_samples" not in raw


@pytest.mark.integration
def test_continuous_collector_short_control_matches_oracle(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    wave_path = tmp_path / "control.wav"
    media = tmp_path / "control.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=20260915, sample_rate=48000, duration_seconds=12),
        sample_rate=48000,
    )
    _mux_audio(media, wave_path, source_rate=48000, codec="pcm")
    stream, plan = _plan_for_media(
        media,
        window_length_seconds=0.25,
        window_stride_seconds=3.0,
        output_sample_rate=_OUTPUT_SAMPLE_RATE,
    )
    intervals = _intervals_for_role(plan, "reference")
    result, comparisons = _collect_against_oracle(
        media,
        stream,
        intervals,
        sample_rate=_OUTPUT_SAMPLE_RATE,
        timeout_seconds=180.0,
    )
    _assert_success(result, intervals, comparisons)
    _record_evidence(
        "short_deterministic_control",
        {
            "source": _source_record(
                media,
                stream,
                output_sample_rate=_OUTPUT_SAMPLE_RATE,
            ),
            "plan": _plan_record(plan, intervals),
            "collector": _collector_record(result, intervals, comparisons),
            "retained_windows_equal_continuous_oracle": True,
        },
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("output_sample_rate", "section", "collector_key", "window_length_seconds"),
    [
        pytest.param(
            _OUTPUT_SAMPLE_RATE,
            "positive_start_aac",
            "collector_8k",
            0.256,
            id="8k",
        ),
        pytest.param(
            _REQUESTED_OUTPUT_SAMPLE_RATE,
            "positive_start_aac_48k",
            "collector_48k",
            2048 / _REQUESTED_OUTPUT_SAMPLE_RATE,
            id="48k",
        ),
    ],
)
def test_continuous_collector_repairs_positive_start_aac_grid(
    tmp_path: Path,
    require_ffmpeg: None,
    output_sample_rate: int,
    section: str,
    collector_key: str,
    window_length_seconds: float,
) -> None:
    source_rate = 44100
    wave_path = tmp_path / "positive-start.wav"
    media = tmp_path / "positive-start.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=9201, sample_rate=source_rate, duration_seconds=12),
        sample_rate=source_rate,
    )
    _mux_audio(
        media,
        wave_path,
        source_rate=source_rate,
        codec="aac",
        start_seconds=2,
    )
    stream, plan = _plan_for_media(
        media,
        window_length_seconds=window_length_seconds,
        window_stride_seconds=4.0,
        output_sample_rate=output_sample_rate,
    )
    intervals = _fully_observable_intervals(
        plan,
        "reference",
        max_interval_count=3,
    )
    result, comparisons = _collect_against_oracle(
        media,
        stream,
        intervals,
        sample_rate=output_sample_rate,
        timeout_seconds=180.0,
    )
    _assert_success(result, intervals, comparisons)
    baseline = _bounded_oracle_record(
        media,
        stream,
        sample_rate=48000,
        start_sample=0,
        sample_count=2048,
    )
    _record_evidence(
        section,
        {
            "source": _source_record(
                media,
                stream,
                output_sample_rate=output_sample_rate,
            ),
            "plan": _plan_record(plan, intervals),
            "metadata_padding_endpoint_excluded": True,
            "pre_end_grid_selection": "first three pre-end windows only",
            "independent_seek_baseline_48k": baseline,
            collector_key: _collector_record(result, intervals, comparisons),
            "collector_retained_windows_equal_continuous_oracle": True,
        },
    )


@pytest.mark.integration
def test_continuous_collector_repairs_late_aac_window_grid(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    source_rate = 48000
    wave_path = tmp_path / "late-aac.wav"
    media = tmp_path / "late-aac.mkv"
    write_pcm_wave(
        wave_path,
        deterministic_signal(seed=48000 + 8000 + 1, sample_rate=source_rate, duration_seconds=12),
        sample_rate=source_rate,
    )
    _mux_audio(media, wave_path, source_rate=source_rate, codec="aac")
    stream, plan = _plan_for_media(
        media,
        window_length_seconds=0.512,
        window_stride_seconds=4.0,
        output_sample_rate=_OUTPUT_SAMPLE_RATE,
    )
    intervals = _fully_observable_intervals(plan, "reference")
    result, comparisons = _collect_against_oracle(
        media,
        stream,
        intervals,
        sample_rate=_OUTPUT_SAMPLE_RATE,
        timeout_seconds=180.0,
    )
    _assert_success(result, intervals, comparisons)
    late = intervals[-1]
    baseline = _bounded_oracle_record(
        media,
        stream,
        sample_rate=_OUTPUT_SAMPLE_RATE,
        start_sample=late.start_sample,
        sample_count=late.sample_count,
    )
    _record_evidence(
        "ordinary_late_aac",
        {
            "source": _source_record(
                media,
                stream,
                output_sample_rate=_OUTPUT_SAMPLE_RATE,
            ),
            "plan": _plan_record(plan, intervals),
            "metadata_padding_endpoint_excluded": True,
            "late_interval_index": len(intervals) - 1,
            "independent_seek_baseline": baseline,
            "collector_8k": _collector_record(result, intervals, comparisons),
            "collector_retained_windows_equal_continuous_oracle": True,
        },
    )


@pytest.mark.integration
def test_continuous_collector_cancellation_reaps_ffmpeg(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    media = tmp_path / "cancellation.m4a"
    command = _encode_synthetic_aac(media, duration_seconds=30)
    stream, plan = _plan_for_media(
        media,
        window_length_seconds=0.0,
        output_sample_rate=_OUTPUT_SAMPLE_RATE,
    )
    intervals = _intervals_for_role(plan, "reference")
    result = _collect_continuous_windows(
        media,
        stream,
        intervals,
        sample_rate=_OUTPUT_SAMPLE_RATE,
        timeout_seconds=60.0,
        cancel_after_samples=8192,
    )
    assert result.cancelled
    assert not result.timed_out
    assert result.cleanup_completed
    assert result.error == "collector_cancelled"
    assert result.total_output_samples >= 8192
    assert (
        result.max_retained_bytes
        <= sum(interval.sample_count for interval in intervals) * _FLOAT32_BYTES
    )
    _record_evidence(
        "cancellation_cleanup",
        {
            "source": _source_record(
                media,
                stream,
                output_sample_rate=_OUTPUT_SAMPLE_RATE,
            ),
            "generation_recipe_sha256": recipe_identity(command),
            "plan": _plan_record(plan, intervals),
            "collector": _collector_record(result, intervals, []),
            "cleanup_proven": result.cleanup_completed,
        },
    )


@pytest.mark.integration
@pytest.mark.slow
def test_continuous_collector_three_hour_aac_traversal(
    tmp_path: Path,
    require_ffmpeg: None,
) -> None:
    if os.environ.get(_LONG_SOURCE_ENV) != "1":
        pytest.skip(f"set {_LONG_SOURCE_ENV}=1 to run the long traversal evidence case")
    duration_seconds = _long_duration_seconds()
    media = tmp_path / "long-aac.m4a"
    command = _encode_synthetic_aac(media, duration_seconds=duration_seconds)
    stream, plan = _plan_for_media(
        media,
        window_length_seconds=_LONG_SOURCE_WINDOW_LENGTH_SECONDS,
        output_sample_rate=_REQUESTED_OUTPUT_SAMPLE_RATE,
    )
    intervals = _intervals_for_role(plan, "reference")
    result = _collect_continuous_windows(
        media,
        stream,
        intervals,
        sample_rate=_REQUESTED_OUTPUT_SAMPLE_RATE,
        timeout_seconds=_long_timeout_seconds(),
    )
    expected_counts = [interval.sample_count for interval in intervals]
    assert result.error is None
    assert result.returncode == 0
    assert result.cleanup_completed
    assert [int(samples.size) for samples in result.retained] == expected_counts
    assert result.max_retained_bytes == sum(expected_counts) * _FLOAT32_BYTES
    _record_evidence(
        "long_compressed_traversal",
        {
            "generation_recipe_sha256": recipe_identity(command),
            "source": _source_record(
                media,
                stream,
                output_sample_rate=_REQUESTED_OUTPUT_SAMPLE_RATE,
            ),
            "plan": _plan_record(plan, intervals),
            "collector": _collector_record(result, intervals, []),
            "metadata_padding_endpoint_excluded": False,
            "oracle_comparison": "not_run; three-hour output exceeds the existing 256 MiB oracle cap",
            "pair_decode": {
                "measured": False,
                "source_decode_count": 1,
                "pair_wall_clock_seconds": None,
                "note": "only one continuous source traversal was measured; reference/comparison pair timing was not measured",
            },
            "configured_decode_timeout_seconds": _long_timeout_seconds(),
            "duration_selection": {
                "requested_seconds": duration_seconds,
                "target_seconds": _LONG_SOURCE_DEFAULT_SECONDS,
                "used_fallback": duration_seconds != _LONG_SOURCE_DEFAULT_SECONDS,
            },
        },
    )
