from pathlib import Path
from threading import Event, Thread
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ColorConfig, ConfigSchema
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
    with patch("frame_compare.render.batch.orchestrator.render_frame_detailed") as mock_render:
        mock_render.side_effect = _rendered
        results = render_batch_detailed(requests, parallelism=2)
        assert [result.path for result in results] == [r.output_path for r in requests]
        assert [result.facts.source_frame for result in results] == [
            r.frame_number for r in requests
        ]


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
