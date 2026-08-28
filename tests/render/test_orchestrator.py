from collections.abc import Sequence
from pathlib import Path
from threading import Barrier, Event, Lock, Thread
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from frame_compare.config.schema import ColorConfig, ConfigSchema
from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.render.batch.orchestrator import (
    ProgressReporter,
    render_batch,
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
            render_batch(requests, parallelism=2)

        invoked_requests = [call.args[0] for call in mock_render.call_args_list]
        assert requests[2] in invoked_requests
        assert len(invoked_requests) < len(requests)


@pytest.fixture
def default_config() -> ConfigSchema:
    """Default config with tonemap disabled for isolated tests."""
    return ConfigSchema(color=ColorConfig(enable_tonemap=False))


def test_render_batch_progress(mock_render_request):
    requests = [mock_render_request] * 3
    reporter = MagicMock(spec=ProgressReporter)

    with patch("frame_compare.render.batch.orchestrator.render_frame_detailed") as mock_render:
        mock_render.side_effect = _rendered
        render_batch(requests, parallelism=1, reporter=reporter)

        reporter.start_phase.assert_called_once_with("Rendering", 3)
        assert reporter.set_description.call_count == 3
        assert reporter.advance.call_count == 3
        reporter.complete_phase.assert_called_once()


def test_render_batch_progress_prefers_dedicated_presentation_label(mock_render_request):
    request = RenderRequest(
        clip=mock_render_request.clip,
        diagnostic_source=mock_render_request.diagnostic_source,
        frame_number=42,
        output_path=mock_render_request.output_path,
        overlay=None,
        encoder_settings=mock_render_request.encoder_settings,
        progress_label="Comparison 1 | ATV WEB-DL",
    )
    reporter = MagicMock(spec=ProgressReporter)

    with patch(
        "frame_compare.render.batch.orchestrator.render_frame_detailed",
        side_effect=_rendered,
    ):
        render_batch([request], reporter=reporter)

    reporter.set_description.assert_called_once_with("Comparison 1 | ATV WEB-DL - frame 42")


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
            render_batch(requests, parallelism=2)
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


def test_render_batch_marks_progress_failed_on_exception(mock_render_request) -> None:
    reporter = MagicMock(spec=ProgressReporter)

    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_frame_detailed",
            side_effect=RuntimeError("Failed"),
        ),
        pytest.raises(RuntimeError, match="Failed"),
    ):
        render_batch([mock_render_request], parallelism=1, reporter=reporter)

    reporter.complete_phase.assert_called_once_with(ProgressPhaseStatus.FAILED)


def test_render_batch_sequential(mock_render_request):
    requests = [mock_render_request] * 3
    with patch("frame_compare.render.batch.orchestrator.render_frame_detailed") as mock_render:
        mock_render.side_effect = _rendered
        results = render_batch(requests, parallelism=1)
        assert results == [r.output_path for r in requests]
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


def test_render_batch_sequential_batches_adjacent_default_ffmpeg_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = DefaultFFmpegRunner()
    batches: list[tuple[Path, list[int]]] = []

    def _extract_frames(
        video: Path,
        frame_nums: Sequence[int],
        output_dir: Path,
        **_kwargs: object,
    ) -> list[RenderedFrameFacts]:
        batches.append((video, list(frame_nums)))
        for index in range(len(frame_nums)):
            Image.new("RGB", (2, 2), color=(index, 0, 0)).save(output_dir / f"{index:09d}.png")
        return [
            RenderedFrameFacts(source_frame=frame_num, picture_type="I") for frame_num in frame_nums
        ]

    monkeypatch.setattr(runner, "extract_frames", _extract_frames)
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
        for frame in [10, 20, 42]
    ]

    results = render_batch_detailed(requests, parallelism=1)

    assert batches == [(Path("video.mkv"), [10, 20, 42])]
    assert [result.path for result in results] == [request.output_path for request in requests]
    assert [result.facts.source_frame for result in results] == [10, 20, 42]
    assert all(request.output_path.is_file() for request in requests)


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


def test_clip_unit_progress_advances_before_the_unit_finishes(tmp_path: Path) -> None:
    release_units = Event()
    progress_advanced = Event()
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
    reporter = MagicMock(spec=ProgressReporter)
    reporter.advance.side_effect = lambda _amount=1: progress_advanced.set()
    exceptions: list[BaseException] = []

    def render_single(request: RenderRequest) -> RenderedFrameResult:
        if request.frame_number in {20, 30}:
            assert release_units.wait(timeout=2.0)
        return _rendered(request)

    def run_render() -> None:
        try:
            render_batch_detailed(
                requests,
                parallelism=2,
                reporter=reporter,
                work_unit_ranges=[range(0, 2), range(2, 4)],
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
            assert progress_advanced.wait(timeout=1.0)
        finally:
            release_units.set()
            thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert exceptions == []
    reporter.start_phase.assert_called_once_with("Screenshots", 4)
    reporter.set_description.assert_not_called()
    assert reporter.advance.call_count == 4


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

    def render_failing_group(_group: list[RenderRequest]) -> list[RenderedFrameResult]:
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
