"""Contract tests for paired lockstep audio collection.

Two prepared child recipes run concurrently; the collector reads both float32
mono stdout streams in lockstep and delivers aligned (reference chunk,
comparison window) pairs. Children here are controlled ``sys.executable -c``
scripts, as in the single-child suites.
"""

from __future__ import annotations

import io
import os
import struct
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from frame_compare.services import alignment_streaming
from frame_compare.services.alignment_correlation import (
    ChunkedCorrelation,
    comparison_window,
    plan_audio_chunks,
)
from frame_compare.services.alignment_streaming import (
    PairedAudioCollection,
    PairedAudioCollectionFailure,
    collect_paired_audio_chunks,
    paired_collection_timeout_seconds,
    paired_output_limit_samples,
)

_FLOAT32_DTYPE = np.dtype("<f4")


def _payload(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


_PAIRED_SCRIPT = (
    "import os,sys,time\n"
    "out=bytes.fromhex(sys.argv[1])\nerr=bytes.fromhex(sys.argv[2])\n"
    "step=int(sys.argv[3])\npause=float(sys.argv[4])\n"
    "os.write(2,err) if err else None\n"
    "os.write(2,b'e'*int(sys.argv[7])) if int(sys.argv[7]) else None\n"
    "pos=0\nsize=len(out) if step<=0 else step\n"
    "while pos<len(out):\n"
    " os.write(1,out[pos:pos+size])\n"
    " pos+=size\n"
    " time.sleep(pause) if pause>0 and pos<len(out) else None\n"
    "time.sleep(float(sys.argv[5]))\n"
    "raise SystemExit(int(sys.argv[6]))\n"
)


def _child_argv(
    payload: bytes = b"",
    *,
    stderr: bytes = b"",
    stderr_flood_bytes: int = 0,
    exit_code: int = 0,
    delay_seconds: float = 0.0,
    write_step: int = 0,
    write_pause: float = 0.0,
) -> list[str]:
    assert len(payload) <= 32_000, "keep hex argv small; generate floods in-child"
    assert len(stderr) <= 32_000, "keep hex argv small; generate floods in-child"
    return [
        sys.executable,
        "-c",
        _PAIRED_SCRIPT,
        payload.hex(),
        stderr.hex(),
        str(write_step),
        str(write_pause),
        str(delay_seconds),
        str(exit_code),
        str(stderr_flood_bytes),
    ]


_FLOOD_SCRIPT = (
    "import os,struct,sys,time\n"
    "n=int(sys.argv[1])\nreps=int(sys.argv[2])\npause=float(sys.argv[3])\n"
    "block=struct.pack('<%df'%n, *([0.0]*n))\n"
    "os.write(2,b'e'*int(sys.argv[4])) if int(sys.argv[4]) else None\n"
    "i=0\n"
    "while i<reps:\n"
    " os.write(1,block)\n"
    " i+=1\n"
    " time.sleep(pause) if pause>0 and i<reps else None\n"
    "time.sleep(float(sys.argv[5]))\n"
    "raise SystemExit(int(sys.argv[6]))\n"
)


_FILE_SCRIPT = (
    "import os,sys,time\n"
    "data=open(sys.argv[1],'rb').read()\n"
    "step=int(sys.argv[2])\npause=float(sys.argv[3])\n"
    "pos=0\nsize=len(data) if step<=0 else step\n"
    "while pos<len(data):\n"
    " os.write(1,data[pos:pos+size])\n"
    " pos+=size\n"
    " time.sleep(pause) if pause>0 and pos<len(data) else None\n"
    "time.sleep(float(sys.argv[4]))\n"
    "raise SystemExit(int(sys.argv[5]))\n"
)


def _file_writer_argv(
    path: Any,
    *,
    write_step: int = 0,
    write_pause: float = 0.0,
    delay_seconds: float = 0.0,
    exit_code: int = 0,
) -> list[str]:
    """Serve a payload file from the child; dodges argv size limits."""
    return [
        sys.executable,
        "-c",
        _FILE_SCRIPT,
        str(path),
        str(write_step),
        str(write_pause),
        str(delay_seconds),
        str(exit_code),
    ]


def _flood_argv(
    *,
    samples_per_write: int,
    writes: int,
    pause: float = 0.0,
    stderr_bytes: int = 0,
    delay_seconds: float = 0.0,
    exit_code: int = 0,
) -> list[str]:
    """Generate constant output inside the child to dodge argv size limits."""
    return [
        sys.executable,
        "-c",
        _FLOOD_SCRIPT,
        str(samples_per_write),
        str(writes),
        str(pause),
        str(stderr_bytes),
        str(delay_seconds),
        str(exit_code),
    ]


class _StrictAccumulator:
    """Test-side consumer stand-in: pairs arrive in order, never finished on failure."""

    def __init__(self) -> None:
        self.indices: list[int] = []
        self.pairs: list[tuple[np.ndarray, np.ndarray]] = []
        self.writeable_inside: list[bool] = []

    def __call__(self, index: int, reference: np.ndarray, window: np.ndarray) -> None:
        assert index == len(self.pairs)
        self.indices.append(index)
        assert reference.dtype == _FLOAT32_DTYPE
        assert window.dtype == _FLOAT32_DTYPE
        self.writeable_inside.append(reference.flags.writeable or window.flags.writeable)
        self.pairs.append((np.array(reference, copy=True), np.array(window, copy=True)))


def _paired_kwargs(
    accumulator: Callable[[int, np.ndarray, np.ndarray], None],
    **overrides: Any,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "chunks": ((0, 500), (500, 500)),
        "lag_samples": 50,
        "consumer": accumulator,
        "reference_limit_samples": 100_000,
        "comparison_limit_samples": 100_000,
        "total_timeout_seconds": 20.0,
        "stall_timeout_seconds": 5.0,
    }
    kwargs.update(overrides)
    return kwargs


def _assert_failed(
    result: object,
    category: str,
    side: str | None,
) -> PairedAudioCollectionFailure:
    assert isinstance(result, PairedAudioCollectionFailure)
    assert result.category == category
    assert result.side == side
    assert not hasattr(result, "chunks_delivered")
    assert result.reference_cleanup.stdout_pipe_closed
    assert result.reference_cleanup.stderr_pipe_closed
    assert result.comparison_cleanup.stdout_pipe_closed
    assert result.comparison_cleanup.stderr_pipe_closed
    return result


def _expected_reference(full: np.ndarray, start: int, count: int) -> np.ndarray:
    expected = np.zeros(count, dtype=np.float64)
    have = full[start : start + count]
    expected[: have.size] = have
    return expected


def _check_geometry(
    pairs: list[tuple[np.ndarray, np.ndarray]],
    *,
    reference_full: np.ndarray,
    comparison_full: np.ndarray,
    chunks: tuple[tuple[int, int], ...],
    lag_samples: int,
) -> None:
    for position, ((start, count), (got_reference, got_window)) in enumerate(
        zip(chunks, pairs, strict=True)
    ):
        assert got_reference.shape == (count,)
        assert got_window.shape == (count + 2 * lag_samples,)
        assert np.array_equal(
            got_reference.astype(np.float64),
            _expected_reference(reference_full, start, count),
        ), f"reference chunk {position}"
        assert np.array_equal(
            got_window.astype(np.float64),
            comparison_window(comparison_full, start, count, lag_samples),
        ), f"comparison window {position}"


def _f4_block(rng: np.random.Generator, size: int) -> np.ndarray:
    return rng.standard_normal(size).astype(_FLOAT32_DTYPE)


def test_geometry_with_early_comparison_eof_matches_u1_value_for_value() -> None:
    rng = np.random.default_rng(11)
    reference = _f4_block(rng, 4000)
    comparison = _f4_block(rng, 2500)
    chunks = ((0, 1000), (1000, 1000), (2000, 1000), (3000, 1000))
    lag_samples = 200
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(reference.tobytes()),
        _child_argv(comparison.tobytes()),
        **_paired_kwargs(accumulator, chunks=chunks, lag_samples=lag_samples),
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == len(chunks)
    assert accumulator.indices == list(range(len(chunks)))
    assert accumulator.writeable_inside == [False] * len(chunks)
    _check_geometry(
        accumulator.pairs,
        reference_full=reference.astype(np.float64),
        comparison_full=comparison.astype(np.float64),
        chunks=chunks,
        lag_samples=lag_samples,
    )


def test_geometry_with_early_reference_eof_delivers_zero_chunks_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_streaming, "_READ_BYTES", 7)
    rng = np.random.default_rng(12)
    reference = _f4_block(rng, 1500)
    comparison = _f4_block(rng, 4000)
    chunks = ((0, 1000), (1000, 1000), (2000, 1000), (3000, 1000))
    lag_samples = 200
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(reference.tobytes()),
        _child_argv(comparison.tobytes()),
        **_paired_kwargs(accumulator, chunks=chunks, lag_samples=lag_samples),
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == len(chunks)
    # The trailing chunks start at or beyond the reference EOF: all zeros.
    assert np.array_equal(accumulator.pairs[2][0], np.zeros(1000, dtype=_FLOAT32_DTYPE))
    assert np.array_equal(accumulator.pairs[3][0], np.zeros(1000, dtype=_FLOAT32_DTYPE))
    _check_geometry(
        accumulator.pairs,
        reference_full=reference.astype(np.float64),
        comparison_full=comparison.astype(np.float64),
        chunks=chunks,
        lag_samples=lag_samples,
    )
    assert result.reference_facts.emitted_sample_count == 1500
    assert result.comparison_facts.emitted_sample_count == 4000


