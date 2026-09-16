"""Contract tests for bounded continuous audio collection."""

from __future__ import annotations

import os
import struct
import sys
import threading
from dataclasses import replace
from typing import Any

import pytest

from frame_compare.services import alignment_streaming
from frame_compare.services.alignment_streaming import (
    AudioSampleInterval,
    ContinuousAudioCollection,
    ContinuousAudioCollectionFailure,
    ContinuousAudioCollectionResult,
)
from frame_compare.services.alignment_streaming import (
    collect_continuous_audio as _collect_continuous_audio,
)


def _payload(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def _writer_argv(
    stdout: bytes = b"",
    *,
    stderr: bytes = b"",
    exit_code: int = 0,
    delay_seconds: float = 0.0,
) -> list[str]:
    script = (
        "import os,sys,time;"
        "out=bytes.fromhex(sys.argv[1]);err=bytes.fromhex(sys.argv[2]);"
        "os.write(1,out) if out else None;"
        "os.write(2,err) if err else None;"
        "time.sleep(float(sys.argv[3]));"
        "raise SystemExit(int(sys.argv[4]))"
    )
    return [
        sys.executable,
        "-c",
        script,
        stdout.hex(),
        stderr.hex(),
        str(delay_seconds),
        str(exit_code),
    ]


def _stderr_writer_argv(byte_count: int) -> list[str]:
    script = (
        "import os,struct,sys;os.write(1,struct.pack('<f',1.0));os.write(2,b'e'*int(sys.argv[1]))"
    )
    return [sys.executable, "-c", script, str(byte_count)]


def collect_continuous_audio(
    argv: list[str],
    intervals: tuple[AudioSampleInterval, ...],
    **kwargs: Any,
) -> ContinuousAudioCollectionResult:
    """Exercise ordinary cases at the exact admitted retained-sample limit."""
    return _collect_continuous_audio(
        argv,
        intervals,
        max_retained_samples=sum(interval.sample_count for interval in intervals),
        **kwargs,
    )


def _assert_failed(result: object, category: str) -> ContinuousAudioCollectionFailure:
    assert isinstance(result, ContinuousAudioCollectionFailure)
    assert result.category == category
    assert not hasattr(result, "intervals")
    assert result.cleanup.stdout_pipe_closed
    assert result.cleanup.stderr_pipe_closed
    return result


def test_collects_fragmented_overlapping_and_disjoint_intervals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_streaming, "_READ_BYTES", 3)
    result = collect_continuous_audio(
        _writer_argv(_payload([float(value) for value in range(12)])),
        (
            AudioSampleInterval(0, 3),
            AudioSampleInterval(2, 4),
            AudioSampleInterval(9, 3),
        ),
        planned_end_sample=12,
    )

    assert isinstance(result, ContinuousAudioCollection)
    assert result.end == "planned_end_reached"
    assert result.observed_eof_sample is None
    assert [item.samples.tolist() for item in result.intervals] == [
        [0.0, 1.0, 2.0],
        [2.0, 3.0, 4.0, 5.0],
        [9.0, 10.0, 11.0],
    ]
    assert all(not item.samples.flags.writeable for item in result.intervals)
    assert result.facts.emitted_sample_count == 12
    assert result.facts.retained_sample_count == 10
    assert result.cleanup.completed


def test_clean_early_eof_clamps_short_and_empty_endpoint_rows() -> None:
    result = collect_continuous_audio(
        _writer_argv(_payload([0.0, 1.0, 2.0, 3.0, 4.0])),
        (AudioSampleInterval(3, 4), AudioSampleInterval(7, 2)),
        planned_end_sample=10,
    )

    assert isinstance(result, ContinuousAudioCollection)
    assert result.end == "observed_eof"
    assert result.observed_eof_sample == 5
    assert result.intervals[0].planned_sample_count == 4
    assert result.intervals[0].actual_sample_count == 2
    assert result.intervals[0].samples.tolist() == [3.0, 4.0]
    assert result.intervals[1].planned_sample_count == 2
    assert result.intervals[1].actual_sample_count == 0
    assert result.intervals[1].samples.size == 0


@pytest.mark.parametrize(
    ("stdout", "planned_end", "category"),
    [
        (b"\x00\x00\x00", 1, "partial_float32_sample"),
        (_payload([1.0, 2.0]), 1, "output_exceeded"),
        (_payload([float("nan")]), 1, "nonfinite_output"),
    ],
)
def test_invalid_payload_never_returns_pcm(
    stdout: bytes,
    planned_end: int,
    category: str,
) -> None:
    result = collect_continuous_audio(
        _writer_argv(stdout),
        (AudioSampleInterval(0, planned_end),),
        planned_end_sample=planned_end,
    )

    failed = _assert_failed(result, category)
    assert failed.cleanup.completed


