from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class Task:
    id: int
    description: str
    completed: float
    total: float | None
    percentage: float | None
    fields: dict[str, Any]


class ProgressColumn:
    ...


class TextColumn(ProgressColumn):
    def __init__(self, text_format: str, *args: Any, **kwargs: Any) -> None: ...


class BarColumn(ProgressColumn):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class SpinnerColumn(ProgressColumn):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class TimeElapsedColumn(ProgressColumn):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class TimeRemainingColumn(ProgressColumn):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class Progress:
    columns: Sequence[ProgressColumn]
    tasks: dict[int, Task]

    def __init__(self, *columns: ProgressColumn, **kwargs: Any) -> None: ...
    def add_task(
        self,
        description: str,
        *,
        total: float | None = ...,
        completed: float = ...,
        start: bool = ...,
        **kwargs: Any,
    ) -> int: ...
    def update(
        self,
        task_id: int,
        *,
        completed: float | None = ...,
        advance: float | None = ...,
        total: float | None = ...,
        description: str | None = ...,
        **kwargs: Any,
    ) -> None: ...
    def advance(self, task_id: int, advance: float = ...) -> None: ...
    def reset(self, task_id: int, *, total: float | None = ..., start: bool = ...) -> None: ...
    def remove_task(self, task_id: int) -> None: ...
    def refresh(self) -> None: ...
    def stop(self) -> None: ...
    def __enter__(self) -> "Progress": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None: ...
