"""Phase definitions and execution wiring for Frame Compare.

This module defines the comparison pipeline phases and their execution behavior.
See orchestration-module.md §4.4.4 for the canonical phase ordering semantics.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum

import structlog

from frame_compare.config import ConfigSchema
from frame_compare.orchestration.context import RunContext
from frame_compare.utils.progress import ProgressReporter

log = structlog.get_logger()


class PhaseStatus(str, Enum):
    """Canonical phase execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    WARNED = "warned"
    FAILED = "failed"


PhaseExecute = Callable[[RunContext], Awaitable[None]]
PhaseSkipCondition = Callable[[ConfigSchema], bool]


@dataclass
class Phase:
    """Single orchestration phase definition."""

    name: str
    execute: PhaseExecute
    skip_condition: PhaseSkipCondition | None = None
    progress_total: int = 1
    status: PhaseStatus = PhaseStatus.PENDING
    warn_only: bool = False


async def execute_phases(
    phases: list[Phase],
    context: RunContext,
    reporter: ProgressReporter,
) -> None:
    """Execute phases in order with skip + failure semantics per SSOT.

    Raises:
        Exception: Propagates any exception from a required phase.
    """
    for phase in phases:
        if phase.skip_condition is not None and phase.skip_condition(context.config):
            phase.status = PhaseStatus.SKIPPED
            reporter.start_phase(phase.name, total=phase.progress_total)
            reporter.set_description("Skipped")
            reporter.complete_phase()
            continue

        phase.status = PhaseStatus.RUNNING
        reporter.start_phase(phase.name, total=phase.progress_total)
        try:
            await phase.execute(context)
        except Exception as exc:
            if not phase.warn_only:
                phase.status = PhaseStatus.FAILED
                raise
            phase.status = PhaseStatus.WARNED
            log.warning(
                "phase_warned",
                phase=phase.name,
                error_type=type(exc).__name__,
                error=str(exc),
                exc_info=exc,
            )
        else:
            phase.status = PhaseStatus.COMPLETED
            reporter.advance(1)
        finally:
            reporter.complete_phase()
