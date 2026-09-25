"""Bounded continuous FFmpeg audio collection."""

from __future__ import annotations

import functools
import math
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
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
_DEFAULT_STALL_TIMEOUT_SECONDS = 30.0
_PAIRED_TIMEOUT_BASE_SECONDS = 120.0
_PAIRED_TIMEOUT_RATE = 0.1
_PAIRED_OUTPUT_HEADROOM_SECONDS = 60.0
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
    "stalled",
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

type PairedSide = Literal["reference", "comparison"]


@dataclass(frozen=True, slots=True)
class PairedAudioCollection:
    """A fully validated paired collection whose delivered pairs are safe to consume.

    ``CollectionFacts.planned_end_sample`` on each side carries that side's output
    limit (``known duration + 60 s``, in samples), not a planned endpoint: the
    paired collector reads to EOF on both sides.
    """

    reference_facts: CollectionFacts
    comparison_facts: CollectionFacts
    reference_cleanup: CollectionCleanup
    comparison_cleanup: CollectionCleanup
    chunks_delivered: int
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class PairedAudioCollectionFailure:
    """A failed paired collection with no usable PCM.

    ``side`` names the child the failure is attributed to, or ``None`` for
    side-independent causes (cancellation, the total timeout, consumer failure).
    Per-side facts and cleanups describe whatever was started; a side that never
    spawned reports an empty completed cleanup. Holds no PCM or exceptions.
    """

    category: CollectionFailureCategory
    side: PairedSide | None
    message: str
    reference_facts: CollectionFacts
    comparison_facts: CollectionFacts
    reference_cleanup: CollectionCleanup
    comparison_cleanup: CollectionCleanup


type PairedAudioCollectionResult = PairedAudioCollection | PairedAudioCollectionFailure


@dataclass(slots=True)
class _FailureSlot:
    lock: threading.Lock = field(default_factory=threading.Lock)
    category: CollectionFailureCategory | None = None
    message: str | None = None
    side: PairedSide | None = None

    def record(
        self,
        category: CollectionFailureCategory,
        message: str,
        *,
        side: PairedSide | None = None,
    ) -> None:
        with self.lock:
            if self.category is None:
                self.category = category
                self.message = _bounded_message(message)
                self.side = side

    def read(self) -> tuple[CollectionFailureCategory | None, str | None, PairedSide | None]:
        with self.lock:
            return self.category, self.message, self.side


type _RecordFailure = Callable[[CollectionFailureCategory, str], None]


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
    record_failure: _RecordFailure,
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
        record_failure("stdout_reader_failed", f"stdout reader failed: {exc}")
    finally:
        done.set()


