---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v6
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v5.md
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v5.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v6.md
---

# Implementation Plan: Configuration Module

## Changes Since plan-v5

- **[Edit 1]** Added `exclude_none=True` to `save_preset()` serialization since TOML cannot represent `None`.
- **[Edit 2]** Updated `test_save_preset_roundtrip` assertion to use `exclude_none=True` comparison.
- **[Edit 3]** Added `test_save_preset_apply_restores_defaults` to verify round-trip through `ConfigSchema.model_validate()` restores defaults for omitted optional fields.

---

## Context

**Phase:** 1
**Module:** `frame_compare.config`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`
**Dependencies:**

- `pydantic>=2.10.0` ✅ (in pyproject.toml)
- `pydantic-settings>=2.7.0` ✅ (in pyproject.toml)
- `tomli-w>=1.0.0` ❌ (add to **runtime** dependencies)
- `frame_compare.errors` ❌ (minimal stub created in this plan)

## Scope

This plan covers:

- [x] `pyproject.toml` — Add `tomli-w>=1.0.0` to **runtime** dependencies
- [x] `src/frame_compare/errors.py` — Minimal config-related error types (FC-1001 to FC-1005)
- [x] `src/frame_compare/config/__init__.py` — Public exports
- [x] `src/frame_compare/config/schema.py` — Pydantic v2 models + enums
- [x] `src/frame_compare/config/loader.py` — Config loading with exact implementations
- [x] `src/frame_compare/config/overrides.py` — CLI override mapping with exact merge algorithm
- [x] `src/frame_compare/config/presets.py` — Preset management with tomli-w
- [x] `src/frame_compare/config/defaults.py` — Default TOML template
- [x] `tests/config/__init__.py` — Test package marker
- [x] `tests/config/test_schema.py` — Schema validation tests
- [x] `tests/config/test_loader.py` — Loader tests including env alias tests
- [x] `tests/config/test_presets.py` — Preset tests including determinism
- [x] `tests/config/test_overrides.py` — Override tests including inversion
- [x] Delete `.gitkeep` from `src/frame_compare/config/`

This plan does NOT cover:

- Full error hierarchy (Phase 1.2)
- CLI integration (Phase 1.4)
- Logging infrastructure (Phase 1.3)

## Contract Impact

**Contracts touched:** NO

---

## Rollback Guidance

### STOP Triggers

The Coding Agent MUST stop and return to Planning if:

1. `pydantic-settings` does not support `TomlConfigSettingsSource` as documented
2. The `settings_customise_sources` signature differs from the spec
3. Any spec mismatch is discovered that requires design decisions

### Rollback Steps

If implementation fails midway:

1. Delete all files created under `src/frame_compare/config/` except `.gitkeep`
2. Delete `src/frame_compare/errors.py` if created
3. Revert `pyproject.toml` changes (remove `tomli-w` from dependencies)
4. Delete `tests/config/` directory if created
5. Run `uv sync --group dev` to revert dependency changes

---

## Files to Create/Modify

### 0. `pyproject.toml` [MODIFY]

**Purpose:** Add `tomli-w` as a **runtime** dependency.

**Exact edit:** In the `[project]` section, add `tomli-w>=1.0.0` to the `dependencies` list:

```toml
dependencies = [
    "typer>=0.15.0",
    "rich>=13.9.0",
    "numpy>=2.2.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "structlog>=24.4.0",
    "anyio>=4.7.0",
    "tomli-w>=1.0.0",  # <-- ADD THIS LINE
]
```

---

### 1. `src/frame_compare/errors.py` [NEW]

```python
"""Frame Compare error types (minimal stub for config module).

Error Codes:
    FC-1001: CONFIG_NOT_FOUND
    FC-1002: CONFIG_PARSE_ERROR
    FC-1003: CONFIG_VALIDATION_ERROR
    FC-1004: PRESET_NOT_FOUND
    FC-1005: PRESET_INVALID
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Sequence

JSONValue: TypeAlias = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
ErrorDetails: TypeAlias = dict[str, JSONValue]


def normalize_pydantic_errors(
    errors: Sequence[dict[str, object]],
) -> list[dict[str, JSONValue]]:
    """Convert Pydantic validation error payloads to JSONValue-safe format."""
    result: list[dict[str, JSONValue]] = []
    for err in errors:
        safe_err: dict[str, JSONValue] = {}
        for key, value in err.items():
            safe_err[key] = _to_json_value(value)
        result.append(safe_err)
    return result


def _to_json_value(value: object) -> JSONValue:
    """Recursively convert a value to JSONValue."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_json_value(v) for k, v in value.items()}
    return str(value)


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Structured error information."""

    code: str
    name: str
    message: str
    details: ErrorDetails | None = None
    hint: str | None = None
    cause: BaseException | None = None

    def to_dict(self) -> dict[str, JSONValue]:
        result: dict[str, JSONValue] = {
            "code": self.code,
            "name": self.name,
            "message": self.message,
        }
        if self.hint:
            result["hint"] = self.hint
        if self.details:
            result["details"] = self.details
        return result


class FrameCompareError(Exception):
    """Base exception for all Frame Compare errors."""

    def __init__(self, context: ErrorContext) -> None:
        self.context = context
        super().__init__(context.message)

    @property
    def code(self) -> str:
        return self.context.code

    @property
    def name(self) -> str:
        return self.context.name

    @property
    def hint(self) -> str | None:
        return self.context.hint

    def __str__(self) -> str:
        base = f"[{self.code}] {self.context.message}"
        if self.hint:
            base += f"\nHint: {self.hint}"
        return base

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.context!r})"


class ConfigError(FrameCompareError):
    """Base class for configuration errors."""


class ConfigNotFoundError(ConfigError):
    """Configuration file not found (FC-1001)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1001",
                name="CONFIG_NOT_FOUND",
                message=f"Configuration file not found: {path}",
                hint="Run 'frame-compare wizard' or create config/config.toml",
                details={"path": str(path)},
            )
        )
        self.path = path


