from typing import Any, Iterable, Sequence


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

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    def add_task(self, description: str, total: float | None = None, **kwargs: Any) -> int:
        return 0

    def update(self, task_id: int, **kwargs: Any) -> None:
        pass

    def advance(self, task_id: int, advance: float = 1.0) -> None:
        pass


__all__ = [
    "Progress",
    "ProgressColumn",
    "TextColumn",
    "BarColumn",
    "Task",
]
