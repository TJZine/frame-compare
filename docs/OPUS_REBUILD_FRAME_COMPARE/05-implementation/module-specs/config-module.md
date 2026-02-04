# Config Module Implementation Spec

> **Module:** `frame_compare.config`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The Config module handles configuration loading, validation, and management using Pydantic v2.

### 1.1 Responsibilities

- Load TOML configuration files
- Validate configuration with type safety
- Apply environment variable overrides
- Apply CLI argument overrides
- Manage presets

### 1.2 Module Structure

```text
src/frame_compare/config/
├── __init__.py          # Public exports
├── schema.py            # Pydantic models
├── loader.py            # Config loading
├── overrides.py         # CLI/env overrides
├── presets.py           # Preset management
└── defaults.py          # Default values
```

---

## 2. Configuration Schema

### 2.1 Root Schema

```python
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from pathlib import Path

class ConfigSchema(BaseSettings):
    """Root configuration schema."""

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
        """
        Enforce precedence: init/CLI > ENV > TOML > defaults.

        Notes:
        - `init_settings` is fed by `load_config(..., overrides=...)`.
        - `TomlConfigSettingsSource(settings_cls)` reads `model_config['toml_file']`.
        """
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

### 2.2 Section Schemas

```python
class PathsConfig(BaseModel):
    """Path configuration."""
    input_dir: str = "comparison_videos"
    screenshots_dir: str = "screenshots"
    generated_dir: str = "generated"
    config_dir: str = "config"

class AnalysisConfig(BaseModel):
    """Frame analysis configuration."""
    frame_count: int = Field(default=10, ge=1, le=100)
    random_seed: int = 42
    save_frames_data: bool = True
    selection_mode: SelectionMode = SelectionMode.MIXED
    dark_quantile: float = Field(default=0.05, ge=0.0, le=0.5)
    bright_quantile: float = Field(default=0.95, ge=0.5, le=1.0)

class AudioAlignmentConfig(BaseModel):
    """Audio alignment configuration."""
    enable: bool = True
    sample_rate: int = Field(default=8000, ge=4000, le=48000)
    max_offset_seconds: float = Field(default=30.0, ge=1.0)
    use_vspreview: bool = False
    force_interactive: bool = False
    cache_results: bool = True

class ScreenshotsConfig(BaseModel):
    """Screenshot rendering configuration."""
    use_ffmpeg: bool = False
    directory_name: str = "screenshots"
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    include_frame_number: bool = True
    png_compression: int = Field(default=6, ge=0, le=9)
    ffmpeg_timeout_seconds: float = Field(default=30.0, ge=5.0)

class ColorConfig(BaseModel):
    """Color and tonemapping configuration."""
    enable_tonemap: bool = True
    preset: TonemapPreset = TonemapPreset.REFERENCE
    target_nits: int = Field(default=203, ge=100, le=1000)
    tone_curve: ToneCurve = ToneCurve.BT2390
    gamma_lift: bool = False
    contrast_recovery: float = Field(default=0.0, ge=0.0, le=1.0)

class SlowpicsConfig(BaseModel):
    """slow.pics publishing configuration."""
    auto_upload: bool = True
    visibility: Visibility = Visibility.UNLISTED
    delete_after_upload: bool = False
    timeout_seconds: float = Field(default=60.0, ge=10.0)
    max_retries: int = Field(default=3, ge=1, le=10)

class TmdbConfig(BaseModel):
    """TMDB metadata configuration."""
    api_key: str | None = None
    enabled: bool = True
    unattended: bool = False
    timeout_seconds: float = Field(default=10.0, ge=1.0)

class ReportConfig(BaseModel):
    """HTML report configuration."""
    enable: bool = True
    output_dir: str | None = None  # None/empty = use screenshots_dir
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
    """Dolby Vision handling configuration.

    This is the canonical definition. The services/dovi.py module
    imports DoviConfig from here. TOML/ENV values are strings;
    Pydantic converts to Path.
    """
    enable: bool = True
    dovi_tool_path: Path | None = None  # Auto-detect from PATH or tools/
    cache_results: bool = True  # Cache extracted metadata to .dovi_info.json

