"""Implementation for configuration preset CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import typer

from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import FrameCompareError


class LoadConfigFn(Protocol):
    def __call__(
        self,
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema: ...


class WriteConfigFn(Protocol):
    def __call__(self, path: Path, config: ConfigSchema) -> None: ...


class HandleErrorFn(Protocol):
    def __call__(self, error: Exception, *, no_color: bool, verbose: bool) -> int: ...


class ListPresetsFn(Protocol):
    def __call__(self, *, presets_dir: Path) -> list[str]: ...


class ApplyPresetFn(Protocol):
    def __call__(
        self,
        config: ConfigSchema,
        preset_name: str,
        presets_dir: Path | None = None,
    ) -> ConfigSchema: ...


class SavePresetFn(Protocol):
    def __call__(
        self,
        name: str,
        config: ConfigSchema,
        presets_dir: Path | None = None,
    ) -> Path: ...


def handle_preset_list(
    resolved_root: Path,
    *,
    list_presets: ListPresetsFn,
    handle_error: HandleErrorFn,
) -> None:
    try:
        presets_dir = resolved_root / "config" / "presets"
        for name in list_presets(presets_dir=presets_dir):
            typer.echo(name)
    except FrameCompareError as error:
        raise typer.Exit(code=handle_error(error, no_color=True, verbose=False)) from error


def handle_preset_apply(
    name: str,
    resolved_root: Path,
    config_path: Path,
    *,
    load_config: LoadConfigFn,
    apply_preset: ApplyPresetFn,
    write_config_to: WriteConfigFn,
    handle_error: HandleErrorFn,
) -> None:
    try:
        presets_dir = resolved_root / "config" / "presets"
        config_data = load_config(config_path)
        updated = apply_preset(config_data, name, presets_dir=presets_dir)
        write_config_to(config_path, updated)
    except FrameCompareError as error:
        raise typer.Exit(code=handle_error(error, no_color=True, verbose=False)) from error


def handle_preset_save(
    name: str,
    resolved_root: Path,
    config_path: Path,
    *,
    load_config: LoadConfigFn,
    save_preset: SavePresetFn,
    handle_error: HandleErrorFn,
) -> None:
    try:
        presets_dir = resolved_root / "config" / "presets"
        config_data = load_config(config_path)
        save_preset(name, config_data, presets_dir=presets_dir)
    except FrameCompareError as error:
        raise typer.Exit(code=handle_error(error, no_color=True, verbose=False)) from error
