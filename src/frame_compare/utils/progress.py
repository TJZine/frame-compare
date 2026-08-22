"""Progress reporting utilities for Frame Compare."""

import sys
from dataclasses import dataclass
from io import TextIOBase
from threading import RLock
from time import monotonic

import structlog
from rich.console import Console, RenderableType
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Column
from rich.text import Text

from frame_compare.utils.progress_protocol import ProgressPhaseStatus, ProgressReporter

log = structlog.get_logger()

_MIN_DURABLE_PHASE_SECONDS = 10.0
_DURABLE_STATUS_MARKERS = {
    ProgressPhaseStatus.COMPLETED: "[OK]",
    ProgressPhaseStatus.SKIPPED: "[SKIP]",
    ProgressPhaseStatus.WARNED: "[WARN]",
    ProgressPhaseStatus.FAILED: "[FAIL]",
}


def _format_elapsed(seconds: float) -> str:
    whole_seconds = int(max(0.0, seconds))
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


__all__ = [
    "LogProgressReporter",
    "NullProgressReporter",
    "PlainProgressReporter",
    "ProgressReporter",
    "RichProgressReporter",
]


@dataclass(frozen=True)
class _PlainTask:
    label: str
    started_at: float


class _TaskPresentationColumn(ProgressColumn):
    def __init__(self, column: ProgressColumn, *presentations: str) -> None:
        super().__init__(table_column=column.get_table_column())
        self._column = column
        self._presentations = presentations

    def render(self, task: Task) -> RenderableType:
        if task.fields.get("presentation") not in self._presentations:
            return Text("")
        return self._column.render(task)


class NullProgressReporter:
    """No-op progress reporter."""

    def start_phase(self, name: str, total: int) -> None:
        del name, total

    def start_indeterminate(self, name: str) -> None:
        del name

    def advance(self, amount: int = 1) -> None:
        del amount

    def set_description(self, desc: str) -> None:
        del desc

    def complete_phase(
        self,
        status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
        *,
        retain: bool | None = None,
    ) -> None:
        del self, status, retain

    def suspend(self) -> None:
        del self

    def resume(self) -> None:
        del self


class PlainProgressReporter:
    """Chronological ASCII progress for redirected human output."""

    def __init__(self, stream: TextIOBase | None = None) -> None:
        self._stream = stream
        self._task: _PlainTask | None = None
        self._task_stack: list[_PlainTask] = []
        self._lock = RLock()

    def start_phase(self, name: str, total: int) -> None:
        del total
        with self._lock:
            if self._task is not None:
                self._task_stack.append(self._task)
            self._task = _PlainTask(name, monotonic())

    def start_indeterminate(self, name: str) -> None:
        self.start_phase(name, total=0)

    def advance(self, amount: int = 1) -> None:
        del amount

    def set_description(self, desc: str) -> None:
        del desc

    def complete_phase(
        self,
        status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
        *,
        retain: bool | None = None,
    ) -> None:
        del retain
        with self._lock:
            if self._task is None:
                return
            task = self._task
            nested = bool(self._task_stack)
            if not nested or status in {
                ProgressPhaseStatus.WARNED,
                ProgressPhaseStatus.FAILED,
            }:
                detail = (
                    f"  Completed in {_format_elapsed(monotonic() - task.started_at)}"
                    if status == ProgressPhaseStatus.COMPLETED
                    else ""
                )
                line = f"{_DURABLE_STATUS_MARKERS[status]} {task.label}{detail}"
                stream = self._stream if self._stream is not None else sys.stderr
                print(line.encode("ascii", "backslashreplace").decode("ascii"), file=stream)
            self._task = self._task_stack.pop() if self._task_stack else None

    def suspend(self) -> None:
        return

    def resume(self) -> None:
        return