class ConfigParseError(ConfigError):
    """TOML parsing failed (FC-1002)."""

    def __init__(self, path: Path, parse_details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1002",
                name="CONFIG_PARSE_ERROR",
                message=f"Failed to parse {path}: {parse_details}",
                hint="Check TOML syntax at the indicated line",
                details={"path": str(path), "parse_error": parse_details},
            )
        )
        self.path = path


class ConfigValidationError(ConfigError):
    """Config validation failed (FC-1003)."""

    def __init__(self, errors: list[dict[str, JSONValue]]) -> None:
        fields = [str(e.get("loc", ["unknown"])[-1]) for e in errors]
        super().__init__(
            ErrorContext(
                code="FC-1003",
                name="CONFIG_VALIDATION_ERROR",
                message=f"Invalid configuration: {', '.join(fields)}",
                hint="Check field types and constraints",
                details={"validation_errors": errors},
            )
        )
        self.validation_errors = errors


class PresetNotFoundError(ConfigError):
    """Preset not found (FC-1004)."""

    def __init__(self, name: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1004",
                name="PRESET_NOT_FOUND",
                message=f"Preset not found: {name}",
                hint="Run 'frame-compare preset list' to see available",
                details={"preset_name": name},
            )
        )
        self.preset_name = name


class PresetInvalidError(ConfigError):
    """Preset file has invalid TOML syntax (FC-1005)."""

    def __init__(self, path: Path, parse_details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1005",
                name="PRESET_INVALID",
                message=f"Invalid preset file: {path}",
                hint="Check TOML syntax in preset file",
                details={"path": str(path), "parse_error": parse_details},
            )
        )
        self.path = path
