from __future__ import annotations
from typing import Any, Dict
import tomllib
from .datatypes import AppConfig, AnalysisConfig, ScreenshotConfig, SlowpicsConfig, NamingConfig, PathsConfig, RuntimeConfig, OverridesConfig

class ConfigError(ValueError):
    pass

def _section(raw: dict, name: str, cls):
    data: Dict[str, Any] = raw.get(name, {})
    if not isinstance(data, dict):
        raise ConfigError(f"[{name}] must be a table")
    try:
        obj = cls(**data)
    except TypeError as e:
        raise ConfigError(f"Invalid keys in [{name}]: {e}") from e
    return obj

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
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    app = AppConfig(
        analysis=_section(raw, "analysis", AnalysisConfig),
        screenshots=_section(raw, "screenshots", ScreenshotConfig),
        slowpics=_section(raw, "slowpics", SlowpicsConfig),
        naming=_section(raw, "naming", NamingConfig),
        paths=_section(raw, "paths", PathsConfig),
        runtime=_section(raw, "runtime", RuntimeConfig),
        overrides=_section(raw, "overrides", OverridesConfig),
    )
    # Basic validation (extend as needed)
    if app.analysis.step < 1:
        raise ConfigError("analysis.step must be >= 1")
    if app.analysis.random_seed < 0:
        raise ConfigError("analysis.random_seed must be >= 0")
    if not app.analysis.frame_data_filename:
        raise ConfigError("analysis.frame_data_filename must be set")
    if app.screenshots.compression_level not in (0, 1, 2):
        raise ConfigError("screenshots.compression_level must be 0, 1, or 2")
    if app.screenshots.mod_crop < 0:
        raise ConfigError("screenshots.mod_crop must be >= 0")
    if app.runtime.ram_limit_mb <= 0:
        raise ConfigError("runtime.ram_limit_mb must be > 0")
    _validate_trim(app.overrides.trim, "overrides.trim")
    _validate_trim(app.overrides.trim_end, "overrides.trim_end")
    _validate_change_fps(app.overrides.change_fps)
    return app
