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

from frame_compare.services import alignment, alignment_audio
from frame_compare.services.alignment_audio import (
    AudioStreamInfo,
    AudioStreamSelection,
    AudioStreamTimeline,
    ProbedStreams,
    VideoStreamStart,
)
from frame_compare.services.alignment_streaming import (
    CollectionCleanup,
    CollectionFacts,
    PairedAudioCollectionFailure,
    collect_paired_audio_chunks,
)
from frame_compare.services.errors import (
    AudioAlignmentCancellationError,
    AudioAlignmentCleanupError,
    raise_if_alignment_cancelled,
)
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.alignment_evidence import CollectionFailureCategory
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


def _selection() -> AudioStreamSelection:
    return AudioStreamSelection(
        stream=_stream(),
        video_start=VideoStreamStart(start_time=Fraction(0), basis="default_zero"),
    )


def _probe() -> ProbedStreams:
    selection = _selection()
    return ProbedStreams(audio=(selection.stream,), video_start=selection.video_start)


def _float_writer_argv() -> list[str]:
    script = (
        "import sys,time\n"
        "chunk = bytes(65536)\n"
        "out = sys.stdout.buffer\n"
        "try:\n"
        " while True:\n"
        "  out.write(chunk)\n"
        "  out.flush()\n"
        "  time.sleep(0.001)\n"
        "except (BrokenPipeError, ValueError):\n"
        " pass\n"
    )
    return [sys.executable, "-c", script]


def _paired_kwargs(
    consumer: Any,
    *,
    chunks: tuple[tuple[int, int], ...] = ((0, 8000),),
    cancellation: threading.Event | None = None,
) -> dict[str, Any]:
    return {
        "chunks": chunks,
        "lag_samples": 100,
        "consumer": consumer,
        "reference_limit_samples": 8_000_000,
        "comparison_limit_samples": 8_000_000,
        "total_timeout_seconds": 30.0,
        "stall_timeout_seconds": 5.0,
        "cancellation": cancellation,
    }


def test_outer_cancellation_reaches_collection_and_blocks_post_work(
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
        generated_dir=tmp_path,
    )
    pair_reached = threading.Event()
    calls: list[Path] = []

    def collect_until_cancelled(
        _reference: Path,
        comparison: Path,
        *,
        cancellation: threading.Event | None = None,
        **_kwargs: Any,
    ) -> Any:
        assert cancellation is not None
        calls.append(comparison)
        pair_reached.set()
        while not cancellation.is_set():
            time.sleep(0.001)
        raise_if_alignment_cancelled(cancellation)

    monkeypatch.setattr(alignment, "_estimate_audio_pair", collect_until_cancelled)
    diagnostics = MagicMock()
    review = MagicMock()
    cache_write = MagicMock()
    monkeypatch.setattr(alignment, "_write_run_diagnostics", diagnostics)
    monkeypatch.setattr(alignment, "maybe_launch_alignment_vsview", review)
    monkeypatch.setattr(alignment, "save_reusable_offsets", cache_write)

    async def run() -> None:
        task = asyncio.create_task(
            alignment.align_clips_from_request(request, config, reference_fps=Fraction(24))
        )
        await _wait_until(pair_reached)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())

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
            stage="collection",
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


def test_prespawn_cancellation_delivers_no_pairs_and_completes_cleanup() -> None:
    cancellation = threading.Event()
    cancellation.set()
    delivered: list[int] = []

    def consumer(index: int, _reference: np.ndarray, _window: np.ndarray) -> None:
        delivered.append(index)

    result = collect_paired_audio_chunks(
        _float_writer_argv(),
        _float_writer_argv(),
        **_paired_kwargs(consumer, cancellation=cancellation),
    )

    assert isinstance(result, PairedAudioCollectionFailure)
    assert result.category == "cancelled"
    assert result.side is None
    assert delivered == []
    assert result.reference_cleanup.completed
    assert result.comparison_cleanup.completed


def test_in_flight_consumer_finishes_before_cancellation_is_observed() -> None:
    cancellation = threading.Event()
    entered = threading.Event()
    exited = threading.Event()

    def consumer(index: int, _reference: np.ndarray, _window: np.ndarray) -> None:
        assert index == 0
        entered.set()
        time.sleep(0.3)
        exited.set()

    def cancel_once_inside() -> None:
        assert entered.wait(timeout=10)
        cancellation.set()

    canceller = threading.Thread(target=cancel_once_inside, daemon=True)
    canceller.start()
    result = collect_paired_audio_chunks(
        _float_writer_argv(),
        _float_writer_argv(),
        **_paired_kwargs(consumer, cancellation=cancellation),
    )
    canceller.join(timeout=10)

    assert isinstance(result, PairedAudioCollectionFailure)
    assert result.category == "cancelled"
    assert exited.is_set()
    assert result.reference_cleanup.completed
    assert result.comparison_cleanup.completed


