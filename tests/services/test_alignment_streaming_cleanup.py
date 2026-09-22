"""Regression coverage for a reader scheduled after the collector child exits."""

from __future__ import annotations

import struct
import sys
import threading

import pytest

from frame_compare.services import alignment_streaming
from frame_compare.services.alignment_streaming import (
    AudioSampleInterval,
    ContinuousAudioCollection,
    ContinuousAudioCollectionFailure,
)


@pytest.mark.parametrize("exit_code", [0, 17])
def test_completed_child_drains_delayed_stderr_before_pipe_close(
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
) -> None:
    release_reader = threading.Event()
    start_reader = alignment_streaming._start_reader

    def start_with_delayed_stderr(thread: threading.Thread) -> None:
        if thread.name == "alignment-stderr-reader":
            run = thread.run
            join = thread.join

            def delayed_run() -> None:
                if not release_reader.wait(timeout=5.0):
                    raise RuntimeError("collector did not reach bounded reader cleanup")
                run()

            def release_and_join(timeout: float | None = None) -> None:
                release_reader.set()
                join(timeout=timeout)

            monkeypatch.setattr(thread, "run", delayed_run)
            monkeypatch.setattr(thread, "join", release_and_join)
        start_reader(thread)

    monkeypatch.setattr(alignment_streaming, "_start_reader", start_with_delayed_stderr)
    stderr = b"bounded decoder diagnostic\n"
    argv = [
        sys.executable,
        "-c",
        "import os,sys;os.write(1,bytes.fromhex(sys.argv[1]));"
        "os.write(2,bytes.fromhex(sys.argv[2]));raise SystemExit(int(sys.argv[3]))",
        struct.pack("<f", 1.0).hex(),
        stderr.hex(),
        str(exit_code),
    ]
    try:
        result = alignment_streaming.collect_continuous_audio(
            argv,
            (AudioSampleInterval(0, 1),),
            planned_end_sample=1,
            max_retained_samples=1,
            timeout_seconds=5.0,
        )
    finally:
        release_reader.set()

    if exit_code:
        assert isinstance(result, ContinuousAudioCollectionFailure)
        assert result.category == "nonzero_exit"
    else:
        assert isinstance(result, ContinuousAudioCollection)
        assert result.end == "planned_end_reached"
        assert result.intervals[0].samples.tolist() == [1.0]
    assert result.facts.returncode == exit_code
    assert result.facts.stderr_byte_count == len(stderr)
    assert result.facts.stderr_retained == stderr
    assert result.cleanup.completed