def test_success_result_carries_per_side_limits_eof_counts_and_cleanup() -> None:
    reference = _payload([1.0, 2.0, 3.0, 4.0])
    comparison = _payload([5.0, 6.0, 7.0, 8.0, 9.0])
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(reference),
        _child_argv(comparison),
        **_paired_kwargs(
            accumulator,
            chunks=((0, 2), (2, 2)),
            lag_samples=1,
            reference_limit_samples=100,
            comparison_limit_samples=200,
        ),
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == 2
    assert result.elapsed_seconds >= 0
    assert result.reference_facts.planned_end_sample == 100
    assert result.comparison_facts.planned_end_sample == 200
    assert result.reference_facts.emitted_sample_count == 4
    assert result.comparison_facts.emitted_sample_count == 5
    assert result.reference_facts.emitted_byte_count == len(reference)
    assert result.comparison_facts.emitted_byte_count == len(comparison)
    assert result.reference_facts.returncode == 0
    assert result.comparison_facts.returncode == 0
    spill = alignment_streaming._READ_BYTES // 4 + 1
    assert result.reference_facts.retained_sample_count <= 2 + spill
    assert result.comparison_facts.retained_sample_count <= 2 + 2 + spill
    for cleanup in (result.reference_cleanup, result.comparison_cleanup):
        assert cleanup.completed
        assert not cleanup.termination_requested
        assert not cleanup.kill_requested


