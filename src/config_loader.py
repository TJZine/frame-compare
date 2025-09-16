from __future__ import annotations
from typing import Any, Dict
import tomllib
from .datatypes import AppConfig, AnalysisConfig, ScreenshotConfig, SlowpicsConfig, NamingConfig, PathsConfig

class ConfigError(ValueError):
    pass

def _section(raw: dict, name: str, cls):
    data: Dict[str, Any] = raw.get(name, {})
    try:
        obj = cls(**data)
    except TypeError as e:
        raise ConfigError(f"Invalid keys in [{name}]: {e}") from e
    return obj

def load_config(path: str) -> AppConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    app = AppConfig(
        analysis=_section(raw, "analysis", AnalysisConfig),
        screenshots=_section(raw, "screenshots", ScreenshotConfig),
        slowpics=_section(raw, "slowpics", SlowpicsConfig),
        naming=_section(raw, "naming", NamingConfig),
        paths=_section(raw, "paths", PathsConfig),
    )
    # Basic validation (extend as needed)
    if app.analysis.step < 1:
        raise ConfigError("analysis.step must be >= 1")
    if app.screenshots.compression_level not in (0,1,2):
        raise ConfigError("screenshots.compression_level must be 0, 1, or 2")
    if app.screenshots.mod_crop < 0:
        raise ConfigError("screenshots.mod_crop must be >= 0")
    return app
