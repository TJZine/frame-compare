import asyncio
import json
import subprocess
import sys
import textwrap
from collections.abc import Callable, Iterable
from concurrent.futures import CancelledError, Future
from concurrent.futures import wait as real_wait
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event, Lock, Thread
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.render.batch.orchestrator import (
    ProgressReporter,
    render_batch_detailed,
)
from frame_compare.render.types import (
    EncoderSettings,
    RenderedFrameResult,
    RenderRequest,
)
from frame_compare.utils.media_facts import RenderedFrameFacts
from frame_compare.utils.progress_protocol import ProgressPhaseStatus


class _CustomFFmpegRunner(DefaultFFmpegRunner):
    def __init__(self) -> None:
        super().__init__()
        self.single_calls: list[int] = []

    def extract_frame(
        self,
        video: Path,
        frame_num: int,
        output: Path,
        **_kwargs: object,
    ) -> RenderedFrameFacts:
        _ = video
        self.single_calls.append(frame_num)
        Image.new("RGB", (2, 2), color=(frame_num, 0, 0)).save(output)
        return RenderedFrameFacts(source_frame=frame_num, picture_type="I")


@pytest.fixture
def mock_render_request(tmp_path):
    return RenderRequest(
        clip=Path("video.mkv"),
        diagnostic_source=Path("video.mkv"),
        frame_number=42,
        output_path=tmp_path / "out.png",
        overlay=None,
        encoder_settings=EncoderSettings(),
    )


def _rendered(request: RenderRequest) -> RenderedFrameResult:
    return RenderedFrameResult(
        path=request.output_path,
        facts=RenderedFrameFacts(source_frame=request.frame_number),
    )