def _paired_failure(
    *,
    category: CollectionFailureCategory,
    reference_exited: bool = True,
    comparison_exited: bool = True,
) -> PairedAudioCollectionFailure:
    def facts() -> CollectionFacts:
        return CollectionFacts(
            planned_end_sample=4800000,
            emitted_sample_count=8000,
            emitted_byte_count=32000,
            retained_sample_count=8000,
            stderr_byte_count=0,
            stderr_retained=b"",
            stderr_truncated=False,
            elapsed_seconds=0.1,
            returncode=0,
        )

    def cleanup(exited: bool) -> CollectionCleanup:
        return CollectionCleanup(
            process_exited=exited,
            stdout_reader_joined=True,
            stderr_reader_joined=True,
            stdout_pipe_closed=True,
            stderr_pipe_closed=True,
            termination_requested=True,
            kill_requested=True,
            failure=None if exited else "process remained live after kill",
        )

    return PairedAudioCollectionFailure(
        category=category,
        side="reference",
        message=f"paired audio collection failed: {category}",
        reference_facts=facts(),
        comparison_facts=facts(),
        reference_cleanup=cleanup(reference_exited),
        comparison_cleanup=cleanup(comparison_exited),
    )


@pytest.mark.parametrize(
    "category, reference_exited, comparison_exited, change_identity, expected_error, expected_category, detail",
    [
        pytest.param(
            "cancelled",
            False,
            True,
            False,
            AudioAlignmentCleanupError,
            "cancelled",
            None,
            id="cancelled_pair_with_incomplete_cleanup_raises_cleanup_error",
        ),
        pytest.param(
            "timeout",
            False,
            True,
            True,
            AudioAlignmentCleanupError,
            "timeout",
            None,
            id="identity_change_with_incomplete_cleanup_raises_cleanup_error",
        ),
        pytest.param(
            "cancelled",
            True,
            True,
            True,
            AudioAlignmentCancellationError,
            None,
            None,
            id="cancelled_pair_with_identity_change_still_cancels",
        ),
        pytest.param(
            "nonzero_exit",
            True,
            False,
            False,
            AudioAlignmentCleanupError,
            "nonzero_exit",
            "cleanup did not complete",
            id="incomplete_cleanup_after_failed_pair_is_fatal",
        ),
    ],
)
def test_pair_failure_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    category: CollectionFailureCategory,
    reference_exited: bool,
    comparison_exited: bool,
    change_identity: bool,
    expected_error: type[Exception],
    expected_category: str | None,
    detail: str | None,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    request = alignment_request(
        reference=reference, comparisons=[comparison], generated_dir=tmp_path
    )
    monkeypatch.setattr(alignment_audio, "probe_streams", lambda _path, **_kwargs: _probe())

    def collect(*_args: Any, **_kwargs: Any) -> Any:
        if change_identity:
            with open(comparison, "ab") as handle:
                handle.write(b"mutated")
        return _paired_failure(
            category=category,
            reference_exited=reference_exited,
            comparison_exited=comparison_exited,
        )

    monkeypatch.setattr(alignment, "collect_paired_audio_chunks", collect)
    with pytest.raises(expected_error) as raised:
        alignment._estimate_audio_pair(
            reference,
            comparison,
            cache_settings=request.settings,
            fps_reference=Fraction(24),
            reference_request=request.reference,
            comparison_request=request.comparisons[0],
        )
    if expected_category is not None:
        assert isinstance(raised.value, AudioAlignmentCleanupError)
        assert raised.value.category == expected_category
    if detail is not None:
        assert detail in str(raised.value)


@pytest.mark.skipif(sys.platform == "win32", reason="os.kill(SIGINT) uses POSIX signal delivery")
def test_ctrl_c_cancels_alignment_cleanup_before_keyboard_interrupt(tmp_path: Path) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    script = """
import faulthandler
faulthandler.dump_traceback_later(5)
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
from frame_compare.utils.alignment_evidence import CollectionFailureCategory
from tests.services.alignment_request_test_support import alignment_request

reference = Path(sys.argv[1])
comparison = Path(sys.argv[2])
config = AlignmentConfig(cache_results=False)
request = alignment_request(
    reference=reference,
    comparisons=[comparison],
    generated_dir=reference.parent,
)

worker_reached_block = threading.Event()
print("ctrl_c_stage=imports-ready", file=sys.stderr, flush=True)

def block(**kwargs):
    print("ctrl_c_stage=worker-ready", file=sys.stderr, flush=True)
    worker_reached_block.set()
    cancellation = kwargs["cancellation"]
    while not cancellation.is_set():
        time.sleep(0.001)
    print("ctrl_c_stage=worker-cancelled", file=sys.stderr, flush=True)
    raise_if_alignment_cancelled(cancellation)

alignment._compute_requested_alignments = block

def interrupt_once_worker_ready():
    if worker_reached_block.wait(timeout=5):
        print("ctrl_c_stage=sending-sigint", file=sys.stderr, flush=True)
        os.kill(os.getpid(), signal.SIGINT)
        return
    print("ctrl_c_setup=worker-never-reached-block", file=sys.stderr, flush=True)
    os._exit(42)

helper = threading.Thread(target=interrupt_once_worker_ready, daemon=True)
helper.start()
try:
    asyncio.run(alignment.align_clips_from_request(request, config))
except KeyboardInterrupt:
    print("ctrl_c_cleanup=ok", flush=True)
else:
    raise SystemExit("SIGINT did not become KeyboardInterrupt")
finally:
    faulthandler.cancel_dump_traceback_later()
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, str(reference), str(comparison)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"alignment child timed out; stdout={exc.stdout!r}; stderr={exc.stderr!r}")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ctrl_c_cleanup=ok"