def test_nonzero_exit_invalidates_already_filled_interval() -> None:
    result = collect_continuous_audio(
        _writer_argv(_payload([1.0, 2.0]), exit_code=7),
        (AudioSampleInterval(0, 2),),
        planned_end_sample=2,
    )

    failed = _assert_failed(result, "nonzero_exit")
    assert failed.facts.emitted_sample_count == 2
    assert failed.cleanup.completed


def test_stderr_is_drained_and_retained_within_fixed_limit() -> None:
    result = collect_continuous_audio(
        _stderr_writer_argv(70_000),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    assert isinstance(result, ContinuousAudioCollection)
    assert result.facts.stderr_byte_count == 70_000
    assert len(result.facts.stderr_retained) == 65_536
    assert result.facts.stderr_truncated


def test_cancellation_terminates_child_and_joins_both_readers() -> None:
    cancellation = threading.Event()
    cancellation.set()
    result = collect_continuous_audio(
        _writer_argv(delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
        cancellation=cancellation,
    )

    failed = _assert_failed(result, "cancelled")
    assert failed.cleanup.completed
    assert failed.cleanup.termination_requested


def test_no_output_timeout_terminates_child_and_joins_both_readers() -> None:
    result = collect_continuous_audio(
        _writer_argv(delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
        timeout_seconds=0.1,
    )

    failed = _assert_failed(result, "timeout")
    assert failed.cleanup.completed
    assert failed.cleanup.termination_requested


@pytest.mark.skipif(os.name == "nt", reason="Windows terminate and kill are equivalent")
def test_uncooperative_child_requires_kill_and_is_reaped() -> None:
    script = (
        "import os,signal,struct,time;"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        "os.write(1,struct.pack('<f',1.0));"
        "time.sleep(10)"
    )
    result = collect_continuous_audio(
        [sys.executable, "-c", script],
        (AudioSampleInterval(0, 2),),
        planned_end_sample=2,
        timeout_seconds=0.2,
    )

    failed = _assert_failed(result, "timeout")
    assert failed.cleanup.completed
    assert failed.cleanup.termination_requested
    assert failed.cleanup.kill_requested


def test_second_reader_start_failure_still_cleans_started_reader_and_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    starts = 0

    def fail_second_reader(thread: threading.Thread) -> None:
        nonlocal starts
        starts += 1
        if starts == 2:
            raise RuntimeError("injected second-reader startup failure")
        thread.start()

    monkeypatch.setattr(alignment_streaming, "_start_reader", fail_second_reader)
    result = collect_continuous_audio(
        _writer_argv(delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, "reader_start_failed")
    assert failed.cleanup.completed
    assert failed.cleanup.stdout_reader_joined
    assert failed.cleanup.stderr_reader_joined


@pytest.mark.parametrize(
    ("reader_name", "category"),
    [
        ("_read_stdout", "stdout_reader_failed"),
        ("_read_stderr", "stderr_reader_failed"),
    ],
)
def test_reader_failure_is_distinct_from_eof_and_cleans_every_owner(
    monkeypatch: pytest.MonkeyPatch,
    reader_name: str,
    category: str,
) -> None:
    def fail_reader(*args: Any) -> None:
        done = args[-2]
        slot = args[-1]
        slot.record(category, "injected reader failure")
        done.set()

    monkeypatch.setattr(alignment_streaming, reader_name, fail_reader)
    result = collect_continuous_audio(
        _writer_argv(delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, category)
    assert failed.cleanup.completed


def test_stdout_reader_failure_invalidates_already_consumed_pcm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def output_then_fail(stream: Any, chunks: Any, stop: Any, done: Any, slot: Any) -> None:
        del stream, stop
        chunks.put(_payload([1.0]))
        threading.Event().wait(0.05)
        slot.record("stdout_reader_failed", "injected failure after data")
        done.set()

    monkeypatch.setattr(alignment_streaming, "_read_stdout", output_then_fail)
    result = collect_continuous_audio(
        _writer_argv(delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, "stdout_reader_failed")
    assert failed.facts.emitted_sample_count == 1
    assert failed.cleanup.completed


def test_out_of_band_reader_error_survives_full_stdout_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fill_then_fail(stream: Any, chunks: Any, stop: Any, done: Any, slot: Any) -> None:
        del stream, stop
        for _ in range(8):
            chunks.put(b"\x00" * 65_536)
        slot.record("stdout_reader_failed", "injected failure behind full queue")
        done.set()

    monkeypatch.setattr(alignment_streaming, "_read_stdout", fill_then_fail)
    result = collect_continuous_audio(
        _writer_argv(delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, "stdout_reader_failed")
    assert failed.cleanup.completed
    assert failed.facts.elapsed_seconds < 2.0


def test_consumer_failure_invalidates_pcm_and_cleans_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_copy(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise ValueError("injected consumer failure")

    monkeypatch.setattr(alignment_streaming, "_copy_intersections", fail_copy)
    result = collect_continuous_audio(
        _writer_argv(_payload([1.0]), delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, "consumer_failed")
    assert failed.cleanup.completed


def test_first_reader_failure_survives_separate_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_cleanup = alignment_streaming._cleanup

    def fail_stdout(*args: Any) -> None:
        done = args[-2]
        slot = args[-1]
        slot.record("stdout_reader_failed", "first cause")
        done.set()

    def cleanup_with_failure(*args: Any, **kwargs: Any) -> Any:
        cleanup = original_cleanup(*args, **kwargs)
        return replace(cleanup, failure="injected cleanup failure")

    monkeypatch.setattr(alignment_streaming, "_read_stdout", fail_stdout)
    monkeypatch.setattr(alignment_streaming, "_cleanup", cleanup_with_failure)
    result = collect_continuous_audio(
        _writer_argv(delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, "stdout_reader_failed")
    assert failed.message == "first cause"
    assert failed.cleanup.failure == "injected cleanup failure"
    assert failed.cleanup.process_exited
    assert failed.cleanup.stdout_reader_joined
    assert failed.cleanup.stderr_reader_joined


def test_cleanup_failure_prevents_successful_pcm_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_cleanup = alignment_streaming._cleanup

    def cleanup_with_failure(*args: Any, **kwargs: Any) -> Any:
        cleanup = original_cleanup(*args, **kwargs)
        return replace(cleanup, failure="injected handle-release failure")

    monkeypatch.setattr(alignment_streaming, "_cleanup", cleanup_with_failure)
    result = collect_continuous_audio(
        _writer_argv(_payload([1.0])),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, "cleanup_failed")
    assert failed.cleanup.failure == "injected handle-release failure"


def test_request_limits_are_validated_before_spawn() -> None:
    with pytest.raises(ValueError, match="interval count"):
        collect_continuous_audio(
            _writer_argv(),
            (),
            planned_end_sample=1,
        )
    with pytest.raises(ValueError, match="120"):
        collect_continuous_audio(
            _writer_argv(),
            (AudioSampleInterval(0, 1),),
            planned_end_sample=1,
            timeout_seconds=121,
        )


@pytest.mark.parametrize("limit", [0, -1, sys.maxsize])
def test_invalid_retained_sample_limit_is_rejected_before_executable_resolution(
    monkeypatch: pytest.MonkeyPatch,
    limit: int,
) -> None:
    resolved = False

    def unexpected_resolution(executable: str) -> str:
        nonlocal resolved
        resolved = True
        return executable

    monkeypatch.setattr(alignment_streaming, "resolve_executable", unexpected_resolution)
    with pytest.raises(ValueError, match="max_retained_samples"):
        _collect_continuous_audio(
            _writer_argv(),
            (AudioSampleInterval(0, 1),),
            planned_end_sample=1,
            max_retained_samples=limit,
        )
    assert not resolved


def test_separately_charged_overlapping_intervals_reject_above_retained_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved = False

    def unexpected_resolution(executable: str) -> str:
        nonlocal resolved
        resolved = True
        return executable

    monkeypatch.setattr(alignment_streaming, "resolve_executable", unexpected_resolution)
    with pytest.raises(ValueError, match="planned interval capacity"):
        _collect_continuous_audio(
            _writer_argv(),
            (AudioSampleInterval(0, 3), AudioSampleInterval(1, 3)),
            planned_end_sample=4,
            max_retained_samples=5,
        )
    assert not resolved


def test_post_spawn_infrastructure_failure_cleans_child_and_pipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_infrastructure(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise RuntimeError("injected post-spawn infrastructure failure")

    monkeypatch.setattr(
        alignment_streaming,
        "_create_reader_infrastructure",
        fail_infrastructure,
    )
    result = collect_continuous_audio(
        _writer_argv(delay_seconds=5.0),
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, "reader_start_failed")
    assert "injected post-spawn infrastructure failure" in failed.message
    assert failed.cleanup.process_exited
    assert failed.cleanup.stdout_pipe_closed
    assert failed.cleanup.stderr_pipe_closed
    assert failed.cleanup.completed


def test_spawn_failure_is_typed_and_has_completed_empty_cleanup() -> None:
    result = collect_continuous_audio(
        ["frame-compare-definitely-missing-executable"],
        (AudioSampleInterval(0, 1),),
        planned_end_sample=1,
    )

    failed = _assert_failed(result, "spawn_failed")
    assert failed.cleanup.completed
    assert failed.facts.emitted_sample_count == 0