def test_render_batch_detailed_parallel_order(mock_render_request):
    frame_zero_started = Event()
    frame_one_completed = Event()
    requests = [
        RenderRequest(
            clip=Path("video.mkv"),
            diagnostic_source=Path("video.mkv"),
            frame_number=i,
            output_path=Path(f"out_{i}.png"),
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        for i in range(5)
    ]
    reporter = MagicMock(spec=ProgressReporter)

    with patch("frame_compare.render.batch.orchestrator.render_frame_detailed") as mock_render:

        def side_effect(request: RenderRequest) -> RenderedFrameResult:
            if request.frame_number == 0:
                frame_zero_started.set()
                assert frame_one_completed.wait(timeout=1.0)
            else:
                assert frame_zero_started.wait(timeout=1.0)
                rendered = _rendered(request)
                if request.frame_number == 1:
                    frame_one_completed.set()
                return rendered
            return _rendered(request)

        mock_render.side_effect = side_effect
        results = render_batch_detailed(requests, parallelism=2, reporter=reporter)
        assert [result.path for result in results] == [r.output_path for r in requests]
        assert [result.facts.source_frame for result in results] == [
            r.frame_number for r in requests
        ]
        assert [call.args[0] for call in reporter.set_description.call_args_list] == [
            f"frame {request.frame_number}" for request in requests
        ]
        assert reporter.advance.call_count == len(requests)


def test_render_batch_fail_fast(mock_render_request):
    requests = [
        RenderRequest(
            clip=mock_render_request.clip,
            diagnostic_source=mock_render_request.diagnostic_source,
            frame_number=index,
            output_path=mock_render_request.output_path.parent / f"out_{index}.png",
            overlay=mock_render_request.overlay,
            encoder_settings=mock_render_request.encoder_settings,
        )
        for index in range(10)
    ]
    with patch("frame_compare.render.batch.orchestrator.render_frame_detailed") as mock_render:

        def side_effect(r):
            if r.frame_number == 2:
                raise RuntimeError("Failed")
            return _rendered(r)

        mock_render.side_effect = side_effect
        with pytest.raises(RuntimeError, match="Failed"):
            render_batch_detailed(requests, parallelism=2)

        invoked_requests = [call.args[0] for call in mock_render.call_args_list]
        assert requests[2] in invoked_requests
        assert len(invoked_requests) < len(requests)


def test_render_batch_parallel_prefers_real_failure_to_cancelled_sibling(
    tmp_path: Path,
) -> None:
    class ControlledFuture(Future[list[RenderedFrameResult]]):
        def cancel(self) -> bool:
            cancelled = super().cancel()
            if cancelled:
                self.set_running_or_notify_cancel()
            return cancelled

    class ControlledExecutor:
        def __init__(self, max_workers: int) -> None:
            assert max_workers == 2
            self.futures: list[ControlledFuture] = []
            controlled_executors.append(self)

        def __enter__(self) -> "ControlledExecutor":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
            _ = wait, cancel_futures

        def submit(
            self, _function: object, *args: object, **kwargs: object
        ) -> Future[list[RenderedFrameResult]]:
            _ = kwargs
            future = ControlledFuture()
            self.futures.append(future)
            if len(self.futures) == 1:
                unit = args[0]
                assert isinstance(unit, tuple)
                future.set_result([_rendered(request) for request in unit])
            elif len(self.futures) == 3:
                future.set_exception(RuntimeError("real failure"))
            return future

    controlled_executors: list[ControlledExecutor] = []
    requests = [
        RenderRequest(
            clip=tmp_path / f"clip_{index}.mkv",
            diagnostic_source=tmp_path / f"clip_{index}.mkv",
            frame_number=index,
            output_path=tmp_path / f"out_{index}.jpg",
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        for index in range(3)
    ]

    with (
        patch(
            "frame_compare.render.batch.orchestrator.ThreadPoolExecutor",
            ControlledExecutor,
        ),
        pytest.raises(RuntimeError, match="real failure"),
    ):
        render_batch_detailed(
            requests,
            parallelism=2,
            work_unit_ranges=[range(0, 1), range(1, 2), range(2, 3)],
        )

    assert len(controlled_executors) == 1
    assert controlled_executors[0].futures[1].cancelled()


def test_render_batch_parallel_propagates_worker_cancellation(tmp_path: Path) -> None:
    cancelled = Future[list[RenderedFrameResult]]()
    cancelled.set_exception(CancelledError("caller cancelled"))

    class ControlledExecutor:
        def __init__(self, max_workers: int) -> None:
            _ = max_workers

        def __enter__(self) -> "ControlledExecutor":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
            _ = wait, cancel_futures

        def submit(
            self, _function: object, *args: object, **kwargs: object
        ) -> Future[list[RenderedFrameResult]]:
            _ = args, kwargs
            return cancelled

    request = RenderRequest(
        clip=tmp_path / "clip.mkv",
        diagnostic_source=tmp_path / "clip.mkv",
        frame_number=0,
        output_path=tmp_path / "out.jpg",
        overlay=None,
        encoder_settings=EncoderSettings(),
    )

    with (
        patch(
            "frame_compare.render.batch.orchestrator.ThreadPoolExecutor",
            ControlledExecutor,
        ),
        pytest.raises(CancelledError, match="caller cancelled"),
    ):
        render_batch_detailed(
            [request],
            parallelism=2,
            work_unit_ranges=[range(0, 1)],
        )


@pytest.fixture
def default_config() -> ConfigSchema:
    """Default config with tonemap disabled for isolated tests."""
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


def test_render_batch_parallel_waits_for_in_flight_work_before_raising() -> None:
    slow_started = Event()
    slow_blocked = Event()
    failure_raised = Event()
    release_slow = Event()
    slow_finished = Event()
    render_done = Event()
    render_exceptions: list[BaseException] = []

    requests = [
        RenderRequest(
            clip=Path("video.mkv"),
            diagnostic_source=Path("video.mkv"),
            frame_number=0,
            output_path=Path("out_0.png"),
            overlay=None,
            encoder_settings=EncoderSettings(),
        ),
        RenderRequest(
            clip=Path("video.mkv"),
            diagnostic_source=Path("video.mkv"),
            frame_number=1,
            output_path=Path("out_1.png"),
            overlay=None,
            encoder_settings=EncoderSettings(),
        ),
    ]

    # Let one task block after it starts, then fail from the other worker.
    def side_effect(r):
        if r.frame_number == 0:
            slow_started.set()
            slow_blocked.set()
            assert release_slow.wait(timeout=1.0)
            slow_finished.set()
            return _rendered(r)
        assert slow_blocked.wait(timeout=1.0)
        failure_raised.set()
        raise RuntimeError("Failed immediately")

    def run_render() -> None:
        try:
            render_batch_detailed(requests, parallelism=2)
        except BaseException as exc:
            render_exceptions.append(exc)
        finally:
            render_done.set()

    with patch(
        "frame_compare.render.batch.orchestrator.render_frame_detailed", side_effect=side_effect
    ):
        thread = Thread(target=run_render, daemon=True)
        thread.start()
        try:
            assert slow_started.wait(timeout=1.0)
            assert failure_raised.wait(timeout=1.0)
            assert not render_done.is_set()
        finally:
            release_slow.set()
            thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert slow_finished.is_set()
    assert len(render_exceptions) == 1
    assert isinstance(render_exceptions[0], RuntimeError)
    assert str(render_exceptions[0]) == "Failed immediately"


def test_render_batch_parallel_reports_lowest_request_index_failure(
    tmp_path: Path,
) -> None:
    frame_zero_started = Event()
    frame_two_failed = Event()
    release_frame_zero = Event()
    exceptions: list[BaseException] = []
    requests = [
        RenderRequest(
            clip=tmp_path / f"clip_{frame}.mkv",
            diagnostic_source=tmp_path / f"clip_{frame}.mkv",
            frame_number=frame,
            output_path=tmp_path / f"out_{frame}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        for frame in range(3)
    ]

    def render_single(request: RenderRequest) -> RenderedFrameResult:
        if request.frame_number == 0:
            frame_zero_started.set()
            assert release_frame_zero.wait(timeout=2.0)
            raise RuntimeError("error-0")
        if request.frame_number == 2:
            assert frame_zero_started.wait(timeout=2.0)
            frame_two_failed.set()
            raise RuntimeError("error-2")
        return _rendered(request)

    def run_render() -> None:
        try:
            render_batch_detailed(requests, parallelism=3)
        except BaseException as exc:
            exceptions.append(exc)

    with patch(
        "frame_compare.render.batch.orchestrator.render_frame_detailed",
        side_effect=render_single,
    ):
        thread = Thread(target=run_render, daemon=True)
        thread.start()
        try:
            assert frame_zero_started.wait(timeout=2.0)
            assert frame_two_failed.wait(timeout=2.0)
        finally:
            release_frame_zero.set()
            thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert len(exceptions) == 1
    assert isinstance(exceptions[0], RuntimeError)
    assert str(exceptions[0]) == "error-0"


def test_render_batch_marks_progress_failed_on_exception(mock_render_request) -> None:
    reporter = MagicMock(spec=ProgressReporter)

    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_frame_detailed",
            side_effect=RuntimeError("Failed"),
        ),
        pytest.raises(RuntimeError, match="Failed"),
    ):
        render_batch_detailed([mock_render_request], parallelism=1, reporter=reporter)

    reporter.complete_phase.assert_called_once_with(ProgressPhaseStatus.FAILED)


def test_render_batch_sequential(mock_render_request):
    requests = [
        replace(mock_render_request, frame_number=index, output_path=Path(f"out_{index}.png"))
        for index in range(3)
    ]
    with patch("frame_compare.render.batch.orchestrator.render_frame_detailed") as mock_render:
        mock_render.side_effect = _rendered
        results = [rendered.path for rendered in render_batch_detailed(requests, parallelism=1)]
        assert results == [Path("out_0.png"), Path("out_1.png"), Path("out_2.png")]
        assert mock_render.call_count == 3


def test_render_batch_empty_validates_work_unit_ranges() -> None:
    assert (
        render_batch_detailed(
            [],
            work_unit_ranges=[range(0, 0), range(0, 0)],
        )
        == []
    )
    with pytest.raises(ValueError, match="contiguous and ordered"):
        render_batch_detailed([], work_unit_ranges=[range(1, 1)])


def test_render_batch_sequential_preserves_default_runner_subclass_override(
    tmp_path: Path,
) -> None:
    runner = _CustomFFmpegRunner()
    requests = [
        RenderRequest(
            clip=Path("video.mkv"),
            diagnostic_source=Path("video.mkv"),
            frame_number=frame,
            output_path=tmp_path / f"out_{frame}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
            ffmpeg_runner=runner,
        )
        for frame in [1, 2]
    ]

    render_batch_detailed(requests, parallelism=1)

    assert runner.single_calls == [1, 2]


def test_render_batch_sequential_does_not_batch_non_png_outputs(tmp_path: Path) -> None:
    runner = DefaultFFmpegRunner()
    requests = [
        RenderRequest(
            clip=Path("video.mkv"),
            diagnostic_source=Path("video.mkv"),
            frame_number=frame,
            output_path=tmp_path / f"out_{frame}.jpg",
            overlay=None,
            encoder_settings=EncoderSettings(),
            ffmpeg_runner=runner,
        )
        for frame in [1, 2]
    ]

    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_frame_detailed",
            side_effect=_rendered,
        ) as render_frame,
        patch(
            "frame_compare.render.batch.orchestrator.render_ffmpeg_batch_detailed"
        ) as render_ffmpeg_batch,
    ):
        render_batch_detailed(requests, parallelism=1)

    assert render_frame.call_count == 2
    render_ffmpeg_batch.assert_not_called()


