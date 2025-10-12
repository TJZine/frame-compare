from typing import Any, Callable, Iterable, Mapping, Sequence

class Command:
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
    def main(self, *args: Any, **kwargs: Any) -> Any: ...

Context = object

class Param:
    name: str
    type: Any

Parameter = Param

__all__ = ["Command", "Context", "Param", "Parameter"]