def _read_stderr(
    stream: BinaryIO,
    capture: _StderrCapture,
    done: threading.Event,
    record_failure: _RecordFailure,
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
        record_failure("stderr_reader_failed", f"stderr reader failed: {exc}")
    finally:
        done.set()


def _start_reader(thread: threading.Thread) -> None:
    """Start one owned reader; kept narrow so startup failure is testable."""
    thread.start()


def _create_reader_infrastructure(
    stdout: BinaryIO,
    stderr: BinaryIO,
    stderr_capture: _StderrCapture,
    record_failure: _RecordFailure,
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
            args=(stdout, chunks, stop, stdout_done, record_failure),
            name="alignment-stdout-reader",
            daemon=True,
        ),
        stderr_thread=threading.Thread(
            target=_read_stderr,
            args=(stderr, stderr_capture, stderr_done, record_failure),
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


def _spawn_child(argv: Sequence[str]) -> subprocess.Popen[bytes]:
    resolved = [str(part) for part in argv]
    resolved[0] = resolve_executable(resolved[0])
    # Explicit argument array, no shell, unbuffered pipes; the default
    # close_fds=True keeps each child's pipe ends private so one child lingering
    # can never hold the other side's stdout open past EOF.
    return subprocess.Popen(  # noqa: S603 - validated explicit argument array
        resolved,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        bufsize=0,
    )


def _close_pipe(stream: BinaryIO, cleanup_failures: list[str]) -> bool:
    try:
        stream.close()
    except Exception as exc:
        cleanup_failures.append(f"pipe close failed: {exc}")
    return stream.closed


def _request_terminate(
    process: subprocess.Popen[bytes],
    cleanup_failures: list[str],
) -> bool:
    """Send terminate to a live child. True when termination was requested."""
    if process.poll() is not None:
        return False
    try:
        process.terminate()
    except (OSError, ProcessLookupError) as exc:
        cleanup_failures.append(f"terminate failed: {exc}")
    return True


def _wait_then_kill(
    process: subprocess.Popen[bytes],
    cleanup_failures: list[str],
) -> bool:
    """Wait the existing terminate bound, then kill after the existing kill bound."""
    if process.poll() is None and not _wait_for_exit(process, _TERMINATE_WAIT_SECONDS):
        try:
            process.kill()
        except (OSError, ProcessLookupError) as exc:
            cleanup_failures.append(f"kill failed: {exc}")
        if process.poll() is None and not _wait_for_exit(process, _KILL_WAIT_SECONDS):
            cleanup_failures.append("process remained live after kill")
        return True
    return False


def _join_started_readers(
    stdout_thread: threading.Thread | None,
    stderr_thread: threading.Thread | None,
    *,
    stdout_started: bool,
    stderr_started: bool,
) -> tuple[bool, bool]:
    # Let readers finish draining an exited child before closing their pipes.
    # Closing first can manufacture a reader failure on otherwise valid output.
    join_deadline = time.monotonic() + _READER_JOIN_SECONDS
    if stdout_started and stdout_thread is not None:
        stdout_thread.join(timeout=max(0.0, join_deadline - time.monotonic()))
    if stderr_started and stderr_thread is not None:
        stderr_thread.join(timeout=max(0.0, join_deadline - time.monotonic()))
    stdout_joined = not stdout_started or (
        stdout_thread is not None and not stdout_thread.is_alive()
    )
    stderr_joined = not stderr_started or (
        stderr_thread is not None and not stderr_thread.is_alive()
    )
    return stdout_joined, stderr_joined


def _summarize_cleanup(
    process: subprocess.Popen[bytes],
    cleanup_failures: list[str],
    *,
    stdout_joined: bool,
    stderr_joined: bool,
    stdout_closed: bool,
    stderr_closed: bool,
    termination_requested: bool,
    kill_requested: bool,
) -> CollectionCleanup:
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
    if failed:
        termination_requested = _request_terminate(process, cleanup_failures)
        if termination_requested:
            kill_requested = _wait_then_kill(process, cleanup_failures)

    stdout_joined, stderr_joined = _join_started_readers(
        stdout_thread,
        stderr_thread,
        stdout_started=stdout_started,
        stderr_started=stderr_started,
    )
    stdout_closed = _close_pipe(stdout, cleanup_failures)
    stderr_closed = _close_pipe(stderr, cleanup_failures)
    return _summarize_cleanup(
        process,
        cleanup_failures,
        stdout_joined=stdout_joined,
        stderr_joined=stderr_joined,
        stdout_closed=stdout_closed,
        stderr_closed=stderr_closed,
        termination_requested=termination_requested,
        kill_requested=kill_requested,
    )


@dataclass(slots=True)
class _SampleStore:
    """Bounded unconsumed-sample buffer over one child's float32 stdout stream.

    ``emitted`` counts every complete sample received (including samples dropped
    below ``floor`` on arrival); ``front`` is the absolute index of the first
    buffered sample and ``count`` how many follow it contiguously. ``floor`` is
    the absolute index below which samples are never needed again: the reference
    side raises it to each chunk start (gap skip) and the comparison side to each
    window start (slide). Buffered samples always lie in ``[floor, emitted)``,
    so the capacity (one read spill for the reference side, which only receives
    when empty; one window plus one spill for the comparison side) is never
    exceeded no matter how far one child lags the other, and retained PCM never
    grows with media duration.
    """

    capacity: int
    store: np.ndarray = field(init=False)
    start: int = field(default=0, init=False)
    count: int = field(default=0, init=False)
    front: int = field(default=0, init=False)
    emitted: int = field(default=0, init=False)
    floor: int = field(default=0, init=False)
    peak_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.store = np.empty(self.capacity, dtype="<f4")

    def evict_before(self, position: int) -> None:
        """Drop buffered samples below ``position`` and raise the floor to it."""
        if position > self.floor:
            self.floor = position
        drop = min(self.count, max(0, self.floor - self.front))
        self.start += drop
        self.count -= drop
        self.front += drop

    def append(self, samples: np.ndarray) -> None:
        size = int(samples.size)
        if size == 0:
            return
        skip = max(0, self.floor - self.emitted)
        self.emitted += size
        if skip >= size:
            return
        if self.count == 0:
            self.front = self.emitted - size + skip
            self.start = 0
        kept = samples[skip:]
        if self.start + self.count + int(kept.size) > self.capacity:
            self.store[0 : self.count] = self.store[self.start : self.start + self.count]
            self.start = 0
        # The fill loops stop pulling once each need is met and the floor keeps
        # buffered samples within one window plus one read spill, so the store
        # always fits after compacting; a miscalculation must fail loudly here
        # rather than silently truncate correlation input.
        if self.start + self.count + int(kept.size) > self.capacity:
            raise RuntimeError("paired sample store overflow")
        self.store[self.start + self.count : self.start + self.count + int(kept.size)] = kept
        self.count += int(kept.size)
        self.peak_count = max(self.peak_count, self.count)

    def consume(self, count: int) -> None:
        take = max(0, min(count, self.count))
        self.start += take
        self.count -= take
        self.front += take

    def view(self) -> np.ndarray:
        return self.store[self.start : self.start + self.count]


@dataclass(slots=True)
class _PairedSide:
    """Live transport state for one child of a paired collection."""

    name: PairedSide
    limit_samples: int
    process: subprocess.Popen[bytes] | None = None
    stdout: BinaryIO | None = None
    stderr: BinaryIO | None = None
    infrastructure: _ReaderInfrastructure | None = None
    stdout_started: bool = False
    stderr_started: bool = False
    stderr_capture: _StderrCapture = field(default_factory=_StderrCapture)
    samples: _SampleStore | None = None
    emitted_bytes: int = 0
    pending: bytes = b""
    eof: bool = False
    termination_requested: bool = False
    kill_requested: bool = False
    cleanup_failures: list[str] = field(default_factory=list[str])


def _cleanup_paired(
    reference: _PairedSide,
    comparison: _PairedSide,
    *,
    failed: bool,
) -> tuple[CollectionCleanup, CollectionCleanup]:
    """Clean both paired children: stops, then terminate-all before any wait/join.

    Terminate reaches every still-running child before any wait or join begins, so
    one hung child can never hold the other one's reaping hostage. Joining readers
    still precedes closing pipes, as in the single-child cleanup.
    """
    for side in (reference, comparison):
        if side.infrastructure is not None:
            side.infrastructure.stop.set()
    if failed:
        for side in (reference, comparison):
            if side.process is not None:
                side.termination_requested = _request_terminate(side.process, side.cleanup_failures)
    cleanups: list[CollectionCleanup] = []
    for side in (reference, comparison):
        if side.process is not None and side.termination_requested:
            side.kill_requested = _wait_then_kill(side.process, side.cleanup_failures)
        cleanups.append(_reap_paired_side(side))
    return cleanups[0], cleanups[1]


def _reap_paired_side(side: _PairedSide) -> CollectionCleanup:
    """Join one paired side's readers and close its pipes after termination."""
    if side.process is None:
        return _empty_cleanup()
    infrastructure = side.infrastructure
    stdout_joined, stderr_joined = _join_started_readers(
        infrastructure.stdout_thread if infrastructure is not None else None,
        infrastructure.stderr_thread if infrastructure is not None else None,
        stdout_started=side.stdout_started,
        stderr_started=side.stderr_started,
    )
    stdout_closed = (
        _close_pipe(side.stdout, side.cleanup_failures) if side.stdout is not None else True
    )
    stderr_closed = (
        _close_pipe(side.stderr, side.cleanup_failures) if side.stderr is not None else True
    )
    return _summarize_cleanup(
        side.process,
        side.cleanup_failures,
        stdout_joined=stdout_joined,
        stderr_joined=stderr_joined,
        stdout_closed=stdout_closed,
        stderr_closed=stderr_closed,
        termination_requested=side.termination_requested,
        kill_requested=side.kill_requested,
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
        process = _spawn_child(argv)
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
                failure.record,
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

        category, _, _ = failure.read()
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

    category, message, _ = failure.read()
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


def _as_usable_duration(value: object) -> float | None:
    """Normalize a probed duration; unusable values become None (refuse)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return float(value)


def paired_collection_timeout_seconds(
    reference_seconds: float | None,
    comparison_seconds: float | None,
) -> float | None:
    """Total-cap seconds for a paired collection: ``120 + 0.1 * max(known)`` (A8).

    Returns None when neither duration is known; the caller maps that to the
    existing ``selected_audio_timeline_unavailable`` refusal. Unusable durations
    (None, non-finite, negative) are ignored, so a garbage probe can only cause
    a refusal, never a shortened or unbounded collection.
    """
    known = [
        duration
        for duration in (
            _as_usable_duration(reference_seconds),
            _as_usable_duration(comparison_seconds),
        )
        if duration is not None
    ]
    if not known:
        return None
    return _PAIRED_TIMEOUT_BASE_SECONDS + _PAIRED_TIMEOUT_RATE * max(known)


def paired_output_limit_samples(
    duration_seconds: float | None,
    sample_rate: int,
) -> int | None:
    """Sanity-limit samples for one paired side: known duration + 60 s (A8).

    Returns None for an unknown or unusable duration; the caller refuses instead
    of collecting.
    """
    duration = _as_usable_duration(duration_seconds)
    if duration is None:
        return None
    total = (duration + _PAIRED_OUTPUT_HEADROOM_SECONDS) * sample_rate
    return math.ceil(total) if math.isfinite(total) else None


def _validated_chunk_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"chunk {label} must be an integer")
    return value


def _validated_limit(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _validated_timeout(value: object, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{label} must be a positive finite number of seconds")
    return float(value)


def _validate_paired_request(
    reference_argv: Sequence[str],
    comparison_argv: Sequence[str],
    chunks: Sequence[tuple[int, int]],
    lag_samples: object,
    consumer: Callable[[int, np.ndarray, np.ndarray], None],
    reference_limit_samples: object,
    comparison_limit_samples: object,
    total_timeout_seconds: object,
    stall_timeout_seconds: object,
) -> tuple[tuple[int, int], ...]:
    """Validate a paired request before spawning anything; raises ValueError."""
    if not reference_argv or not reference_argv[0]:
        raise ValueError("reference_argv must contain a non-empty executable")
    if not comparison_argv or not comparison_argv[0]:
        raise ValueError("comparison_argv must contain a non-empty executable")
    if not chunks:
        raise ValueError("chunks must contain at least one planned chunk")
    planned: list[tuple[int, int]] = []
    for entry in chunks:
        try:
            raw_start, raw_count = entry
        except (TypeError, ValueError) as exc:
            raise ValueError("chunks must hold (reference_start, reference_count) pairs") from exc
        start = _validated_chunk_int(raw_start, label="reference_start")
        count = _validated_chunk_int(raw_count, label="reference_count")
        if start < 0 or count < 1:
            raise ValueError("chunks must cover at least one sample at a non-negative start")
        planned.append((start, count))
    for (previous_start, previous_count), (start, _) in zip(planned, planned[1:], strict=False):
        if start <= previous_start:
            raise ValueError("chunks must be in increasing start order")
        if start < previous_start + previous_count:
            raise ValueError("chunks must not overlap")
    if isinstance(lag_samples, bool) or not isinstance(lag_samples, int) or lag_samples < 0:
        raise ValueError("lag_samples must be a non-negative integer")
    if not callable(consumer):
        raise ValueError("consumer must be callable")
    _validated_limit(reference_limit_samples, label="reference_limit_samples")
    _validated_limit(comparison_limit_samples, label="comparison_limit_samples")
    _validated_timeout(total_timeout_seconds, label="total_timeout_seconds")
    _validated_timeout(stall_timeout_seconds, label="stall_timeout_seconds")
    return tuple(planned)


def _start_paired_side_readers(side: _PairedSide, shared: _FailureSlot) -> bool:
    """Start one side's stdout/stderr readers; False after recording the failure."""
    assert side.stdout is not None and side.stderr is not None
    try:
        side.infrastructure = _create_reader_infrastructure(
            side.stdout,
            side.stderr,
            side.stderr_capture,
            functools.partial(shared.record, side=side.name),
        )
        _start_reader(side.infrastructure.stdout_thread)
        side.stdout_started = True
        _start_reader(side.infrastructure.stderr_thread)
        side.stderr_started = True
    except Exception as exc:
        shared.record(
            "reader_start_failed",
            f"paired audio {side.name} reader setup failed: {exc}",
            side=side.name,
        )
        return False
    return True


def _receive_paired_block(
    side: _PairedSide,
    shared: _FailureSlot,
    *,
    deadline: float,
    stall_timeout_seconds: float,
    cancellation: threading.Event | None,
) -> bytes | None:
    """Wait for one stdout block from ``side`` under the stall/total deadlines.

    Returns the block, or None at EOF (``side.eof`` set) or after recording a
    failure (cancelled, timeout, stalled). At EOF the side's child is reaped
    right away, so a trailing partial float32 sample or a nonzero exit is
    recorded at the earliest point it is known, before the other side can run on.
    """
    infrastructure = side.infrastructure
    assert infrastructure is not None
    last_progress = time.monotonic()
    while True:
        if shared.read()[0] is not None:
            return None
        if cancellation is not None and cancellation.is_set():
            shared.record("cancelled", "paired audio collection was cancelled")
            return None
        now = time.monotonic()
        remaining = deadline - now
        if remaining <= 0:
            shared.record("timeout", "paired audio collection exceeded its total timeout")
            return None
        if now - last_progress >= stall_timeout_seconds:
            shared.record(
                "stalled",
                f"paired audio {side.name} child made no progress for {stall_timeout_seconds} s",
                side=side.name,
            )
            return None
        if infrastructure.stdout_done.is_set() and infrastructure.chunks.empty():
            side.eof = True
            if side.pending:
                shared.record(
                    "partial_float32_sample",
                    f"paired audio {side.name} output ended with "
                    f"{len(side.pending)} trailing byte(s)",
                    side=side.name,
                )
            else:
                _await_exit_after_eof(
                    side,
                    shared,
                    deadline=deadline,
                    stall_timeout_seconds=stall_timeout_seconds,
                    cancellation=cancellation,
                )
            return None
        wait = min(
            _QUEUE_WAIT_SECONDS,
            remaining,
            max(0.0, last_progress + stall_timeout_seconds - now),
        )
        try:
            return infrastructure.chunks.get(timeout=wait)
        except Empty:
            continue


def _ingest_paired_block(
    side: _PairedSide,
    shared: _FailureSlot,
    block: bytes,
    *,
    retain: bool,
) -> np.ndarray | None:
    """Validate one stdout block, count it, and buffer it when retained.

    Every block is checked for finiteness and counted against the side's output
    limit, whether retained or discarded past the last planned chunk (A7a).
    Returns the decoded samples, or None after recording a failure.
    """
    store = side.samples
    assert store is not None
    side.emitted_bytes += len(block)
    payload = side.pending + block
    complete_bytes = len(payload) - len(payload) % _FLOAT32_BYTES
    samples = (
        np.frombuffer(payload[:complete_bytes], dtype="<f4")
        if complete_bytes
        else np.empty(0, dtype="<f4")
    )
    if not bool(np.isfinite(samples).all()):
        shared.record(
            "nonfinite_output",
            f"paired audio {side.name} output contained a non-finite block",
            side=side.name,
        )
        return None
    if store.emitted + int(samples.size) > side.limit_samples:
        shared.record(
            "output_exceeded",
            f"paired audio {side.name} output exceeded its {side.limit_samples}-sample limit",
            side=side.name,
        )
        return None
    side.pending = payload[complete_bytes:]
    if retain:
        store.append(samples)
    else:
        store.emitted += int(samples.size)
    return samples


def _fill_reference_chunk(
    side: _PairedSide,
    shared: _FailureSlot,
    *,
    start: int,
    count: int,
    out: np.ndarray,
    deadline: float,
    stall_timeout_seconds: float,
    cancellation: threading.Event | None,
) -> bool:
    """Assemble reference ``[start, start + count)`` into zeroed ``out``.

    Samples the reference never produced (early EOF, including a chunk starting
    at or beyond EOF) stay zero, which the activity gate treats as inactive.
    Returns False after recording a failure.
    """
    store = side.samples
    assert store is not None
    store.evict_before(start)
    filled = 0
    while filled < count:
        if shared.read()[0] is not None:
            return False
        take = min(store.count, count - filled)
        if take:
            out[filled : filled + take] = store.view()[:take]
            store.consume(take)
            filled += take
            continue
        if side.eof:
            return True
        block = _receive_paired_block(
            side,
            shared,
            deadline=deadline,
            stall_timeout_seconds=stall_timeout_seconds,
            cancellation=cancellation,
        )
        if block is None:
            if shared.read()[0] is not None:
                return False
            continue  # EOF newly observed; the loop re-checks and zero-pads.
        if _ingest_paired_block(side, shared, block, retain=True) is None:
            return False
    return True


def _fill_comparison_need(
    side: _PairedSide,
    shared: _FailureSlot,
    *,
    window_start: int,
    need: int,
    deadline: float,
    stall_timeout_seconds: float,
    cancellation: threading.Event | None,
) -> bool:
    """Pull comparison output until absolute sample ``need`` arrived, or EOF."""
    store = side.samples
    assert store is not None
    store.evict_before(max(window_start, 0))
    while store.emitted < need:
        if shared.read()[0] is not None:
            return False
        if side.eof:
            return True
        block = _receive_paired_block(
            side,
            shared,
            deadline=deadline,
            stall_timeout_seconds=stall_timeout_seconds,
            cancellation=cancellation,
        )
        if block is None:
            if shared.read()[0] is not None:
                return False
            continue  # EOF newly observed; the loop re-checks.
        if _ingest_paired_block(side, shared, block, retain=True) is None:
            return False
    return True


def _assemble_comparison_window(
    side: _PairedSide,
    *,
    window_start: int,
    out: np.ndarray,
) -> None:
    """Copy stream ``[window_start, window_start + out.size)`` into zeroed ``out``.

    Anything outside ``[0, emitted)`` stays zero, which matches U1's
    ``comparison_window`` value for value once float32 samples are viewed as
    float64 (an exact conversion).
    """
    store = side.samples
    assert store is not None
    source_start = max(window_start, store.front, 0)
    source_end = min(window_start + int(out.size), store.emitted)
    if source_end > source_start and store.count:
        out[source_start - window_start : source_end - window_start] = store.view()[
            source_start - store.front : source_end - store.front
        ]


def _drain_paired_tail(
    reference: _PairedSide,
    comparison: _PairedSide,
    shared: _FailureSlot,
    *,
    deadline: float,
    stall_timeout_seconds: float,
    cancellation: threading.Event | None,
) -> None:
    """Read and discard both tails past the last planned chunk, still counted."""
    while not (reference.eof and comparison.eof):
        if shared.read()[0] is not None:
            return
        for side in (reference, comparison):
            if side.eof or shared.read()[0] is not None:
                continue
            block = _receive_paired_block(
                side,
                shared,
                deadline=deadline,
                stall_timeout_seconds=stall_timeout_seconds,
                cancellation=cancellation,
            )
            if block is None:
                continue
            if _ingest_paired_block(side, shared, block, retain=False) is None:
                return


def _await_exit_after_eof(
    side: _PairedSide,
    shared: _FailureSlot,
    *,
    deadline: float,
    stall_timeout_seconds: float,
    cancellation: threading.Event | None,
) -> None:
    """Reap one side whose stdout ended, recording a nonzero exit against it.

    A child that closed stdout but does not exit is the awaited side making no
    progress, so the stall watchdog applies here too (A8).
    """
    process = side.process
    assert process is not None
    wait_started = time.monotonic()
    while process.poll() is None:
        if shared.read()[0] is not None:
            return
        if time.monotonic() - wait_started >= stall_timeout_seconds:
            shared.record(
                "stalled",
                f"paired audio {side.name} child did not exit after its output ended",
                side=side.name,
            )
            return
        if cancellation is not None and cancellation.is_set():
            shared.record("cancelled", "paired audio collection was cancelled")
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            shared.record("timeout", "paired audio collection exceeded its total timeout")
            return
        _wait_for_exit(process, min(_QUEUE_WAIT_SECONDS, remaining))
    if process.returncode != 0:
        shared.record(
            "nonzero_exit",
            f"paired audio {side.name} child exited with status {process.returncode}",
            side=side.name,
        )


def _paired_side_facts(side: _PairedSide, *, started: float) -> CollectionFacts:
    store = side.samples
    return _facts(
        planned_end_sample=side.limit_samples,
        emitted_sample_count=store.emitted if store is not None else 0,
        emitted_byte_count=side.emitted_bytes,
        retained_sample_count=store.peak_count if store is not None else 0,
        stderr_capture=side.stderr_capture,
        started=started,
        returncode=side.process.returncode if side.process is not None else None,
    )


def _paired_failure(
    category: CollectionFailureCategory,
    failure_side: PairedSide | None,
    message: str,
    *,
    reference: _PairedSide,
    comparison: _PairedSide,
    started: float,
    reference_cleanup: CollectionCleanup,
    comparison_cleanup: CollectionCleanup,
) -> PairedAudioCollectionFailure:
    return PairedAudioCollectionFailure(
        category=category,
        side=failure_side,
        message=_bounded_message(message),
        reference_facts=_paired_side_facts(reference, started=started),
        comparison_facts=_paired_side_facts(comparison, started=started),
        reference_cleanup=reference_cleanup,
        comparison_cleanup=comparison_cleanup,
    )


def collect_paired_audio_chunks(
    reference_argv: Sequence[str],
    comparison_argv: Sequence[str],
    *,
    chunks: Sequence[tuple[int, int]],
    lag_samples: int,
    consumer: Callable[[int, np.ndarray, np.ndarray], None],
    reference_limit_samples: int,
    comparison_limit_samples: int,
    total_timeout_seconds: float,
    stall_timeout_seconds: float = _DEFAULT_STALL_TIMEOUT_SECONDS,
    cancellation: threading.Event | None = None,
) -> PairedAudioCollectionResult:
    """Run two prepared FFmpeg recipes concurrently and deliver aligned pairs.

    For each planned ``(reference_start, reference_count)`` chunk, in order, the
    consumer receives ``(index, reference, window)``: ``count`` float32 reference
    samples over ``[start, start + count)`` (zero where the reference produced
    nothing) and ``count + 2 * lag_samples`` float32 comparison samples over
    ``[start - lag, start + count + lag)`` (zero outside the comparison stream),
    equal to U1's ``comparison_window`` value for value. Reference output past
    the last planned chunk is read, counted and limit-checked, then discarded.

    Lockstep: the loop pulls from whichever side the current chunk still needs
    while the other side waits in its bounded queue. That cannot deadlock: each
    child's progress depends only on its own pipe being drained, and the loop
    always drains the side it waits on. The side held back by back-pressure is
    never stall-timed for that. Retained PCM stays bounded independent of media
    duration: per side, one sample store (one read spill for the reference, one
    window plus one spill for the comparison) and one delivery scratch buffer
    (one chunk, one window), plus the bounded pipe queues.

    Delivered arrays are read-only views of reused internal buffers; the
    consumer must not keep them after returning. On a failure result the caller
    must discard everything the consumer accumulated; deliveries cannot be
    undone, so an accumulator is only usable after a success result (A7a).
    """
    planned = _validate_paired_request(
        reference_argv,
        comparison_argv,
        chunks,
        lag_samples,
        consumer,
        reference_limit_samples,
        comparison_limit_samples,
        total_timeout_seconds,
        stall_timeout_seconds,
    )
    reference = _PairedSide(name="reference", limit_samples=reference_limit_samples)
    comparison = _PairedSide(name="comparison", limit_samples=comparison_limit_samples)
    started = time.monotonic()
    deadline = started + float(total_timeout_seconds)
    shared = _FailureSlot()
    cleanups: tuple[CollectionCleanup, CollectionCleanup] | None = None

    # Allocate before spawning so an allocation error leaves nothing to clean.
    # The reference store only receives a block once it is empty, so one read
    # spill bounds it; the comparison store holds one window plus one spill.
    spill = _READ_BYTES // _FLOAT32_BYTES + 1
    max_count = max(count for _, count in planned)
    reference.samples = _SampleStore(spill)
    comparison.samples = _SampleStore(max_count + 2 * lag_samples + spill)
    reference_scratch = np.empty(max_count, dtype="<f4")
    window_scratch = np.empty(max_count + 2 * lag_samples, dtype="<f4")

    if cancellation is not None and cancellation.is_set():
        return _paired_failure(
            "cancelled",
            None,
            "paired audio collection was cancelled",
            reference=reference,
            comparison=comparison,
            started=started,
            reference_cleanup=_empty_cleanup(),
            comparison_cleanup=_empty_cleanup(),
        )

    try:
        try:
            reference.process = _spawn_child(reference_argv)
        except (OSError, ValueError) as exc:
            return _paired_failure(
                "spawn_failed",
                "reference",
                f"paired audio reference child could not start: {exc}",
                reference=reference,
                comparison=comparison,
                started=started,
                reference_cleanup=_empty_cleanup(),
                comparison_cleanup=_empty_cleanup(),
            )
        reference.stdout = cast(BinaryIO, reference.process.stdout)
        reference.stderr = cast(BinaryIO, reference.process.stderr)
        try:
            comparison.process = _spawn_child(comparison_argv)
        except (OSError, ValueError) as exc:
            reference_cleanup, comparison_cleanup = _cleanup_paired(
                reference, comparison, failed=True
            )
            return _paired_failure(
                "spawn_failed",
                "comparison",
                f"paired audio comparison child could not start: {exc}",
                reference=reference,
                comparison=comparison,
                started=started,
                reference_cleanup=reference_cleanup,
                comparison_cleanup=comparison_cleanup,
            )
        comparison.stdout = cast(BinaryIO, comparison.process.stdout)
        comparison.stderr = cast(BinaryIO, comparison.process.stderr)
        if not _start_paired_side_readers(reference, shared) or not _start_paired_side_readers(
            comparison, shared
        ):
            reference_cleanup, comparison_cleanup = _cleanup_paired(
                reference, comparison, failed=True
            )
            category, message, failure_side = shared.read()
            assert category is not None and message is not None
            return _paired_failure(
                category,
                failure_side,
                message,
                reference=reference,
                comparison=comparison,
                started=started,
                reference_cleanup=reference_cleanup,
                comparison_cleanup=comparison_cleanup,
            )

        delivered = 0
        for index, (start, count) in enumerate(planned):
            reference_view = reference_scratch[:count]
            reference_view[:] = 0
            if not _fill_reference_chunk(
                reference,
                shared,
                start=start,
                count=count,
                out=reference_view,
                deadline=deadline,
                stall_timeout_seconds=stall_timeout_seconds,
                cancellation=cancellation,
            ):
                break
            window_start = start - lag_samples
            if not _fill_comparison_need(
                comparison,
                shared,
                window_start=window_start,
                need=start + count + lag_samples,
                deadline=deadline,
                stall_timeout_seconds=stall_timeout_seconds,
                cancellation=cancellation,
            ):
                break
            window_view = window_scratch[: count + 2 * lag_samples]
            window_view[:] = 0
            _assemble_comparison_window(comparison, window_start=window_start, out=window_view)
            reference_view.flags.writeable = False
            window_view.flags.writeable = False
            try:
                consumer(index, reference_view, window_view)
            except Exception as exc:
                shared.record(
                    "consumer_failed",
                    f"paired audio consumer failed: {type(exc).__name__}: {exc}",
                )
            finally:
                reference_view.flags.writeable = True
                window_view.flags.writeable = True
            if time.monotonic() > deadline:
                shared.record(
                    "timeout",
                    "paired audio collection exceeded its total timeout",
                )
            if shared.read()[0] is not None:
                break
            if cancellation is not None and cancellation.is_set():
                shared.record("cancelled", "paired audio collection was cancelled")
                break
            delivered += 1
        if shared.read()[0] is None and delivered == len(planned):
            _drain_paired_tail(
                reference,
                comparison,
                shared,
                deadline=deadline,
                stall_timeout_seconds=stall_timeout_seconds,
                cancellation=cancellation,
            )
        cleanups = _cleanup_paired(reference, comparison, failed=shared.read()[0] is not None)
        reference_cleanup, comparison_cleanup = cleanups
        # Read again after cleanup: a stderr reader can still fail while it is
        # joined, and that must not turn into a success. Nonzero exits were
        # already recorded, per side, when each stream reached EOF.
        category, message, failure_side = shared.read()
        if category is None and not (reference_cleanup.completed and comparison_cleanup.completed):
            category = "cleanup_failed"
            failure_side = "reference" if not reference_cleanup.completed else "comparison"
            message = "paired audio collection cleanup did not complete"
        if category is not None:
            return _paired_failure(
                category,
                failure_side,
                message or category,
                reference=reference,
                comparison=comparison,
                started=started,
                reference_cleanup=reference_cleanup,
                comparison_cleanup=comparison_cleanup,
            )
        return PairedAudioCollection(
            reference_facts=_paired_side_facts(reference, started=started),
            comparison_facts=_paired_side_facts(comparison, started=started),
            reference_cleanup=reference_cleanup,
            comparison_cleanup=comparison_cleanup,
            chunks_delivered=delivered,
            elapsed_seconds=time.monotonic() - started,
        )
    except BaseException:
        # Anything raised in setup, the consumer loop or result building: leave
        # no child or reader behind (cleaning at most once), then propagate.
        if cleanups is None:
            _cleanup_paired(reference, comparison, failed=True)
        raise


__all__ = [
    "AudioSampleInterval",
    "CollectedAudioInterval",
    "CollectionCleanup",
    "CollectionFacts",
    "CollectionFailureCategory",
    "ContinuousAudioCollection",
    "ContinuousAudioCollectionFailure",
    "ContinuousAudioCollectionResult",
    "PairedAudioCollection",
    "PairedAudioCollectionFailure",
    "PairedAudioCollectionResult",
    "PairedSide",
    "collect_continuous_audio",
    "collect_paired_audio_chunks",
    "paired_collection_timeout_seconds",
    "paired_output_limit_samples",
]
