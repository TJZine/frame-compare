"""Preset management for Frame Compare configuration."""

from __future__ import annotations

import re
import stat
import tomllib
from pathlib import Path

import tomli_w

from frame_compare.config.errors import (
    ConfigWriteError,
    PresetInvalidError,
    PresetNameInvalidError,
    PresetNotFoundError,
)
from frame_compare.config.loader import validate_raw_config_payload
from frame_compare.config.persistence import (
    dump_config_for_persistence,
    dump_config_with_explicit_color,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.utils import deep_merge
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.serialized_decode import SERIALIZED_DECODE_FAILURES

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

    try:
        if not stat.S_ISREG(preset_path.stat().st_mode):
            raise PresetInvalidError(preset_path, "preset must be a regular file")
        text = preset_path.read_text(encoding="utf-8-sig")
        try:
            payload = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            raise
        except SERIALIZED_DECODE_FAILURES:
            raise PresetInvalidError(
                preset_path, "configuration exceeds TOML parser limits"
            ) from None
    except FileNotFoundError:
        raise PresetNotFoundError(name) from None
    except tomllib.TOMLDecodeError as exc:
        raise PresetInvalidError(preset_path, str(exc)) from None
    except UnicodeDecodeError:
        raise PresetInvalidError(preset_path, "preset is not valid UTF-8") from None
    except OSError:
        raise PresetInvalidError(preset_path, "could not read preset file") from None
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

    data = dump_config_for_persistence(config)
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
    preset_data = load_preset(preset_name, presets_dir=presets_dir)
    base_dict = dump_config_with_explicit_color(config)
    merged = deep_merge(base_dict, preset_data)

    return validate_raw_config_payload(merged, redact_inputs=False)
