from typing import Any, Callable, Iterable, Optional, Protocol, TypeVar


class SupportsDunderLT(Protocol):
    def __lt__(self, __other: Any, /) -> Any: ...


class SupportsDunderGT(Protocol):
    def __gt__(self, __other: Any, /) -> Any: ...

_T = TypeVar("_T")


def os_sorted(
    seq: Iterable[_T],
    *,
    key: Optional[Callable[[_T], Any]] = ...,
    reverse: bool = ...,
    presort: bool = ...,
) -> list[_T]: ...


__all__ = ["os_sorted"]
