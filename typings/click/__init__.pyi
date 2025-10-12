from typing import Any, Callable, MutableMapping, TypeVar, overload

_F = TypeVar("_F", bound=Callable[..., Any])


class Command:
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
    def main(self, *args: Any, **kwargs: Any) -> Any: ...


class Context:
    params: MutableMapping[str, Any]


class Param:
    name: str
    type: Any


Parameter = Param


@overload
def command(__func: _F) -> Command: ...


@overload
def command(*, name: str | None = ..., cls: type[Command] | None = ..., **kwargs: Any) -> Callable[[_F], Command]: ...


def command(*args: Any, **kwargs: Any) -> Callable[[_F], Command] | Command: ...


def option(*param_decls: str, **kwargs: Any) -> Callable[[_F], _F]: ...


def prompt(
    text: str,
    default: Any = ..., 
    *,
    type: Any | None = ..., 
    show_default: bool | str | None = ..., 
) -> Any: ...


def confirm(text: str, default: bool = ..., **kwargs: Any) -> bool: ...


def echo(message: object | None = ..., **kwargs: Any) -> None: ...


def launch(url: str, **kwargs: Any) -> bool | None: ...


class exceptions:
    class Exit(SystemExit):
        code: int | str | None

        def __init__(self, code: int | str | None = ...) -> None: ...


__all__ = [
    "Command",
    "Context",
    "Param",
    "Parameter",
    "command",
    "option",
    "prompt",
    "confirm",
    "echo",
    "launch",
    "exceptions",
]
