from collections.abc import Callable, Iterable, Sequence
from typing import Any

class Result:
    exit_code: int
    output: str
    exception: BaseException | None

    def __iter__(self) -> Iterable[str]: ...

class CliRunner:
    def invoke(
        self,
        cli: Callable[..., Any],
        args: Sequence[str] | None = ..., 
        input: str | bytes | None = ..., 
        catch_exceptions: bool = ..., 
        **kwargs: Any,
    ) -> Result: ...

__all__ = ["CliRunner", "Result"]
