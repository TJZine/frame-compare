"""Progress reporting utilities for Frame Compare 2.0."""

from typing import Protocol, runtime_checkable

import structlog
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

log = structlog.get_logger()


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting progress of long-running operations."""

    def start_phase(self, name: str, total: int) -> None:
        """Start a new phase of the operation."""
        ...

    def advance(self, amount: int = 1) -> None:
        """Advance the progress of the current phase."""
        ...

    def set_description(self, desc: str) -> None:
        """Set the description for the current phase."""
        ...

    def complete_phase(self) -> None:
        """Mark the current phase as complete."""
        ...


class NullProgressReporter:
    """No-op progress reporter."""

    def start_phase(self, name: str, total: int) -> None:
        """No-op."""
        pass

    def advance(self, amount: int = 1) -> None:
        """No-op."""
        pass

    def set_description(self, desc: str) -> None:
        """No-op."""
        pass

    def complete_phase(self) -> None:
        """No-op."""
        pass


class RichProgressReporter:
    """Progress reporter using the rich library for CLI display."""

    def __init__(self) -> None:
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            transient=True,
            console=None,  # Use default console (stderr)
        )
        self._task_id: TaskID | None = None

    def start_phase(self, name: str, total: int) -> None:
        """Start a new phase with a rich progress bar."""
        if not self._progress.live.is_started:
            self._progress.start()
        self._task_id = self._progress.add_task(name, total=total)

    def advance(self, amount: int = 1) -> None:
        """Advance the rich progress bar."""
        if self._task_id is not None:
            self._progress.advance(self._task_id, amount)

    def set_description(self, desc: str) -> None:
        """Update the rich progress bar description."""
        if self._task_id is not None:
            self._progress.update(self._task_id, description=desc)

    def complete_phase(self) -> None:
        """Complete the current phase and stop progress if all tasks done."""
        if self._task_id is not None:
            self._progress.update(
                self._task_id, completed=self._progress.tasks[self._task_id].total
            )
            self._task_id = None

        # Check if all tasks are complete to stop the progress display
        if all(task.finished for task in self._progress.tasks):
            self._progress.stop()


class LogProgressReporter:
    """Progress reporter that logs milestones via structlog."""

    def __init__(self) -> None:
        self._name: str = ""
        self._total: int = 0
        self._current: int = 0
        self._milestones: set[int] = {10, 25, 50, 75, 100}
        self._last_logged_milestone: int = 0

    def start_phase(self, name: str, total: int) -> None:
        """Start logging a new phase."""
        self._name = name
        self._total = total
        self._current = 0
        self._last_logged_milestone = 0
        log.info("phase_started", phase=name, total=total)

    def advance(self, amount: int = 1) -> None:
        """Advance progress and log milestones."""
        self._current += amount
        if self._total > 0:
            percentage = int((self._current / self._total) * 100)
            for m in sorted(self._milestones):
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
        """No-op for log reporter (per SSOT)."""
        pass

    def complete_phase(self) -> None:
        """Log phase completion."""
        log.info("phase_completed", phase=self._name)
        self._name = ""
        self._total = 0
        self._current = 0