@pytest.mark.parametrize("failing_side", ["reference", "comparison"])
def test_nonzero_exit_after_good_pcm_is_a_failure(failing_side: str) -> None:
    good = _payload([float(value) for value in range(600)])
    accumulator = _StrictAccumulator()
    if failing_side == "reference":
        reference_argv = _child_argv(good, exit_code=3)
        comparison_argv = _child_argv(_payload([1.0] * 1200))
    else:
        reference_argv = _child_argv(_payload([1.0] * 1200))
        comparison_argv = _child_argv(good, exit_code=5)
    result = collect_paired_audio_chunks(
        reference_argv,
        comparison_argv,
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "nonzero_exit", failing_side)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    # Good PCM was delivered before the crash surfaced, but the result is
    # unusable: the test-side accumulator is never finished. The crash is
    # detected when that side's stream ends, not after every chunk.
    assert accumulator.indices[:1] == [0]
    assert "3" in failed.message if failing_side == "reference" else "5" in failed.message


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal death")
@pytest.mark.parametrize("failing_side", ["reference", "comparison"])
def test_child_killed_by_signal_after_good_pcm_is_a_failure(failing_side: str) -> None:
    script = (
        "import os,signal,struct;"
        "os.write(1,struct.pack('<600f',*([0.5]*600)));"
        "os.kill(os.getpid(), signal.SIGKILL)"
    )
    killed = [sys.executable, "-c", script]
    healthy = _child_argv(_payload([1.0] * 1200))
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        killed if failing_side == "reference" else healthy,
        healthy if failing_side == "reference" else killed,
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "nonzero_exit", failing_side)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed


def test_stderr_reader_failure_during_final_join_is_not_a_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reader that fails only while cleanup joins it still fails the run."""
    joining = threading.Event()
    real_read_stderr = alignment_streaming._read_stderr
    real_join = alignment_streaming._join_started_readers

    def late_failing_stderr(stream: Any, capture: Any, done: Any, record: Any) -> None:
        if record.keywords["side"] != "reference":  # only the reference fails late
            real_read_stderr(stream, capture, done, record)
            return
        real_read_stderr(stream, capture, threading.Event(), record)
        joining.wait(timeout=5.0)
        record("stderr_reader_failed", "injected failure during join")
        done.set()

    def signalling_join(*args: Any, **kwargs: Any) -> Any:
        joining.set()
        return real_join(*args, **kwargs)

    monkeypatch.setattr(alignment_streaming, "_read_stderr", late_failing_stderr)
    monkeypatch.setattr(alignment_streaming, "_join_started_readers", signalling_join)
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(_payload([1.0] * 1200)),
        _child_argv(_payload([1.0] * 1200)),
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "stderr_reader_failed", "reference")
    assert failed.message == "injected failure during join"
    assert accumulator.indices == [0, 1]


def test_child_that_closes_stdout_but_never_exits_stalls_on_its_side() -> None:
    script = (
        "import os,struct,time;"
        "os.write(1,struct.pack('<1200f',*([0.5]*1200)));"
        "os.close(1);"
        "time.sleep(30)"
    )
    accumulator = _StrictAccumulator()
    started = time.monotonic()
    result = collect_paired_audio_chunks(
        [sys.executable, "-c", script],
        _child_argv(_payload([1.0] * 1200)),
        **_paired_kwargs(accumulator, stall_timeout_seconds=2.0, total_timeout_seconds=20.0),
    )

    failed = _assert_failed(result, "stalled", "reference")
    assert failed.reference_cleanup.completed
    assert time.monotonic() - started < 10


def _fail_one_side_reader(
    monkeypatch: pytest.MonkeyPatch,
    *,
    target: str,
    reader: str,
    category: str,
) -> None:
    """Fail one side's stdout/stderr reader, identified by stream identity."""
    real_create = alignment_streaming._create_reader_infrastructure
    real_read = getattr(alignment_streaming, reader)
    stream_side: dict[int, str] = {}
    created = 0

    def create(stdout: Any, stderr: Any, capture: Any, failure: Any) -> Any:
        nonlocal created
        side = "reference" if created == 0 else "comparison"
        created += 1
        stream_side[id(stdout)] = side
        stream_side[id(stderr)] = side
        return real_create(stdout, stderr, capture, failure)

    def read(stream: Any, *args: Any) -> Any:
        if stream_side.get(id(stream)) == target:
            done = args[-2]
            slot = args[-1]
            slot(category, f"injected {target} {reader} failure")
            done.set()
            return None
        return real_read(stream, *args)

    monkeypatch.setattr(alignment_streaming, "_create_reader_infrastructure", create)
    monkeypatch.setattr(alignment_streaming, reader, read)


@pytest.mark.parametrize("target", ["reference", "comparison"])
@pytest.mark.parametrize(
    ("reader", "category"),
    [("_read_stdout", "stdout_reader_failed"), ("_read_stderr", "stderr_reader_failed")],
)
def test_reader_error_is_attributed_to_its_side(
    monkeypatch: pytest.MonkeyPatch, target: str, reader: str, category: str
) -> None:
    _fail_one_side_reader(monkeypatch, target=target, reader=reader, category=category)
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(delay_seconds=5.0),
        _child_argv(delay_seconds=5.0),
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, category, target)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed


