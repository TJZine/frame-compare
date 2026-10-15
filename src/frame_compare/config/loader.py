"""Configuration loading functions."""

from __future__ import annotations

import stat
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
)

from frame_compare.config.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_sources import EnvironmentSettingsSource
from frame_compare.errors import normalize_pydantic_errors
from frame_compare.utils.serialized_decode import SERIALIZED_DECODE_FAILURES

type _SettingsSourcesCustomizer = Callable[
    [
        type[BaseSettings],
        type[BaseSettings],
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
    ],
    tuple[PydanticBaseSettingsSource, ...],
]

type TomlScalar = str | int | float | bool | date | datetime | time
type TomlValue = TomlScalar | list["TomlValue"] | dict[str, "TomlValue"]
type TomlPayload = dict[str, TomlValue]


@dataclass(frozen=True, slots=True)
class RawConfigDocument:
    """Validated config plus its environment-independent parsed TOML payload."""

    payload: TomlPayload
    config: ConfigSchema


def _defaults_only_settings_sources(
    cls: type[BaseSettings],
    settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource,
) -> tuple[PydanticBaseSettingsSource, ...]:
    return (init_settings,)


def _toml_suppressed_settings_schema(
    name: str,
    settings_customise_sources: _SettingsSourcesCustomizer,
) -> type[ConfigSchema]:
    # Explicitly set toml_file to None to suppress UserWarning from pydantic-settings.
    config_dict = cast(dict[str, Any], ConfigSchema.model_config)
    new_config_dict = config_dict.copy()
    new_config_dict["toml_file"] = None

    return type(
        name,
        (ConfigSchema,),
        {
            "model_config": SettingsConfigDict(**new_config_dict),
            "settings_customise_sources": classmethod(settings_customise_sources),
        },
    )


def _require_regular_config_file(path: Path, *, required: bool) -> None:
    """Follow authored symlinks, but never read a directory or special device."""
    try:
        source_stat = path.stat()
    except FileNotFoundError:
        if required:
            raise ConfigNotFoundError(path) from None
    except OSError:
        raise ConfigParseError(path, "could not access configuration file") from None
    else:
        if not stat.S_ISREG(source_stat.st_mode):
            raise ConfigParseError(path, "configuration must be a regular file")


