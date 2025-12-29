---
RUN_ID: 2025-12-28__p1-1__config-module
VERSION: v1
TARGET: Phase 1 → Item 1.1 (Configuration Module)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v1.md
---

# Implementation Plan: Configuration Module

## Context

**Phase:** 1
**Module:** `frame_compare.config`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md`
**Dependencies:**

- `pydantic>=2.10.0` ✅ (in pyproject.toml)
- `pydantic-settings>=2.7.0` ✅ (in pyproject.toml)
- `frame_compare.errors` ❌ (Phase 1.2 – **not yet implemented**)

### Dependency Resolution Strategy

The config module spec requires importing error types from `frame_compare.errors`, but that module is scheduled for Phase 1.2. To unblock Phase 1.1:

1. **Create minimal error stubs** in `src/frame_compare/errors.py` containing ONLY the config-related exceptions:
   - `ErrorContext` dataclass
   - `FrameCompareError` base class
   - `ConfigError`, `ConfigNotFoundError`, `ConfigParseError`, `ConfigValidationError`, `PresetNotFoundError`
2. Phase 1.2 will **extend** (not replace) this file with the full exception hierarchy.
3. This maintains forward compatibility and allows config development without modification later.

## Scope

This plan covers:

- [x] `src/frame_compare/errors.py` — Minimal config-related error types only
- [x] `src/frame_compare/config/__init__.py` — Public exports
- [x] `src/frame_compare/config/schema.py` — Pydantic v2 models for all config sections + enums
- [x] `src/frame_compare/config/loader.py` — `load_config()`, `load_config_from_env()`, `get_default_config()`
- [x] `src/frame_compare/config/overrides.py` — CLI override mapping and application
- [x] `src/frame_compare/config/presets.py` — Preset list/load/save/apply
- [x] `src/frame_compare/config/defaults.py` — Default TOML template constant
- [x] `tests/config/test_schema.py` — Schema validation tests
- [x] `tests/config/test_loader.py` — Loader tests with TOML/ENV/overrides
- [x] `tests/config/test_presets.py` — Preset management tests
- [x] Delete `.gitkeep` from `src/frame_compare/config/`

This plan does NOT cover:

- Full error hierarchy (Phase 1.2)
- CLI integration (Phase 1.4)
- Logging infrastructure (Phase 1.3)

## Contract Impact

**Contracts touched:** NO

No canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` are modified by this plan.

---

## Files to Create/Modify

### 1. `src/frame_compare/errors.py` [NEW – Minimal Stub]

**Purpose:** Define config-related error types. Extended in Phase 1.2.

```python
"""Frame Compare error types (minimal stub for config module).

This module defines the error hierarchy for Frame Compare 2.0.
Phase 1.1 provides only config-related exceptions; Phase 1.2 extends
with the full hierarchy (dependency, input, processing, network, internal).

Error Codes:
    FC-1001: CONFIG_NOT_FOUND
    FC-1002: CONFIG_PARSE_ERROR
    FC-1003: CONFIG_VALIDATION_ERROR
    FC-1004: PRESET_NOT_FOUND
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

# Type alias for JSON-safe values
JSONValue: TypeAlias = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
ErrorDetails: TypeAlias = dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Structured error information for consistent error handling.

    Attributes:
        code: Machine-readable error code (e.g., "FC-1001")
        name: Short error name (e.g., "CONFIG_NOT_FOUND")
        message: Human-readable error description
        details: Optional structured data for debugging/logging
        hint: Optional recovery suggestion for the user
        cause: Optional underlying exception that caused this error
    """

    code: str
    name: str
    message: str
    details: ErrorDetails | None = None
    hint: str | None = None
    cause: BaseException | None = None

    def to_dict(self) -> dict[str, JSONValue]:
        """Convert to JSON-serializable dictionary."""
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
    """Base exception for all Frame Compare errors.

    All subclasses MUST provide an ErrorContext with a valid FC-xxxx code.
    """

    def __init__(self, context: ErrorContext) -> None:
        self.context = context
        super().__init__(context.message)

    @property
    def code(self) -> str:
        """Machine-readable error code."""
        return self.context.code

    @property
    def name(self) -> str:
        """Short error name."""
        return self.context.name

    @property
    def hint(self) -> str | None:
        """Recovery suggestion."""
        return self.context.hint

    def __str__(self) -> str:
        base = f"[{self.code}] {self.context.message}"
        if self.hint:
            base += f"\nHint: {self.hint}"
        return base

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.context!r})"


# ─── Configuration Errors (FC-1xxx) ────────────────────────────────────────────


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
```

