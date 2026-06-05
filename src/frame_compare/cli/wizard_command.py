"""Implementation for the interactive configuration wizard command."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

import tomli_w
import typer
from pydantic import ValidationError

from frame_compare.cli.errors import ExitCode
from frame_compare.config.errors import ConfigValidationError, ConfigWriteError
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import ConfigSchema, Visibility
from frame_compare.errors import FrameCompareError, normalize_pydantic_errors

from .cli_helpers import TextWriter, prepare_toml_payload


class ConfirmFn(Protocol):
    def __call__(self, text: str, *, default: bool) -> bool: ...


class PromptSecretFn(Protocol):
    def __call__(self, text: str, *, default: str, hide_input: bool) -> str: ...


class PromptInputDirFn(Protocol):
    def __call__(self, default: str, *, base_dir: Path) -> str: ...


class PromptVisibilityFn(Protocol):
    def __call__(self, default: Visibility) -> str: ...


class WriteWizardPayloadFn(Protocol):
    def __call__(self, config_path: Path, data: dict[str, object]) -> None: ...


class HandleErrorFn(Protocol):
    def __call__(
        self,
        error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int: ...


def handle_wizard(
    root: Path,
    config_path: Path,
    *,
    prompt_input_dir: PromptInputDirFn,
    prompt_visibility: PromptVisibilityFn,
    confirm: ConfirmFn,
    prompt_secret: PromptSecretFn,
    write_payload: WriteWizardPayloadFn,
    handle_error: HandleErrorFn,
    stdin_is_tty: bool,
    no_color: bool,
) -> None:
    """Interactive configuration wizard."""
    defaults = get_default_config()

    try:
        input_dir = prompt_input_dir(defaults.paths.input_dir, base_dir=root)
        auto_upload = confirm(
            "Enable slow.pics auto-upload?",
            default=defaults.slowpics.auto_upload,
        )
        visibility = prompt_visibility(defaults.slowpics.visibility)
        delete_after_upload = confirm(
            "Delete after upload?",
            default=defaults.slowpics.delete_after_upload,
        )
        tmdb_api_key = prompt_secret(
            "TMDB API key (optional)",
            default="",
            hide_input=stdin_is_tty,
        ).strip()
    except (KeyboardInterrupt, typer.Abort):
        raise typer.Exit(code=int(ExitCode.INTERRUPTED)) from None

    tmdb_value: str | None = tmdb_api_key if tmdb_api_key else None
    config_data = build_minimal_config(
        input_dir=input_dir,
        auto_upload=auto_upload,
        visibility=visibility,
        delete_after_upload=delete_after_upload,
        tmdb_api_key=tmdb_value,
    )
    try:
        validate_config(config_data)
        write_payload(config_path, config_data)
        typer.echo(f"Configuration written: {config_path}", err=True)
    except ValidationError as error:
        normalized = normalize_pydantic_errors(cast(Sequence[dict[str, object]], error.errors()))
        config_error = ConfigValidationError(normalized)
        raise typer.Exit(
            code=handle_error(
                config_error,
                no_color=no_color,
                verbose=False,
                verbose_hint=None,
            )
        ) from error
    except FrameCompareError as error:
        raise typer.Exit(
            code=handle_error(
                error,
                no_color=no_color,
                verbose=False,
                verbose_hint=None,
            )
        ) from error


def prompt_input_dir(default: str, *, base_dir: Path) -> str:
    """Prompt for input directory and validate existence."""
    while True:
        value = typer.prompt("Input directory", default=default)
        path = Path(value)
        if not path.is_absolute():
            path = base_dir / path
        if path.exists() and path.is_dir():
            return value
        typer.echo("Input directory does not exist or is not a directory.")


def prompt_visibility(default: Visibility) -> str:
    """Prompt for slow.pics visibility."""
    allowed = {v.value for v in Visibility}
    default_value = default.value
    while True:
        value = typer.prompt(
            "slow.pics visibility (public|unlisted)",
            default=default_value,
        ).strip()
        if value in allowed:
            return value
        typer.echo("Invalid visibility. Choose public or unlisted.")


def build_minimal_config(
    *,
    input_dir: str,
    auto_upload: bool,
    visibility: str,
    delete_after_upload: bool,
    tmdb_api_key: str | None,
) -> dict[str, object]:
    """Build minimal config payload for wizard output."""
    return {
        "paths": {"input_dir": input_dir},
        "slowpics": {
            "auto_upload": auto_upload,
            "visibility": visibility,
            "delete_after_upload": delete_after_upload,
        },
        "tmdb": {"api_key": tmdb_api_key},
    }


def validate_config(data: dict[str, object]) -> None:
    """Validate config data against ConfigSchema."""
    ConfigSchema.model_validate(data)


def write_wizard_config_payload(
    config_path: Path,
    data: dict[str, object],
    *,
    text_writer: TextWriter,
) -> None:
    """Write wizard config payload to the provided destination."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        toml_text = tomli_w.dumps(prepare_toml_payload(data))
        text_writer(config_path, toml_text, encoding="utf-8")
    except OSError as exc:
        raise ConfigWriteError(config_path, label="configuration file", cause=exc) from exc
