"""Application-owned cancellation across audio alignment work."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
import time
from fractions import Fraction
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from frame_compare.services import (
    alignment,
    alignment_audio,
    alignment_correlation,
    alignment_streaming,
)
from frame_compare.services.alignment_audio import AudioStreamInfo, AudioStreamTimeline
from frame_compare.services.alignment_streaming import (
    AudioSampleInterval,
    CollectionCleanup,
    CollectionFacts,
    ContinuousAudioCollectionFailure,
)
from frame_compare.services.errors import (
    AudioAlignmentCancellationError,
    AudioAlignmentCleanupError,
    raise_if_alignment_cancelled,
)
from frame_compare.services.types import AlignmentConfig
from tests.services.alignment_request_test_support import alignment_request


async def _wait_until(event: threading.Event) -> None:
    for _ in range(200):
        if event.is_set():
            return
        await asyncio.sleep(0.005)
    raise AssertionError("alignment worker did not reach the expected boundary")


def _stream() -> AudioStreamInfo:
    return AudioStreamInfo(
        audio_stream_index=0,
        absolute_stream_index=0,
        codec_name="pcm_f32le",
        channels=1,
        channel_layout="mono",
        sample_rate=8000,
        language=None,
        is_default=True,
        is_original=False,
        is_commentary=False,
        timeline=AudioStreamTimeline(
            start_time=Fraction(0),
            duration=Fraction(600),
            time_base=Fraction(1, 8000),
            duration_basis="duration_ts",
        ),
    )


def _writer_argv() -> list[str]:
    script = (
        "import os,sys,time\n"
        "chunk = bytes(65536)\n"
        "try:\n"
        " while True:\n"
        "  os.write(sys.stdout.fileno(), chunk)\n"
        "  time.sleep(0.001)\n"
        "except BrokenPipeError:\n"
        " pass\n"
    )
    return [sys.executable, "-c", script]


@pytest.mark.parametrize("boundary", ["discarded_gap", "queue_pressure", "requested_rate"])
@pytest.mark.anyio
async def test_outer_cancellation_reaches_collection_and_blocks_post_work(
    boundary: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparisons = [tmp_path / "comparison-a.mkv", tmp_path / "comparison-b.mkv"]
    reference.touch()
    for comparison in comparisons:
        comparison.touch()
    config = AlignmentConfig(cache_results=True, use_vsview=True)
    request = alignment_request(
        reference=reference,
        comparisons=comparisons,
        config=config,
        generated_dir=tmp_path,
    )
    boundary_reached = threading.Event()
    calls: list[Path] = []
    real_popen = alignment_streaming.subprocess.Popen

    def observed_popen(*args: Any, **kwargs: Any) -> Any:
        process = real_popen(*args, **kwargs)
        if boundary == "requested_rate":
            boundary_reached.set()
        return process

    monkeypatch.setattr(alignment_streaming.subprocess, "Popen", observed_popen)
    monkeypatch.setattr(
        alignment_audio, "continuous_collection_argv", lambda *_a, **_k: _writer_argv()
    )

    if boundary in {"discarded_gap", "queue_pressure"}:
        real_copy = alignment_streaming._copy_intersections
        cancellation_holder: list[threading.Event] = []

        def observed_copy(*args: Any, **kwargs: Any) -> None:
            boundary_reached.set()
            if boundary == "queue_pressure":
                while not cancellation_holder[0].is_set():
                    time.sleep(0.001)
            real_copy(*args, **kwargs)

        monkeypatch.setattr(alignment_streaming, "_copy_intersections", observed_copy)

    def collect_until_cancelled(
        _reference: Path,
        comparison: Path,
        *,
        cancellation: threading.Event | None = None,
        **_kwargs: Any,
    ) -> Any:
        assert cancellation is not None
        calls.append(comparison)
        if boundary in {"discarded_gap", "queue_pressure"}:
            cancellation_holder.append(cancellation)
        start = 2_000_000 if boundary == "discarded_gap" else 0
        alignment_audio._collect_role(
            reference,
            _stream(),
            (alignment_streaming.AudioSampleInterval(start, 1),),
            phase="verification" if boundary == "requested_rate" else "discovery",
            role="reference",
            sample_rate=48_000 if boundary == "requested_rate" else 8_000,
            channel_strategy="mono_downmix",
            max_retained_samples=1,
            cancellation=cancellation,
        )
        raise AssertionError("cancelled collection returned usable audio")

    monkeypatch.setattr(alignment, "_estimate_audio_pair", collect_until_cancelled)
    diagnostics = MagicMock()
    review = MagicMock()
    cache_write = MagicMock()
    monkeypatch.setattr(alignment, "_write_run_diagnostics", diagnostics)
    monkeypatch.setattr(alignment, "maybe_launch_alignment_vsview", review)
    monkeypatch.setattr(alignment, "save_reusable_offsets", cache_write)

    task = asyncio.create_task(
        alignment.align_clips_from_request(request, config, reference_fps=Fraction(24))
    )
    await _wait_until(boundary_reached)
    if boundary == "queue_pressure":
        await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls == [comparisons[0]]
    diagnostics.assert_not_called()
    review.assert_not_called()
    cache_write.assert_not_called()


@pytest.mark.anyio
async def test_repeated_cancellation_waits_for_worker_cleanup_and_preserves_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    config = AlignmentConfig(cache_results=False)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    started = threading.Event()
    cleanup_release = threading.Event()

    def delayed_cleanup(*_args: Any, cancellation: threading.Event, **_kwargs: Any) -> Any:
        started.set()
        while not cancellation.is_set():
            time.sleep(0.001)
        cleanup_release.wait(timeout=2)
        raise_if_alignment_cancelled(cancellation)

    monkeypatch.setattr(alignment, "_estimate_audio_pair", delayed_cleanup)
    task = asyncio.create_task(
        alignment.align_clips_from_request(request, config, reference_fps=Fraction(24))
    )
    await _wait_until(started)
    task.cancel()
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.sleep(0.01)
    assert not task.done()
    cleanup_release.set()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.anyio
async def test_worker_error_racing_outer_cancellation_does_not_replace_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    config = AlignmentConfig(cache_results=False)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    started = threading.Event()

    def fail_after_cancel(*_args: Any, cancellation: threading.Event, **_kwargs: Any) -> Any:
        started.set()
        while not cancellation.is_set():
            time.sleep(0.001)
        raise RuntimeError("worker failed during cancellation")

    monkeypatch.setattr(alignment, "_estimate_audio_pair", fail_after_cancel)
    task = asyncio.create_task(
        alignment.align_clips_from_request(request, config, reference_fps=Fraction(24))
    )
    await _wait_until(started)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.anyio
async def test_cleanup_failure_after_cancellation_replaces_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    config = AlignmentConfig(cache_results=False)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        config=config,
        generated_dir=tmp_path,
    )
    started = threading.Event()
    cleanup_release = threading.Event()

    def fail_cleanup_after_cancel(
        *_args: Any, cancellation: threading.Event, **_kwargs: Any
    ) -> Any:
        started.set()
        while not cancellation.is_set():
            time.sleep(0.001)
        cleanup_release.wait(timeout=2)
        raise AudioAlignmentCleanupError(
            "collector child was not reaped",
            category="cancelled",
            stage="discovery",
        )

    monkeypatch.setattr(alignment, "_estimate_audio_pair", fail_cleanup_after_cancel)
    diagnostics = MagicMock()
    review = MagicMock()
    cache_write = MagicMock()
    monkeypatch.setattr(alignment, "_write_run_diagnostics", diagnostics)
    monkeypatch.setattr(alignment, "maybe_launch_alignment_vsview", review)
    monkeypatch.setattr(alignment, "save_reusable_offsets", cache_write)
    task = asyncio.create_task(
        alignment.align_clips_from_request(request, config, reference_fps=Fraction(24))
    )
    await _wait_until(started)
    task.cancel()
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.sleep(0.01)
    assert not task.done()
    cleanup_release.set()

    with pytest.raises(AudioAlignmentCleanupError) as caught:
        await task

    assert caught.value.category == "cancelled"
    assert isinstance(caught.value.__cause__, asyncio.CancelledError)
    diagnostics.assert_not_called()
    review.assert_not_called()
    cache_write.assert_not_called()


def test_maximum_admitted_scoring_stops_between_hypotheses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancellation = threading.Event()
    first_score = threading.Event()
    calls = 0
    real_score = alignment_correlation._normalized_overlap_score

    def observed_score(*args: Any, **kwargs: Any) -> float | None:
        nonlocal calls
        calls += 1
        first_score.set()
        time.sleep(0.005)
        return real_score(*args, **kwargs)

    monkeypatch.setattr(alignment_correlation, "_normalized_overlap_score", observed_score)
    outcome: list[BaseException] = []

    def score() -> None:
        try:
            alignment_correlation.refine_aligned_score(
                np.arange(512, dtype=np.float64),
                np.arange(512, dtype=np.float64),
                preprocessing_mode="none",
                correction_bounds_samples=(-255, 255),
                cancellation=cancellation,
            )
        except BaseException as exc:
            outcome.append(exc)

    worker = threading.Thread(target=score)
    worker.start()
    assert first_score.wait(timeout=1)
    started = time.monotonic()
    cancellation.set()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert time.monotonic() - started < 1
    assert len(outcome) == 1
    assert isinstance(outcome[0], AudioAlignmentCancellationError)
    assert calls < 511


def test_cancelled_collection_with_incomplete_cleanup_preserves_cause_as_fatal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cleanup = CollectionCleanup(
        process_exited=False,
        stdout_reader_joined=True,
        stderr_reader_joined=True,
        stdout_pipe_closed=True,
        stderr_pipe_closed=True,
        termination_requested=True,
        kill_requested=True,
        failure="process remained live after kill",
    )
    failure = ContinuousAudioCollectionFailure(
        category="cancelled",
        message="continuous audio collection was cancelled",
        facts=CollectionFacts(
            planned_end_sample=1,
            emitted_sample_count=0,
            emitted_byte_count=0,
            retained_sample_count=0,
            stderr_byte_count=0,
            stderr_retained=b"",
            stderr_truncated=False,
            elapsed_seconds=0.1,
            returncode=None,
        ),
        cleanup=cleanup,
    )
    monkeypatch.setattr(alignment_audio, "collect_continuous_audio", lambda *_a, **_k: failure)

    with pytest.raises(AudioAlignmentCleanupError) as raised:
        alignment_audio._collect_role(
            tmp_path / "source.mkv",
            _stream(),
            (AudioSampleInterval(0, 1),),
            phase="discovery",
            role="reference",
            sample_rate=8000,
            channel_strategy="mono_downmix",
            max_retained_samples=1,
            cancellation=None,
        )

    assert raised.value.category == "cancelled"
    assert "continuous audio collection was cancelled" in str(raised.value)
    assert raised.value.collection_summaries[0].cleanup_failure_count == 1


def test_maximum_admitted_native_fft_finishes_safe_boundary_before_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancellation = threading.Event()
    fft_started = threading.Event()
    fft_release = threading.Event()
    real_fft = alignment_correlation._linear_correlation

    def bounded_fft(*args: Any, **kwargs: Any) -> Any:
        fft_started.set()
        assert fft_release.wait(timeout=1)
        return real_fft(*args, **kwargs)

    monkeypatch.setattr(alignment_correlation, "_linear_correlation", bounded_fft)
    outcome: list[BaseException] = []
    samples = np.sin(np.arange(1 << 20, dtype=np.float64) * 0.01)

    def correlate() -> None:
        try:
            alignment_correlation.correlate_audio(
                samples,
                samples,
                cancellation=cancellation,
            )
        except BaseException as exc:
            outcome.append(exc)

    worker = threading.Thread(target=correlate)
    worker.start()
    assert fft_started.wait(timeout=1)
    started = time.monotonic()
    cancellation.set()
    worker.join(timeout=0.01)
    assert worker.is_alive()
    fft_release.set()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert time.monotonic() - started < 5
    assert len(outcome) == 1
    assert isinstance(outcome[0], AudioAlignmentCancellationError)


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(SIGINT) uses POSIX signal delivery")
def test_ctrl_c_cancels_alignment_cleanup_before_keyboard_interrupt(tmp_path: Path) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    script = """
import asyncio
import os
import signal
import sys
import threading
import time
from pathlib import Path

from frame_compare.services import alignment
from frame_compare.services.errors import raise_if_alignment_cancelled
from frame_compare.services.types import AlignmentConfig
from tests.services.alignment_request_test_support import alignment_request

reference = Path(sys.argv[1])
comparison = Path(sys.argv[2])
config = AlignmentConfig(cache_results=False)
request = alignment_request(
    reference=reference,
    comparisons=[comparison],
    config=config,
    generated_dir=reference.parent,
)

def block(**kwargs):
    cancellation = kwargs["cancellation"]
    while not cancellation.is_set():
        time.sleep(0.001)
    raise_if_alignment_cancelled(cancellation)

alignment._compute_requested_alignments = block
timer = threading.Timer(0.1, os.kill, args=(os.getpid(), signal.SIGINT))
timer.start()
try:
    asyncio.run(alignment.align_clips_from_request(request, config))
except KeyboardInterrupt:
    print("ctrl_c_cleanup=ok")
else:
    raise SystemExit("SIGINT did not become KeyboardInterrupt")
finally:
    timer.cancel()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(reference), str(comparison)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ctrl_c_cleanup=ok"