def load_config(
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> ConfigSchema:
    """Load configuration from TOML file with overrides."""
    source_path = config_path or Path("config/config.toml")
    _require_regular_config_file(source_path, required=config_path is not None)

    merged_overrides = overrides or {}

    settings_cls: type[ConfigSchema]
    if config_path is None:
        settings_cls = ConfigSchema
    else:
        # Create a dynamic subclass to override the toml_file
        # This is the standard way in Pydantic V2 settings to override config location at runtime
        # We cast the config dict to Any to satisfy Pyright strict mode
        config_dict = cast(dict[str, Any], ConfigSchema.model_config)
        new_config_dict = config_dict.copy()
        new_config_dict["toml_file"] = str(config_path)

        settings_cls = type(
            "ConfigSchemaFromFile",
            (ConfigSchema,),
            {"model_config": SettingsConfigDict(**new_config_dict)},
        )

    return _load_settings(settings_cls, merged_overrides, source_path)


def load_environment_config() -> ConfigSchema:
    """Load defaults and the normal environment chain without any TOML lookup."""
    settings_cls = _toml_suppressed_settings_schema(
        "EnvironmentOnlySchema", _environment_settings_sources
    )
    return _load_settings(settings_cls, {}, Path("config/config.toml"))


def _environment_settings_sources(
    cls: type[BaseSettings],
    settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource,
) -> tuple[PydanticBaseSettingsSource, ...]:
    return init_settings, EnvironmentSettingsSource(settings_cls), file_secret_settings


def _load_settings(
    settings_cls: type[ConfigSchema], overrides: dict[str, object], source_path: Path
) -> ConfigSchema:
    try:
        # Pydantic validates inputs at runtime, so we cast to Any to bypass static checks
        # on kwargs unpacking.
        return settings_cls(**cast(Any, overrides))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(source_path, str(exc)) from None
    except UnicodeDecodeError:
        raise ConfigParseError(
            source_path,
            "configuration is not valid UTF-8",
        ) from None
    except SettingsError:
        raise ConfigValidationError(
            [],
            message="Could not decode configuration settings from environment",
            hint="Check JSON syntax in FRAME_COMPARE_* section and list variables",
        ) from None
    except OSError:
        raise ConfigParseError(source_path, "could not read configuration file") from None
    except ValidationError as exc:
        # pydantic errors are compatible with our normalizer but require a cast for strict typing
        normalized = normalize_pydantic_errors(cast(Any, exc.errors()))
        raise ConfigValidationError(normalized) from None


def load_raw_config(config_path: Path) -> RawConfigDocument:
    """Load TOML without environment precedence and preserve every parsed value."""
    _require_regular_config_file(config_path, required=True)
    try:
        text = config_path.read_text(encoding="utf-8-sig")
        try:
            untrusted: object = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            raise
        except SERIALIZED_DECODE_FAILURES:
            raise ConfigParseError(
                config_path, "configuration exceeds TOML parser limits"
            ) from None
    except FileNotFoundError:
        raise ConfigNotFoundError(config_path) from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(config_path, str(exc)) from None
    except UnicodeDecodeError:
        raise ConfigParseError(config_path, "configuration is not valid UTF-8") from None
    except OSError:
        raise ConfigParseError(config_path, "could not read configuration file") from None

    payload = _narrow_toml_table(untrusted, path="root")
    return RawConfigDocument(
        payload=payload,
        config=validate_raw_config_payload(payload, redact_inputs=True),
    )


def validate_raw_config_payload(
    payload: Mapping[str, object],
    *,
    redact_inputs: bool,
) -> ConfigSchema:
    """Validate parsed or already resolved values without reacquiring sources.

    Config merges must retain their acquired values and authored field presence;
    neither ambient TOML nor environment settings may fill omitted placeholders.
    """
    defaults_only_schema = _toml_suppressed_settings_schema(
        "RawConfigSchema",
        _defaults_only_settings_sources,
    )
    try:
        return defaults_only_schema(**cast(Any, payload))
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(cast(Any, exc.errors()))
        if redact_inputs:
            for error in normalized:
                if "input" in error:
                    error["input"] = "<redacted>"
        raise ConfigValidationError(normalized) from None


def _narrow_toml_table(value: object, *, path: str) -> TomlPayload:
    if not isinstance(value, dict):
        raise ConfigParseError(Path(path), "expected a TOML table")

    narrowed: TomlPayload = {}
    for raw_key, raw_value in cast("dict[object, object]", value).items():
        if not isinstance(raw_key, str):
            raise ConfigParseError(Path(path), "TOML table keys must be strings")
        narrowed[raw_key] = _narrow_toml_value(raw_value, path=f"{path}.{raw_key}")
    return narrowed


def _narrow_toml_value(value: object, *, path: str) -> TomlValue:
    if isinstance(value, str | int | float | bool | date | datetime | time):
        return value
    if isinstance(value, list):
        return [_narrow_toml_value(item, path=f"{path}[]") for item in cast("list[object]", value)]
    if isinstance(value, dict):
        nested: object = cast("dict[object, object]", value)
        return _narrow_toml_table(nested, path=path)
    raise ConfigParseError(Path(path), f"unsupported TOML value type: {type(value).__name__}")


def get_default_config() -> ConfigSchema:
    """Get config with all default values (no TOML, no env)."""
    defaults_only_schema = _toml_suppressed_settings_schema(
        "DefaultsOnlySchema",
        _defaults_only_settings_sources,
    )
    return defaults_only_schema()
