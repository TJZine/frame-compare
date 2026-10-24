"""Progress reporting utilities for Frame Compare."""

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from threading import RLock
from time import monotonic

import structlog
from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.constrain import Constrain
from rich.live import Live
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
from rich.progress_bar import ProgressBar
from rich.table import Column, Table
from rich.text import Text

from frame_compare.utils.logging import register_log_console, release_log_console
from frame_compare.utils.progress_protocol import (
    AlignmentSummary,
    AlignmentSummaryEntry,
    ProgressPhaseStatus,
)
from frame_compare.utils.terminal_theme import (
    ACCENT,
    FAIL,
    OK,
    WARN,
    glyphs_for_console,
    human_console,
)

log = structlog.get_logger()

_MIN_DURABLE_PHASE_SECONDS = 10.0
_DURABLE_STATUS_MARKERS = {
    ProgressPhaseStatus.COMPLETED: "[OK]",
    ProgressPhaseStatus.SKIPPED: "[SKIP]",
    ProgressPhaseStatus.WARNED: "[WARN]",
    ProgressPhaseStatus.FAILED: "[FAIL]",
}
_DURABLE_STATUS_GLYPHS = {
    ProgressPhaseStatus.COMPLETED: "ok",
    ProgressPhaseStatus.SKIPPED: "skipped",
    ProgressPhaseStatus.WARNED: "warning",
    ProgressPhaseStatus.FAILED: "failed",
}
_DURABLE_STATUS_STYLES = {
    ProgressPhaseStatus.COMPLETED: OK,
    ProgressPhaseStatus.SKIPPED: "dim",
    ProgressPhaseStatus.WARNED: WARN,
    ProgressPhaseStatus.FAILED: FAIL,
}

UPLOAD_PRESENTATION = "upload"


def _format_elapsed(seconds: float) -> str:
    whole_seconds = int(max(0.0, seconds))
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def align_phase_duration_text(*, align_seconds: float, review_seconds: float) -> str | None:
    """Format the Align phase duration override splitting machine and review time.

    Returns None when no review wait was measured so the caller keeps the
    measured phase duration.
    """
    if review_seconds <= 0.0:
        return None
    machine_seconds = max(0.0, align_seconds - review_seconds)
    return f"{_format_elapsed(machine_seconds)} + {_format_elapsed(review_seconds)} review"


__all__ = [
    "LogProgressReporter",
    "NullProgressReporter",
    "PlainProgressReporter",
    "RichProgressReporter",
    "align_phase_duration_text",
]


def _alignment_offset_text(entry: AlignmentSummaryEntry) -> Text:
    if entry.offset is not None:
        return Text(entry.value)
    text = Text("not applied", style=WARN)
    if entry.origin == "kept":
        text.append(" (kept)", style="default")
    return text


def alignment_summary_lines(summary: AlignmentSummary, *, width: int) -> tuple[Text, ...]:
    """Render AL1–AL5 at the width available for the value column."""
    common = summary.common_origin
    inline = Text()
    for index, entry in enumerate(summary.entries):
        if index:
            inline.append(" · ")
        inline.append(entry.name + " ")
        inline.append_text(_alignment_offset_text(entry))
        if common is None and entry.offset is not None:
            inline.append(" " + entry.origin)
    if common:
        inline.append(" · " + common)
    if inline.cell_len <= width:
        return (inline,)
    header = Text(f"{len(summary.entries)} sources aligned" + (f" · {common}" if common else ""))
    name_width = max((cell_len(entry.name) for entry in summary.entries), default=0)
    rows: list[Text] = [header]
    for entry in summary.entries:
        row = Text(entry.name + " " * (name_width - cell_len(entry.name) + 2))
        row.append_text(_alignment_offset_text(entry))
        if common is None and entry.offset is not None:
            row.append(" " + entry.origin)
        rows.append(row)
    return tuple(rows)


@dataclass(frozen=True)
class AlignmentSummaryValue:
    """Completion-section alignment value, sized by its actual column."""

    summary: AlignmentSummary

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield from alignment_summary_lines(self.summary, width=options.max_width)


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


class _ActiveDescriptionColumn(ProgressColumn):
    """Render the active marker separately from the unstyled description."""

    def __init__(self, running_glyph: str) -> None:
        super().__init__(table_column=Column(ratio=1, overflow="ellipsis", no_wrap=True))
        self._running_glyph = running_glyph

    def render(self, task: Task) -> RenderableType:
        return Text.assemble(
            "  ",
            Text(self._running_glyph, style=ACCENT),
            " ",
            task.description,
        )