```

---

### 2. `src/frame_compare/config/schema.py` [NEW]

```python
"""Configuration schema using Pydantic v2."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


# ─── Enums ─────────────────────────────────────────────────────────────────────
# Most enums use lowercase string values (Pydantic accepts lowercase only).
# Exception: LogLevel uses uppercase values per standard Python logging convention.


class SelectionMode(str, Enum):
    QUANTILE = "quantile"
    MOTION = "motion"
    RANDOM = "random"
    MIXED = "mixed"


class OverlayMode(str, Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    DIAGNOSTIC = "diagnostic"
    NONE = "none"


class TonemapPreset(str, Enum):
    REFERENCE = "reference"
    FILMIC = "filmic"
    CONTRAST = "contrast"
    BT2390_SPEC = "bt2390_spec"
    SPLINE = "spline"
    BRIGHT_LIFT = "bright_lift"
    HIGHLIGHT_GUARD = "highlight_guard"


class ToneCurve(str, Enum):
    BT2390 = "bt2390"
    SPLINE = "spline"
    REINHARD = "reinhard"
    MOBIUS = "mobius"
    LINEAR = "linear"


class Visibility(str, Enum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class ViewerMode(str, Enum):
    SLIDER = "slider"
    OVERLAY = "overlay"
    DIFF = "diff"
    BLINK = "blink"


class LogLevel(str, Enum):
    """Log level using uppercase values per Python logging convention."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogFormat(str, Enum):
    JSON = "json"
    CONSOLE = "console"


# ─── Section Models ────────────────────────────────────────────────────────────


class PathsConfig(BaseModel):
    input_dir: str = "comparison_videos"
    screenshots_dir: str = "screenshots"
    generated_dir: str = "generated"
    config_dir: str = "config"


class AnalysisConfig(BaseModel):
    frame_count: int = Field(default=10, ge=1, le=100)
    random_seed: int = 42
    save_frames_data: bool = True
    selection_mode: SelectionMode = SelectionMode.MIXED
    dark_quantile: float = Field(default=0.05, ge=0.0, le=0.5)
    bright_quantile: float = Field(default=0.95, ge=0.5, le=1.0)


class AudioAlignmentConfig(BaseModel):
    enable: bool = True
    sample_rate: int = Field(default=8000, ge=4000, le=48000)
    max_offset_seconds: float = Field(default=30.0, ge=1.0)
    use_vspreview: bool = False
    cache_results: bool = True


class ScreenshotsConfig(BaseModel):
    use_ffmpeg: bool = False
    directory_name: str = "screenshots"
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    include_frame_number: bool = True
    png_compression: int = Field(default=6, ge=0, le=9)
    ffmpeg_timeout_seconds: float = Field(default=30.0, ge=5.0)


class ColorConfig(BaseModel):
    enable_tonemap: bool = True
    preset: TonemapPreset = TonemapPreset.REFERENCE
    target_nits: int = Field(default=203, ge=100, le=1000)
    tone_curve: ToneCurve = ToneCurve.BT2390
    gamma_lift: bool = False
    contrast_recovery: float = Field(default=0.0, ge=0.0, le=1.0)


class SlowpicsConfig(BaseModel):
    auto_upload: bool = True
    visibility: Visibility = Visibility.UNLISTED
    delete_after_upload: bool = False
    timeout_seconds: float = Field(default=60.0, ge=10.0)
    max_retries: int = Field(default=3, ge=1, le=10)


class TmdbConfig(BaseModel):
    api_key: str | None = None
    enabled: bool = True
    unattended: bool = False
    timeout_seconds: float = Field(default=10.0, ge=1.0)


class ReportConfig(BaseModel):
    enable: bool = True
    output_dir: str | None = None
    default_mode: ViewerMode = ViewerMode.SLIDER
    include_filmstrip: bool = True
    embed_images: bool = False

    @field_validator("output_dir", mode="before")
    @classmethod
    def normalize_empty_string(cls, v: str | None) -> str | None:
        """Convert empty string to None for output_dir."""
        if v == "":
            return None
        return v