def test_render_batch_sequential_does_not_batch_negative_frame(tmp_path: Path) -> None:
    runner = DefaultFFmpegRunner()
    requests = [
        RenderRequest(
            clip=Path("video.mkv"),
            diagnostic_source=Path("video.mkv"),
            frame_number=frame,
            output_path=tmp_path / f"out_{index}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
            ffmpeg_runner=runner,
        )
        for index, frame in enumerate((-1, 0))
    ]

    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_frame_detailed",
            side_effect=RuntimeError("single-frame path"),
        ) as render_frame,
        patch(
            "frame_compare.render.batch.orchestrator.render_ffmpeg_batch_detailed"
        ) as render_ffmpeg_batch,
        pytest.raises(RuntimeError, match="single-frame path"),
    ):
        render_batch_detailed(requests, parallelism=1)

    render_frame.assert_called_once_with(requests[0])
    render_ffmpeg_batch.assert_not_called()


@pytest.mark.parametrize(
    "incompatibility",
    ["clip", "runner", "geometry", "output-directory", "duplicate", "decreasing"],
)
def test_render_batch_sequential_splits_incompatible_ffmpeg_requests(
    incompatibility: str,
    tmp_path: Path,
) -> None:
    runner = DefaultFFmpegRunner()
    requests = [
        RenderRequest(
            clip=Path("video.mkv"),
            diagnostic_source=Path("video.mkv"),
            frame_number=frame,
            output_path=tmp_path / f"out_{frame}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
            ffmpeg_runner=runner,
        )
        for frame in (1, 2)
    ]
    if incompatibility == "clip":
        requests[1].clip = Path("other.mkv")
    elif incompatibility == "runner":
        requests[1].ffmpeg_runner = DefaultFFmpegRunner()
    elif incompatibility == "geometry":
        requests[0].geometry_plan = MagicMock()
        requests[1].geometry_plan = MagicMock()
    elif incompatibility == "output-directory":
        requests[1].output_path = tmp_path / "other" / "out_2.png"
    elif incompatibility == "duplicate":
        requests[1].frame_number = requests[0].frame_number
    elif incompatibility == "decreasing":
        requests[0].frame_number = 3

    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_frame_detailed",
            side_effect=_rendered,
        ) as render_frame,
        patch(
            "frame_compare.render.batch.orchestrator.render_ffmpeg_batch_detailed"
        ) as render_ffmpeg_batch,
    ):
        render_batch_detailed(requests, parallelism=1)

    assert render_frame.call_count == len(requests)
    render_ffmpeg_batch.assert_not_called()


