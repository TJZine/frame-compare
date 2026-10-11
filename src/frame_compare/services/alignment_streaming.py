"""Bounded paired FFmpeg audio collection for whole-track alignment."""

from __future__ import annotations

import functools
import math
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from typing import BinaryIO, cast

import numpy as np

from frame_compare.utils.alignment_evidence import AudioPairSide, CollectionFailureCategory
from frame_compare.utils.subproc import resolve_executable

_FLOAT32_BYTES = np.dtype("<f4").itemsize
_READ_BYTES = 65_536
_QUEUE_CAPACITY = 8
_STDERR_LIMIT_BYTES = 65_536
_QUEUE_WAIT_SECONDS = 0.1
_TERMINATE_WAIT_SECONDS = 2.0
_KILL_WAIT_SECONDS = 2.0
_READER_JOIN_SECONDS = 1.0
_DEFAULT_STALL_TIMEOUT_SECONDS = 30.0
_PAIRED_TIMEOUT_BASE_SECONDS = 120.0
_PAIRED_TIMEOUT_RATE = 0.1
_PAIRED_OUTPUT_HEADROOM_SECONDS = 60.0
_MESSAGE_LIMIT = 512


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
    side: AudioPairSide | None
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
    side: AudioPairSide | None = None

    def record(
        self,
        category: CollectionFailureCategory,
        message: str,
        *,
        side: AudioPairSide | None = None,
    ) -> None:
        with self.lock:
            if self.category is None:
                self.category = category
                self.message = _bounded_message(message)
                self.side = side

    def read(self) -> tuple[CollectionFailureCategory | None, str | None, AudioPairSide | None]:
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


@dataclass(frozen=True, slots=True)
class _RunContext:
    """Frozen run facts shared by both children of one paired collection."""

    shared: _FailureSlot
    deadline: float
    stall_timeout_seconds: float
    cancellation: threading.Event | None


