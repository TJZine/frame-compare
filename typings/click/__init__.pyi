from types import ModuleType
from typing import Any, Callable, Generic, MutableMapping, TypeVar, overload
from .exceptions import Exit

_F = TypeVar("_F", bound=Callable[..., Any])


class Command(Generic[_F]):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
    def main(self, *args: Any, **kwargs: Any) -> Any: ...
    def command(
        self,
        name: str | None = ...,
        cls: type[Command[Any]] | None = ...,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Command[Any]]: ...

    def group(
        self,
        name: str | None = ...,
        cls: type[Command[Any]] | None = ...,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Command[Any]]: ...


class Context:
    params: MutableMapping[str, Any]
    obj: MutableMapping[str, Any] | dict[str, Any]
    invoked_subcommand: str | None
    parent: Context | None

    def ensure_object(self, object_type: type[MutableMapping[str, Any]] | type[dict[str, Any]] = ...) -> MutableMapping[str, Any]: ...


class Param:
    name: str
    type: Any


Parameter = Param


@overload
def command(__func: _F) -> Command[_F]: ...


@overload
def command(
    name: str | None = ...,
    cls: type[Command[Any]] | None = ...,
    **kwargs: Any,
) -> Callable[[_F], Command[_F]]: ...


def command(
    __func: _F | None = ...,
    name: str | None = ...,
    cls: type[Command[Any]] | None = ...,
    **kwargs: Any,
) -> Callable[[_F], Command[_F]] | Command[_F]: ...


@overload
def group(__func: _F) -> Command[_F]: ...


@overload
def group(
    name: str | None = ...,
    cls: type[Command[Any]] | None = ...,
    **kwargs: Any,
) -> Callable[[_F], Command[_F]]: ...


def group(
    __func: _F | None = ...,
    name: str | None = ...,
    cls: type[Command[Any]] | None = ...,
    **kwargs: Any,
) -> Callable[[_F], Command[_F]] | Command[_F]: ...


def option(*param_decls: str, **kwargs: Any) -> Callable[[_F], _F]: ...


def prompt(
    text: str,
    default: Any = ...,
    *,
    hide_input: bool = ...,
    confirmation_prompt: bool | str = ...,
    type: Any | None = ...,
    value_proc: Callable[[str], Any] | None = ...,
    prompt_suffix: str = ...,
    show_default: bool | str | None = ...,
    err: bool = ...,
    show_choices: bool = ...,
) -> Any: ...


def confirm(text: str, default: bool = ..., **kwargs: Any) -> bool: ...


@overload
def pass_context(__func: _F) -> _F: ...


@overload
def pass_context() -> Callable[[_F], _F]: ...


def echo(message: object | None = ..., **kwargs: Any) -> None: ...


def launch(url: str, **kwargs: Any) -> bool | None: ...


def argument(*param_decls: str, **kwargs: Any) -> Callable[[_F], _F]: ...


exceptions: ModuleType


class Choice:
    def __init__(self, choices: Any, case_sensitive: bool = ...) -> None: ...


class ClickException(Exception):
    message: str


__all__ = [
    "Command",
    "Context",
    "Param",
    "Parameter",
    "command",
    "group",
    "option",
    "argument",
    "prompt",
    "confirm",
    "pass_context",
    "echo",
    "launch",
    "Exit",
    "exceptions",
    "Choice",
    "ClickException",
]
