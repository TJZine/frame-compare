"""Bounded continuous FFmpeg audio collection."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from typing import BinaryIO, Literal, cast

import numpy as np

from frame_compare.utils.subproc import resolve_executable

_FLOAT32_BYTES = np.dtype("<f4").itemsize
_READ_BYTES = 65_536
_QUEUE_CAPACITY = 8
_STDERR_LIMIT_BYTES = 65_536
_QUEUE_WAIT_SECONDS = 0.1
_DEFAULT_TIMEOUT_SECONDS = 120.0
_TERMINATE_WAIT_SECONDS = 2.0
_KILL_WAIT_SECONDS = 2.0
_READER_JOIN_SECONDS = 1.0
_MAX_INTERVALS = 16
_MAX_RETAINED_SAMPLES = sys.maxsize // _FLOAT32_BYTES
_MESSAGE_LIMIT = 512

type CollectionEnd = Literal["planned_end_reached", "observed_eof"]
type CollectionFailureCategory = Literal[
    "spawn_failed",
    "reader_start_failed",
    "stdout_reader_failed",
    "stderr_reader_failed",
    "timeout",
    "cancelled",
    "partial_float32_sample",
    "output_exceeded",
    "nonfinite_output",
    "nonzero_exit",
    "consumer_failed",
    "cleanup_failed",
]


@dataclass(frozen=True, slots=True)
class AudioSampleInterval:
    """One admitted half-open interval on the continuous output sample grid."""

    start_sample: int
    sample_count: int

    @property
    def end_sample(self) -> int:
        return self.start_sample + self.sample_count


@dataclass(frozen=True, slots=True)
class CollectedAudioInterval:
    """Initialized read-only samples for one planned interval."""

    start_sample: int
    planned_sample_count: int
    actual_sample_count: int
    samples: np.ndarray


@dataclass(frozen=True, slots=True)
class CollectionCleanup:
    """Observed subprocess and reader cleanup state."""

    process_exited: bool
    stdout_reader_joined: bool
    stderr_reader_joined: bool
    stdout_pipe_closed: bool
    stderr_pipe_closed: bool
    termination_requested: bool
    kill_requested: bool
    failure: str | None = None

    @property
    def completed(self) -> bool:
        return (
            self.process_exited
            and self.stdout_reader_joined
            and self.stderr_reader_joined
            and self.stdout_pipe_closed
            and self.stderr_pipe_closed
            and self.failure is None
        )


@dataclass(frozen=True, slots=True)
class CollectionFacts:
    """Bounded scalar transport facts retained for success or failure."""

    planned_end_sample: int
    emitted_sample_count: int
    emitted_byte_count: int
    retained_sample_count: int
    stderr_byte_count: int
    stderr_retained: bytes
    stderr_truncated: bool
    elapsed_seconds: float
    returncode: int | None


@dataclass(frozen=True, slots=True)
class ContinuousAudioCollection:
    """A fully validated collection whose interval arrays are safe to consume."""

    intervals: tuple[CollectedAudioInterval, ...]
    end: CollectionEnd
    observed_eof_sample: int | None
    facts: CollectionFacts
    cleanup: CollectionCleanup


@dataclass(frozen=True, slots=True)
class ContinuousAudioCollectionFailure:
    """A failed collection with no usable PCM."""

    category: CollectionFailureCategory
    message: str
    facts: CollectionFacts
    cleanup: CollectionCleanup


type ContinuousAudioCollectionResult = ContinuousAudioCollection | ContinuousAudioCollectionFailure


@dataclass(slots=True)
class _FailureSlot:
    lock: threading.Lock = field(default_factory=threading.Lock)
    category: CollectionFailureCategory | None = None
    message: str | None = None

    def record(self, category: CollectionFailureCategory, message: str) -> None:
        with self.lock:
            if self.category is None:
                self.category = category
                self.message = _bounded_message(message)

    def read(self) -> tuple[CollectionFailureCategory | None, str | None]:
        with self.lock:
            return self.category, self.message


@dataclass(slots=True)
class _StderrCapture:
    retained: bytearray = field(default_factory=bytearray)
    byte_count: int = 0
    truncated: bool = False


@dataclass(slots=True)
class _ReaderInfrastructure:
    chunks: Queue[bytes]
    stop: threading.Event
    stdout_done: threading.Event
    stderr_done: threading.Event
    stdout_thread: threading.Thread
    stderr_thread: threading.Thread


def _bounded_message(message: str) -> str:
    return message[:_MESSAGE_LIMIT]


def _read_stdout(
    stream: BinaryIO,
    chunks: Queue[bytes],
    stop: threading.Event,
    done: threading.Event,
    failure: _FailureSlot,
) -> None:
    try:
        while not stop.is_set():
            chunk = stream.read(_READ_BYTES)
            if not chunk:
                return
            while not stop.is_set():
                try:
                    chunks.put(chunk, timeout=_QUEUE_WAIT_SECONDS)
                    break
                except Full:
                    continue
    except Exception as exc:
        failure.record("stdout_reader_failed", f"stdout reader failed: {exc}")
    finally:
        done.set()


def _read_stderr(
    stream: BinaryIO,
    capture: _StderrCapture,
    done: threading.Event,
    failure: _FailureSlot,
) -> None:
    try:
        while True:
            chunk = stream.read(_READ_BYTES)
            if not chunk:
                return
            capture.byte_count += len(chunk)
            remaining = _STDERR_LIMIT_BYTES - len(capture.retained)
            if remaining > 0:
                capture.retained.extend(chunk[:remaining])
            if capture.byte_count > _STDERR_LIMIT_BYTES:
                capture.truncated = True
    except Exception as exc:
        failure.record("stderr_reader_failed", f"stderr reader failed: {exc}")
    finally:
        done.set()


def _start_reader(thread: threading.Thread) -> None:
    """Start one owned reader; kept narrow so startup failure is testable."""
    thread.start()


def _create_reader_infrastructure(
    stdout: BinaryIO,
    stderr: BinaryIO,
    stderr_capture: _StderrCapture,
    failure: _FailureSlot,
) -> _ReaderInfrastructure:
    chunks: Queue[bytes] = Queue(maxsize=_QUEUE_CAPACITY)
    stop = threading.Event()
    stdout_done = threading.Event()
    stderr_done = threading.Event()
    return _ReaderInfrastructure(
        chunks=chunks,
        stop=stop,
        stdout_done=stdout_done,
        stderr_done=stderr_done,
        stdout_thread=threading.Thread(
            target=_read_stdout,
            args=(stdout, chunks, stop, stdout_done, failure),
            name="alignment-stdout-reader",
            daemon=True,
        ),
        stderr_thread=threading.Thread(
            target=_read_stderr,
            args=(stderr, stderr_capture, stderr_done, failure),
            name="alignment-stderr-reader",
            daemon=True,
        ),
    )


def _copy_intersections(
    samples: np.ndarray,
    *,
    chunk_start_sample: int,
    intervals: Sequence[AudioSampleInterval],
    buffers: Sequence[np.ndarray],
    initialized: list[int],
) -> None:
    chunk_end_sample = chunk_start_sample + int(samples.size)
    for index, interval in enumerate(intervals):
        start = max(chunk_start_sample, interval.start_sample)
        end = min(chunk_end_sample, interval.end_sample)
        if start >= end:
            continue
        source_start = start - chunk_start_sample
        count = end - start
        destination_start = start - interval.start_sample
        buffers[index][destination_start : destination_start + count] = samples[
            source_start : source_start + count
        ]
        initialized[index] = max(initialized[index], destination_start + count)


def _wait_for_exit(
    process: subprocess.Popen[bytes],
    timeout_seconds: float,
) -> bool:
    try:
        process.wait(timeout=max(0.0, timeout_seconds))
    except subprocess.TimeoutExpired:
        return False
    return True


def _close_pipe(stream: BinaryIO, cleanup_failures: list[str]) -> bool:
    try:
        stream.close()
    except Exception as exc:
        cleanup_failures.append(f"pipe close failed: {exc}")
    return stream.closed


def _cleanup(
    process: subprocess.Popen[bytes],
    stdout: BinaryIO,
    stderr: BinaryIO,
    stdout_thread: threading.Thread | None,
    stderr_thread: threading.Thread | None,
    *,
    stdout_started: bool,
    stderr_started: bool,
    failed: bool,
    stop: threading.Event | None,
) -> CollectionCleanup:
    cleanup_failures: list[str] = []
    termination_requested = False
    kill_requested = False

    if stop is not None:
        stop.set()
    if failed and process.poll() is None:
        termination_requested = True
        try:
            process.terminate()
        except (OSError, ProcessLookupError) as exc:
            cleanup_failures.append(f"terminate failed: {exc}")
        if process.poll() is None and not _wait_for_exit(process, _TERMINATE_WAIT_SECONDS):
            kill_requested = True
            try:
                process.kill()
            except (OSError, ProcessLookupError) as exc:
                cleanup_failures.append(f"kill failed: {exc}")
            if process.poll() is None and not _wait_for_exit(process, _KILL_WAIT_SECONDS):
                cleanup_failures.append("process remained live after kill")

    # Let readers finish draining an exited child before closing their pipes.
    # Closing first can manufacture a reader failure on otherwise valid output.
    join_deadline = time.monotonic() + _READER_JOIN_SECONDS
    if stdout_started and stdout_thread is not None:
        stdout_thread.join(timeout=max(0.0, join_deadline - time.monotonic()))
    if stderr_started and stderr_thread is not None:
        stderr_thread.join(timeout=max(0.0, join_deadline - time.monotonic()))

    stdout_closed = _close_pipe(stdout, cleanup_failures)
    stderr_closed = _close_pipe(stderr, cleanup_failures)

    stdout_joined = not stdout_started or (
        stdout_thread is not None and not stdout_thread.is_alive()
    )
    stderr_joined = not stderr_started or (
        stderr_thread is not None and not stderr_thread.is_alive()
    )
    process_exited = process.poll() is not None
    if not process_exited:
        cleanup_failures.append("process remained live after cleanup")
    if not stdout_joined:
        cleanup_failures.append("stdout reader remained live after cleanup")
    if not stderr_joined:
        cleanup_failures.append("stderr reader remained live after cleanup")
    failure = _bounded_message("; ".join(cleanup_failures)) if cleanup_failures else None
    return CollectionCleanup(
        process_exited=process_exited,
        stdout_reader_joined=stdout_joined,
        stderr_reader_joined=stderr_joined,
        stdout_pipe_closed=stdout_closed,
        stderr_pipe_closed=stderr_closed,
        termination_requested=termination_requested,
        kill_requested=kill_requested,
        failure=failure,
    )


def _empty_cleanup(*, failure: str | None = None) -> CollectionCleanup:
    return CollectionCleanup(
        process_exited=True,
        stdout_reader_joined=True,
        stderr_reader_joined=True,
        stdout_pipe_closed=True,
        stderr_pipe_closed=True,
        termination_requested=False,
        kill_requested=False,
        failure=failure,
    )


def _facts(
    *,
    planned_end_sample: int,
    emitted_sample_count: int,
    emitted_byte_count: int,
    retained_sample_count: int,
    stderr_capture: _StderrCapture,
    started: float,
    returncode: int | None,
) -> CollectionFacts:
    return CollectionFacts(
        planned_end_sample=planned_end_sample,
        emitted_sample_count=emitted_sample_count,
        emitted_byte_count=emitted_byte_count,
        retained_sample_count=retained_sample_count,
        stderr_byte_count=stderr_capture.byte_count,
        stderr_retained=bytes(stderr_capture.retained),
        stderr_truncated=stderr_capture.truncated,
        elapsed_seconds=time.monotonic() - started,
        returncode=returncode,
    )


def _validate_request(
    argv: Sequence[str],
    intervals: Sequence[AudioSampleInterval],
    planned_end_sample: int,
    max_retained_samples: int,
    timeout_seconds: float,
) -> None:
    if not argv or not argv[0]:
        raise ValueError("argv must contain a non-empty executable")
    if not 1 <= len(intervals) <= _MAX_INTERVALS:
        raise ValueError(f"interval count must be between 1 and {_MAX_INTERVALS}")
    if planned_end_sample <= 0:
        raise ValueError("planned_end_sample must be positive")
    if (
        isinstance(max_retained_samples, bool)
        or max_retained_samples <= 0
        or max_retained_samples > _MAX_RETAINED_SAMPLES
    ):
        raise ValueError(f"max_retained_samples must be in (0, {_MAX_RETAINED_SAMPLES}]")
    if not 0 < timeout_seconds <= _DEFAULT_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be in (0, {_DEFAULT_TIMEOUT_SECONDS}]")
    retained_samples = 0
    for interval in intervals:
        if interval.start_sample < 0 or interval.sample_count <= 0:
            raise ValueError("intervals must be non-empty and non-negative")
        if interval.sample_count > _MAX_RETAINED_SAMPLES:
            raise ValueError("interval sample count exceeds the platform allocation limit")
        if interval.end_sample > planned_end_sample:
            raise ValueError("intervals must not extend beyond planned_end_sample")
        retained_samples += interval.sample_count
        if retained_samples > max_retained_samples:
            raise ValueError("planned interval capacity exceeds max_retained_samples")


def collect_continuous_audio(
    argv: Sequence[str],
    intervals: Sequence[AudioSampleInterval],
    *,
    planned_end_sample: int,
    max_retained_samples: int,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    cancellation: threading.Event | None = None,
) -> ContinuousAudioCollectionResult:
    """Run one prepared FFmpeg recipe and retain only admitted sample intervals.

    The caller owns recipe construction, including its final sample endpoint. This
    owner resolves the executable, bounds transport storage, validates the complete
    float32 payload, and returns PCM only after child and reader cleanup succeeds.
    """
    _validate_request(
        argv,
        intervals,
        planned_end_sample,
        max_retained_samples,
        timeout_seconds,
    )
    requested_intervals = tuple(intervals)
    started = time.monotonic()
    deadline = started + timeout_seconds
    stderr_capture = _StderrCapture()
    failure = _FailureSlot()
    emitted_bytes = 0
    emitted_samples = 0
    retained_samples = 0
    buffers: list[np.ndarray] = []
    initialized = [0 for _ in requested_intervals]
    pending = b""

    if cancellation is not None and cancellation.is_set():
        facts = _facts(
            planned_end_sample=planned_end_sample,
            emitted_sample_count=0,
            emitted_byte_count=0,
            retained_sample_count=0,
            stderr_capture=stderr_capture,
            started=started,
            returncode=None,
        )
        return ContinuousAudioCollectionFailure(
            category="cancelled",
            message="continuous audio collection was cancelled",
            facts=facts,
            cleanup=_empty_cleanup(),
        )

    try:
        resolved_argv = [str(part) for part in argv]
        resolved_argv[0] = resolve_executable(resolved_argv[0])
        process = subprocess.Popen(  # noqa: S603 - validated explicit argument array
            resolved_argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            bufsize=0,
        )
    except (OSError, ValueError) as exc:
        facts = _facts(
            planned_end_sample=planned_end_sample,
            emitted_sample_count=0,
            emitted_byte_count=0,
            retained_sample_count=0,
            stderr_capture=stderr_capture,
            started=started,
            returncode=None,
        )
        return ContinuousAudioCollectionFailure(
            category="spawn_failed",
            message=_bounded_message(f"collector process could not start: {exc}"),
            facts=facts,
            cleanup=_empty_cleanup(),
        )

    stdout = cast(BinaryIO, process.stdout)
    stderr = cast(BinaryIO, process.stderr)
    infrastructure: _ReaderInfrastructure | None = None
    stdout_started = False
    stderr_started = False

    try:
        try:
            infrastructure = _create_reader_infrastructure(
                stdout,
                stderr,
                stderr_capture,
                failure,
            )
            buffers = [
                np.empty(interval.sample_count, dtype="<f4") for interval in requested_intervals
            ]
            _start_reader(infrastructure.stdout_thread)
            stdout_started = True
            _start_reader(infrastructure.stderr_thread)
            stderr_started = True
        except Exception as exc:
            failure.record("reader_start_failed", f"collector reader setup failed: {exc}")

        while failure.read()[0] is None:
            assert infrastructure is not None
            if cancellation is not None and cancellation.is_set():
                failure.record("cancelled", "continuous audio collection was cancelled")
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure.record("timeout", "continuous audio collection timed out")
                break
            if infrastructure.stdout_done.is_set() and infrastructure.chunks.empty():
                break
            try:
                chunk = infrastructure.chunks.get(timeout=min(_QUEUE_WAIT_SECONDS, remaining))
            except Empty:
                continue

            payload = pending + chunk
            complete_bytes = len(payload) - len(payload) % _FLOAT32_BYTES
            if complete_bytes:
                complete = np.frombuffer(payload[:complete_bytes], dtype="<f4")
                try:
                    _copy_intersections(
                        complete,
                        chunk_start_sample=emitted_samples,
                        intervals=requested_intervals,
                        buffers=buffers,
                        initialized=initialized,
                    )
                except Exception as exc:
                    failure.record("consumer_failed", f"audio collector consumer failed: {exc}")
                    break
                emitted_samples += int(complete.size)
            emitted_bytes += len(chunk)
            if emitted_samples > planned_end_sample:
                failure.record(
                    "output_exceeded",
                    "FFmpeg output exceeded the planned sample endpoint",
                )
                break
            pending = payload[complete_bytes:]

        if failure.read()[0] is None and pending:
            failure.record(
                "partial_float32_sample",
                f"FFmpeg output ended with {len(pending)} trailing byte(s)",
            )

        while failure.read()[0] is None and process.poll() is None:
            if cancellation is not None and cancellation.is_set():
                failure.record("cancelled", "continuous audio collection was cancelled")
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure.record("timeout", "continuous audio collection timed out")
                break
            _wait_for_exit(process, min(_QUEUE_WAIT_SECONDS, remaining))

        category, _ = failure.read()
        cleanup = _cleanup(
            process,
            stdout,
            stderr,
            infrastructure.stdout_thread if infrastructure is not None else None,
            infrastructure.stderr_thread if infrastructure is not None else None,
            stdout_started=stdout_started,
            stderr_started=stderr_started,
            failed=category is not None,
            stop=infrastructure.stop if infrastructure is not None else None,
        )
    except BaseException:
        _cleanup(
            process,
            stdout,
            stderr,
            infrastructure.stdout_thread if infrastructure is not None else None,
            infrastructure.stderr_thread if infrastructure is not None else None,
            stdout_started=stdout_started,
            stderr_started=stderr_started,
            failed=True,
            stop=infrastructure.stop if infrastructure is not None else None,
        )
        raise

    category, message = failure.read()
    if category is None and process.returncode != 0:
        category = "nonzero_exit"
        message = f"FFmpeg exited with status {process.returncode}"
    if category is None and not cleanup.completed:
        category = "cleanup_failed"
        message = "continuous audio collection cleanup did not complete"

    if category is None:
        for count, buffer in zip(initialized, buffers, strict=True):
            if count and not bool(np.isfinite(buffer[:count]).all()):
                category = "nonfinite_output"
                message = "FFmpeg output contained non-finite retained samples"
                break

    retained_samples = sum(initialized)
    facts = _facts(
        planned_end_sample=planned_end_sample,
        emitted_sample_count=emitted_samples,
        emitted_byte_count=emitted_bytes,
        retained_sample_count=retained_samples,
        stderr_capture=stderr_capture,
        started=started,
        returncode=process.returncode,
    )
    if category is not None:
        buffers.clear()
        return ContinuousAudioCollectionFailure(
            category=category,
            message=message or category,
            facts=facts,
            cleanup=cleanup,
        )

    collected: list[CollectedAudioInterval] = []
    for interval, count, buffer in zip(requested_intervals, initialized, buffers, strict=True):
        buffer.flags.writeable = False
        samples = buffer[:count]
        collected.append(
            CollectedAudioInterval(
                start_sample=interval.start_sample,
                planned_sample_count=interval.sample_count,
                actual_sample_count=count,
                samples=samples,
            )
        )
    end: CollectionEnd
    observed_eof: int | None
    if emitted_samples == planned_end_sample:
        end = "planned_end_reached"
        observed_eof = None
    else:
        end = "observed_eof"
        observed_eof = emitted_samples
    return ContinuousAudioCollection(
        intervals=tuple(collected),
        end=end,
        observed_eof_sample=observed_eof,
        facts=facts,
        cleanup=cleanup,
    )


__all__ = [
    "AudioSampleInterval",
    "CollectedAudioInterval",
    "CollectionCleanup",
    "CollectionFacts",
    "CollectionFailureCategory",
    "ContinuousAudioCollection",
    "ContinuousAudioCollectionFailure",
    "ContinuousAudioCollectionResult",
    "collect_continuous_audio",
]