---

### 2. `src/frame_compare/config/schema.py` [NEW]

**Purpose:** Define Pydantic v2 models for all configuration sections and enums.

**Enums to define:**

| Enum | Values |
|------|--------|
| `SelectionMode` | `QUANTILE`, `MOTION`, `RANDOM`, `MIXED` |
| `OverlayMode` | `MINIMAL`, `STANDARD`, `DIAGNOSTIC`, `NONE` |
| `TonemapPreset` | `REFERENCE`, `FILMIC`, `CONTRAST`, `BT2390_SPEC`, `SPLINE`, `BRIGHT_LIFT`, `HIGHLIGHT_GUARD` |
| `ToneCurve` | `BT2390`, `SPLINE`, `REINHARD`, `MOBIUS`, `LINEAR` |
| `Visibility` | `PUBLIC`, `UNLISTED`, `PRIVATE` |
| `ViewerMode` | `SLIDER`, `OVERLAY`, `DIFF`, `BLINK` |
| `LogLevel` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LogFormat` | `JSON`, `CONSOLE` |

**Section models:**

| Model | Key Fields | Notes |
|-------|------------|-------|
| `PathsConfig` | `input_dir`, `screenshots_dir`, `generated_dir`, `config_dir` | All `str`, defaults per spec |
| `AnalysisConfig` | `frame_count` (1-100), `random_seed`, `selection_mode`, quantiles | Use `Field(ge=, le=)` |
| `AudioAlignmentConfig` | `enable`, `sample_rate`, `max_offset_seconds`, `cache_results` | |
| `ScreenshotsConfig` | `use_ffmpeg`, `overlay_mode`, `png_compression` (0-9) | |
| `ColorConfig` | `enable_tonemap`, `preset`, `target_nits` (100-1000), `tone_curve` | |
| `SlowpicsConfig` | `auto_upload`, `visibility`, `timeout_seconds`, `max_retries` | |
| `TmdbConfig` | `api_key` (optional), `enabled`, `unattended`, `timeout_seconds` | |
| `ReportConfig` | `enable`, `output_dir` (optional), `default_mode`, `include_filmstrip` | `field_validator` for empty→None |
| `DoviConfig` | `enable`, `dovi_tool_path` (Path\|None), `cache_results` | |
| `DiagnosticsConfig` | `per_frame_nits`, `show_hdr_info`, `frame_timing` | All `bool` |
| `LoggingConfig` | `level`, `format`, `file` (optional) | |

**Root model:**

```python
class ConfigSchema(BaseSettings):
    """Root configuration schema using pydantic-settings.

    Precedence (highest to lowest):
    1. init/CLI overrides
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

**Purpose:** Config loading functions.

**Functions:**

```python
def load_config(
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> ConfigSchema:
    """Load configuration from TOML file with overrides.

    Priority (highest to lowest):
    1. Explicit overrides dict
    2. Environment variables (FRAME_COMPARE_*)
    3. TOML file values
    4. Default values

    Args:
        config_path: Path to TOML file, or None for defaults
        overrides: Optional overrides dict (nested keys via dicts)

    Returns:
        Validated ConfigSchema

    Raises:
        ConfigNotFoundError: If path specified but file missing
        ConfigParseError: If TOML syntax invalid
        ConfigValidationError: If values fail validation

    Implementation notes:
    1. If config_path is None, use default ConfigSchema (TOML from model_config)
    2. If config_path provided and exists, dynamically subclass ConfigSchema
       with model_config["toml_file"] = str(config_path)
    3. Catch tomllib.TOMLDecodeError -> ConfigParseError
    4. Catch pydantic.ValidationError -> ConfigValidationError
    """


def load_config_from_env() -> ConfigSchema:
    """Load config entirely from environment variables.

    Returns:
        ConfigSchema with defaults + env overrides only (no TOML file)
    """
    # Implementation: use a subclass with toml_file disabled


def get_default_config() -> ConfigSchema:
    """Get config with all default values (no TOML, no env).

    Returns:
        ConfigSchema with all defaults
    """
    # Implementation: construct with model_construct() to bypass
    # all sources except defaults
```

---

### 4. `src/frame_compare/config/overrides.py` [NEW]

**Purpose:** CLI override mapping and application.

```python
CLI_OVERRIDE_MAP: dict[str, str] = {
    # Analysis settings
    "tm_preset": "color.preset",
    "tm_target": "color.target_nits",
    "tm_curve": "color.tone_curve",
    "frame_count": "analysis.frame_count",
    "random_seed": "analysis.random_seed",
    # Screenshot settings
    "overlay": "screenshots.overlay_mode",
    # Publishing settings
    "no_upload": "slowpics.auto_upload",  # Inverted logic
    # Paths
    "input": "paths.input_dir",
    "output": "report.output_dir",
}


def apply_cli_overrides(
    config: ConfigSchema,
    cli_args: dict[str, object],
) -> ConfigSchema:
    """Apply CLI arguments as config overrides.

    Args:
        config: Base configuration to override
        cli_args: Dict of CLI argument names to values (from Typer)

    Returns:
        New ConfigSchema with overrides applied

    Implementation notes:
    1. Filter cli_args to only include keys in CLI_OVERRIDE_MAP
    2. Build nested override dict from dotted paths
    3. Handle inverted flags (no_upload -> auto_upload=False)
    4. Use config.model_copy(update=...) to produce new instance
    """
```

---

### 5. `src/frame_compare/config/presets.py` [NEW]

**Purpose:** Preset management.

```python
from pathlib import Path

from frame_compare.config.schema import ConfigSchema

DEFAULT_PRESETS_DIR = Path("config/presets")


def list_presets(presets_dir: Path | None = None) -> list[str]:
    """List available preset names.

    Args:
        presets_dir: Directory containing preset TOML files, or None for default

    Returns:
        List of preset names (without .toml extension), sorted alphabetically

    Implementation:
    1. Use presets_dir or DEFAULT_PRESETS_DIR
    2. Glob *.toml files
    3. Return sorted list of stems
    """


def load_preset(name: str, presets_dir: Path | None = None) -> dict[str, object]:
    """Load preset data by name.

    Args:
        name: Preset name (without .toml extension)
        presets_dir: Directory containing preset TOML files, or None for default

    Returns:
        Parsed TOML data as dict

    Raises:
        PresetNotFoundError: If preset file doesn't exist
        ConfigParseError: If TOML syntax invalid

    Implementation:
    1. Construct path: presets_dir / f"{name}.toml"
    2. Read and parse with tomllib
    3. Raise PresetNotFoundError if not exists
    """


def save_preset(
    name: str,
    config: ConfigSchema,
    presets_dir: Path | None = None,
) -> Path:
    """Save current config as preset.

    Args:
        name: Preset name (without .toml extension)
        config: Configuration to save
        presets_dir: Directory to save preset, or None for default

    Returns:
        Path to saved preset file

    Implementation:
    1. Serialize config to TOML using config.model_dump()
    2. Write to presets_dir / f"{name}.toml"
    3. Create presets_dir if not exists
    """


def apply_preset(config: ConfigSchema, preset_name: str) -> ConfigSchema:
    """Apply preset overrides to config.

    Args:
        config: Base configuration
        preset_name: Name of preset to apply

    Returns:
        New ConfigSchema with preset values merged

    Implementation:
    1. Load preset data via load_preset()
    2. Merge with config using model_copy(update=...)
    """
```

---

### 6. `src/frame_compare/config/defaults.py` [NEW]

**Purpose:** Default TOML template as a constant string.

```python
"""Default configuration template for Frame Compare.