def test_render_batch_parallel_overlaps_ffmpeg_groups_and_preserves_order_and_progress(
    tmp_path: Path,
) -> None:
    runner = DefaultFFmpegRunner()
    requests = [
        RenderRequest(
            clip=Path(clip_name),
            diagnostic_source=Path(clip_name),
            frame_number=frame,
            output_path=tmp_path / f"{clip_name}-{frame}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
            ffmpeg_runner=runner,
        )
        for clip_name, frames in (("reference.mkv", [10, 20]), ("comparison.mkv", [30, 40, 50]))
        for frame in frames
    ]
    both_groups_started = Barrier(2)
    reporter = MagicMock(spec=ProgressReporter)

    def render_ffmpeg_group(
        group: list[RenderRequest],
        *,
        abort: Callable[[], bool] | None = None,
    ) -> list[RenderedFrameResult]:
        both_groups_started.wait(timeout=1.0)
        return [_rendered(request) for request in group]

    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_ffmpeg_batch_detailed",
            side_effect=render_ffmpeg_group,
        ) as render_batch,
        patch("frame_compare.render.batch.orchestrator.render_frame_detailed") as render_frame,
    ):
        results = render_batch_detailed(
            requests,
            parallelism=2,
            reporter=reporter,
            work_unit_ranges=[range(0, 2), range(2, 5)],
        )

    assert sorted(
        tuple(request.frame_number for request in call.args[0])
        for call in render_batch.call_args_list
    ) == [(10, 20), (30, 40, 50)]
    render_frame.assert_not_called()
    assert [result.path for result in results] == [request.output_path for request in requests]
    assert [result.facts.source_frame for result in results] == [10, 20, 30, 40, 50]
    reporter.start_phase.assert_called_once_with("Screenshots", len(requests))
    reporter.set_description.assert_not_called()
    assert sorted(call.args[0] for call in reporter.advance.call_args_list) == [2, 3]


