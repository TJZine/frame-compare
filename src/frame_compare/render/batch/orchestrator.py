from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import TYPE_CHECKING

from frame_compare.render.batch.expansion import (
    expand_batch_render_requests,
    render_batch_results_by_label,
    resolve_batch_ffmpeg_runner,
    resolve_target_renderer,
    validate_batch_requests,
    validate_ffmpeg_batch_tonemap_gate,
)
from frame_compare.render.encoders import render_frame_detailed
from frame_compare.render.types import (
    BatchRenderOptions,
    RenderedBatchResult,
    RenderedFrameResult,
    RenderRequest,
    ScreenshotBatchRequest,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema


def _render_description(request: RenderRequest) -> str:
    """Build a consistent progress description for a render request."""
    label = request.progress_label
    if label is None and request.overlay is not None:
        label = request.overlay.label
    return f"{label} - frame {request.frame_number}" if label else f"frame {request.frame_number}"


def _record_render_progress(
    reporter: ProgressReporter | None,
    request: RenderRequest,
) -> None:
    if reporter is None:
        return
    reporter.set_description(_render_description(request))
    reporter.advance(1)


def _submit_render_request(
    executor: ThreadPoolExecutor,
    requests: list[RenderRequest],
    futures: dict[Future[RenderedFrameResult], int],
    index: int,
) -> None:
    futures[executor.submit(render_frame_detailed, requests[index])] = index


def _render_batch_sequential(
    requests: list[RenderRequest],
    results: list[RenderedFrameResult | None],
    reporter: ProgressReporter | None,
) -> None:
    for index, request in enumerate(requests):
        results[index] = render_frame_detailed(request)
        _record_render_progress(reporter, request)


def _render_batch_parallel(
    requests: list[RenderRequest],
    results: list[RenderedFrameResult | None],
    parallelism: int,
    reporter: ProgressReporter | None,
) -> None:
    futures: dict[Future[RenderedFrameResult], int] = {}
    next_index = 0
    first_exception: Exception | None = None

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        while next_index < min(parallelism, len(requests)):
            _submit_render_request(executor, requests, futures, next_index)
            next_index += 1

        while futures:
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
            completed: list[tuple[int, RenderedFrameResult]] = []
            for future in done:
                index = futures.pop(future)
                try:
                    completed.append((index, future.result()))
                except Exception as exc:
                    if first_exception is None:
                        first_exception = exc

            for index, rendered_path in completed:
                results[index] = rendered_path
                _record_render_progress(reporter, requests[index])

            if first_exception is not None:
                # Do not start new work after a failure. Cancel any futures that
                # have not begun; running renders are allowed to finish so the
                # executor has one deterministic cleanup path.
                for future in futures:
                    future.cancel()

            while (
                first_exception is None
                and next_index < len(requests)
                and len(futures) < parallelism
            ):
                _submit_render_request(executor, requests, futures, next_index)
                next_index += 1

    if first_exception is not None:
        raise first_exception


def render_batch(
    requests: list[RenderRequest], parallelism: int = 1, reporter: ProgressReporter | None = None
) -> list[Path]:
    """
    Execute a batch of render requests.

    Args:
        requests: List of requests to process
        parallelism: Number of concurrent threads
        reporter: Optional progress reporter

    Returns:
        List of paths to rendered files in input order

    Raises:
        Exception: The first exception encountered during rendering (fail-fast).
            Once a failure occurs, no new tasks are scheduled. Any work already
            submitted to the executor is allowed to finish before the first
            exception is re-raised.
    """
    return [result.path for result in render_batch_detailed(requests, parallelism, reporter)]


def render_batch_detailed(
    requests: list[RenderRequest],
    parallelism: int = 1,
    reporter: ProgressReporter | None = None,
) -> list[RenderedFrameResult]:
    """Execute render jobs and preserve exact-frame facts in request order."""
    if not requests:
        return []

    results: list[RenderedFrameResult | None] = [None] * len(requests)

    if reporter:
        reporter.start_phase("Rendering", len(requests))

    phase_status = ProgressPhaseStatus.COMPLETED
    try:
        if parallelism <= 1:
            _render_batch_sequential(requests, results, reporter)
        else:
            _render_batch_parallel(requests, results, parallelism, reporter)
    except Exception:
        phase_status = ProgressPhaseStatus.FAILED
        raise
    finally:
        if reporter:
            reporter.complete_phase(phase_status)

    completed: list[RenderedFrameResult] = []
    for result in results:
        if result is None:
            raise RuntimeError("render batch completed without a rendered result")
        completed.append(result)
    return completed


def render_screenshots_from_batch(
    batch_requests: list[ScreenshotBatchRequest],
    output_dir: Path,
    config: ConfigSchema,
    options: BatchRenderOptions | None = None,
) -> dict[str, list[Path]]:
    """Render screenshots from batch requests, choosing FFmpeg or VapourSynth path accordingly.

    Args:
        batch_requests: List of ScreenshotBatchRequest
        output_dir: Output directory
        config: Configuration
        options: Renderer, overlay, FFmpeg, and progress options

    Returns:
        Dict mapping label -> list of rendered screenshot paths
    """
    return render_screenshots_from_batch_detailed(
        batch_requests, output_dir, config, options
    ).screenshots_by_label


def render_screenshots_from_batch_detailed(
    batch_requests: list[ScreenshotBatchRequest],
    output_dir: Path,
    config: ConfigSchema,
    options: BatchRenderOptions | None = None,
) -> RenderedBatchResult:
    """Render a validated batch with aligned path, frame-fact, and clip-fact mappings."""
    if not batch_requests:
        return RenderedBatchResult()
    resolved_options = options or BatchRenderOptions()
    resolved_ffmpeg_runner = resolve_batch_ffmpeg_runner(
        resolved_options.ffmpeg_runner,
        extraction_timeout_seconds=config.screenshots.ffmpeg_timeout_seconds,
    )
    target_renderer = resolve_target_renderer(config, resolved_options.renderer)

    validate_ffmpeg_batch_tonemap_gate(batch_requests, config, target_renderer)
    validate_batch_requests(batch_requests)

    all_requests, label_to_range, clip_facts = expand_batch_render_requests(
        batch_requests,
        output_dir=output_dir,
        config=config,
        overlay_mode=resolved_options.overlay_mode,
        renderer=target_renderer,
        ffmpeg_runner=resolved_ffmpeg_runner,
    )

    rendered = render_batch_detailed(
        all_requests,
        parallelism=max(1, resolved_options.parallelism),
        reporter=resolved_options.reporter,
    )
    rendered_paths = [result.path for result in rendered]
    screenshots = render_batch_results_by_label(batch_requests, rendered_paths, label_to_range)
    frame_facts = {
        request.label: [
            result.facts
            for result in rendered[
                label_to_range[request.label].start : label_to_range[request.label].stop
            ]
        ]
        for request in batch_requests
    }
    return RenderedBatchResult(
        screenshots_by_label=screenshots,
        frame_facts_by_label=frame_facts,
        clip_facts_by_label=clip_facts,
    )
