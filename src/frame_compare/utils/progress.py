"""Progress reporting utilities for Frame Compare."""

import structlog
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter

log = structlog.get_logger()

__all__ = [
    "LogProgressReporter",
    "NullProgressReporter",
    "ProgressReporter",
    "RichProgressReporter",
]


class NullProgressReporter:
    """No-op progress reporter."""

    def start_phase(self, name: str, total: int) -> None:
        del name, total

    def advance(self, amount: int = 1) -> None:
        del amount

    def set_description(self, desc: str) -> None:
        del desc

    def complete_phase(
        self,
        status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
    ) -> None:
        del self, status

    def suspend(self) -> None:
        del self

    def resume(self) -> None:
        del self


class RichProgressReporter:
    """Progress reporter using the rich library for CLI display."""

    def __init__(self, *, no_color: bool = False) -> None:
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            transient=True,
            console=Console(stderr=True, no_color=no_color),
        )
        self._task_id: TaskID | None = None
        self._task_stack: list[TaskID] = []
        self._task_totals: dict[TaskID, int] = {}
        self._suspend_depth = 0

    @property
    def no_color(self) -> bool:
        """Return whether Rich rendering disables ANSI color."""
        return self._progress.console.no_color

    @property
    def writes_to_stderr(self) -> bool:
        """Return whether Rich progress targets stderr."""
        return self._progress.console.stderr

    def start_phase(self, name: str, total: int) -> None:
        """Start a new phase with a rich progress bar."""
        if not self._progress.live.is_started:
            self._progress.start()
        if self._task_id is not None:
            self._progress.update(self._task_id, visible=False)
            self._task_stack.append(self._task_id)
        self._task_id = self._progress.add_task(name, total=total)
        self._task_totals[self._task_id] = total

    def advance(self, amount: int = 1) -> None:
        """Advance the rich progress bar."""
        if self._task_id is not None:
            self._progress.advance(self._task_id, amount)

    def set_description(self, desc: str) -> None:
        """Update the rich progress bar description."""
        if self._task_id is not None:
            self._progress.update(self._task_id, description=desc)

    def complete_phase(
        self,
        status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
    ) -> None:
        """Complete the current phase and stop progress if all tasks done."""
        if self._task_id is not None:
            total = self._task_totals.get(self._task_id)
            if status == ProgressPhaseStatus.SKIPPED:
                self._progress.update(self._task_id, description="Skipped")
            elif status == ProgressPhaseStatus.WARNED:
                self._progress.update(self._task_id, description="Warning")
            elif status == ProgressPhaseStatus.FAILED:
                self._progress.update(self._task_id, description="Failed")

            if total is not None and status in {
                ProgressPhaseStatus.COMPLETED,
                ProgressPhaseStatus.SKIPPED,
            }:
                self._progress.update(self._task_id, completed=total)
            self._progress.remove_task(self._task_id)
            self._task_totals.pop(self._task_id, None)
            self._task_id = None

        if self._task_stack:
            self._task_id = self._task_stack.pop()
            self._progress.update(self._task_id, visible=True)
            return

        if self._progress.live.is_started:
            self._progress.stop()

    def suspend(self) -> None:
        """Pause live progress rendering during blocking terminal interaction."""
        self._suspend_depth += 1
        if self._suspend_depth == 1 and self._progress.live.is_started:
            self._progress.stop()

    def resume(self) -> None:
        """Resume live progress rendering after blocking terminal interaction."""
        if self._suspend_depth == 0:
            return
        self._suspend_depth -= 1
        if (
            self._suspend_depth == 0
            and self._task_id is not None
            and not self._progress.live.is_started
        ):
            self._progress.start()


class LogProgressReporter:
    """Progress reporter that logs milestones via structlog."""

    def __init__(self) -> None:
        self._name: str = ""
        self._total: int = 0
        self._current: int = 0
        self._task_stack: list[tuple[str, int, int, int]] = []
        self._milestones: tuple[int, ...] = (10, 25, 50, 75, 100)
        self._last_logged_milestone: int = 0

    def start_phase(self, name: str, total: int) -> None:
        """Start logging a new phase."""
        if self._name:
            self._task_stack.append(
                (self._name, self._total, self._current, self._last_logged_milestone)
            )
        self._name = name
        self._total = total
        self._current = 0
        self._last_logged_milestone = 0
        log.info("phase_started", phase=name, total=total)

    def advance(self, amount: int = 1) -> None:
        """Advance progress and log milestones."""
        self._current += amount
        if self._total <= 0:
            return

        percentage = int((self._current / self._total) * 100)
        for m in self._milestones:
            if percentage >= m > self._last_logged_milestone:
                log.info(
                    "phase_progress",
                    phase=self._name,
                    percentage=m,
                    current=self._current,
                    total=self._total,
                )
                self._last_logged_milestone = m

    def set_description(self, desc: str) -> None:
        """No-op for log reporter."""
        del desc

    def complete_phase(
        self,
        status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
    ) -> None:
        """Log phase completion."""
        log.info("phase_completed", phase=self._name, status=status.value)
        if self._task_stack:
            self._name, self._total, self._current, self._last_logged_milestone = (
                self._task_stack.pop()
            )
            return
        self._name = ""
        self._total = 0
        self._current = 0
        self._last_logged_milestone = 0

    def suspend(self) -> None:
        """No-op for log reporter."""
        return

    def resume(self) -> None:
        """No-op for log reporter."""
        return