def test_render_batch_parallelizes_clip_units_but_serializes_each_clip(
    tmp_path: Path,
) -> None:
    requests = [
        RenderRequest(
            clip=Path(clip_name),
            diagnostic_source=Path(clip_name),
            frame_number=frame,
            output_path=tmp_path / f"{clip_name}-{frame}.jpg",
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        for clip_name, frames in (("reference.mkv", [10, 20]), ("comparison.mkv", [30, 40]))
        for frame in frames
    ]
    first_frame_by_clip = {Path("reference.mkv"): 10, Path("comparison.mkv"): 30}
    both_clips_started = Barrier(2)
    state_lock = Lock()
    active_by_clip: dict[Path, int] = {}
    calls_by_clip: dict[Path, list[int]] = {}

    def render_single(request: RenderRequest) -> RenderedFrameResult:
        clip = request.clip
        assert isinstance(clip, Path)
        with state_lock:
            active_by_clip[clip] = active_by_clip.get(clip, 0) + 1
            assert active_by_clip[clip] == 1
            calls_by_clip.setdefault(clip, []).append(request.frame_number)
        try:
            if request.frame_number == first_frame_by_clip[clip]:
                both_clips_started.wait(timeout=1.0)
            return _rendered(request)
        finally:
            with state_lock:
                active_by_clip[clip] -= 1

    with patch(
        "frame_compare.render.batch.orchestrator.render_frame_detailed",
        side_effect=render_single,
    ):
        results = render_batch_detailed(
            requests,
            parallelism=2,
            work_unit_ranges=[range(0, 2), range(2, 4)],
        )

    assert calls_by_clip == {
        Path("reference.mkv"): [10, 20],
        Path("comparison.mkv"): [30, 40],
    }
    assert [result.facts.source_frame for result in results] == [10, 20, 30, 40]


def test_clip_unit_failure_preserves_partial_serialized_progress_and_admission(
    tmp_path: Path,
) -> None:
    first_advance_started = Event()
    release_first_advance = Event()
    second_clip_started = Event()
    second_clip_blocked = Event()
    release_second_clip = Event()
    failure_reported = Event()
    progress_state_lock = Lock()
    active_advances = 0
    max_active_advances = 0
    invoked_frames: list[int] = []
    exceptions: list[BaseException] = []
    requests = [
        RenderRequest(
            clip=Path(clip_name),
            diagnostic_source=Path(clip_name),
            frame_number=frame,
            output_path=tmp_path / f"{clip_name}-{frame}.jpg",
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        for clip_name, frames in (
            ("failing.mkv", [0, 1]),
            ("in-flight.mkv", [2, 3]),
            ("later.mkv", [4]),
        )
        for frame in frames
    ]
    reporter = MagicMock(spec=ProgressReporter)

    def advance(_amount: int = 1) -> None:
        nonlocal active_advances, max_active_advances
        with progress_state_lock:
            active_advances += 1
            max_active_advances = max(max_active_advances, active_advances)
            first = reporter.advance.call_count == 1
        try:
            if first:
                first_advance_started.set()
                assert release_first_advance.wait(timeout=2.0)
        finally:
            with progress_state_lock:
                active_advances -= 1

    reporter.advance.side_effect = advance

    def render_single(request: RenderRequest) -> RenderedFrameResult:
        invoked_frames.append(request.frame_number)
        if request.frame_number == 1:
            assert second_clip_blocked.wait(timeout=2.0)
            failure_reported.set()
            raise RuntimeError("failed after one screenshot")
        if request.frame_number == 2:
            second_clip_started.set()
            assert first_advance_started.wait(timeout=2.0)
        elif request.frame_number == 3:
            second_clip_blocked.set()
            assert release_second_clip.wait(timeout=2.0)
        return _rendered(request)

    def run_render() -> None:
        try:
            render_batch_detailed(
                requests,
                parallelism=2,
                reporter=reporter,
                work_unit_ranges=[range(0, 2), range(2, 4), range(4, 5)],
            )
        except BaseException as exc:
            exceptions.append(exc)

    with patch(
        "frame_compare.render.batch.orchestrator.render_frame_detailed",
        side_effect=render_single,
    ):
        thread = Thread(target=run_render, daemon=True)
        thread.start()
        try:
            assert second_clip_started.wait(timeout=2.0)
            assert first_advance_started.wait(timeout=2.0)
            release_first_advance.set()
            assert failure_reported.wait(timeout=2.0)
            assert 4 not in invoked_frames
        finally:
            release_first_advance.set()
            release_second_clip.set()
            thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert len(exceptions) == 1
    assert isinstance(exceptions[0], RuntimeError)
    assert str(exceptions[0]) == "failed after one screenshot"
    assert set(invoked_frames) == {0, 1, 2, 3}
    assert invoked_frames.index(0) < invoked_frames.index(1)
    assert invoked_frames.index(2) < invoked_frames.index(3)
    assert reporter.advance.call_count == 3
    assert max_active_advances == 1
    reporter.complete_phase.assert_called_once_with(ProgressPhaseStatus.FAILED)


def test_render_batch_parallel_mixes_indivisible_ffmpeg_groups_and_singletons(
    tmp_path: Path,
) -> None:
    default_runner = DefaultFFmpegRunner()
    singleton_runner = _CustomFFmpegRunner()
    requests = [
        RenderRequest(
            clip=Path(clip_name),
            diagnostic_source=Path(clip_name),
            frame_number=frame,
            output_path=tmp_path / f"{clip_name}-{frame}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
            ffmpeg_runner=runner,
        )
        for clip_name, frames, runner in (
            ("first.mkv", [1, 2], default_runner),
            ("single.mkv", [3], singleton_runner),
            ("last.mkv", [4, 5], default_runner),
        )
        for frame in frames
    ]
    batches: list[list[int]] = []
    singletons: list[int] = []

    def render_ffmpeg_group(
        group: list[RenderRequest],
        *,
        abort: Callable[[], bool] | None = None,
    ) -> list[RenderedFrameResult]:
        batches.append([request.frame_number for request in group])
        return [_rendered(request) for request in group]

    def render_single(request: RenderRequest) -> RenderedFrameResult:
        singletons.append(request.frame_number)
        return _rendered(request)

    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_ffmpeg_batch_detailed",
            side_effect=render_ffmpeg_group,
        ),
        patch(
            "frame_compare.render.batch.orchestrator.render_frame_detailed",
            side_effect=render_single,
        ),
    ):
        results = render_batch_detailed(requests, parallelism=2)

    assert sorted(batches) == [[1, 2], [4, 5]]
    assert singletons == [3]
    assert [result.facts.source_frame for result in results] == [1, 2, 3, 4, 5]


