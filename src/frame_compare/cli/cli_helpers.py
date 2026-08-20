"""Shared CLI helper functions."""

from __future__ import annotations

import contextlib
import os
import webbrowser
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import tomli_w
import typer
import typer.rich_utils as typer_rich_utils
from rich.console import Console
from typer.core import TyperGroup

from frame_compare.cli.errors import ExitCode, format_error_console, get_exit_code
from frame_compare.config.errors import ConfigWriteError
from frame_compare.config.persistence import dump_config_for_persistence
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import FrameCompareError
from frame_compare.utils.terminal import no_color_requested


class TextWriter(Protocol):
    def __call__(self, path: Path, content: str, *, encoding: str) -> None: ...


class LoadConfigFn(Protocol):
    def __call__(
        self,
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema: ...


class WriteConfigFn(Protocol):
    def __call__(self, path: Path, config: ConfigSchema) -> None: ...


class HandleErrorFn(Protocol):
    def __call__(
        self,
        error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int: ...


def stabilize_typer_help_width(terminal_width: int | None = None) -> None:
    """Give Typer's Rich help renderer the current width when one is explicit."""
    if terminal_width is not None:
        if terminal_width > 0:
            typer_rich_utils.MAX_WIDTH = terminal_width
        return
    if typer_rich_utils.MAX_WIDTH is not None:
        return
    configured_width = os.environ.get("TERMINAL_WIDTH")
    if configured_width is None:
        return
    with contextlib.suppress(ValueError):
        parsed_width = int(configured_width)
        if parsed_width > 0:
            typer_rich_utils.MAX_WIDTH = parsed_width


class FrameCompareTyperGroup(TyperGroup):
    def main(self, *args: Any, **kwargs: Any) -> Any:
        previous_width = typer_rich_utils.MAX_WIDTH
        previous_force_terminal = typer_rich_utils.FORCE_TERMINAL
        terminal_width = kwargs.get("terminal_width")
        if not isinstance(terminal_width, int):
            terminal_width = None
        stabilize_typer_help_width(terminal_width)
        if no_color_requested():
            typer_rich_utils.FORCE_TERMINAL = False
        try:
            return super().main(*args, **kwargs)
        finally:
            typer_rich_utils.MAX_WIDTH = previous_width
            typer_rich_utils.FORCE_TERMINAL = previous_force_terminal


def maybe_open_report(report_path: Path) -> bool:
    """Best-effort open of a generated HTML report in the default browser."""
    if os.name == "nt" and hasattr(os, "startfile"):
        try:
            os.startfile(str(report_path))  # type: ignore[attr-defined]  # nosec B606
            return True
        except OSError:
            try:
                return webbrowser.open(report_path.resolve().as_uri())
            except (OSError, webbrowser.Error):
                return False

    try:
        return webbrowser.open(report_path.resolve().as_uri())
    except (OSError, webbrowser.Error):
        return False


def copy_text_to_clipboard(text: str) -> None:
    """Copy text to the clipboard while keeping pyperclip import lazy."""
    import pyperclip

    pyperclip.copy(text)


def open_url_in_browser(url: str) -> bool:
    """Open a URL in the default browser and report whether a handler accepted it."""
    return webbrowser.open(url)


def handle_error(
    error: Exception,
    *,
    no_color: bool,
    verbose: bool,
    verbose_hint: str | None = "--verbose",
) -> int:
    """Render errors to stderr and return exit code.

    Raises:
        None.
    """
    if isinstance(error, FrameCompareError):
        message = format_error_console(
            error,
            verbose=verbose,
            verbose_hint=verbose_hint,
        )
        console = Console(stderr=True, no_color=no_color)
        console.print(message)
        return int(get_exit_code(error))
    typer.echo("Unexpected error: please report this bug.", err=True)
    return int(ExitCode.GENERAL_ERROR)


def resolve_root_and_config(root: Path, config: Path | None) -> tuple[Path, Path]:
    resolved_root = Path(root).resolve()
    if config is not None:
        config_path = Path(config)
        if not config_path.is_absolute():
            config_path = (resolved_root / config_path).resolve()
        else:
            config_path = config_path.resolve()
    else:
        config_path = (resolved_root / "config" / "config.toml").resolve()
    return resolved_root, config_path


def write_config_to(path: Path, config: ConfigSchema, *, text_writer: TextWriter) -> None:
    data = dump_config_for_persistence(config)
    toml_text = tomli_w.dumps(data)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text_writer(path, toml_text, encoding="utf-8")
    except OSError as exc:
        raise ConfigWriteError(path, label="configuration file", cause=exc) from exc


def format_enum_expected(enum_type: type[Enum]) -> str:
    return ", ".join(repr(member.value) for member in enum_type)
