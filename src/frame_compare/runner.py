"""Package-root runner surface for Frame Compare 2.0."""

from __future__ import annotations

import asyncio

from frame_compare.orchestration import coordinator
from frame_compare.orchestration.coordinator import (
    RunDependencies,
    RunRequest,
    RunResult,
)

__all__ = ["RunDependencies", "RunRequest", "RunResult", "run"]


def run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
    """Run a comparison request.

    Raises:
        RuntimeError: If called from a running event loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        import logging

        logging.getLogger("frame_compare.runner").debug(
            "No running event loop detected; running via asyncio.run is safe."
        )
    else:
        raise RuntimeError(
            "Do not call frame_compare.runner.run from an async context; "
            "await frame_compare.orchestration.execute_run instead."
        )

    execute_run = getattr(coordinator, "execute_run", None)
    if execute_run is None:
        raise NotImplementedError(
            "Missing required entry point: frame_compare.orchestration.coordinator.execute_run"
        )
    return asyncio.run(execute_run(request, dependencies))