@pytest.mark.parametrize("failing_side", ["reference", "comparison"])
def test_nonfinite_block_is_attributed_to_its_side(failing_side: str) -> None:
    good = [float(value) for value in range(1000)]
    bad = good[:750] + [float("nan")] + good[751:]
    accumulator = _StrictAccumulator()
    if failing_side == "reference":
        reference_argv = _child_argv(_payload(bad))
        comparison_argv = _child_argv(_payload([1.0] * 1200))
    else:
        reference_argv = _child_argv(_payload([1.0] * 1200))
        comparison_argv = _child_argv(_payload(bad))
    result = collect_paired_audio_chunks(
        reference_argv,
        comparison_argv,
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "nonfinite_output", failing_side)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    # Whether chunk 0 was delivered depends on read grouping; chunk 1, which
    # needs the non-finite block, never is.
    assert accumulator.indices in ([], [0])


@pytest.mark.parametrize("failing_side", ["reference", "comparison"])
def test_trailing_partial_float_is_a_failure(failing_side: str) -> None:
    payload = _payload([float(value) for value in range(1000)]) + b"\x01\x02\x03"
    accumulator = _StrictAccumulator()
    if failing_side == "reference":
        reference_argv = _child_argv(payload)
        comparison_argv = _child_argv(_payload([1.0] * 1200))
    else:
        reference_argv = _child_argv(_payload([1.0] * 1200))
        comparison_argv = _child_argv(payload)
    result = collect_paired_audio_chunks(
        reference_argv,
        comparison_argv,
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "partial_float32_sample", failing_side)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed


@pytest.mark.parametrize("failing_side", ["reference", "comparison"])
def test_output_beyond_limit_is_a_failure(failing_side: str) -> None:
    flood = _payload([1.0] * 1200)
    accumulator = _StrictAccumulator()
    if failing_side == "reference":
        reference_argv = _child_argv(flood)
        comparison_argv = _child_argv(_payload([1.0] * 100))
        limits = {"reference_limit_samples": 1000}
    else:
        reference_argv = _child_argv(_payload([1.0] * 100))
        comparison_argv = _child_argv(flood)
        limits = {"comparison_limit_samples": 1000}
    result = collect_paired_audio_chunks(
        reference_argv,
        comparison_argv,
        **_paired_kwargs(accumulator, **limits),
    )

    failed = _assert_failed(result, "output_exceeded", failing_side)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed


@pytest.mark.parametrize(
    ("side", "position"),
    [
        ("reference", 200),  # in a gap below the only planned chunk
        ("comparison", 100),  # below the comparison window
        ("comparison", 1100),  # in the tail past every planned need
    ],
)
def test_nonfinite_sample_anywhere_in_the_stream_fails(side: str, position: int) -> None:
    """Every decoded block is checked (A7a), so read grouping cannot change the outcome."""
    values = [0.5] * 1200
    values[position] = float("nan")
    poisoned = _child_argv(_payload(values))
    clean = _child_argv(_payload([0.5] * 1200))
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        poisoned if side == "reference" else clean,
        clean if side == "reference" else poisoned,
        **_paired_kwargs(accumulator, chunks=((500, 100),), lag_samples=10),
    )

    failed = _assert_failed(result, "nonfinite_output", side)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed


def test_first_error_wins_when_both_sides_fault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reader failure beats a later nonzero exit: first recorded wins."""
    _fail_one_side_reader(
        monkeypatch,
        target="reference",
        reader="_read_stdout",
        category="stdout_reader_failed",
    )
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(delay_seconds=5.0),
        _child_argv(_payload([1.0] * 100), exit_code=5),
        **_paired_kwargs(accumulator),
    )

    # The reference reader fails at startup, long before the comparison exit
    # code is ever inspected; the nonzero exit must not overwrite it.
    failed = _assert_failed(result, "stdout_reader_failed", "reference")
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed


def test_paired_reader_start_failure_is_attributed_and_cleans_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    starts = 0
    real_start_reader = alignment_streaming._start_reader

    def fail_third_start(thread: threading.Thread) -> None:
        nonlocal starts
        starts += 1
        if starts == 3:
            raise RuntimeError("injected comparison reader startup failure")
        real_start_reader(thread)

    monkeypatch.setattr(alignment_streaming, "_start_reader", fail_third_start)
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(delay_seconds=5.0),
        _child_argv(delay_seconds=5.0),
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "reader_start_failed", "comparison")
    assert "injected comparison reader startup failure" in failed.message
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    assert failed.reference_cleanup.process_exited
    assert failed.comparison_cleanup.process_exited


def test_second_child_spawn_failure_still_cleans_the_first() -> None:
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(delay_seconds=10.0),
        ["frame-compare-definitely-missing-executable"],
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "spawn_failed", "comparison")
    assert failed.reference_cleanup.completed
    assert failed.reference_cleanup.process_exited
    assert failed.reference_cleanup.termination_requested
    assert failed.comparison_cleanup.completed
    assert failed.reference_facts.emitted_sample_count == 0


def test_first_child_spawn_failure_spawns_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spawns = 0
    real_popen = alignment_streaming.subprocess.Popen

    def count_spawns(*args: Any, **kwargs: Any) -> Any:
        nonlocal spawns
        spawns += 1
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(alignment_streaming.subprocess, "Popen", count_spawns)
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        ["frame-compare-definitely-missing-executable"],
        _child_argv(),
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "spawn_failed", "reference")
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    assert spawns == 0


def test_stalled_reference_side_reports_its_side() -> None:
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(_payload([1.0] * 200), delay_seconds=5.0),
        _child_argv(_payload([2.0] * 1200)),
        **_paired_kwargs(accumulator, stall_timeout_seconds=0.3),
    )

    failed = _assert_failed(result, "stalled", "reference")
    assert failed.reference_cleanup.completed
    assert failed.reference_cleanup.termination_requested
    assert failed.comparison_cleanup.completed
    assert accumulator.indices == []


def test_stalled_comparison_side_reports_its_side() -> None:
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(_payload([1.0] * 1200)),
        _child_argv(_payload([2.0] * 200), delay_seconds=5.0),
        **_paired_kwargs(accumulator, stall_timeout_seconds=0.3),
    )

    failed = _assert_failed(result, "stalled", "comparison")
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    # Chunk 0 needs 550 comparison samples but only 200 arrive, so nothing
    # delivers before the watchdog fires.
    assert accumulator.indices == []


def test_backpressured_side_is_never_stall_timed() -> None:
    """A slow awaited side keeps producing while the other side stays blocked."""
    accumulator = _StrictAccumulator()
    started = time.monotonic()
    result = collect_paired_audio_chunks(
        _child_argv(
            _payload([1.0] * 800),
            write_step=320,
            write_pause=0.15,
        ),
        _flood_argv(samples_per_write=16_384, writes=16),
        **_paired_kwargs(
            accumulator,
            chunks=((0, 800),),
            lag_samples=80,
            reference_limit_samples=300_000,
            comparison_limit_samples=300_000,
            stall_timeout_seconds=0.5,
        ),
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == 1
    assert accumulator.indices == [0]
    # The comparison child emitted 262144 samples while blocked on its pipe for
    # well over the stall timeout; the run still succeeds, outlasting a full
    # watchdog window (the awaited reference side takes ~1.4 s to trickle in).
    assert result.comparison_facts.emitted_sample_count == 262_144
    assert time.monotonic() - started > 0.5
    assert result.reference_cleanup.completed
    assert result.comparison_cleanup.completed


def test_total_timeout_reaps_both_children() -> None:
    accumulator = _StrictAccumulator()
    started = time.monotonic()
    result = collect_paired_audio_chunks(
        _child_argv(delay_seconds=10.0),
        _child_argv(delay_seconds=10.0),
        **_paired_kwargs(accumulator, total_timeout_seconds=0.3),
    )
    elapsed = time.monotonic() - started

    failed = _assert_failed(result, "timeout", None)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    assert failed.reference_cleanup.process_exited
    assert failed.comparison_cleanup.process_exited
    assert elapsed < 10


@pytest.mark.parametrize("short_side", ["reference", "comparison"])
def test_one_side_at_eof_while_the_other_streams(short_side: str) -> None:
    accumulator = _StrictAccumulator()
    if short_side == "reference":
        reference_argv = _child_argv(_payload([1.0] * 400))
        comparison_argv = _child_argv(_payload([2.0] * 3000), write_step=1200, write_pause=0.2)
    else:
        reference_argv = _child_argv(_payload([1.0] * 3000), write_step=1200, write_pause=0.2)
        comparison_argv = _child_argv(_payload([2.0] * 400))
    result = collect_paired_audio_chunks(
        reference_argv,
        comparison_argv,
        **_paired_kwargs(accumulator, chunks=((0, 500), (500, 500), (1000, 500)), lag_samples=50),
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == 3
    assert accumulator.indices == [0, 1, 2]
    if short_side == "reference":
        assert result.reference_facts.emitted_sample_count == 400
        assert result.comparison_facts.emitted_sample_count == 3000
    else:
        assert result.reference_facts.emitted_sample_count == 3000
        assert result.comparison_facts.emitted_sample_count == 400


def test_prespawn_cancellation_spawns_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_streaming.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("cancelled collection spawned a process"),
    )
    cancellation = threading.Event()
    cancellation.set()
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(),
        _child_argv(),
        **_paired_kwargs(accumulator, cancellation=cancellation),
    )

    failed = _assert_failed(result, "cancelled", None)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    assert not failed.reference_cleanup.termination_requested


def _cancel_after(cancellation: threading.Event, delay: float) -> threading.Thread:
    def wait_and_cancel() -> None:
        time.sleep(delay)
        cancellation.set()

    waiter = threading.Thread(target=wait_and_cancel, daemon=True)
    waiter.start()
    return waiter


@pytest.mark.parametrize("phase", ["decode", "backpressure"])
def test_cancellation_during_decode_reaps_both_children(phase: str) -> None:
    cancellation = threading.Event()
    accumulator = _StrictAccumulator()
    if phase == "decode":
        reference_argv = _child_argv(delay_seconds=10.0)
        comparison_argv = _child_argv(delay_seconds=10.0)
        kwargs = _paired_kwargs(accumulator, cancellation=cancellation)
    else:
        reference_argv = _child_argv(_payload([1.0] * 800), write_step=320, write_pause=0.15)
        comparison_argv = _flood_argv(samples_per_write=16_384, writes=16)
        kwargs = _paired_kwargs(
            accumulator,
            chunks=((0, 800),),
            lag_samples=80,
            reference_limit_samples=300_000,
            comparison_limit_samples=300_000,
            cancellation=cancellation,
        )
    waiter = _cancel_after(cancellation, 0.5)
    result = collect_paired_audio_chunks(reference_argv, comparison_argv, **kwargs)
    waiter.join(timeout=5.0)

    failed = _assert_failed(result, "cancelled", None)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    assert failed.reference_cleanup.process_exited
    assert failed.comparison_cleanup.process_exited
    assert failed.reference_cleanup.stdout_reader_joined
    assert failed.comparison_cleanup.stderr_reader_joined


def test_cancellation_inside_consumer_is_observed() -> None:
    cancellation = threading.Event()
    calls = 0

    def cancel_on_first(index: int, reference: np.ndarray, window: np.ndarray) -> None:
        nonlocal calls
        del reference, window
        calls += 1
        assert index == 0
        cancellation.set()

    result = collect_paired_audio_chunks(
        _child_argv(_payload([1.0] * 1200)),
        _child_argv(_payload([2.0] * 1200)),
        **_paired_kwargs(cancel_on_first, cancellation=cancellation),
    )

    failed = _assert_failed(result, "cancelled", None)
    assert calls == 1
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    assert failed.reference_cleanup.process_exited
    assert failed.comparison_cleanup.process_exited


class _RecordingChild:
    """A fake Popen that logs terminate/wait/kill order without timing luck."""

    def __init__(self, log: list[tuple[str, str]], name: str, stdout_bytes: bytes):
        self._log = log
        self._name = name
        self.stdout: Any = io.BytesIO(stdout_bytes)
        self.stderr: Any = io.BytesIO(b"")
        self.returncode: int | None = None
        self.pid = 10_000 + len(log)

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self._log.append(("terminate", self._name))

    def kill(self) -> None:
        self._log.append(("kill", self._name))
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        self._log.append(("wait", self._name))
        self.returncode = 0
        return 0


def test_terminate_reaches_both_children_before_any_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[tuple[str, str]] = []

    def fake_popen(argv: Any, **kwargs: Any) -> Any:
        del kwargs
        name = str(argv[0])
        size = 64 if name == "fake-reference" else 128
        return _RecordingChild(log, name, _payload([1.0] * size))

    monkeypatch.setattr(alignment_streaming, "resolve_executable", lambda name: name)
    monkeypatch.setattr(alignment_streaming.subprocess, "Popen", fake_popen)

    def fail_consumer(index: int, reference: np.ndarray, window: np.ndarray) -> None:
        del index, reference, window
        raise RuntimeError("injected consumer boom")

    result = collect_paired_audio_chunks(
        ["fake-reference"],
        ["fake-comparison"],
        **_paired_kwargs(
            fail_consumer, chunks=((0, 64),), lag_samples=8, stall_timeout_seconds=5.0
        ),
    )

    failed = _assert_failed(result, "consumer_failed", None)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    kinds = [kind for kind, _ in log]
    assert kinds.count("terminate") == 2
    # Both terminates precede any wait; kills are never needed.
    assert "kill" not in kinds
    assert max(index for index, kind in enumerate(kinds) if kind == "terminate") < min(
        index for index, kind in enumerate(kinds) if kind == "wait"
    )


@pytest.mark.skipif(os.name == "nt", reason="Windows terminate and kill are equivalent")
def test_uncooperative_children_are_killed_and_reaped() -> None:
    script = (
        "import os,signal,struct,time;"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        "os.write(1,struct.pack('<f',1.0));"
        "time.sleep(30)"
    )
    accumulator = _StrictAccumulator()
    started = time.monotonic()
    result = collect_paired_audio_chunks(
        [sys.executable, "-c", script],
        [sys.executable, "-c", script],
        # Long enough for both children to install SIG_IGN on a loaded host.
        **_paired_kwargs(accumulator, total_timeout_seconds=3.0),
    )
    elapsed = time.monotonic() - started

    failed = _assert_failed(result, "timeout", None)
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed
    assert failed.reference_cleanup.termination_requested
    assert failed.reference_cleanup.kill_requested
    assert failed.comparison_cleanup.termination_requested
    assert failed.comparison_cleanup.kill_requested
    assert elapsed < 12


def test_cleanup_failure_is_fatal_and_attributed_per_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_reap = alignment_streaming._reap_paired_side

    def reap_with_failure(side: Any) -> Any:
        cleanup = real_reap(side)
        if side.name == "reference":
            return replace(cleanup, failure="injected leftover reader")
        return cleanup

    monkeypatch.setattr(alignment_streaming, "_reap_paired_side", reap_with_failure)
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(_payload([1.0] * 1200)),
        _child_argv(_payload([2.0] * 1200)),
        **_paired_kwargs(accumulator),
    )

    failed = _assert_failed(result, "cleanup_failed", "reference")
    assert failed.reference_cleanup.failure == "injected leftover reader"


def test_stderr_flood_on_both_sides_is_drained_and_capped() -> None:
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(_payload([1.0] * 10), stderr_flood_bytes=70_000),
        _child_argv(_payload([2.0] * 10), stderr_flood_bytes=70_000),
        **_paired_kwargs(accumulator, chunks=((0, 10),), lag_samples=2),
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == 1
    assert result.reference_facts.stderr_byte_count == 70_000
    assert result.comparison_facts.stderr_byte_count == 70_000
    assert len(result.reference_facts.stderr_retained) == 65_536
    assert len(result.comparison_facts.stderr_retained) == 65_536
    assert result.reference_facts.stderr_truncated
    assert result.comparison_facts.stderr_truncated


def test_at_most_two_simultaneous_children(monkeypatch: pytest.MonkeyPatch) -> None:
    real_popen = alignment_streaming.subprocess.Popen
    state = {"active": 0, "peak": 0}
    lock = threading.Lock()

    def tracking_popen(*args: Any, **kwargs: Any) -> Any:
        process = real_popen(*args, **kwargs)
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        real_poll = process.poll
        real_wait = process.wait
        released = False

        def release() -> None:
            nonlocal released
            if not released:
                released = True
                with lock:
                    state["active"] -= 1

        def poll() -> Any:
            code = real_poll()
            if code is not None:
                release()
            return code

        def wait(timeout: Any = None) -> Any:
            code = real_wait(timeout=timeout)
            release()
            return code

        process.poll = poll  # type: ignore[method-assign]
        process.wait = wait  # type: ignore[method-assign]
        return process

    monkeypatch.setattr(alignment_streaming.subprocess, "Popen", tracking_popen)
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(_payload([1.0] * 100), delay_seconds=1.0),
        _child_argv(_payload([2.0] * 100), delay_seconds=1.0),
        **_paired_kwargs(accumulator, chunks=((0, 100),), lag_samples=10),
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == 1
    assert state["peak"] == 2


def test_consumer_exception_keeps_cause_and_cleans_up() -> None:
    def fail_consumer(index: int, reference: np.ndarray, window: np.ndarray) -> None:
        del index, reference, window
        raise ValueError("injected consumer boom")

    result = collect_paired_audio_chunks(
        _child_argv(_payload([1.0] * 1200)),
        _child_argv(_payload([2.0] * 1200)),
        **_paired_kwargs(fail_consumer),
    )

    failed = _assert_failed(result, "consumer_failed", None)
    assert "ValueError" in failed.message
    assert "injected consumer boom" in failed.message
    assert failed.reference_cleanup.completed
    assert failed.comparison_cleanup.completed


def test_keyboard_interrupt_in_consumer_reraises_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_popen = alignment_streaming.subprocess.Popen
    real_create = alignment_streaming._create_reader_infrastructure
    processes: list[Any] = []
    threads: list[threading.Thread] = []

    def tracking_popen(*args: Any, **kwargs: Any) -> Any:
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    def tracking_create(*args: Any, **kwargs: Any) -> Any:
        infrastructure = real_create(*args, **kwargs)
        threads.extend([infrastructure.stdout_thread, infrastructure.stderr_thread])
        return infrastructure

    monkeypatch.setattr(alignment_streaming.subprocess, "Popen", tracking_popen)
    monkeypatch.setattr(alignment_streaming, "_create_reader_infrastructure", tracking_create)

    def interrupt_consumer(index: int, reference: np.ndarray, window: np.ndarray) -> None:
        del index, reference, window
        raise KeyboardInterrupt("injected interrupt")

    with pytest.raises(KeyboardInterrupt, match="injected interrupt"):
        collect_paired_audio_chunks(
            _child_argv(_payload([1.0] * 1200)),
            _child_argv(_payload([2.0] * 1200)),
            **_paired_kwargs(interrupt_consumer),
        )

    assert processes
    assert threads
    assert all(process.poll() is not None for process in processes)
    # ident is set only once a thread actually started, so this proves the
    # readers ran and were joined (rather than never started).
    assert all(thread.ident is not None for thread in threads)
    assert all(not thread.is_alive() for thread in threads)


def test_keyboard_interrupt_mid_queue_wait_reraises_after_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SIGINT landing while blocked in Queue.get still reaps everything."""
    real_popen = alignment_streaming.subprocess.Popen
    real_create = alignment_streaming._create_reader_infrastructure
    processes: list[Any] = []

    def tracking_popen(*args: Any, **kwargs: Any) -> Any:
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    def create_with_armed_queue(*args: Any, **kwargs: Any) -> Any:
        infrastructure = real_create(*args, **kwargs)
        real_get = infrastructure.chunks.get
        armed = True

        def get_once(*get_args: Any, **get_kwargs: Any) -> Any:
            nonlocal armed
            if armed:
                armed = False
                raise KeyboardInterrupt("injected mid-wait interrupt")
            return real_get(*get_args, **get_kwargs)

        infrastructure.chunks.get = get_once  # type: ignore[method-assign]
        return infrastructure

    monkeypatch.setattr(alignment_streaming.subprocess, "Popen", tracking_popen)
    monkeypatch.setattr(
        alignment_streaming, "_create_reader_infrastructure", create_with_armed_queue
    )
    accumulator = _StrictAccumulator()
    with pytest.raises(KeyboardInterrupt, match="injected mid-wait interrupt"):
        collect_paired_audio_chunks(
            _child_argv(delay_seconds=5.0),
            _child_argv(delay_seconds=5.0),
            **_paired_kwargs(accumulator),
        )

    assert accumulator.indices == []
    assert processes
    assert all(process.poll() is not None for process in processes)


