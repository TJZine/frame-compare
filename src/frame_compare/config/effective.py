"""Helpers for resolving the effective run configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from frame_compare.config.loader import load_config
from frame_compare.config.overrides import CLIConfigOverrides, apply_cli_overrides
from frame_compare.config.schema import ConfigSchema


class LoadConfigFn(Protocol):
    def __call__(
        self,
        config_path: Path | None = None,
        overrides: dict[str, object] | None = None,
    ) -> ConfigSchema: ...


def build_preflight_input_dir_override(input_dir: Path | None) -> dict[str, object] | None:
    """Build the narrow config override used only for preflight input discovery."""
    if input_dir is None:
        return None
    return {"paths": {"input_dir": str(input_dir)}}


def resolve_effective_config(
    config: ConfigSchema,
    cli_overrides: CLIConfigOverrides,
) -> ConfigSchema:
    """Apply runtime CLI overrides to an already loaded base config."""
    return apply_cli_overrides(config, cli_args=cli_overrides)


def load_effective_config(
    config_path: Path | None,
    *,
    cli_overrides: CLIConfigOverrides,
    load_config_fn: LoadConfigFn = load_config,
    base_overrides: dict[str, object] | None = None,
) -> ConfigSchema:
    """Load base config, then apply the canonical runtime CLI overrides."""
    if base_overrides is None:
        base_config = load_config_fn(config_path)
    else:
        base_config = load_config_fn(config_path, base_overrides)
    return resolve_effective_config(base_config, cli_overrides)
