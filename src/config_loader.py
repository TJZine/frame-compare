from __future__ import annotations

"""Configuration loader that parses and validates user-provided TOML."""

from dataclasses import fields
from typing import Any, Dict

import tomllib

from .datatypes import (
    AppConfig,
    AnalysisConfig,
    ScreenshotConfig,
    SlowpicsConfig,
    NamingConfig,
    PathsConfig,
    RuntimeConfig,
    OverridesConfig,
    ColorConfig,
)


class ConfigError(ValueError):
    """Raised when the configuration file is malformed or fails validation."""


def _coerce_bool(value: Any, dotted_key: str) -> bool:
    """Return a bool, coercing simple 0/1 representations when necessary."""

    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "1"}:
            return normalized == "1"
        if normalized in {"true", "false"}:
            return normalized == "true"
    raise ConfigError(f"{dotted_key} must be a boolean (use true/false).")


def _sanitize_section(raw: dict[str, Any], name: str, cls):
    if not isinstance(raw, dict):
        raise ConfigError(f"[{name}] must be a table")
    cleaned: Dict[str, Any] = {}
    bool_fields = {field.name for field in fields(cls) if field.type is bool}
    for key, value in raw.items():
        if key in bool_fields:
            cleaned[key] = _coerce_bool(value, f"{name}.{key}")
        else:
            cleaned[key] = value
    try:
        return cls(**cleaned)
    except TypeError as exc:
        raise ConfigError(f"Invalid keys in [{name}]: {exc}") from exc


def _validate_trim(mapping: Dict[str, Any], label: str) -> None:
    for key, value in mapping.items():
        if not isinstance(value, int):
            raise ConfigError(f"{label} entry '{key}' must map to an integer")


def _validate_change_fps(change_fps: Dict[str, Any]) -> None:
    for key, value in change_fps.items():
        if isinstance(value, str):
            if value != "set":
                raise ConfigError(f"change_fps entry '{key}' must be a [num, den] pair or \"set\"")
        elif isinstance(value, list):
            if len(value) != 2 or not all(isinstance(v, int) and v > 0 for v in value):
                raise ConfigError(f"change_fps entry '{key}' must contain two positive integers")
        else:
            raise ConfigError(f"change_fps entry '{key}' must be a list or \"set\"")


def load_config(path: str) -> AppConfig:
    """Read, parse, and validate configuration from *path*."""

    with open(path, "rb") as handle:
        raw_bytes = handle.read()
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]
    try:
        raw = tomllib.loads(raw_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ConfigError("Configuration file must be UTF-8 encoded") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Failed to parse TOML: {exc}") from exc

    app = AppConfig(
        analysis=_sanitize_section(raw.get("analysis", {}), "analysis", AnalysisConfig),
        screenshots=_sanitize_section(raw.get("screenshots", {}), "screenshots", ScreenshotConfig),
        slowpics=_sanitize_section(raw.get("slowpics", {}), "slowpics", SlowpicsConfig),
        naming=_sanitize_section(raw.get("naming", {}), "naming", NamingConfig),
        paths=_sanitize_section(raw.get("paths", {}), "paths", PathsConfig),
        runtime=_sanitize_section(raw.get("runtime", {}), "runtime", RuntimeConfig),
        overrides=_sanitize_section(raw.get("overrides", {}), "overrides", OverridesConfig),
        color=_sanitize_section(raw.get("color", {}), "color", ColorConfig),
    )

    if app.analysis.step < 1:
        raise ConfigError("analysis.step must be >= 1")
    if app.analysis.downscale_height < 64:
        raise ConfigError("analysis.downscale_height must be >= 64")
    if app.analysis.random_seed < 0:
        raise ConfigError("analysis.random_seed must be >= 0")
    if not app.analysis.frame_data_filename:
        raise ConfigError("analysis.frame_data_filename must be set")
    if app.analysis.skip_head_seconds < 0:
        raise ConfigError("analysis.skip_head_seconds must be >= 0")
    if app.analysis.skip_tail_seconds < 0:
        raise ConfigError("analysis.skip_tail_seconds must be >= 0")
    if app.analysis.ignore_lead_seconds < 0:
        raise ConfigError("analysis.ignore_lead_seconds must be >= 0")
    if app.analysis.ignore_trail_seconds < 0:
        raise ConfigError("analysis.ignore_trail_seconds must be >= 0")
    if app.analysis.min_window_seconds < 0:
        raise ConfigError("analysis.min_window_seconds must be >= 0")

    if app.screenshots.compression_level not in (0, 1, 2):
        raise ConfigError("screenshots.compression_level must be 0, 1, or 2")
    if app.screenshots.mod_crop < 0:
        raise ConfigError("screenshots.mod_crop must be >= 0")

    if app.slowpics.remove_after_days < 0:
        raise ConfigError("slowpics.remove_after_days must be >= 0")

    if app.runtime.ram_limit_mb <= 0:
        raise ConfigError("runtime.ram_limit_mb must be > 0")

    if app.color.target_nits <= 0:
        raise ConfigError("color.target_nits must be > 0")
    if app.color.dst_min_nits < 0:
        raise ConfigError("color.dst_min_nits must be >= 0")
    if app.color.verify_luma_threshold < 0 or app.color.verify_luma_threshold > 1:
        raise ConfigError("color.verify_luma_threshold must be between 0 and 1")
    if app.color.verify_start_seconds < 0:
        raise ConfigError("color.verify_start_seconds must be >= 0")
    if app.color.verify_step_seconds <= 0:
        raise ConfigError("color.verify_step_seconds must be > 0")
    if app.color.verify_max_seconds < 0:
        raise ConfigError("color.verify_max_seconds must be >= 0")

    _validate_trim(app.overrides.trim, "overrides.trim")
    _validate_trim(app.overrides.trim_end, "overrides.trim_end")
    _validate_change_fps(app.overrides.change_fps)
    return app
