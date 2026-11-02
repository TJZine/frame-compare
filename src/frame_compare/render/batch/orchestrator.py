from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Event, Lock
from typing import TYPE_CHECKING

from frame_compare.render.batch.expansion import (
    expand_batch_render_requests,
    resolve_batch_ffmpeg_runner,
    resolve_target_renderer,
    validate_batch_requests,
    validate_ffmpeg_batch_tonemap_gate,
)
from frame_compare.render.encoders import (
    is_ffmpeg_batch_compatible,
    render_ffmpeg_batch_detailed,
    render_frame_detailed,
)
from frame_compare.render.types import (
    BatchRenderOptions,
    PreparedClipRender,
    RenderedClip,
    RenderedFrameResult,
    RenderedScreenshot,
    RenderRequest,
    ScreenshotBatchRequest,
)
from frame_compare.utils.cancellation import is_cancelling, raise_if_cancelling
from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter
from frame_compare.utils.subproc import SubprocessAborted

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema


_RENDER_POLL_INTERVAL_SECONDS = 0.05


class _RenderStopped(Exception):
    """A clip drained its in-flight frame after stop admission closed."""


def _render_work_unit(
    requests: tuple[RenderRequest, ...],
    on_progress: Callable[[int], None] | None = None,
    stop: Event | None = None,
) -> list[RenderedFrameResult]:
    """Render one logical unit, batching FFmpeg or serializing its other frames."""
    request_list = list(requests)
    if not request_list:
        return []
    is_ffmpeg_batch = len(request_list) > 1 and _can_batch_clip(request_list)
    rendered: list[RenderedFrameResult]
    if is_ffmpeg_batch:
        try:
            rendered = render_ffmpeg_batch_detailed(
                request_list, abort=is_cancelling if stop is None else stop.is_set
            )
        except SubprocessAborted:
            if stop is None:
                raise_if_cancelling()
                raise
            raise _RenderStopped() from None
    else:
        rendered = []
        for request in request_list:
            if stop is None:
                raise_if_cancelling()
            elif stop.is_set():
                raise _RenderStopped()
            rendered.append(render_frame_detailed(request))
            if on_progress is not None:
                on_progress(1)
    if on_progress is not None and is_ffmpeg_batch:
        on_progress(len(rendered))
    return rendered


def _can_batch_clip(requests: list[RenderRequest]) -> bool:
    first = requests[0]
    previous_frame = -1
    for request in requests:
        if not is_ffmpeg_batch_compatible(first, request, previous_frame=previous_frame):
            return False
        previous_frame = request.frame_number
    return True


def _completed_clip(job: PreparedClipRender, results: list[RenderedFrameResult]) -> RenderedClip:
    if len(results) != len(job.frames):
        raise RuntimeError("render clip completed without one result per request")
    return RenderedClip(
        job.label,
        job.clip_facts,
        tuple(
            RenderedScreenshot(selection, result)
            for selection, result in zip(job.frames, results, strict=True)
        ),
    )


def _render_jobs_parallel(
    jobs: Sequence[PreparedClipRender],
    results: list[RenderedClip | None],
    parallelism: int,
    on_progress: Callable[[int], None] | None,
) -> None:
    futures: dict[Future[list[RenderedFrameResult]], int] = {}
    next_job = 0
    first_exception: tuple[int, Exception] | None = None
    stop = Event()
    with ThreadPoolExecutor(max_workers=parallelism) as executor:

        def submit() -> None:
            nonlocal next_job
            futures[
                executor.submit(_render_work_unit, jobs[next_job].requests, on_progress, stop)
            ] = next_job
            next_job += 1

        while next_job < min(parallelism, len(jobs)):
            if is_cancelling():
                stop.set()
                break
            submit()
        while futures:
            if is_cancelling():
                stop.set()
            done, _ = wait(
                futures, timeout=_RENDER_POLL_INTERVAL_SECONDS, return_when=FIRST_COMPLETED
            )
            if is_cancelling():
                stop.set()
            for future in done:
                index = futures.pop(future)
                try:
                    results[index] = _completed_clip(jobs[index], future.result())
                except _RenderStopped:
                    # Progress was recorded as each admitted frame drained; partial
                    # clips are never published as successful results.
                    continue
                except CancelledError as exc:
                    if future.cancelled():
                        continue
                    if first_exception is None or index < first_exception[0]:
                        first_exception = (index, exc)
                    stop.set()
                except Exception as exc:
                    if first_exception is None or index < first_exception[0]:
                        first_exception = (index, exc)
                    stop.set()
            if first_exception is not None or is_cancelling():
                stop.set()
                for future in futures:
                    future.cancel()
            while (
                first_exception is None
                and not stop.is_set()
                and not is_cancelling()
                and next_job < len(jobs)
                and len(futures) < parallelism
            ):
                submit()
    if first_exception is not None:
        raise first_exception[1]
    raise_if_cancelling()


def render_clip_jobs(
    jobs: Sequence[PreparedClipRender],
    *,
    parallelism: int = 1,
    reporter: ProgressReporter | None = None,
) -> tuple[RenderedClip, ...]:
    """Render indivisible per-clip jobs in stable clip and screenshot order."""
    if not jobs:
        return ()
    results: list[RenderedClip | None] = [None] * len(jobs)
    on_progress: Callable[[int], None] | None = None
    if reporter is not None:
        reporter.start_phase("Screenshots", sum(len(job.requests) for job in jobs))
        progress_lock = Lock()

        def advance(amount: int) -> None:
            with progress_lock:
                reporter.advance(amount)

        on_progress = advance
    status = ProgressPhaseStatus.COMPLETED
    try:
        if parallelism <= 1:
            for index, job in enumerate(jobs):
                raise_if_cancelling()
                results[index] = _completed_clip(job, _render_work_unit(job.requests, on_progress))
            raise_if_cancelling()
        else:
            _render_jobs_parallel(jobs, results, parallelism, on_progress)
        completed: list[RenderedClip] = []
        for result in results:
            if result is None:
                raise RuntimeError("render jobs completed without a rendered clip")
            completed.append(result)
        return tuple(completed)
    except BaseException:
        status = ProgressPhaseStatus.FAILED
        raise
    finally:
        if reporter is not None:
            reporter.complete_phase(status)


def render_screenshots_from_batch_detailed(
    batch_requests: list[ScreenshotBatchRequest],
    output_dir: Path,
    config: ConfigSchema,
    options: BatchRenderOptions | None = None,
) -> tuple[RenderedClip, ...]:
    """Prepare and render a stable sequence of clips with their selected screenshots."""
    if not batch_requests:
        return ()
    resolved_options = options or BatchRenderOptions()
    resolved_ffmpeg_runner = resolve_batch_ffmpeg_runner(
        resolved_options.ffmpeg_runner,
        extraction_timeout_seconds=config.screenshots.ffmpeg_timeout_seconds,
    )
    target_renderer = resolve_target_renderer(config, resolved_options.renderer)

    validate_ffmpeg_batch_tonemap_gate(batch_requests, config, target_renderer)
    validate_batch_requests(batch_requests)

    jobs = expand_batch_render_requests(
        batch_requests,
        output_dir=output_dir,
        config=config,
        overlay_mode=resolved_options.overlay_mode,
        renderer=target_renderer,
        ffmpeg_runner=resolved_ffmpeg_runner,
    )

    return render_clip_jobs(
        jobs, parallelism=max(1, resolved_options.parallelism), reporter=resolved_options.reporter
    )