def test_render_batch_parallel_failure_does_not_schedule_later_work(tmp_path: Path) -> None:
    failing_runner = DefaultFFmpegRunner()
    singleton_runner = _CustomFFmpegRunner()
    requests = [
        RenderRequest(
            clip=Path(clip_name),
            diagnostic_source=Path(clip_name),
            frame_number=frame,
            output_path=tmp_path / f"{clip_name}-{frame}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
            ffmpeg_runner=runner,
        )
        for clip_name, frames, runner in (
            ("failing.mkv", [0, 1], failing_runner),
            ("in-flight.mkv", [2], singleton_runner),
            ("later.mkv", [3], singleton_runner),
        )
        for frame in frames
    ]
    failure_reported = Event()
    in_flight_started = Event()
    release_in_flight = Event()
    exceptions: list[BaseException] = []
    invoked_singletons: list[int] = []

    def render_failing_group(
        _group: list[RenderRequest], *, abort: Callable[[], bool] | None = None
    ) -> list[RenderedFrameResult]:
        assert in_flight_started.wait(timeout=1.0)
        failure_reported.set()
        raise RuntimeError("failed batch")

    def render_single(request: RenderRequest) -> RenderedFrameResult:
        invoked_singletons.append(request.frame_number)
        if request.frame_number == 2:
            in_flight_started.set()
            assert release_in_flight.wait(timeout=1.0)
        return _rendered(request)

    def run_render() -> None:
        try:
            render_batch_detailed(requests, parallelism=2)
        except BaseException as exc:
            exceptions.append(exc)

    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_ffmpeg_batch_detailed",
            side_effect=render_failing_group,
        ),
        patch(
            "frame_compare.render.batch.orchestrator.render_frame_detailed",
            side_effect=render_single,
        ),
    ):
        thread = Thread(target=run_render, daemon=True)
        thread.start()
        try:
            assert failure_reported.wait(timeout=1.0)
            assert in_flight_started.wait(timeout=1.0)
            assert 3 not in invoked_singletons
        finally:
            release_in_flight.set()
            thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert len(exceptions) == 1
    assert isinstance(exceptions[0], RuntimeError)
    assert str(exceptions[0]) == "failed batch"
    assert 3 not in invoked_singletons