@dataclass(slots=True)
class _ChildStream:
    """Live transport state for one child of a paired collection.

    Built with its name, argv, output limit, sample store and the frozen run
    context; owns the process, pipes, readers, pending bytes, EOF flag and
    cleanup state.
    """

    name: AudioPairSide
    argv: Sequence[str]
    limit_samples: int
    samples: _SampleStore
    context: _RunContext
    process: subprocess.Popen[bytes] | None = None
    stdout: BinaryIO | None = None
    stderr: BinaryIO | None = None
    infrastructure: _ReaderInfrastructure | None = None
    stdout_started: bool = False
    stderr_started: bool = False
    stderr_capture: _StderrCapture = field(default_factory=_StderrCapture)
    emitted_bytes: int = 0
    pending: bytes = b""
    eof: bool = False
    termination_requested: bool = False
    kill_requested: bool = False
    cleanup_failures: list[str] = field(default_factory=list[str])

    def spawn(self) -> None:
        """Start the child and capture its pipes; raises OSError or ValueError."""
        self.process = _spawn_child(self.argv)
        self.stdout = cast(BinaryIO, self.process.stdout)
        self.stderr = cast(BinaryIO, self.process.stderr)

    def start_readers(self) -> bool:
        """Start this side's stdout/stderr readers; False after recording the failure."""
        assert self.stdout is not None and self.stderr is not None
        try:
            self.infrastructure = _create_reader_infrastructure(
                self.stdout,
                self.stderr,
                self.stderr_capture,
                functools.partial(self.context.shared.record, side=self.name),
            )
            _start_reader(self.infrastructure.stdout_thread)
            self.stdout_started = True
            _start_reader(self.infrastructure.stderr_thread)
            self.stderr_started = True
        except Exception as exc:
            self.context.shared.record(
                "reader_start_failed",
                f"paired audio {self.name} reader setup failed: {exc}",
                side=self.name,
            )
            return False
        return True

    def receive(self) -> bytes | None:
        """Wait for one stdout block under the stall/total deadlines.

        Returns the block, or None at EOF (``eof`` set) or after recording a
        failure (cancelled, timeout, stalled). At EOF the child's exit is awaited
        right away, so a trailing partial float32 sample or a nonzero exit is
        recorded at the earliest point it is known, before the other side runs on.
        """
        infrastructure = self.infrastructure
        assert infrastructure is not None
        context = self.context
        shared = context.shared
        last_progress = time.monotonic()
        while True:
            if shared.read()[0] is not None:
                return None
            if context.cancellation is not None and context.cancellation.is_set():
                shared.record("cancelled", "paired audio collection was cancelled")
                return None
            now = time.monotonic()
            remaining = context.deadline - now
            if remaining <= 0:
                shared.record("timeout", "paired audio collection exceeded its total timeout")
                return None
            if now - last_progress >= context.stall_timeout_seconds:
                shared.record(
                    "stalled",
                    f"paired audio {self.name} child made no progress "
                    f"for {context.stall_timeout_seconds} s",
                    side=self.name,
                )
                return None
            if infrastructure.stdout_done.is_set() and infrastructure.chunks.empty():
                self.eof = True
                if self.pending:
                    shared.record(
                        "partial_float32_sample",
                        f"paired audio {self.name} output ended with "
                        f"{len(self.pending)} trailing byte(s)",
                        side=self.name,
                    )
                else:
                    self._await_exit()
                return None
            wait = min(
                _QUEUE_WAIT_SECONDS,
                remaining,
                max(0.0, last_progress + context.stall_timeout_seconds - now),
            )
            try:
                return infrastructure.chunks.get(timeout=wait)
            except Empty:
                continue

    def _await_exit(self) -> None:
        """Wait for the child's exit after its stdout ended, recording the outcome.

        A child that closed stdout but does not exit is the awaited side making no
        progress, so the stall watchdog applies here too (A8).
        """
        process = self.process
        assert process is not None
        context = self.context
        shared = context.shared
        wait_started = time.monotonic()
        while process.poll() is None:
            if shared.read()[0] is not None:
                return
            if time.monotonic() - wait_started >= context.stall_timeout_seconds:
                shared.record(
                    "stalled",
                    f"paired audio {self.name} child did not exit after its output ended",
                    side=self.name,
                )
                return
            if context.cancellation is not None and context.cancellation.is_set():
                shared.record("cancelled", "paired audio collection was cancelled")
                return
            remaining = context.deadline - time.monotonic()
            if remaining <= 0:
                shared.record("timeout", "paired audio collection exceeded its total timeout")
                return
            _wait_for_exit(process, min(_QUEUE_WAIT_SECONDS, remaining))
        if process.returncode != 0:
            shared.record(
                "nonzero_exit",
                f"paired audio {self.name} child exited with status {process.returncode}",
                side=self.name,
            )

    def ingest(self, block: bytes, *, retain: bool) -> np.ndarray | None:
        """Validate one stdout block, count it, and buffer it when retained.

        Every block is checked for finiteness and counted against the side's output
        limit, whether retained or discarded past the last planned chunk (A7a).
        Returns the decoded samples, or None after recording a failure.
        """
        store = self.samples
        self.emitted_bytes += len(block)
        payload = self.pending + block
        complete_bytes = len(payload) - len(payload) % _FLOAT32_BYTES
        samples = (
            np.frombuffer(payload[:complete_bytes], dtype="<f4")
            if complete_bytes
            else np.empty(0, dtype="<f4")
        )
        if not bool(np.isfinite(samples).all()):
            self.context.shared.record(
                "nonfinite_output",
                f"paired audio {self.name} output contained a non-finite block",
                side=self.name,
            )
            return None
        if store.emitted + int(samples.size) > self.limit_samples:
            self.context.shared.record(
                "output_exceeded",
                f"paired audio {self.name} output exceeded its {self.limit_samples}-sample limit",
                side=self.name,
            )
            return None
        self.pending = payload[complete_bytes:]
        if retain:
            store.append(samples)
        else:
            store.emitted += int(samples.size)
        return samples

    def request_terminate(self) -> None:
        """Send terminate to a live child and record whether it was requested."""
        if self.process is not None:
            self.termination_requested = _request_terminate(self.process, self.cleanup_failures)

    def reap(self) -> CollectionCleanup:
        """Join this side's readers and close its pipes after termination."""
        if self.process is None:
            return CollectionCleanup(
                process_exited=True,
                stdout_reader_joined=True,
                stderr_reader_joined=True,
                stdout_pipe_closed=True,
                stderr_pipe_closed=True,
                termination_requested=False,
                kill_requested=False,
                failure=None,
            )
        infrastructure = self.infrastructure
        stdout_joined, stderr_joined = _join_started_readers(
            infrastructure.stdout_thread if infrastructure is not None else None,
            infrastructure.stderr_thread if infrastructure is not None else None,
            stdout_started=self.stdout_started,
            stderr_started=self.stderr_started,
        )
        stdout_closed = (
            _close_pipe(self.stdout, self.cleanup_failures) if self.stdout is not None else True
        )
        stderr_closed = (
            _close_pipe(self.stderr, self.cleanup_failures) if self.stderr is not None else True
        )
        return _summarize_cleanup(
            self.process,
            self.cleanup_failures,
            stdout_joined=stdout_joined,
            stderr_joined=stderr_joined,
            stdout_closed=stdout_closed,
            stderr_closed=stderr_closed,
            termination_requested=self.termination_requested,
            kill_requested=self.kill_requested,
        )

    def facts(self, *, started: float) -> CollectionFacts:
        """Return bounded scalar transport facts; the output limit stands in for the plan."""
        capture = self.stderr_capture
        return CollectionFacts(
            planned_end_sample=self.limit_samples,
            emitted_sample_count=self.samples.emitted,
            emitted_byte_count=self.emitted_bytes,
            retained_sample_count=self.samples.peak_count,
            stderr_byte_count=capture.byte_count,
            stderr_retained=bytes(capture.retained),
            stderr_truncated=capture.truncated,
            elapsed_seconds=time.monotonic() - started,
            returncode=self.process.returncode if self.process is not None else None,
        )

    def fill_reference_chunk(self, *, start: int, count: int, out: np.ndarray) -> bool:
        """Assemble reference ``[start, start + count)`` into zeroed ``out``.

        Samples the reference never produced (early EOF, including a chunk starting
        at or beyond EOF) stay zero, which the activity gate treats as inactive.
        Returns False after recording a failure.
        """
        shared = self.context.shared
        store = self.samples
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
            if self.eof:
                return True
            block = self.receive()
            if block is None:
                if shared.read()[0] is not None:
                    return False
                continue  # EOF newly observed; the loop re-checks and zero-pads.
            if self.ingest(block, retain=True) is None:
                return False
        return True

    def fill_comparison_need(self, *, window_start: int, need: int) -> bool:
        """Pull comparison output until absolute sample ``need`` arrived, or EOF."""
        shared = self.context.shared
        store = self.samples
        store.evict_before(max(window_start, 0))
        while store.emitted < need:
            if shared.read()[0] is not None:
                return False
            if self.eof:
                return True
            block = self.receive()
            if block is None:
                if shared.read()[0] is not None:
                    return False
                continue  # EOF newly observed; the loop re-checks.
            if self.ingest(block, retain=True) is None:
                return False
        return True

    def assemble_comparison_window(self, *, window_start: int, out: np.ndarray) -> None:
        """Copy stream ``[window_start, window_start + out.size)`` into zeroed ``out``.

        Anything outside ``[0, emitted)`` stays zero.
        """
        store = self.samples
        source_start = max(window_start, store.front, 0)
        source_end = min(window_start + int(out.size), store.emitted)
        if source_end > source_start and store.count:
            out[source_start - window_start : source_end - window_start] = store.view()[
                source_start - store.front : source_end - store.front
            ]