class _PresentationBarColumn(BarColumn):
    """Bar column that fills upload tasks with the accent color."""

    def render(self, task: Task) -> ProgressBar:
        if task.fields.get("presentation") != UPLOAD_PRESENTATION:
            return super().render(task)
        complete_style, finished_style = self.complete_style, self.finished_style
        self.complete_style = ACCENT
        self.finished_style = ACCENT
        try:
            return super().render(task)
        finally:
            self.complete_style = complete_style
            self.finished_style = finished_style


class _UploadDescriptionColumn(ProgressColumn):
    """Render the upload task with the running glyph and no status marker."""

    def __init__(self, running_glyph: str) -> None:
        super().__init__()
        self._running_glyph = running_glyph

    def render(self, task: Task) -> RenderableType:
        return Text.assemble("  ", self._running_glyph, " ", task.description)


class _UploadTimeRemainingColumn(ProgressColumn):
    """Render the muted upload remainder as `· {eta} left`."""

    def render(self, task: Task) -> RenderableType:
        if task.time_remaining is None:
            return Text("")
        return Text(f"· {_format_elapsed(task.time_remaining)} left", style="dim")


class _EstimatedTimeRemainingColumn(ProgressColumn):
    """Render the ETA label and value only after Rich has an estimate."""

    def __init__(self) -> None:
        super().__init__()
        self._remaining = TimeRemainingColumn(compact=True)

    def render(self, task: Task) -> RenderableType:
        if task.time_remaining is None:
            return Text("")
        value = self._remaining.render(task)
        return Text.assemble("ETA ", value)


class _ElapsedTimeColumn(ProgressColumn):
    def render(self, task: Task) -> RenderableType:
        minutes, seconds = divmod(int(task.elapsed or 0), 60)
        return Text(f"{minutes}:{seconds:02d}")


class _RunProgress(Progress):
    """Keep the run's step map below the current task, including nested work."""

    def __init__(self, *columns: ProgressColumn, console: Console) -> None:
        self.steps: dict[str, str] = {}
        super().__init__(
            *columns,
            transient=True,
            auto_refresh=True,
            refresh_per_second=4,
            redirect_stdout=False,
            redirect_stderr=False,
            expand=True,
            console=console,
        )

    def start(self) -> None:
        if not self.live.is_started:
            # Rich Live retains its last cursor geometry after stop(). A resumed
            # session starts at the current cursor, after any suspended sections.
            self.live = Live(
                console=self.console,
                transient=True,
                auto_refresh=True,
                refresh_per_second=4,
                redirect_stdout=False,
                redirect_stderr=False,
                get_renderable=self.get_renderable,
            )
        super().start()

    def get_renderable(self) -> RenderableType:
        return Constrain(super().get_renderable(), width=120)

    def get_renderables(self) -> Iterable[RenderableType]:
        yield from super().get_renderables()
        if self.steps:
            glyphs = glyphs_for_console(self.console)
            unicode = glyphs.ok == "✓"
            markers = {
                "pending": ("○" if unicode else "o", "dim"),
                "running": ("●" if unicode else "*", ACCENT),
                **{
                    status.value: (
                        getattr(glyphs, _DURABLE_STATUS_GLYPHS[status]),
                        _DURABLE_STATUS_STYLES[status],
                    )
                    for status in ProgressPhaseStatus
                },
            }
            line = Text("  ")
            for index, (label, status) in enumerate(tuple(self.steps.items())):
                if index:
                    line.append("  ")
                glyph, style = markers[status]
                line.append(glyph, style=style)
                line.append(f" {label}")
            yield line


class NullProgressReporter:
    """No-op progress reporter."""

    def set_phase_steps(self, labels: list[str]) -> None:
        """Non-interactive reporters do not render the step map."""
        del labels

    def start_phase(self, name: str, total: int, *, presentation: str | None = None) -> None:
        del name, total, presentation

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
        summary: str | None = None,
        duration_text: str | None = None,
        alignment_summary: AlignmentSummary | None = None,
    ) -> None:
        del self, status, retain, summary, duration_text, alignment_summary

    def suspend(self) -> None:
        del self

    def resume(self) -> None:
        del self


