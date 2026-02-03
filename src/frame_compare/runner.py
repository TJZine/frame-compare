"""Package-root runner surface for Frame Compare 2.0."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

import httpx

from frame_compare.orchestration import coordinator
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, RunResult
from frame_compare.orchestration.progress import select_reporter

__all__ = ["RunDependencies", "RunRequest", "RunResult", "run"]


def run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
    """Run a comparison request.

    Raises:
        RuntimeError: If called from a running event loop.
        NotImplementedError: If the orchestration execute_run entry point is missing.
    """
    execute_run = getattr(coordinator, "execute_run", None)
    if execute_run is None:
        raise NotImplementedError(
            "Missing required entry point: frame_compare.orchestration.coordinator.execute_run"
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "Do not call frame_compare.runner.run from an async context; "
            "await frame_compare.orchestration.coordinator.execute_run instead."
        )

    if dependencies is None:
        effective_deps = RunDependencies()
    else:
        effective_deps = RunDependencies(
            vs_loader=dependencies.vs_loader,
            ffmpeg_runner=dependencies.ffmpeg_runner,
            http_client=dependencies.http_client,
            progress=dependencies.progress,
            clock=dependencies.clock,
        )

    if effective_deps.progress is None:
        effective_deps.progress = select_reporter(
            quiet=request.quiet,
            json_output=request.json_output,
        )

    execute_fn = cast(
        Callable[[RunRequest, RunDependencies], Awaitable[RunResult]],
        execute_run,
    )

    async def _run_with_client() -> RunResult:
        if effective_deps.http_client is not None:
            return await execute_fn(request, effective_deps)

        async with httpx.AsyncClient() as http_client:
            effective_deps.http_client = http_client
            return await execute_fn(request, effective_deps)

    return asyncio.run(_run_with_client())
