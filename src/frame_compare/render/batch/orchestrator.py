from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import TYPE_CHECKING

from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.render.batch.expansion import (
    expand_batch_render_requests,
    render_batch_results_by_label,
    resolve_batch_ffmpeg_runner,
    resolve_target_renderer,
    validate_batch_requests,
    validate_ffmpeg_batch_tonemap_gate,
)
from frame_compare.render.encoders import render_ffmpeg_batch_detailed, render_frame_detailed
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


type _RenderWorkUnit = tuple[int, tuple[RenderRequest, ...]]


def _render_work_units(requests: list[RenderRequest]) -> list[_RenderWorkUnit]:
    """Group compatible adjacent requests into indivisible render work units."""
    units: list[_RenderWorkUnit] = []
    index = 0
    while index < len(requests):
        end = _ffmpeg_batch_end(requests, index)
        units.append((index, tuple(requests[index:end])))
        index = end
    return units


def _render_work_unit(requests: tuple[RenderRequest, ...]) -> list[RenderedFrameResult]:
    """Render one logical unit, preserving FFmpeg batches as a single operation."""
    if len(requests) > 1:
        rendered = render_ffmpeg_batch_detailed(list(requests))
    else:
        request = next(iter(requests), None)
        if request is None:
            raise RuntimeError("render work unit cannot be empty")
        rendered = [render_frame_detailed(request)]
    if len(rendered) != len(requests):
        raise RuntimeError("render work unit completed without one result per request")
    return rendered


def _store_work_unit_results(
    unit: _RenderWorkUnit,
    rendered: list[RenderedFrameResult],
    results: list[RenderedFrameResult | None],
) -> None:
    start, requests = unit
    for offset, (_request, result) in enumerate(zip(requests, rendered, strict=True)):
        results[start + offset] = result


def _record_ready_progress(
    requests: list[RenderRequest],
    results: list[RenderedFrameResult | None],
    reporter: ProgressReporter | None,
    start: int,
) -> int:
    """Record the longest completed prefix so progress follows request order."""
    index = start
    while index < len(results) and results[index] is not None:
        _record_render_progress(reporter, requests[index])
        index += 1
    return index


def _submit_render_work_unit(
    executor: ThreadPoolExecutor,
    units: list[_RenderWorkUnit],
    futures: dict[Future[list[RenderedFrameResult]], _RenderWorkUnit],
    index: int,
) -> None:
    unit = units[index]
    futures[executor.submit(_render_work_unit, unit[1])] = unit


def _render_batch_sequential(
    requests: list[RenderRequest],
    results: list[RenderedFrameResult | None],
    reporter: ProgressReporter | None,
) -> None:
    next_progress_index = 0
    for unit in _render_work_units(requests):
        _store_work_unit_results(
            unit,
            _render_work_unit(unit[1]),
            results,
        )
        next_progress_index = _record_ready_progress(
            requests,
            results,
            reporter,
            next_progress_index,
        )


def _ffmpeg_batch_end(requests: list[RenderRequest], start: int) -> int:
    first = requests[start]
    runner = first.ffmpeg_runner
    if (
        not isinstance(first.clip, Path)
        or type(runner) is not DefaultFFmpegRunner
        or first.output_path.suffix.casefold() != ".png"
    ):
        return start + 1

    end = start + 1
    previous_frame = first.frame_number
    while end < len(requests):
        candidate = requests[end]
        if (
            candidate.clip != first.clip
            or candidate.ffmpeg_runner is not runner
            or candidate.geometry_plan is not first.geometry_plan
            or candidate.output_path.parent != first.output_path.parent
            or candidate.output_path.suffix.casefold() != ".png"
            or candidate.frame_number <= previous_frame
        ):
            break
        previous_frame = candidate.frame_number
        end += 1
    return end


def _render_batch_parallel(
    requests: list[RenderRequest],
    results: list[RenderedFrameResult | None],
    parallelism: int,
    reporter: ProgressReporter | None,
) -> None:
    units = _render_work_units(requests)
    futures: dict[Future[list[RenderedFrameResult]], _RenderWorkUnit] = {}
    next_unit_index = 0
    next_progress_index = 0
    first_exception: Exception | None = None

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        while next_unit_index < min(parallelism, len(units)):
            _submit_render_work_unit(executor, units, futures, next_unit_index)
            next_unit_index += 1

        while futures:
            done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
            completed: list[tuple[_RenderWorkUnit, list[RenderedFrameResult]]] = []
            for future in done:
                unit = futures.pop(future)
                try:
                    completed.append((unit, future.result()))
                except Exception as exc:
                    if first_exception is None:
                        first_exception = exc

            for unit, rendered in sorted(completed, key=lambda item: item[0][0]):
                _store_work_unit_results(unit, rendered, results)
            next_progress_index = _record_ready_progress(
                requests,
                results,
                reporter,
                next_progress_index,
            )

            if first_exception is not None:
                # Do not start new work after a failure. Cancel any futures that
                # have not begun; running renders are allowed to finish so the
                # executor has one deterministic cleanup path.
                for future in futures:
                    future.cancel()

            while (
                first_exception is None
                and next_unit_index < len(units)
                and len(futures) < parallelism
            ):
                _submit_render_work_unit(executor, units, futures, next_unit_index)
                next_unit_index += 1

    if first_exception is not None:
        for index in range(next_progress_index, len(results)):
            if results[index] is not None:
                _record_render_progress(reporter, requests[index])
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