class RichProgressReporter:
    """Progress reporter using the rich library for CLI display."""

    def __init__(self, *, no_color: bool = False) -> None:
        self._progress = Progress(
            TextColumn(
                "  [progress.description]{task.description}",
                table_column=Column(ratio=1, overflow="ellipsis", no_wrap=True),
            ),
            _TaskPresentationColumn(TextColumn(" "), "measurable", "indeterminate"),
            _TaskPresentationColumn(
                BarColumn(bar_width=None, table_column=Column(min_width=20, ratio=1)),
                "measurable",
            ),
            _TaskPresentationColumn(MofNCompleteColumn(), "measurable"),
            _TaskPresentationColumn(TextColumn("ETA"), "measurable"),
            _TaskPresentationColumn(TimeRemainingColumn(compact=True), "measurable"),
            _TaskPresentationColumn(SpinnerColumn(spinner_name="line"), "indeterminate"),
            transient=True,
            auto_refresh=False,
            redirect_stdout=False,
            redirect_stderr=False,
            expand=True,
            console=Console(stderr=True, no_color=no_color),
        )
        self._task_id: TaskID | None = None
        self._task_stack: list[TaskID] = []
        self._task_totals: dict[TaskID, int] = {}
        self._task_started_at: dict[TaskID, float] = {}
        self._suspend_depth = 0
        self._lock = RLock()

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
        presentation = "measurable" if total > 1 else "simple"
        self._start_task(name, total=total, presentation=presentation)

    def start_indeterminate(self, name: str) -> None:
        """Start a new phase with spinner-only activity."""
        self._start_task(name, total=None, presentation="indeterminate")

    def _start_task(
        self,
        name: str,
        *,
        total: int | None,
        presentation: str,
    ) -> None:
        with self._lock:
            if presentation == "measurable":
                self._progress.console.print()
            if not self._progress.live.is_started:
                self._progress.start()
            if self._task_id is not None:
                self._progress.update(self._task_id, visible=False, refresh=True)
                self._task_stack.append(self._task_id)
            self._task_id = self._progress.add_task(
                f"[RUN] {name}",
                total=total,
                presentation=presentation,
                phase_label=name,
            )
            task_id = self._task_id
            self._task_started_at[task_id] = monotonic()
            if total is not None:
                self._task_totals[task_id] = total
            self._progress.refresh()

    def advance(self, amount: int = 1) -> None:
        """Advance the rich progress bar."""
        with self._lock:
            if self._task_id is not None:
                self._progress.advance(self._task_id, amount)
                self._progress.refresh()

    def set_description(self, desc: str) -> None:
        """Update the rich progress bar description."""
        with self._lock:
            if self._task_id is not None:
                self._progress.update(self._task_id, description=f"[RUN] {desc}", refresh=True)

    def complete_phase(
        self,
        status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
        *,
        retain: bool | None = None,
    ) -> None:
        """Complete the current phase and stop progress if all tasks done."""
        with self._lock:
            if self._task_id is not None:
                task_id = self._task_id
                total = self._task_totals.get(task_id)
                started_at = self._task_started_at.get(task_id)
                if started_at is None:
                    started_at = monotonic()
                duration = max(0.0, monotonic() - started_at)
                task = next(
                    (candidate for candidate in self._progress.tasks if candidate.id == task_id),
                    None,
                )
                if status == ProgressPhaseStatus.SKIPPED:
                    self._progress.update(task_id, description="Skipped", refresh=True)
                elif status == ProgressPhaseStatus.WARNED:
                    self._progress.update(task_id, description="Warning", refresh=True)
                elif status == ProgressPhaseStatus.FAILED:
                    self._progress.update(task_id, description="Failed", refresh=True)

                if total is not None and status in {
                    ProgressPhaseStatus.COMPLETED,
                    ProgressPhaseStatus.SKIPPED,
                }:
                    self._progress.update(task_id, completed=total, refresh=True)

                nested = bool(self._task_stack)
                should_retain = status != ProgressPhaseStatus.COMPLETED
                if status == ProgressPhaseStatus.COMPLETED and retain is not False:
                    should_retain = retain is True or (
                        not nested and duration >= _MIN_DURABLE_PHASE_SECONDS
                    )
                if should_retain and task is not None:
                    label = task.fields.get("phase_label", task.description)
                    if not isinstance(label, str):
                        label = task.description
                    detail = (
                        f"  Completed in {_format_elapsed(duration)}"
                        if status == ProgressPhaseStatus.COMPLETED
                        else ""
                    )
                    self._progress.console.print(
                        Text(f"  {_DURABLE_STATUS_MARKERS[status]} {label}{detail}")
                    )

                self._progress.remove_task(task_id)
                self._task_totals.pop(task_id, None)
                self._task_started_at.pop(task_id, None)
                self._task_id = None

            if self._task_stack:
                self._task_id = self._task_stack.pop()
                self._progress.update(self._task_id, visible=True, refresh=True)
                return

            if self._progress.live.is_started:
                self._progress.stop()

    def suspend(self) -> None:
        """Pause live progress rendering during blocking terminal interaction."""
        with self._lock:
            self._suspend_depth += 1
            if self._suspend_depth == 1 and self._progress.live.is_started:
                self._progress.stop()

    def resume(self) -> None:
        """Resume live progress rendering after blocking terminal interaction."""
        with self._lock:
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

    def start_indeterminate(self, name: str) -> None:
        """Start logging an activity with no measurable total."""
        self.start_phase(name, total=0)

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
        *,
        retain: bool | None = None,
    ) -> None:
        """Log phase completion."""
        del retain
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