def drain_tail(reference: _ChildStream, comparison: _ChildStream) -> None:
    """Read and discard both tails past the last planned chunk, still counted."""
    shared = reference.context.shared
    while not (reference.eof and comparison.eof):
        if shared.read()[0] is not None:
            return
        for side in (reference, comparison):
            if side.eof or shared.read()[0] is not None:
                continue
            block = side.receive()
            if block is None:
                continue
            if side.ingest(block, retain=False) is None:
                return


def _cleanup_paired(
    reference: _ChildStream,
    comparison: _ChildStream,
    *,
    failed: bool,
) -> tuple[CollectionCleanup, CollectionCleanup]:
    """Clean both paired children: stops, then terminate-all before any wait/join.

    Terminate reaches every still-running child before any wait or join begins, so
    one hung child can never hold the other one's reaping hostage. Joining readers
    still precedes closing pipes.
    """
    for side in (reference, comparison):
        if side.infrastructure is not None:
            side.infrastructure.stop.set()
    if failed:
        for side in (reference, comparison):
            side.request_terminate()
    cleanups: list[CollectionCleanup] = []
    for side in (reference, comparison):
        if side.process is not None and side.termination_requested:
            side.kill_requested = _wait_then_kill(side.process, side.cleanup_failures)
        cleanups.append(side.reap())
    return cleanups[0], cleanups[1]


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
    consumer: Callable[[int, np.ndarray, np.ndarray], object],
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


