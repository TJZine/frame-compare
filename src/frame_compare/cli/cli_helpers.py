"""Shared CLI helper functions."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import tomli_w
import typer
import typer.rich_utils as typer_rich_utils
from typer.core import TyperGroup

from frame_compare.cli.errors import ExitCode, format_error_console, get_exit_code
from frame_compare.config.errors import ConfigWriteError
from frame_compare.config.persistence import dump_config_for_persistence
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import FrameCompareError
from frame_compare.services.slowpics_url import require_comparison_url
from frame_compare.utils.subproc import prepare_python_child
from frame_compare.utils.terminal import no_color_requested
from frame_compare.utils.terminal_theme import human_console


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


# Desktop libraries may launch a browser, shell association, or clipboard
# utility internally, without an environment argument. Isolate that boundary
# in a child with filtered credentials and no capture pipes.
_DESKTOP_ACTION_TIMEOUT_SECONDS = 10.0
_DESKTOP_ACTION_CODE = """
import os
import sys

action, value, *fallback = sys.argv[1:]
if action == "clipboard":
    import pyperclip
    pyperclip.copy(value)
else:
    import webbrowser
    if action == "report" and sys.platform == "win32":
        try:
            os.startfile(value)
        except OSError:
            value = fallback[0]
        else:
            raise SystemExit(0)
    elif action == "report":
        value = fallback[0]
    raise SystemExit(0 if webbrowser.open(value) else 1)
"""


def _run_desktop_action(action: str, value: str, *extra: str) -> bool:
    command, env = prepare_python_child(
        [sys.executable, "-c", _DESKTOP_ACTION_CODE, action, value, *extra]
    )
    # Own only the broker. Desktop handlers and clipboard selection owners may
    # outlive it, including if the broker later fails or times out.
    try:
        process = subprocess.Popen(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
            start_new_session=os.name == "posix",
        )
        try:
            return process.wait(timeout=_DESKTOP_ACTION_TIMEOUT_SECONDS) == 0
        finally:
            if process.returncode is None:
                with contextlib.suppress(OSError, subprocess.SubprocessError):
                    process.kill()
                    process.wait(timeout=2.0)
    except (OSError, subprocess.SubprocessError):
        return False


def maybe_open_report(report_path: Path) -> bool:
    """Best-effort open of a generated HTML report in the default browser."""
    resolved = report_path.resolve()
    return _run_desktop_action("report", str(resolved), resolved.as_uri())


def copy_text_to_clipboard(text: str) -> None:
    """Copy the validated publication URL using the desktop clipboard."""
    if not _run_desktop_action("clipboard", require_comparison_url(text)):
        raise OSError("Could not copy the comparison URL to the clipboard")


def open_url_in_browser(url: str) -> bool:
    """Open a URL in the default browser and report whether a handler accepted it."""
    return _run_desktop_action("browser", require_comparison_url(url))


UNEXPECTED_ERROR_MESSAGE = "Unexpected error: please report this bug."


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
        console = human_console(stderr=True, no_color=no_color)
        console.print(message)
        return int(get_exit_code(error))
    typer.echo(UNEXPECTED_ERROR_MESSAGE, err=True)
    return int(ExitCode.GENERAL_ERROR)


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
