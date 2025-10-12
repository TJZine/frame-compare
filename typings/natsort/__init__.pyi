from typing import Callable, Iterable, TypeVar

_T = TypeVar("_T")


def os_sorted(
    sequence: Iterable[_T],
    *,
    key: Callable[[_T], object] | None = ...,
    reverse: bool = ...,
) -> list[_T]: ...


__all__ = ["os_sorted"]