def _paired_failure(
    category: CollectionFailureCategory,
    failure_side: AudioPairSide | None,
    message: str,
    *,
    reference: _ChildStream,
    comparison: _ChildStream,
    started: float,
    reference_cleanup: CollectionCleanup,
    comparison_cleanup: CollectionCleanup,
) -> PairedAudioCollectionFailure:
    return PairedAudioCollectionFailure(
        category=category,
        side=failure_side,
        message=_bounded_message(message),
        reference_facts=reference.facts(started=started),
        comparison_facts=comparison.facts(started=started),
        reference_cleanup=reference_cleanup,
        comparison_cleanup=comparison_cleanup,
    )


def collect_paired_audio_chunks(
    reference_argv: Sequence[str],
    comparison_argv: Sequence[str],
    *,
    chunks: Sequence[tuple[int, int]],
    lag_samples: int,
    consumer: Callable[[int, np.ndarray, np.ndarray], object],
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
    with exact sample values. Reference output past the last planned chunk is
    read, counted and limit-checked, then discarded.

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
    started = time.monotonic()
    shared = _FailureSlot()
    context = _RunContext(
        shared=shared,
        deadline=started + float(total_timeout_seconds),
        stall_timeout_seconds=float(stall_timeout_seconds),
        cancellation=cancellation,
    )
    cleanups: tuple[CollectionCleanup, CollectionCleanup] | None = None

    # Allocate before spawning so an allocation error leaves nothing to clean.
    # The reference store only receives a block once it is empty, so one read
    # spill bounds it; the comparison store holds one window plus one spill.
    spill = _READ_BYTES // _FLOAT32_BYTES + 1
    max_count = max(count for _, count in planned)
    reference = _ChildStream(
        name="reference",
        argv=reference_argv,
        limit_samples=reference_limit_samples,
        samples=_SampleStore(spill),
        context=context,
    )
    comparison = _ChildStream(
        name="comparison",
        argv=comparison_argv,
        limit_samples=comparison_limit_samples,
        samples=_SampleStore(max_count + 2 * lag_samples + spill),
        context=context,
    )
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
            reference_cleanup=reference.reap(),
            comparison_cleanup=comparison.reap(),
        )

    try:
        try:
            reference.spawn()
        except (OSError, ValueError) as exc:
            return _paired_failure(
                "spawn_failed",
                "reference",
                f"paired audio reference child could not start: {exc}",
                reference=reference,
                comparison=comparison,
                started=started,
                reference_cleanup=reference.reap(),
                comparison_cleanup=comparison.reap(),
            )
        try:
            comparison.spawn()
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
        if not reference.start_readers() or not comparison.start_readers():
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
            if not reference.fill_reference_chunk(
                start=start,
                count=count,
                out=reference_view,
            ):
                break
            window_start = start - lag_samples
            if not comparison.fill_comparison_need(
                window_start=window_start,
                need=start + count + lag_samples,
            ):
                break
            window_view = window_scratch[: count + 2 * lag_samples]
            window_view[:] = 0
            comparison.assemble_comparison_window(window_start=window_start, out=window_view)
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
            if time.monotonic() > context.deadline:
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
            drain_tail(reference, comparison)
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
            reference_facts=reference.facts(started=started),
            comparison_facts=comparison.facts(started=started),
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
    "CollectionCleanup",
    "CollectionFacts",
    "CollectionFailureCategory",
    "PairedAudioCollection",
    "PairedAudioCollectionFailure",
    "PairedAudioCollectionResult",
    "collect_paired_audio_chunks",
    "paired_collection_timeout_seconds",
    "paired_output_limit_samples",
]