class DoviConfig(BaseModel):
    enable: bool = True
    dovi_tool_path: Path | None = None
    cache_results: bool = True


class DiagnosticsConfig(BaseModel):
    per_frame_nits: bool = False
    show_hdr_info: bool = False
    frame_timing: bool = False


class LoggingConfig(BaseModel):
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.CONSOLE
    file: str | None = None


# ─── Root Schema ───────────────────────────────────────────────────────────────


class ConfigSchema(BaseSettings):
    """Root configuration schema using pydantic-settings.

    Precedence (highest to lowest):
    1. init/CLI overrides (passed to constructor)
    2. Environment variables (FRAME_COMPARE_*)
    3. TOML file values
    4. Default values
    """

    model_config = SettingsConfigDict(
        env_prefix="FRAME_COMPARE_",
        env_nested_delimiter="__",
        toml_file="config/config.toml",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    paths: PathsConfig = Field(default_factory=PathsConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    audio_alignment: AudioAlignmentConfig = Field(default_factory=AudioAlignmentConfig)
    screenshots: ScreenshotsConfig = Field(default_factory=ScreenshotsConfig)
    color: ColorConfig = Field(default_factory=ColorConfig)
    slowpics: SlowpicsConfig = Field(default_factory=SlowpicsConfig)
    tmdb: TmdbConfig = Field(default_factory=TmdbConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    dovi: DoviConfig = Field(default_factory=DoviConfig)
    diagnostics: DiagnosticsConfig = Field(default_factory=DiagnosticsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
```

---

### 3. `src/frame_compare/config/loader.py` [NEW]

```python
"""Configuration loading functions."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import cast

from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
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
        settings_cls = type(
            "ConfigSchemaFromFile",
            (ConfigSchema,),
            {
                "model_config": SettingsConfigDict(
                    **{**ConfigSchema.model_config, "toml_file": str(config_path)}
                )
            },
        )

    try:
        return settings_cls(**merged_overrides)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(
            config_path or Path("config/config.toml"), str(exc)
        ) from exc
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(exc.errors())
        raise ConfigValidationError(normalized) from exc


def load_config_from_env() -> ConfigSchema:
    """Load config from environment variables only (no TOML file)."""

    class _EnvOnlySchema(ConfigSchema):
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
        return _EnvOnlySchema(**alias_overrides)
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(exc.errors())
        raise ConfigValidationError(normalized) from exc


def get_default_config() -> ConfigSchema:
    """Get config with all default values (no TOML, no env)."""

    class _DefaultsOnlySchema(ConfigSchema):
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

    if (
        "FRAME_COMPARE_LOG_LEVEL" in os.environ
        and "FRAME_COMPARE_LOGGING__LEVEL" not in os.environ
    ):
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
```

---

### 4. `src/frame_compare/config/overrides.py` [NEW]

```python
"""CLI override mapping and application."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pydantic import ValidationError

from frame_compare.errors import ConfigValidationError, normalize_pydantic_errors

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema

CLI_OVERRIDE_MAP: dict[str, str] = {
    "tm_preset": "color.preset",
    "tm_target": "color.target_nits",
    "tm_curve": "color.tone_curve",
    "frame_count": "analysis.frame_count",
    "random_seed": "analysis.random_seed",
    "overlay": "screenshots.overlay_mode",
    "no_upload": "slowpics.auto_upload",
    "input": "paths.input_dir",
    "output": "report.output_dir",
}

_INVERTED_FLAGS: frozenset[str] = frozenset({"no_upload"})


def apply_cli_overrides(
    config: "ConfigSchema",
    cli_args: dict[str, object],
) -> "ConfigSchema":
    """Apply CLI arguments as config overrides."""
    from frame_compare.config.schema import ConfigSchema

    overrides: dict[str, object] = {}
    for cli_name, config_path in CLI_OVERRIDE_MAP.items():
        if cli_name not in cli_args or cli_args[cli_name] is None:
            continue

        value = cli_args[cli_name]
        if cli_name in _INVERTED_FLAGS:
            value = not value

        _set_nested(overrides, config_path, value)

    if not overrides:
        return config

    base_dict = config.model_dump()
    merged = _deep_merge(base_dict, overrides)

    try:
        return ConfigSchema.model_validate(merged)
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(exc.errors())
        raise ConfigValidationError(normalized) from exc


def _set_nested(d: dict[str, object], path: str, value: object) -> None:
    """Set a value in a nested dict using dotted path notation."""
    keys = path.split(".")
    current: dict[str, object] = d
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        next_level = current[key]
        if not isinstance(next_level, dict):
            current[key] = {}
            next_level = current[key]
        current = cast(dict[str, object], next_level)
    current[keys[-1]] = value


def _deep_merge(base: dict[str, object], updates: dict[str, object]) -> dict[str, object]:
    """Deep merge two dicts. Updates take precedence."""
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
```

---

### 5. `src/frame_compare/config/presets.py` [NEW]

**Key change:** Use `exclude_none=True` in `save_preset()` since TOML has no null representation.

```python
"""Preset management for Frame Compare configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast

import tomli_w
from pydantic import ValidationError

from frame_compare.errors import (
    ConfigValidationError,
    PresetInvalidError,
    PresetNotFoundError,
    normalize_pydantic_errors,
)

if TYPE_CHECKING:
    from frame_compare.config.schema import ConfigSchema

DEFAULT_PRESETS_DIR = Path("config/presets")


def list_presets(presets_dir: Path | None = None) -> list[str]:
    """List available preset names (sorted alphabetically)."""
    directory = presets_dir or DEFAULT_PRESETS_DIR
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.toml"))


def load_preset(name: str, presets_dir: Path | None = None) -> dict[str, object]:
    """Load preset data by name."""
    directory = presets_dir or DEFAULT_PRESETS_DIR
    preset_path = directory / f"{name}.toml"

    if not preset_path.exists():
        raise PresetNotFoundError(name)

    try:
        return tomllib.loads(preset_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise PresetInvalidError(preset_path, str(exc)) from exc


def save_preset(
    name: str,
    config: "ConfigSchema",
    presets_dir: Path | None = None,
) -> Path:
    """Save current config as preset.

    Uses tomli-w for TOML serialization. Output order is stable
    (follows Pydantic model field declaration order).

    None values are excluded because TOML has no null representation.
    When a preset is loaded and applied, Pydantic will use defaults
    for any missing optional fields.
    """
    directory = presets_dir or DEFAULT_PRESETS_DIR
    directory.mkdir(parents=True, exist_ok=True)

    preset_path = directory / f"{name}.toml"

    # exclude_none=True: TOML has no null; omitted keys use defaults when loaded
    data = config.model_dump(mode="json", exclude_none=True)
    toml_text = tomli_w.dumps(data)
    preset_path.write_text(toml_text, encoding="utf-8")

    return preset_path


def apply_preset(config: "ConfigSchema", preset_name: str) -> "ConfigSchema":
    """Apply preset overrides to config.

    Loaded preset data is merged with the config. Missing optional
    keys (excluded due to None) are filled with schema defaults
    during validation.
    """
    from frame_compare.config.schema import ConfigSchema

    preset_data = load_preset(preset_name)
    base_dict = config.model_dump()
    merged = _deep_merge(base_dict, preset_data)

    try:
        return ConfigSchema.model_validate(merged)
    except ValidationError as exc:
        normalized = normalize_pydantic_errors(exc.errors())
        raise ConfigValidationError(normalized) from exc


def _deep_merge(base: dict[str, object], updates: dict[str, object]) -> dict[str, object]:
    """Deep merge two dicts. Updates take precedence."""
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
```

---

### 6. `src/frame_compare/config/defaults.py` [NEW]

```python
"""Default configuration template for Frame Compare."""

DEFAULT_CONFIG_TOML = '''\
# Frame Compare Configuration
# See docs for full options

[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"

[analysis]
frame_count = 10
random_seed = 42
save_frames_data = true
selection_mode = "mixed"
dark_quantile = 0.05
bright_quantile = 0.95

[audio_alignment]
enable = true
sample_rate = 8000
max_offset_seconds = 30.0
use_vspreview = false
cache_results = true

[screenshots]
use_ffmpeg = false
directory_name = "screenshots"
overlay_mode = "standard"
include_frame_number = true
png_compression = 6
ffmpeg_timeout_seconds = 30.0

[color]
enable_tonemap = true
preset = "reference"
target_nits = 203
tone_curve = "bt2390"
gamma_lift = false
contrast_recovery = 0.0

[slowpics]
auto_upload = true
visibility = "unlisted"
delete_after_upload = false
timeout_seconds = 60.0
max_retries = 3

[tmdb]
# api_key = "your-api-key"
enabled = true
unattended = false
timeout_seconds = 10.0

[report]
enable = true
# output_dir = null  # defaults to screenshots_dir
default_mode = "slider"
include_filmstrip = true
embed_images = false

[dovi]
enable = true
# dovi_tool_path = null  # auto-detect from PATH
cache_results = true

[diagnostics]
per_frame_nits = false
show_hdr_info = false
frame_timing = false

[logging]
level = "INFO"
format = "console"
# file = null
'''
```

---

### 7. `src/frame_compare/config/__init__.py` [NEW]

```python
"""Configuration module for Frame Compare."""

from frame_compare.config.defaults import DEFAULT_CONFIG_TOML
from frame_compare.config.loader import (
    get_default_config,
    load_config,
    load_config_from_env,
)
from frame_compare.config.overrides import CLI_OVERRIDE_MAP, apply_cli_overrides
from frame_compare.config.presets import (
    apply_preset,
    list_presets,
    load_preset,
    save_preset,
)
from frame_compare.config.schema import (
    AnalysisConfig,
    AudioAlignmentConfig,
    ColorConfig,
    ConfigSchema,
    DiagnosticsConfig,
    DoviConfig,
    LogFormat,
    LoggingConfig,
    LogLevel,
    OverlayMode,
    PathsConfig,
    ReportConfig,
    ScreenshotsConfig,
    SelectionMode,
    SlowpicsConfig,
    TmdbConfig,
    TonemapPreset,
    ToneCurve,
    ViewerMode,
    Visibility,
)

__all__ = [
    "load_config",
    "load_config_from_env",
    "get_default_config",
    "ConfigSchema",
    "CLI_OVERRIDE_MAP",
    "apply_cli_overrides",
    "apply_preset",
    "list_presets",
    "load_preset",
    "save_preset",
    "DEFAULT_CONFIG_TOML",
    "SelectionMode",
    "OverlayMode",
    "TonemapPreset",
    "ToneCurve",
    "Visibility",
    "ViewerMode",
    "LogLevel",
    "LogFormat",
    "PathsConfig",
    "AnalysisConfig",
    "AudioAlignmentConfig",
    "ScreenshotsConfig",
    "ColorConfig",
    "SlowpicsConfig",
    "TmdbConfig",
    "ReportConfig",
    "DoviConfig",
    "DiagnosticsConfig",
    "LoggingConfig",
]
```

---

### 8. `tests/config/__init__.py` [NEW]

```python
"""Tests for frame_compare.config module."""
```

---

### 9. `tests/config/test_schema.py` [NEW]

| Test | Description |
|------|-------------|
| `test_default_config_values` | `get_default_config()` returns expected defaults |
| `test_analysis_frame_count_bounds_too_low` | `frame_count=0` raises `ValidationError` |
| `test_analysis_frame_count_bounds_too_high` | `frame_count=101` raises `ValidationError` |
| `test_color_target_nits_bounds_too_low` | `target_nits=99` raises `ValidationError` |
| `test_color_target_nits_bounds_too_high` | `target_nits=1001` raises `ValidationError` |
| `test_enum_lowercase_only_accepted` | `"mixed"` works; `"MIXED"` raises `ValidationError` |
| `test_optional_path_accepts_none` | `DoviConfig(dovi_tool_path=None)` is valid |
| `test_report_output_dir_empty_string_to_none` | `output_dir=""` becomes `None` |
| `test_nested_model_defaults` | All nested models have proper defaults |

---

### 10. `tests/config/test_loader.py` [NEW]

| Test | Description |
|------|-------------|
| `test_load_default_config` | `get_default_config()` returns defaults without TOML/env |
| `test_load_from_toml_file` | TOML with `frame_count=20` works |
| `test_toml_file_not_found_raises` | Missing path raises `ConfigNotFoundError` |
| `test_toml_syntax_error_raises` | Invalid TOML raises `ConfigParseError` |
| `test_validation_error_raises` | `frame_count=-1` raises `ConfigValidationError` |
| `test_config_validation_error_context_is_json_serializable` | `exc.context.to_dict()` is JSON-serializable |
| `test_env_override` | `FRAME_COMPARE_ANALYSIS__FRAME_COUNT=30` works |
| `test_cli_override_takes_precedence` | Explicit overrides beat TOML/env |
| `test_precedence_order` | TOML=10, ENV=20, override=30 → result=30 |
| `test_tmdb_api_key_legacy_alias_env_var` | `TMDB_API_KEY=xxx` sets `tmdb.api_key` |
| `test_tmdb_api_key_nested_var_takes_precedence` | `FRAME_COMPARE_TMDB__API_KEY` beats `TMDB_API_KEY` |
| `test_log_level_legacy_alias_env_var` | `FRAME_COMPARE_LOG_LEVEL=DEBUG` sets `logging.level` |

---

### 11. `tests/config/test_overrides.py` [NEW]

| Test | Description |
|------|-------------|
| `test_apply_cli_overrides_basic` | `frame_count=50` override works |
| `test_apply_cli_overrides_inverts_no_upload` | `no_upload=True` → `auto_upload=False` |
| `test_apply_cli_overrides_ignores_none_values` | `None` values are skipped |
| `test_apply_cli_overrides_ignores_unknown_keys` | Unknown keys are ignored |

---

### 12. `tests/config/test_presets.py` [NEW]

| Test | Description |
|------|-------------|
| `test_list_presets_empty_dir` | Empty/missing dir returns `[]` |
| `test_list_presets_finds_toml_files` | Dir with `a.toml`, `b.toml` returns `["a", "b"]` |
| `test_load_preset_success` | Load valid preset works |
| `test_load_preset_not_found_raises` | Missing preset raises `PresetNotFoundError` |
| `test_preset_invalid_toml_raises_parse_error` | Invalid TOML raises `PresetInvalidError` |
| `test_save_preset_creates_file` | `save_preset()` creates file |
| `test_save_preset_roundtrip` | Save → load data equality (exclude_none) |
| `test_save_preset_apply_restores_defaults` | Apply preset restores full config |
| `test_apply_preset_merges_values` | Preset `frame_count=50` overrides default |
| `test_save_preset_deterministic_output` | Calling twice produces identical files |

**Exact implementation for preset roundtrip tests:**

```python
def test_save_preset_roundtrip(tmp_path: Path) -> None:
    """Save a config as preset, load it, and verify data equality.

    Uses exclude_none=True because TOML cannot represent None.
    """
    from frame_compare.config import get_default_config, load_preset, save_preset

    original_config = get_default_config()
    # This is what save_preset serializes (excludes None values)
    expected_data = original_config.model_dump(mode="json", exclude_none=True)

    save_preset("roundtrip", original_config, tmp_path)
    loaded_data = load_preset("roundtrip", tmp_path)

    assert loaded_data == expected_data


def test_save_preset_apply_restores_defaults(tmp_path: Path) -> None:
    """Applying a saved preset restores the full config with defaults."""
    from frame_compare.config import apply_preset, get_default_config, save_preset

    original_config = get_default_config()
    save_preset("defaults", original_config, tmp_path)

    # Start with a fresh default config
    base_config = get_default_config()
    restored_config = apply_preset(base_config, "defaults")

    # The restored config should equal the original (defaults fill missing keys)
    assert restored_config.model_dump(mode="json") == original_config.model_dump(mode="json")
```

---

## Acceptance Criteria

- [x] GIVEN no config file WHEN `get_default_config()` called THEN returns config with all defaults
- [x] GIVEN valid TOML file WHEN `load_config(path)` called THEN returns validated ConfigSchema
- [x] GIVEN invalid TOML syntax WHEN `load_config(path)` called THEN raises `ConfigParseError`
- [x] GIVEN TOML with invalid values WHEN `load_config(path)` called THEN raises `ConfigValidationError` with JSON-serializable context
- [x] GIVEN `FRAME_COMPARE_ANALYSIS__FRAME_COUNT=20` WHEN `load_config_from_env()` called THEN `frame_count=20`
- [x] GIVEN `TMDB_API_KEY=xxx` (without nested var) WHEN `load_config()` called THEN `tmdb.api_key="xxx"`
- [x] GIVEN `no_upload=True` in cli_args WHEN `apply_cli_overrides()` called THEN `slowpics.auto_upload=False`
- [x] GIVEN preset with invalid TOML WHEN `load_preset()` called THEN raises `PresetInvalidError`
- [x] GIVEN `save_preset()` called twice with same config WHEN compared THEN file contents are identical
- [x] GIVEN `save_preset()` then `load_preset()` WHEN compared THEN `load_preset() == config.model_dump(mode="json", exclude_none=True)`
- [x] GIVEN `save_preset()` then `apply_preset()` WHEN applied to default config THEN restored config equals original

---

## Verification Commands

```bash
# Install dependencies including dev tooling
uv sync --group dev

# Type checking (0 errors, 0 warnings, NO type ignores in source)
.venv/bin/pyright --warnings src/frame_compare/config src/frame_compare/errors.py

# Linting (0 errors)
.venv/bin/ruff check src/frame_compare/config src/frame_compare/errors.py

# Tests (all pass)
.venv/bin/pytest -v tests/config/

# Verify no type ignores remain in source
grep -r "type: ignore" src/frame_compare/config/ src/frame_compare/errors.py && exit 1 || echo "OK: no type ignores"
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

---

## Notes for Coding Agent

1. **Order of implementation:**
   - First: `pyproject.toml` (add tomli-w to runtime deps)
   - Second: `uv sync --group dev` to install
   - Third: `errors.py`
   - Fourth: `config/schema.py`
   - Fifth: `config/defaults.py`
   - Sixth: `config/loader.py`
   - Seventh: `config/overrides.py`
   - Eighth: `config/presets.py`
   - Ninth: `config/__init__.py`
   - Finally: Tests

2. **Delete `.gitkeep`:** Remove `src/frame_compare/config/.gitkeep` after creating `__init__.py`.

3. **No `# type: ignore`:** Use `isinstance()` and `cast()` for type narrowing.

4. **`tomli_w.dumps()` returns `str`:** Use `write_text(..., encoding="utf-8")`.

5. **LogLevel is uppercase:** The `LogLevel` enum uses uppercase values per Python logging conventions.

6. **Preset serialization uses `exclude_none=True`:** TOML has no null representation. When preset is loaded and applied, Pydantic fills in defaults for missing optional keys.

7. **STOP triggers:** If `TomlConfigSettingsSource` import fails or signature differs, STOP and return to Planning.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-1__config-module

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v6.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v6.md
