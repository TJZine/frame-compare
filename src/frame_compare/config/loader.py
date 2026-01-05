"""Configuration loading functions."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from frame_compare.config.schema import ConfigSchema
from frame_compare.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    normalize_pydantic_errors,
)


def load_config(
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> ConfigSchema:
    """Load configuration from TOML file with overrides."""
    if config_path is not None and not config_path.exists():
        raise ConfigNotFoundError(config_path)

    alias_overrides = _resolve_env_aliases()
    merged_overrides = _deep_merge(alias_overrides, overrides or {})

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
    # Explicitly set toml_file to None to suppress UserWarning
    config_dict = cast(dict[str, Any], ConfigSchema.model_config)
    new_config_dict = config_dict.copy()
    new_config_dict["toml_file"] = None

    class _EnvOnlySchema(ConfigSchema):
        model_config = SettingsConfigDict(**new_config_dict)

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (init_settings, env_settings)

    alias_overrides = _resolve_env_aliases()

    try:
        return _EnvOnlySchema(**cast(Any, alias_overrides))
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(cast(Any, exc.errors()))
        raise ConfigValidationError(normalized) from exc


def get_default_config() -> ConfigSchema:
    """Get config with all default values (no TOML, no env)."""
    # Explicitly set toml_file to None to suppress UserWarning
    config_dict = cast(dict[str, Any], ConfigSchema.model_config)
    new_config_dict = config_dict.copy()
    new_config_dict["toml_file"] = None

    class _DefaultsOnlySchema(ConfigSchema):
        model_config = SettingsConfigDict(**new_config_dict)

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (init_settings,)

    return _DefaultsOnlySchema()


def _resolve_env_aliases() -> dict[str, object]:
    """Resolve special env var aliases to nested override dict."""
    overrides: dict[str, object] = {}

    if "TMDB_API_KEY" in os.environ and "FRAME_COMPARE_TMDB__API_KEY" not in os.environ:
        overrides["tmdb"] = {"api_key": os.environ["TMDB_API_KEY"]}

    if "FRAME_COMPARE_LOG_LEVEL" in os.environ and "FRAME_COMPARE_LOGGING__LEVEL" not in os.environ:
        overrides["logging"] = {"level": os.environ["FRAME_COMPARE_LOG_LEVEL"]}

    return overrides


def _deep_merge(base: dict[str, object], updates: dict[str, object]) -> dict[str, object]:
    """Deep merge two dicts. Updates take precedence over base."""
    result: dict[str, object] = dict(base)
    for key, value in updates.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            result[key] = _deep_merge(
                cast(dict[str, object], base_value),
                cast(dict[str, object], value),
            )
        else:
            result[key] = value
    return result