def test_request_validation_happens_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_streaming,
        "resolve_executable",
        lambda _name: pytest.fail("validation resolved an executable"),
    )
    monkeypatch.setattr(
        alignment_streaming.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("invalid request spawned a process"),
    )
    accumulator = _StrictAccumulator()
    base = _paired_kwargs(accumulator)
    bad_requests = [
        {**base, "chunks": ()},
        {**base, "chunks": ((500, 10), (0, 10))},
        {**base, "chunks": ((0, 10), (5, 10))},
        {**base, "chunks": ((0, 0),)},
        {**base, "chunks": ((-1, 10),)},
        {**base, "lag_samples": -1},
        {**base, "consumer": None},
        {**base, "reference_limit_samples": 0},
        {**base, "comparison_limit_samples": -5},
        {**base, "total_timeout_seconds": 0.0},
        {**base, "stall_timeout_seconds": float("inf")},
    ]
    for request in bad_requests:
        with pytest.raises(ValueError):
            collect_paired_audio_chunks(_child_argv(), _child_argv(), **request)
    with pytest.raises(ValueError, match="reference_argv"):
        collect_paired_audio_chunks([], _child_argv(), **base)
    with pytest.raises(ValueError, match="comparison_argv"):
        collect_paired_audio_chunks(_child_argv(), [""], **base)


