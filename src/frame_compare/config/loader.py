"""Configuration loading functions."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from frame_compare.config.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import normalize_pydantic_errors

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


def _env_only_settings_sources(
    cls: type[BaseSettings],
    settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource,
) -> tuple[PydanticBaseSettingsSource, ...]:
    return (init_settings, env_settings)


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


def load_config(
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> ConfigSchema:
    """Load configuration from TOML file with overrides."""
    if config_path is not None and not config_path.exists():
        raise ConfigNotFoundError(config_path)

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

    try:
        # Pydantic validates inputs at runtime, so we cast to Any to bypass static checks
        # on kwargs unpacking.
        return settings_cls(**cast(Any, merged_overrides))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(config_path or Path("config/config.toml"), str(exc)) from exc
    except ValidationError as exc:
        # pydantic errors are compatible with our normalizer but require a cast for strict typing
        normalized = normalize_pydantic_errors(cast(Any, exc.errors()))
        raise ConfigValidationError(normalized) from exc


def load_config_from_env() -> ConfigSchema:
    """Load config from environment variables only (no TOML file)."""
    env_only_schema = _toml_suppressed_settings_schema(
        "EnvOnlySchema",
        _env_only_settings_sources,
    )
    try:
        return env_only_schema()
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(cast(Any, exc.errors()))
        raise ConfigValidationError(normalized) from exc


def get_default_config() -> ConfigSchema:
    """Get config with all default values (no TOML, no env)."""
    defaults_only_schema = _toml_suppressed_settings_schema(
        "DefaultsOnlySchema",
        _defaults_only_settings_sources,
    )
    return defaults_only_schema()