@pytest.mark.parametrize("real_failure", [False, True])
def test_clip_workers_stop_before_next_frame_and_preserve_first_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, real_failure: bool
) -> None:
    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint

    started = [Event(), Event()]
    release = Event()
    calls: list[int] = []
    requested_cancel = False
    requests = [
        RenderRequest(
            clip=MagicMock(),
            diagnostic_source=tmp_path / "video.mkv",
            frame_number=frame,
            output_path=tmp_path / f"{frame}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        for frame in range(8)
    ]

    def render(request: RenderRequest) -> RenderedFrameResult:
        calls.append(request.frame_number)
        if request.frame_number in (0, 4):
            started[request.frame_number // 4].set()
            if real_failure and request.frame_number == 0:
                assert started[1].wait(2)
                raise RuntimeError("first render failure")
            assert release.wait(2)
        return _rendered(request)

    def poll(
        futures: Iterable[Future[list[RenderedFrameResult]]],
        *,
        timeout: float,
        return_when: str,
    ) -> tuple[set[Future[list[RenderedFrameResult]]], set[Future[list[RenderedFrameResult]]]]:
        nonlocal requested_cancel
        if requested_cancel:
            # The preceding poll gave the main thread time to propagate stop.
            release.set()
        else:
            assert all(event.wait(2) for event in started)
        outcome = real_wait(futures, timeout=timeout, return_when=return_when)
        if not requested_cancel:
            task = asyncio.current_task()
            assert task is not None
            task.cancel()
            requested_cancel = True
        return outcome

    monkeypatch.setattr("frame_compare.render.batch.orchestrator.wait", poll)
    monkeypatch.setattr("frame_compare.render.batch.orchestrator.render_frame_detailed", render)

    async def run() -> None:
        try:
            if real_failure:
                with pytest.raises(RuntimeError, match="first render failure"):
                    render_batch_detailed(
                        requests, parallelism=2, work_unit_ranges=[range(4), range(4, 8)]
                    )
            else:
                with suppress(_RunInterrupt):
                    render_batch_detailed(
                        requests, parallelism=2, work_unit_ranges=[range(4), range(4, 8)]
                    )
            assert sorted(calls) == [0, 4]
        finally:
            release.set()
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())


@pytest.mark.parametrize("parallelism", [1, 2])
def test_ffmpeg_batch_stop_reaps_child_without_publishing_partial_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, parallelism: int
) -> None:
    import subprocess
    import sys

    from frame_compare.utils import subproc
    from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint

    ready = tmp_path / "ready"
    runner = DefaultFFmpegRunner(extraction_timeout_seconds=3)
    requests = [
        RenderRequest(
            clip=tmp_path / "clip.mkv",
            diagnostic_source=tmp_path / "clip.mkv",
            frame_number=frame,
            output_path=tmp_path / f"{frame}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
            ffmpeg_runner=runner,
        )
        for frame in range(3)
    ]
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen
    task: asyncio.Task[None] | None = None
    requested_cancel = False

    def popen(
        argv: list[str], *, cwd: Path | None, stdout: int, stderr: int, shell: bool
    ) -> subprocess.Popen[bytes]:
        process = original_popen(argv, cwd=cwd, stdout=stdout, stderr=stderr, shell=shell)
        processes.append(process)
        return process

    def cancel_when_ready() -> bool:
        nonlocal requested_cancel
        if ready.exists() and not requested_cancel:
            assert task is not None
            task.cancel()
            requested_cancel = True
        return task is not None and task.cancelling() > 0

    monkeypatch.setattr(subproc, "Popen", popen)
    monkeypatch.setattr("frame_compare.render.batch.orchestrator.is_cancelling", cancel_when_ready)
    monkeypatch.setattr(
        "frame_compare.render.backend.ffmpeg.build_extract_frames_argv",
        lambda **kwargs: [
            sys.executable,
            "-c",
            "import pathlib,sys,time; pathlib.Path(sys.argv[1]).touch(); time.sleep(30)",
            str(ready),
        ],
    )

    async def run() -> None:
        nonlocal task
        task = asyncio.current_task()
        with pytest.raises(_RunInterrupt):
            render_batch_detailed(requests, parallelism=parallelism)
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
    assert requested_cancel
    assert len(processes) == 1
    assert processes[0].returncode is not None
    assert not any(request.output_path.exists() for request in requests)
    assert not list(tmp_path.glob(".frame-compare-ffmpeg-*"))


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX SIGINT injection; Windows console behavior requires physical acceptance",
)
def test_real_sigint_stops_frame_admission_within_150ms() -> None:
    script = textwrap.dedent(
        """
        import asyncio
        import json
        import os
        import signal
        import sys
        import time
        from concurrent.futures import wait as real_wait
        from contextlib import suppress
        from pathlib import Path
        from threading import Event, Lock, Thread
        from unittest.mock import MagicMock

        from frame_compare.render.batch import orchestrator
        from frame_compare.render.types import EncoderSettings, RenderedFrameResult, RenderRequest
        from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint
        from frame_compare.utils.media_facts import RenderedFrameFacts

        slow_poll = sys.argv[1] == 'slow'
        entered_wait = Event()
        started = [Event(), Event()]
        lock = Lock()
        admissions = []
        signal_time = []
        interrupt_observed = []
        sender_errors = []
        requests = [
            RenderRequest(clip=MagicMock(), diagnostic_source=Path('probe.mkv'),
                          frame_number=i, output_path=Path(f'{i}.png'), overlay=None,
                          encoder_settings=EncoderSettings())
            for i in range(120)
        ]

        def render(request):
            with lock:
                admissions.append(time.monotonic())
            if request.frame_number in (0, 60):
                started[request.frame_number // 60].set()
            time.sleep(0.02)
            return RenderedFrameResult(path=request.output_path,
                                       facts=RenderedFrameFacts(source_frame=request.frame_number))

        def poll(futures, *, timeout, return_when):
            entered_wait.set()
            return real_wait(futures, timeout=0.25 if slow_poll else timeout,
                             return_when=return_when)

        def send_interrupt():
            try:
                assert entered_wait.wait(2)
                assert all(event.wait(2) for event in started)
                time.sleep(0.005)
                signal_time.append(time.monotonic())
                os.kill(os.getpid(), signal.SIGINT)
            except BaseException as error:
                sender_errors.append(repr(error))

        async def run():
            sender = Thread(target=send_interrupt)
            sender.start()
            try:
                with suppress(_RunInterrupt):
                    orchestrator.render_batch_detailed(
                        requests, parallelism=2, work_unit_ranges=[range(60), range(60, 120)]
                    )
            finally:
                sender.join(timeout=2)
                assert not sender.is_alive()
            task = asyncio.current_task()
            assert task is not None and task.cancelling() > 0
            interrupt_observed.append(time.monotonic())
            await cancellation_checkpoint()

        orchestrator.render_frame_detailed = render
        orchestrator.wait = poll
        try:
            asyncio.run(run())
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        else:
            raise AssertionError('Expected Runner cancellation')
        assert len(interrupt_observed) == 1, "Runner did not cancel the main task"
        assert not sender_errors, sender_errors
        assert len(signal_time) == 1
        last_start_seconds = max(admissions) - signal_time[0]
        print(json.dumps({'last_start_seconds': last_start_seconds,
                          'signal_to_exit_seconds': time.monotonic() - signal_time[0]}))
        """
    )
    # The bound is the approved 50 ms plus 100 ms slack, independent of the
    # production constant or mutation: a slower poll cannot relax the assertion.
    for mode in ("slow", "production"):
        completed = subprocess.run(
            [sys.executable, "-c", script, mode],
            capture_output=True,
            text=True,
            check=True,
            timeout=8,
        )
        measured = json.loads(completed.stdout)
        last_start = measured["last_start_seconds"]
        print(f"{mode}: {measured}")
        if mode == "slow":
            assert last_start > 0.150, "250 ms mutation did not violate the admission bound"
        else:
            assert last_start <= 0.150, measured
