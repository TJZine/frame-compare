from typing import Any

class Exit(Exception):
    __slots__ = ("exit_code",)

    exit_code: int | str | None

    def __init__(self, exit_code: int | str | None = ...) -> None: ...

__all__ = ["Exit"]
