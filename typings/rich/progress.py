from __future__ import annotations

from typing import Any, Sequence


class Task:
    id: int
    description: str
    completed: float
    total: float | None
    percentage: float | None

    def __init__(self, task_id: int = 0, description: str = "", completed: float = 0.0, total: float | None = None) -> None:
        self.id = task_id
        self.description = description
        self.completed = completed
        self.total = total
        self.percentage = None


class ProgressColumn:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def render(self, task: Task) -> Any:
        return None


class TextColumn(ProgressColumn):
    template: str

    def __init__(self, template: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.template = template


class BarColumn(ProgressColumn):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)


class Progress:
    columns: Sequence[ProgressColumn]

    def __init__(self, *columns: ProgressColumn | Any, console: Any | None = None, transient: bool = False) -> None:
        self.columns = [c for c in columns if isinstance(c, ProgressColumn)]
        self.console = console
        self.transient = transient
        self.tasks: dict[int, Task] = {}
        self._next_task_id = 0

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    def add_task(
        self,
        description: str,
        total: float | None = None,
        completed: float = 0.0,
        start: bool = True,
        **kwargs: Any,
    ) -> int:
        task_id = self._next_task_id
        self._next_task_id += 1
        task = Task(task_id=task_id, description=description, completed=completed, total=total)
        if start:
            task.percentage = self._calculate_percentage(task)
        self.tasks[task_id] = task
        return task_id

    def update(self, task_id: int, **kwargs: Any) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)

        if "description" in kwargs and isinstance(kwargs["description"], str):
            task.description = kwargs["description"]

        if "total" in kwargs:
            total_value = kwargs["total"]
            if total_value is None or isinstance(total_value, (int, float)):
                task.total = None if total_value is None else float(total_value)

        if "completed" in kwargs and isinstance(kwargs["completed"], (int, float)):
            task.completed = float(kwargs["completed"])

        if "advance" in kwargs and isinstance(kwargs["advance"], (int, float)):
            task.completed += float(kwargs["advance"])

        task.percentage = self._calculate_percentage(task)

    def advance(self, task_id: int, advance: float = 1.0) -> None:
        self.update(task_id, advance=advance)

    def _calculate_percentage(self, task: Task) -> float | None:
        if task.total in (None, 0):
            return None
        return (task.completed / task.total) * 100


__all__ = [
    "Progress",
    "ProgressColumn",
    "TextColumn",
    "BarColumn",
    "Task",
]