def test_collection_timeout_helper_implements_a8_formula() -> None:
    assert paired_collection_timeout_seconds(None, None) is None
    assert paired_collection_timeout_seconds(10.0, 20.0) == pytest.approx(122.0)
    assert paired_collection_timeout_seconds(None, 5.0) == pytest.approx(120.5)
    assert paired_collection_timeout_seconds(7.0, None) == pytest.approx(120.7)
    # Unusable durations never widen or create a cap.
    assert paired_collection_timeout_seconds(float("nan"), 5.0) == pytest.approx(120.5)
    assert paired_collection_timeout_seconds(-3.0, 5.0) == pytest.approx(120.5)
    assert paired_collection_timeout_seconds(float("nan"), None) is None


def test_output_limit_helper_implements_a8_sanity_rule() -> None:
    assert paired_output_limit_samples(10.0, 8000) == 560_000
    assert paired_output_limit_samples(None, 8000) is None
    assert paired_output_limit_samples(float("nan"), 8000) is None
    assert paired_output_limit_samples(-1.0, 8000) is None


def test_streamed_pairs_feed_chunked_correlation_like_memory(
    tmp_path: Path,
) -> None:
    """U1's accumulator consumes the streamed pairs exactly like arrays."""
    sample_rate = 8000
    seconds = 10
    size = sample_rate * seconds
    times = np.arange(size, dtype=np.float64) / sample_rate
    tone = np.sin(2 * np.pi * 440.0 * times).astype(_FLOAT32_DTYPE)
    rng = np.random.default_rng(23)
    reference = (tone + 0.05 * rng.standard_normal(size)).astype(_FLOAT32_DTYPE)
    shift = 1500
    comparison = np.zeros(size, dtype=_FLOAT32_DTYPE)
    comparison[shift:] = tone[:-shift] if shift else tone
    comparison = (comparison + 0.05 * rng.standard_normal(size)).astype(_FLOAT32_DTYPE)
    reference_path = tmp_path / "reference.f32"
    comparison_path = tmp_path / "comparison.f32"
    reference_path.write_bytes(reference.tobytes())
    comparison_path.write_bytes(comparison.tobytes())

    plan = plan_audio_chunks(size, size, 1.0)
    assert len(plan.chunks) == 2

    expected = ChunkedCorrelation(plan)
    for index, (start, count) in enumerate(plan.chunks):
        expected.add(
            index,
            reference[start : start + count],
            comparison_window(comparison, start, count, plan.lag_samples),
        )
    expected_estimate = expected.finish()

    streamed = ChunkedCorrelation(plan)

    def feed(index: int, reference_chunk: np.ndarray, window: np.ndarray) -> None:
        streamed.add(index, reference_chunk, window)

    reference_limit = paired_output_limit_samples(seconds, sample_rate)
    comparison_limit = paired_output_limit_samples(seconds, sample_rate)
    total_timeout = paired_collection_timeout_seconds(seconds, seconds)
    assert reference_limit is not None
    assert comparison_limit is not None
    assert total_timeout is not None
    result = collect_paired_audio_chunks(
        _file_writer_argv(reference_path),
        _file_writer_argv(comparison_path),
        chunks=plan.chunks,
        lag_samples=plan.lag_samples,
        consumer=feed,
        reference_limit_samples=reference_limit,
        comparison_limit_samples=comparison_limit,
        total_timeout_seconds=total_timeout,
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == len(plan.chunks)
    streamed_estimate = streamed.finish()
    assert streamed_estimate == expected_estimate


def test_gapped_chunks_with_zero_lag_match_u1() -> None:
    """Non-contiguous chunks and lag 0 stream exactly like memory."""
    rng = np.random.default_rng(31)
    reference = _f4_block(rng, 600)
    comparison = _f4_block(rng, 600)
    chunks = ((0, 100), (300, 100))
    accumulator = _StrictAccumulator()
    result = collect_paired_audio_chunks(
        _child_argv(reference.tobytes()),
        _child_argv(comparison.tobytes()),
        **_paired_kwargs(accumulator, chunks=chunks, lag_samples=0),
    )

    assert isinstance(result, PairedAudioCollection)
    assert result.chunks_delivered == 2
    assert accumulator.indices == [0, 1]
    _check_geometry(
        accumulator.pairs,
        reference_full=reference.astype(np.float64),
        comparison_full=comparison.astype(np.float64),
        chunks=chunks,
        lag_samples=0,
    )
