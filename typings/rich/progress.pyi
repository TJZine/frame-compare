from typing import Any, Protocol


from typing import Any, Iterable, Sequence


class Task:
    id: int
    completed: float
    total: float | None
    percentage: float | None


class ProgressColumn:
    ...


class TextColumn(ProgressColumn):
    def __init__(self, text_format: str, *args: Any, **kwargs: Any) -> None: ...


class BarColumn(ProgressColumn):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class TimeElapsedColumn(ProgressColumn):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class TimeRemainingColumn(ProgressColumn):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class Progress:
    columns: Sequence[ProgressColumn]
    tasks: dict[int, Task]

    def __init__(self, *columns: ProgressColumn, **kwargs: Any) -> None: ...
    def add_task(self, description: str, *args: Any, **kwargs: Any) -> int: ...
    def update(self, task_id: int, *args: Any, **kwargs: Any) -> None: ...
    def refresh(self) -> None: ...
    def stop(self) -> None: ...
    def __enter__(self) -> "Progress": ...
    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None: ...
