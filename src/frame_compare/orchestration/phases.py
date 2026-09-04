"""Phase definitions and execution wiring for Frame Compare.

This module defines the comparison pipeline phases and their execution behavior.
See docs/current-architecture.md for the canonical phase ordering semantics.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

import structlog

from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.progress import phase_display_label, start_phase_progress
from frame_compare.utils.progress import LogProgressReporter
from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter

log = structlog.get_logger()


class PhaseStatus(StrEnum):
    """Canonical phase execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    WARNED = "warned"
    FAILED = "failed"


PhaseExecute = Callable[[RunContext], Awaitable[None]]
PhaseSkipCondition = Callable[[ConfigSchema], bool]
PhaseSkipDetail = str | Callable[[ConfigSchema], str | None]


@dataclass
class Phase:
    """Single orchestration phase definition."""

    name: str
    execute: PhaseExecute
    skip_condition: PhaseSkipCondition | None = None
    progress_total: int = 1
    display_label: str | None = None
    status: PhaseStatus = PhaseStatus.PENDING
    warn_only: bool = False
    fatal_exceptions: tuple[type[BaseException], ...] = ()
    retain_on_success: bool | None = None
    skip_detail: PhaseSkipDetail | None = None

    @property
    def progress_label(self) -> str:
        """Human label used by interactive progress reporters."""
        if self.display_label is not None:
            return self.display_label
        return phase_display_label(self.name)


async def execute_phases(
    phases: list[Phase],
    context: RunContext,
    reporter: ProgressReporter,
) -> None:
    """Execute phases in order with skip + failure semantics.

    Raises:
        Exception: Propagates any exception from a required phase.
    """
    for phase in phases:
        if phase.skip_condition is not None and phase.skip_condition(context.config):
            phase.status = PhaseStatus.SKIPPED
            skip_detail = (
                phase.skip_detail(context.config)
                if callable(phase.skip_detail)
                else phase.skip_detail
            )
            start_phase_progress(
                reporter,
                name=phase.name,
                display_label=(
                    f"{phase.progress_label}  {skip_detail}"
                    if skip_detail is not None
                    else phase.progress_label
                ),
                total=phase.progress_total,
            )
            reporter.set_description("Skipped")
            reporter.complete_phase(ProgressPhaseStatus.SKIPPED)
            continue

        phase.status = PhaseStatus.RUNNING
        start_phase_progress(
            reporter,
            name=phase.name,
            display_label=phase.progress_label,
            total=phase.progress_total,
        )
        phase_progress_status = ProgressPhaseStatus.COMPLETED
        try:
            await phase.execute(context)
        except Exception as exc:
            if not phase.warn_only or isinstance(exc, phase.fatal_exceptions):
                phase.status = PhaseStatus.FAILED
                phase_progress_status = ProgressPhaseStatus.FAILED
                raise
            phase.status = PhaseStatus.WARNED
            phase_progress_status = ProgressPhaseStatus.WARNED
            if isinstance(reporter, LogProgressReporter):
                log.warning(
                    "phase_warned",
                    phase=phase.name,
                    error_type=type(exc).__name__,
                    error=str(exc),
                    exc_info=exc,
                )
        except BaseException:
            # Cancellation and other control-flow exceptions do not inherit
            # from Exception.  They still need a terminal lifecycle status so
            # progress cannot report a cancelled phase as completed.
            phase.status = PhaseStatus.FAILED
            phase_progress_status = ProgressPhaseStatus.FAILED
            raise
        else:
            phase.status = PhaseStatus.COMPLETED
            reporter.advance(1)
        finally:
            if phase.retain_on_success is None:
                reporter.complete_phase(phase_progress_status)
            else:
                reporter.complete_phase(
                    phase_progress_status,
                    retain=phase.retain_on_success,
                )