class DiagnosticsConfig(BaseModel):
    """Diagnostics overlay configuration."""
    per_frame_nits: bool = False
    show_hdr_info: bool = False
    frame_timing: bool = False

class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.CONSOLE
    file: str | None = None
```

### 2.3 Enums

```python
from enum import Enum

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
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class LogFormat(str, Enum):
    JSON = "json"
    CONSOLE = "console"
```

---

## 3. Config Loading

### 3.1 Public API

```python
def load_config(
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> ConfigSchema:
    """
    Load configuration from TOML file with overrides.

    Priority (highest to lowest):
    1. Explicit overrides dict
    2. Environment variables (FRAME_COMPARE_*)
    3. TOML file values
    4. Default values

    Args:
        config_path: Path to TOML file, or None for defaults
        overrides: Optional overrides dict

    Returns:
        Validated ConfigSchema

    Raises:
        ConfigNotFoundError: If path specified but file missing
        ConfigParseError: If TOML syntax invalid
        ConfigValidationError: If values fail validation
    """

def load_config_from_env() -> ConfigSchema:
    """Load config entirely from environment variables."""

def get_default_config() -> ConfigSchema:
    """Get config with all default values."""
```

### 3.2 Implementation

```python
import tomllib
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

def load_config(
    config_path: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> ConfigSchema:
    """
    Load configuration using pydantic-settings sources with a fixed precedence:
    overrides/init > ENV > TOML > defaults.
    """
    if config_path is not None and not config_path.exists():
        raise ConfigNotFoundError(config_path)

    settings_cls: type[ConfigSchema]
    if config_path is None:
        settings_cls = ConfigSchema
    else:
        # Dynamic subclass so each call can point at a different TOML path.
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
        return settings_cls(**(overrides or {}))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(config_path or Path("config/config.toml"), str(exc)) from exc
    except ValidationError as exc:
        raise ConfigValidationError(exc.errors()) from exc
```

### 3.3 Special Environment Variables

The following environment variables are treated as **special/compatibility** knobs and are not expected to map 1:1 to nested Pydantic settings fields:

- `FRAME_COMPARE_ROOT` — Workspace root (resolved in `preflight.resolve_workspace_root()`).
- `FRAME_COMPARE_CONFIG` — Config file path (resolved in CLI/preflight, then passed to `load_config()`).
- `TMDB_API_KEY` — Legacy alias for `FRAME_COMPARE_TMDB__API_KEY` (supported for convenience).
- `FRAME_COMPARE_LOG_LEVEL` — Convenience alias for `FRAME_COMPARE_LOGGING__LEVEL`.

The config module should document which of these are honored directly vs injected into settings as overrides.

---

## 4. CLI Overrides

### 4.1 Override Mapping

```python
 # Map CLI flags to config paths
 # Note: Flags marked with "# Direct" are handled directly by the CLI layer
 # and don't map to config keys. They're documented here for completeness.
CLI_OVERRIDE_MAP: dict[str, str] = {
     # Analysis settings
    "tm_preset": "color.preset",
    "tm_target": "color.target_nits",
    "tm_curve": "color.tone_curve",
    "frame_count": "analysis.frame_count",
    "seed": "analysis.random_seed",
    "force_interactive_alignment": "audio_alignment.force_interactive",
     # Screenshot settings
    "overlay": "screenshots.overlay_mode",
     # Publishing settings
    "no_upload": "slowpics.auto_upload",  # Inverted: True = False
     # Paths (override workspace resolution, not stored in config)
    "input": "paths.input_dir",  # Direct path override
    "output": "report.output_dir",  # Direct path override
}

 # Flags handled directly by CLI (not config overrides)
 # - --quiet: Sets logging.level = "WARNING", captured in RunRequest
 # - --verbose: Sets logging.level = "DEBUG", captured in RunRequest
 # - --json: Sets output format, captured in RunRequest
 # - --no-color: Disables rich output, captured in RunRequest
 # - --version, --help: CLI-only flags

def apply_cli_overrides(
    config: ConfigSchema,
    cli_args: dict[str, object],
) -> ConfigSchema:
    """
    Apply CLI arguments as config overrides.

    Creates a new ConfigSchema with overrides applied.
    """
```

**Required implication (SSOT):**

If `force_interactive_alignment` is enabled by CLI override application, it MUST also set:

- `audio_alignment.use_vspreview = True`

---

## 5. Preset Management

### 5.1 Public API

```python
def list_presets(
    presets_dir: Path | None = None,
) -> list[str]:
    """List available preset names."""

def load_preset(
    name: str,
    presets_dir: Path | None = None,
) -> dict[str, object]:
    """Load preset data by name."""

def save_preset(
    name: str,
    config: ConfigSchema,
    presets_dir: Path | None = None,
) -> Path:
    """Save current config as preset."""

def apply_preset(
    config: ConfigSchema,
    preset_name: str,
) -> ConfigSchema:
    """Apply preset overrides to config."""
```

---

## 6. Config Template

### 6.1 Default Template

```toml
# Frame Compare Configuration
# See docs for full options

[paths]
input_dir = "comparison_videos"

[analysis]
frame_count = 10
random_seed = 42

[audio_alignment]
enable = true

[screenshots]
overlay_mode = "standard"

[color]
enable_tonemap = true
preset = "reference"
target_nits = 203

[slowpics]
auto_upload = true
visibility = "unlisted"

[tmdb]
# api_key = "your-api-key"
unattended = false

[report]
enable = true
default_mode = "slider"

[logging]
level = "INFO"
format = "console"
```

---

## 7. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors` (see [errors-module.md](errors-module.md)).
> This module should import and use these classes, not define its own.

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `ConfigError` | FC-1xxx | Base for config errors |
| `ConfigNotFoundError` | FC-1001 | Config file not found |
| `ConfigParseError` | FC-1002 | TOML parsing failed |
| `ConfigValidationError` | FC-1003 | Pydantic validation failed |

**Usage pattern:**

```python
from frame_compare.errors import (
    ConfigError,
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
)

# Raise when config file missing
raise ConfigNotFoundError(path)

# Raise when TOML invalid
raise ConfigParseError(path, "Invalid syntax at line 5")

# Raise when Pydantic validation fails
raise ConfigValidationError(pydantic_errors)
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
def test_load_default_config():
    config = get_default_config()
    assert config.analysis.frame_count == 10
    assert config.color.preset == TonemapPreset.REFERENCE

def test_load_from_toml(tmp_path):
    toml_file = tmp_path / "config.toml"
    toml_file.write_text('[analysis]\nframe_count = 20')

    config = load_config(toml_file)
    assert config.analysis.frame_count == 20

def test_env_override(monkeypatch):
    monkeypatch.setenv("FRAME_COMPARE_ANALYSIS__FRAME_COUNT", "30")
    config = load_config_from_env()
    assert config.analysis.frame_count == 30

def test_validation_error():
    with pytest.raises(ConfigValidationError):
        load_config(overrides={"analysis": {"frame_count": -1}})
```

---

## 9. AI Agent Implementation Prompt

```markdown
# Task: Implement Config Module

## Context
Implement the configuration module for Frame Compare 2.0 using Pydantic v2.

## Files to Create
1. `src/frame_compare/config/__init__.py` - Public exports
2. `src/frame_compare/config/schema.py` - Pydantic models
3. `src/frame_compare/config/loader.py` - Config loading
4. `src/frame_compare/config/overrides.py` - CLI/env overrides
5. `src/frame_compare/config/presets.py` - Preset management
6. `src/frame_compare/config/defaults.py` - Default values

## Key Requirements
- Pydantic v2 with pydantic-settings
- TOML loading with tomllib
- Environment variable overrides
- CLI argument overrides
- Strong validation with helpful errors

## Dependencies
- pydantic >= 2.0
- pydantic-settings >= 2.0

## Acceptance Criteria
- Config loads from TOML with validation
- Environment variables override TOML values
- CLI args override environment variables
- Validation errors include field names and hints
- Presets can be listed, loaded, saved, applied
```