class PlainProgressReporter:
    """Chronological ASCII progress for redirected human output."""

    def __init__(self) -> None:
        self._task: _PlainTask | None = None
        self._task_stack: list[_PlainTask] = []
        self._lock = RLock()

    def set_phase_steps(self, labels: list[str]) -> None:
        """Non-interactive reporters do not render the step map."""
        del labels

    def start_phase(self, name: str, total: int, *, presentation: str | None = None) -> None:
        del total, presentation
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
        summary: str | None = None,
        duration_text: str | None = None,
        alignment_summary: AlignmentSummary | None = None,
    ) -> None:
        del retain, summary, duration_text, alignment_summary
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
                print(line.encode("ascii", "backslashreplace").decode("ascii"), file=sys.stderr)
            self._task = self._task_stack.pop() if self._task_stack else None

    def suspend(self) -> None:
        return

    def resume(self) -> None:
        return


class RichProgressReporter:
    """Progress reporter using the rich library for CLI display."""

    def __init__(self, *, no_color: bool = False) -> None:
        console = human_console(stderr=True, no_color=no_color)
        glyphs = glyphs_for_console(console)
        self._progress = _RunProgress(
            _TaskPresentationColumn(
                _ActiveDescriptionColumn(glyphs.running),
                "measurable",
                "simple",
                "indeterminate",
            ),
            _TaskPresentationColumn(_UploadDescriptionColumn(glyphs.running), UPLOAD_PRESENTATION),
            _TaskPresentationColumn(
                TextColumn(" "), "measurable", "indeterminate", UPLOAD_PRESENTATION
            ),
            _TaskPresentationColumn(
                _PresentationBarColumn(bar_width=None, table_column=Column(min_width=20, ratio=1)),
                "measurable",
                UPLOAD_PRESENTATION,
            ),
            _TaskPresentationColumn(MofNCompleteColumn(), "measurable", UPLOAD_PRESENTATION),
            _TaskPresentationColumn(_EstimatedTimeRemainingColumn(), "measurable"),
            _TaskPresentationColumn(_UploadTimeRemainingColumn(), UPLOAD_PRESENTATION),
            _TaskPresentationColumn(SpinnerColumn(spinner_name="line"), "indeterminate"),
            _TaskPresentationColumn(_ElapsedTimeColumn(), "indeterminate"),
            console=console,
        )
        self._task_id: TaskID | None = None
        self._task_stack: list[TaskID] = []
        self._task_totals: dict[TaskID, int] = {}
        self._task_started_at: dict[TaskID, float] = {}
        self._suspend_depth = 0
        self._lock = RLock()

    def _start_live(self) -> None:
        register_log_console(self._progress.console)
        try:
            self._progress.start()
        except BaseException:
            release_log_console(self._progress.console)
            raise

    def _stop_live(self) -> None:
        try:
            self._progress.stop()
        finally:
            release_log_console(self._progress.console)

    def set_phase_steps(self, labels: list[str]) -> None:
        """Initialize the run footer with its enabled phases in execution order."""
        with self._lock:
            self._progress.steps = dict.fromkeys(labels, "pending")

    def start_phase(self, name: str, total: int, *, presentation: str | None = None) -> None:
        """Start a new phase with a rich progress bar."""
        resolved = presentation
        if resolved is None:
            resolved = "measurable" if total > 1 else "simple"
        # Only the Rich reporter shortens the upload phase: every other
        # reporter keeps the caller-supplied phase name.
        label = "Upload" if resolved == UPLOAD_PRESENTATION else name
        self._start_task(label, total=total, presentation=resolved)

    def start_indeterminate(self, name: str) -> None:
        """Start a new phase with a spinner and elapsed time."""
        self._start_task(name, total=None, presentation="indeterminate")

    def _start_task(
        self,
        name: str,
        *,
        total: int | None,
        presentation: str,
    ) -> None:
        with self._lock:
            if self._task_id is None and name in self._progress.steps:
                self._progress.steps[name] = "running"
            if self._suspend_depth == 0 and not self._progress.live.is_started:
                self._start_live()
            if self._task_id is not None:
                self._progress.update(self._task_id, visible=False, refresh=True)
                self._task_stack.append(self._task_id)
            self._task_id = self._progress.add_task(
                name,
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
                self._progress.update(self._task_id, description=desc, refresh=True)

    def complete_phase(
        self,
        status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
        *,
        retain: bool | None = None,
        summary: str | None = None,
        duration_text: str | None = None,
        alignment_summary: AlignmentSummary | None = None,
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
                if not nested and task is not None:
                    label = task.fields.get("phase_label", task.description)
                    if label in self._progress.steps:
                        self._progress.steps[label] = status.value
                should_retain = status != ProgressPhaseStatus.COMPLETED
                if status == ProgressPhaseStatus.COMPLETED and retain is not False:
                    should_retain = retain is True or (
                        not nested and duration >= _MIN_DURABLE_PHASE_SECONDS
                    )
                if should_retain and task is not None:
                    label = task.fields.get("phase_label", task.description)
                    if not isinstance(label, str):
                        label = task.description
                    self._print_durable_line(
                        status,
                        label,
                        summary=summary,
                        duration=duration,
                        duration_text=duration_text,
                        alignment_summary=alignment_summary,
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
                self._stop_live()

    def _print_durable_line(
        self,
        status: ProgressPhaseStatus,
        label: str,
        *,
        summary: str | None,
        duration: float,
        duration_text: str | None,
        alignment_summary: AlignmentSummary | None = None,
    ) -> None:
        """Print a retained phase line with its duration inline."""
        glyphs = glyphs_for_console(self._progress.console)
        glyph = getattr(glyphs, _DURABLE_STATUS_GLYPHS[status])
        style = _DURABLE_STATUS_STYLES[status]
        prefix = Text.assemble((glyph, style), f" {label:<16}")
        line = Text()
        resolved_duration = duration_text
        if resolved_duration is None and (
            status == ProgressPhaseStatus.COMPLETED
            or (status == ProgressPhaseStatus.WARNED and alignment_summary is not None)
        ):
            resolved_duration = _format_elapsed(duration)
        continuation: tuple[Text, ...] = ()
        if alignment_summary is not None:
            duration_width = cell_len(resolved_duration) + 3 if resolved_duration else 0
            header, *rows = alignment_summary_lines(
                alignment_summary,
                width=max(1, min(self._progress.console.width, 120) - 18 - duration_width),
            )
            line.append_text(header)
            continuation = tuple(rows)
            summary = header.plain
        elif summary:
            line.append(summary)
        if resolved_duration:
            if summary:
                line.append(" · ", style="dim")
            line.append(resolved_duration, style="dim")
        if line:
            phase = Table.grid(padding=0)
            phase.add_column(width=18, no_wrap=True)
            phase.add_column(ratio=1, overflow="fold")
            phase.add_row(prefix, line)
            self._progress.console.print(phase, width=min(self._progress.console.width, 120))
        else:
            prefix.rstrip()
            self._progress.console.print(prefix, width=min(self._progress.console.width, 120))
        for row in continuation:
            self._print_continuation(row)
        if alignment_summary is not None and alignment_summary.extra_footage:
            self._print_continuation(Text(alignment_summary.extra_footage, style="dim"))

    def _print_continuation(self, value: Text) -> None:
        console = self._progress.console
        for line in value.wrap(console, max(1, min(console.width, 120) - 18)):
            line.rstrip()
            console.print(Text.assemble(" " * 18, line))

    def suspend(self) -> None:
        """Pause live progress rendering during blocking terminal interaction."""
        with self._lock:
            self._suspend_depth += 1
            if self._suspend_depth == 1 and self._progress.live.is_started:
                self._stop_live()

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
                self._start_live()


class LogProgressReporter:
    """Progress reporter that logs milestones via structlog."""

    def __init__(self) -> None:
        self._name: str = ""
        self._total: int = 0
        self._current: int = 0
        self._task_stack: list[tuple[str, int, int, int]] = []
        self._milestones: tuple[int, ...] = (10, 25, 50, 75, 100)
        self._last_logged_milestone: int = 0

    def set_phase_steps(self, labels: list[str]) -> None:
        """Non-interactive reporters do not render the step map."""
        del labels

    def start_phase(self, name: str, total: int, *, presentation: str | None = None) -> None:
        """Start logging a new phase."""
        del presentation
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
        summary: str | None = None,
        duration_text: str | None = None,
        alignment_summary: AlignmentSummary | None = None,
    ) -> None:
        """Log phase completion."""
        del retain, summary, duration_text, alignment_summary
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
