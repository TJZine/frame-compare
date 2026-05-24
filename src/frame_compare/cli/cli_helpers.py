"""Shared CLI helper functions."""

from __future__ import annotations

import contextlib
import os
import webbrowser
from collections.abc import Mapping
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, cast

import tomli_w
import typer
import typer.rich_utils as typer_rich_utils
from rich.console import Console
from typer.core import TyperGroup

from frame_compare.cli.errors import ExitCode, format_error_console, get_exit_code
from frame_compare.config.errors import ConfigWriteError
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import FrameCompareError

_DEFAULT_HELP_WIDTH = 200


class TextWriter(Protocol):
    def __call__(self, path: Path, content: str, *, encoding: str) -> None: ...


def stabilize_typer_help_width() -> None:
    """Backfill Typer's cached Rich help width when it was imported too early."""
    os.environ.setdefault("TERMINAL_WIDTH", str(_DEFAULT_HELP_WIDTH))
    if typer_rich_utils.MAX_WIDTH is not None:
        return
    with contextlib.suppress(ValueError):
        typer_rich_utils.MAX_WIDTH = int(os.environ["TERMINAL_WIDTH"])


class FrameCompareTyperGroup(TyperGroup):
    def main(self, *args: Any, **kwargs: Any) -> Any:
        stabilize_typer_help_width()
        return super().main(*args, **kwargs)


def maybe_open_report(report_path: Path) -> None:
    """Best-effort open of a generated HTML report in the default browser."""
    if os.name == "nt" and hasattr(os, "startfile"):
        try:
            os.startfile(str(report_path))  # type: ignore[attr-defined]  # nosec B606
            return
        except OSError:
            with contextlib.suppress(OSError, webbrowser.Error):
                webbrowser.open(report_path.resolve().as_uri())
            return

    try:
        webbrowser.open(report_path.resolve().as_uri())
    except (OSError, webbrowser.Error):
        return


def handle_error(error: Exception, *, no_color: bool, verbose: bool) -> int:
    """Render errors to stderr and return exit code.

    Raises:
        None.
    """
    if isinstance(error, FrameCompareError):
        message = format_error_console(error, verbose=verbose)
        if no_color:
            typer.echo(message, err=True)
        else:
            console = Console(stderr=True)
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
    data = config.model_dump(mode="json", exclude_none=True)
    toml_text = tomli_w.dumps(data)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text_writer(path, toml_text, encoding="utf-8")
    except OSError as exc:
        raise ConfigWriteError(path, label="configuration file", cause=exc) from exc


def _is_toml_scalar(value: object) -> bool:
    return isinstance(value, str | int | float | bool | datetime | date | time)


def _to_toml_safe_value(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        cleaned: dict[str, object] = {}
        mapping = cast(Mapping[object, object], value)
        for key, nested_value in mapping.items():
            cleaned_value = _to_toml_safe_value(nested_value)
            if cleaned_value is not None:
                cleaned[str(key)] = cleaned_value
        return cleaned
    if isinstance(value, list | tuple):
        cleaned_list: list[object] = []
        value_list = cast(list[object] | tuple[object, ...], value)
        for nested_value in value_list:
            cleaned_value = _to_toml_safe_value(nested_value)
            if cleaned_value is not None:
                cleaned_list.append(cleaned_value)
        return cleaned_list
    if _is_toml_scalar(value):
        return value
    return None


def prepare_toml_payload(data: dict[str, object]) -> dict[str, object]:
    """Prepare a TOML-safe payload while preserving unrelated sections."""
    payload: dict[str, object] = {}
    for key, value in data.items():
        cleaned_value = _to_toml_safe_value(value)
        if cleaned_value is None:
            continue
        if key == "tmdb":
            if not isinstance(cleaned_value, dict):
                continue
            tmdb_section = dict(cast(dict[str, object], cleaned_value))
            if tmdb_section.get("api_key") == "":
                del tmdb_section["api_key"]
            if tmdb_section:
                payload[key] = tmdb_section
            continue
        payload[key] = cleaned_value
    return payload


def format_enum_expected(enum_type: type[Enum]) -> str:
    return ", ".join(repr(member.value) for member in enum_type)
