"""Package-root runner surface for Frame Compare 2.0."""

from __future__ import annotations

from frame_compare.orchestration.coordinator import (
    RunDependencies,
    RunRequest,
    RunResult,
)

__all__ = ["RunDependencies", "RunRequest", "RunResult", "run"]


def run(request: RunRequest, dependencies: RunDependencies | None = None) -> RunResult:
    """Run a comparison request.

    Raises:
        NotImplementedError: Always, until the runner implementation lands.
    """
    raise NotImplementedError("frame_compare.runner.run is not implemented yet (scaffold)")
