"""Preset management for Frame Compare configuration."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import tomli_w
from pydantic import ValidationError

from frame_compare.config.errors import (
    ConfigValidationError,
    ConfigWriteError,
    PresetInvalidError,
    PresetNameInvalidError,
    PresetNotFoundError,
)
from frame_compare.config.utils import deep_merge
from frame_compare.errors import normalize_pydantic_errors
from frame_compare.utils.atomic_write import write_text_atomic

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema

DEFAULT_PRESETS_DIR = Path("config/presets")

_PRESET_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_preset_name(name: str) -> None:
    if not name or not _PRESET_NAME_RE.fullmatch(name):
        raise PresetNameInvalidError(name)


def list_presets(presets_dir: Path | None = None) -> list[str]:
    """List available preset names (sorted case-insensitive)."""
    directory = presets_dir or DEFAULT_PRESETS_DIR
    if not directory.exists():
        return []
    names = [p.stem for p in directory.glob("*.toml")]
    return sorted(names, key=lambda name: (name.lower(), name))


def load_preset(name: str, presets_dir: Path | None = None) -> dict[str, object]:
    """Load preset data by name."""
    _validate_preset_name(name)
    directory = presets_dir or DEFAULT_PRESETS_DIR
    preset_path = directory / f"{name}.toml"

    if not preset_path.exists():
        raise PresetNotFoundError(name)

    try:
        payload = tomllib.loads(preset_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PresetInvalidError(preset_path, str(exc)) from exc
    return payload


def save_preset(
    name: str,
    config: ConfigSchema,
    presets_dir: Path | None = None,
) -> Path:
    """Save current config as preset.

    Uses tomli-w for TOML serialization. Output order is stable
    (follows Pydantic model field declaration order).

    None values are excluded because TOML has no null representation.
    When a preset is loaded and applied, Pydantic will use defaults
    for any missing optional fields.
    """
    _validate_preset_name(name)
    directory = presets_dir or DEFAULT_PRESETS_DIR

    preset_path = directory / f"{name}.toml"

    # exclude_none=True: TOML has no null; omitted keys use defaults when loaded
    data = config.model_dump(mode="json", exclude_none=True)
    toml_text = tomli_w.dumps(data)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        write_text_atomic(preset_path, toml_text, encoding="utf-8")
    except OSError as exc:
        raise ConfigWriteError(preset_path, label="preset file", cause=exc) from exc

    return preset_path


def apply_preset(
    config: ConfigSchema,
    preset_name: str,
    presets_dir: Path | None = None,
) -> ConfigSchema:
    """Apply preset overrides to config.

    Loads preset data from presets_dir when provided; otherwise uses
    DEFAULT_PRESETS_DIR (config/presets relative to CWD). Loaded preset data is
    merged with the config. Missing optional keys (excluded due to None) are
    filled with schema defaults during validation.
    """
    from frame_compare.config.schema import ConfigSchema

    preset_data = load_preset(preset_name, presets_dir=presets_dir)
    base_dict = config.model_dump()
    merged = deep_merge(base_dict, preset_data)

    try:
        return ConfigSchema.model_validate(cast(Any, merged))
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(cast(Any, exc.errors()))
        raise ConfigValidationError(normalized) from exc