This template is used by:
- wizard command to generate initial config
- Documentation generation
- Tests that need known default values
"""

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

### 7. `src/frame_compare/config/__init__.py` [MODIFY – Replace .gitkeep]

**Purpose:** Public exports.

```python
"""Configuration module for Frame Compare.

Public API:
    load_config: Load config from TOML file with overrides
    load_config_from_env: Load config from environment variables only
    get_default_config: Get config with all default values
    ConfigSchema: Root configuration model (Pydantic)
    apply_cli_overrides: Apply CLI arguments as config overrides
    apply_preset: Apply a preset to config
    list_presets: List available preset names
    load_preset: Load preset data by name
    save_preset: Save config as a preset

Enums:
    SelectionMode, OverlayMode, TonemapPreset, ToneCurve,
    Visibility, ViewerMode, LogLevel, LogFormat

Section Models:
    PathsConfig, AnalysisConfig, AudioAlignmentConfig, ScreenshotsConfig,
    ColorConfig, SlowpicsConfig, TmdbConfig, ReportConfig, DoviConfig,
    DiagnosticsConfig, LoggingConfig
"""

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
    # Loaders
    "load_config",
    "load_config_from_env",
    "get_default_config",
    # Schema
    "ConfigSchema",
    # Overrides
    "CLI_OVERRIDE_MAP",
    "apply_cli_overrides",
    # Presets
    "apply_preset",
    "list_presets",
    "load_preset",
    "save_preset",
    # Defaults
    "DEFAULT_CONFIG_TOML",
    # Enums
    "SelectionMode",
    "OverlayMode",
    "TonemapPreset",
    "ToneCurve",
    "Visibility",
    "ViewerMode",
    "LogLevel",
    "LogFormat",
    # Section models
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

**Purpose:** Test package marker.

```python
"""Tests for frame_compare.config module."""
```

---

### 9. `tests/config/test_schema.py` [NEW]

**Purpose:** Schema validation tests.

**Tests required:**

| Test | Description |
|------|-------------|
| `test_default_config_values` | `get_default_config()` returns expected defaults (`frame_count=10`, `preset=REFERENCE`) |
| `test_analysis_frame_count_bounds` | `frame_count` must be 1-100; values outside raise `ValidationError` |
| `test_color_target_nits_bounds` | `target_nits` must be 100-1000 |
| `test_enum_values_case_insensitive` | Enum fields accept lowercase string values (e.g., `"mixed"` → `SelectionMode.MIXED`) |
| `test_optional_path_accepts_none` | `DoviConfig.dovi_tool_path` accepts `None` |
| `test_report_output_dir_empty_string_to_none` | Empty string `""` for `output_dir` becomes `None` via validator |
| `test_nested_model_defaults` | All nested models have proper defaults when not specified |

---

### 10. `tests/config/test_loader.py` [NEW]

**Purpose:** Loader tests with TOML/ENV/overrides.

**Tests required:**

| Test | Description |
|------|-------------|
| `test_load_default_config` | `get_default_config()` returns config with all defaults |
| `test_load_from_toml_file` | Create temp TOML with `frame_count=20`, verify `load_config(path)` returns `frame_count=20` |
| `test_toml_file_not_found_raises` | `load_config(nonexistent_path)` raises `ConfigNotFoundError` |
| `test_toml_syntax_error_raises` | Invalid TOML raises `ConfigParseError` |
| `test_validation_error_raises` | TOML with `frame_count=-1` raises `ConfigValidationError` |
| `test_env_override` | Set `FRAME_COMPARE_ANALYSIS__FRAME_COUNT=30`, verify `load_config_from_env()` returns `frame_count=30` |
| `test_cli_override_takes_precedence` | Pass `overrides={"analysis": {"frame_count": 40}}`, verify it overrides TOML and ENV |
| `test_precedence_order` | TOML has `frame_count=10`, ENV has `20`, override has `30` — result is `30` |

---

### 11. `tests/config/test_presets.py` [NEW]

**Purpose:** Preset management tests.

**Tests required:**

| Test | Description |
|------|-------------|
| `test_list_presets_empty_dir` | Empty presets dir returns `[]` |
| `test_list_presets_finds_toml_files` | Dir with `a.toml`, `b.toml` returns `["a", "b"]` |
| `test_load_preset_success` | Load preset, verify contents match file |
| `test_load_preset_not_found_raises` | `load_preset("nonexistent")` raises `PresetNotFoundError` |
| `test_save_preset_creates_file` | `save_preset("test", config)` creates `test.toml` |
| `test_apply_preset_merges_values` | Preset with `frame_count=50` overrides config default |

---

## Acceptance Criteria

- [x] GIVEN no config file WHEN `get_default_config()` called THEN returns config with all defaults from spec
- [x] GIVEN valid TOML file WHEN `load_config(path)` called THEN returns validated ConfigSchema
- [x] GIVEN invalid TOML syntax WHEN `load_config(path)` called THEN raises `ConfigParseError` with path and details
- [x] GIVEN TOML with invalid values WHEN `load_config(path)` called THEN raises `ConfigValidationError` with field names
- [x] GIVEN `FRAME_COMPARE_ANALYSIS__FRAME_COUNT=20` in env WHEN `load_config_from_env()` called THEN `frame_count=20`
- [x] GIVEN overrides dict WHEN `load_config(overrides=...)` called THEN overrides take precedence over env and TOML
- [x] GIVEN presets dir with TOML files WHEN `list_presets()` called THEN returns sorted list of names
- [x] GIVEN preset TOML WHEN `apply_preset(config, name)` called THEN returns merged config

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# Type checking (must pass with 0 errors, 0 warnings)
.venv/bin/pyright --warnings src/frame_compare/config src/frame_compare/errors.py

# Linting (must pass with 0 errors)
.venv/bin/ruff check src/frame_compare/config src/frame_compare/errors.py

# Tests (must all pass)
.venv/bin/pytest -v tests/config/

# Coverage check (informational)
.venv/bin/pytest --cov=src/frame_compare/config --cov-report=term-missing tests/config/
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. **Order of implementation:**
   - First: `errors.py` (stub with config errors only)
   - Then: `config/schema.py` (enums first, then section models, then ConfigSchema)
   - Then: `config/defaults.py` (constant string)
   - Then: `config/loader.py` (imports schema + errors)
   - Then: `config/overrides.py`
   - Then: `config/presets.py`
   - Then: `config/__init__.py`
   - Finally: Tests

2. **Pydantic-settings TOML source:** Use `TomlConfigSettingsSource` from `pydantic_settings`. The import path is:

   ```python
   from pydantic_settings import (
       BaseSettings,
       PydanticBaseSettingsSource,
       SettingsConfigDict,
       TomlConfigSettingsSource,
   )
   ```

3. **Dynamic subclass for custom TOML path:** When `config_path` is provided, create a dynamic subclass:

   ```python
   settings_cls = type(
       "ConfigSchemaFromFile",
       (ConfigSchema,),
       {"model_config": SettingsConfigDict(**{**ConfigSchema.model_config, "toml_file": str(config_path)})},
   )
   ```

4. **Delete `.gitkeep`:** Remove `src/frame_compare/config/.gitkeep` after creating `__init__.py`.

5. **Test fixtures:** Use `pytest`'s `tmp_path` fixture for temp files. Use `monkeypatch.setenv()` for ENV tests.

6. **TOML writing for presets:** Python stdlib has `tomllib` (read-only). For writing TOML, use a simple approach:
   - Serialize to dict via `config.model_dump(mode="json")`
   - Use a simple custom TOML serializer function `_dump_toml(data: dict) -> str` that handles nested dicts.
   - This keeps dependencies minimal without adding `tomli-w`.

7. **Empty file handling:** `load_config_from_env()` should work even if `config/config.toml` doesn't exist (skip TOML source).

8. **field_validator for ReportConfig.output_dir:** Convert empty string to None:

   ```python
   @field_validator("output_dir", mode="before")
   @classmethod
   def normalize_empty_string(cls, v: str | None) -> str | None:
       if v == "":
           return None
       return v
   ```

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-28__p1-1__config-module

## Plan to Review

Read file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-28__p1-1__config-module/plan-review-v1.md
