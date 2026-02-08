"""Configuration schema using Pydantic v2."""

from __future__ import annotations

import tomllib
from enum import Enum
from pathlib import Path
from typing import Any

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


class _TomlConfigSettingsSourceNoBOM(TomlConfigSettingsSource):
    """TOML settings source that accepts UTF-8 BOM-prefixed files.

    Python's built-in `tomllib.load()` rejects UTF-8 BOM at the start of the file
    (common on Windows). We decode with 'utf-8-sig' and parse via `tomllib.loads()`.
    """

    def _read_file(self, file_path: Path) -> dict[str, Any]:
        raw = file_path.read_bytes()
        text = raw.decode("utf-8-sig")
        return tomllib.loads(text)


class SelectionMode(str, Enum):
    """Frame selection strategy for choosing representative comparison frames."""

    QUANTILE = "quantile"
    MOTION = "motion"
    RANDOM = "random"
    MIXED = "mixed"


class OverlayMode(str, Enum):
    """Overlay verbosity level for rendered screenshots."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    DIAGNOSTIC = "diagnostic"
    NONE = "none"


class TonemapPreset(str, Enum):
    """Named tonemap preset applied when tonemapping HDR to SDR."""

    REFERENCE = "reference"
    FILMIC = "filmic"
    CONTRAST = "contrast"
    BT2390_SPEC = "bt2390_spec"
    SPLINE = "spline"
    BRIGHT_LIFT = "bright_lift"
    HIGHLIGHT_GUARD = "highlight_guard"


class ToneCurve(str, Enum):
    """Tone curve algorithm used by the tonemap implementation."""

    BT2390 = "bt2390"
    SPLINE = "spline"
    REINHARD = "reinhard"
    MOBIUS = "mobius"
    LINEAR = "linear"


class Visibility(str, Enum):
    """slow.pics gallery visibility setting."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class ViewerMode(str, Enum):
    """Default comparison viewer mode for generated HTML reports."""

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
    """Logging output format."""

    JSON = "json"
    CONSOLE = "console"


# ─── Section Models ────────────────────────────────────────────────────────────


class PathsConfig(BaseModel):
    """Filesystem paths relative to the workspace root."""

    input_dir: str = "comparison_videos"
    screenshots_dir: str = "screenshots"
    generated_dir: str = "generated"
    config_dir: str = "config"
    use_run_folders: bool = True


class AnalysisConfig(BaseModel):
    """Frame selection and analysis settings."""

    frame_count: int = Field(default=10, ge=1, le=100)
    random_seed: int = 42
    save_frames_data: bool = True
    selection_mode: SelectionMode = SelectionMode.MIXED
    dark_quantile: float = Field(default=0.05, ge=0.0, le=0.5)
    bright_quantile: float = Field(default=0.95, ge=0.5, le=1.0)


class AudioAlignmentConfig(BaseModel):
    """Audio alignment and interactive alignment configuration."""

    enable: bool = True
    sample_rate: int = Field(default=8000, ge=4000, le=48000)
    max_offset_seconds: float = Field(default=30.0, ge=1.0)
    use_vspreview: bool = False
    force_interactive: bool = False
    cache_results: bool = True


class ScreenshotsConfig(BaseModel):
    """Screenshot rendering settings (encoder choice, overlays, compression)."""

    use_ffmpeg: bool = False
    directory_name: str = "screenshots"
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    include_frame_number: bool = True
    png_compression: int = Field(default=6, ge=0, le=9)
    ffmpeg_timeout_seconds: float = Field(default=30.0, ge=5.0)


class ColorConfig(BaseModel):
    """Tonemapping configuration for HDR sources."""

    enable_tonemap: bool = True
    preset: TonemapPreset = TonemapPreset.REFERENCE
    target_nits: int = Field(default=203, ge=100, le=1000)
    tone_curve: ToneCurve = ToneCurve.BT2390
    gamma_lift: bool = False
    contrast_recovery: float = Field(default=0.0, ge=0.0, le=1.0)


class SlowpicsConfig(BaseModel):
    """slow.pics upload configuration and retry policy."""

    auto_upload: bool = True
    visibility: Visibility = Visibility.UNLISTED
    delete_after_upload: bool = False
    timeout_seconds: float = Field(default=60.0, ge=10.0)
    max_retries: int = Field(default=3, ge=1, le=10)


class TmdbConfig(BaseModel):
    """TMDB metadata lookup configuration."""

    api_key: str | None = None
    enabled: bool = True
    unattended: bool = False
    timeout_seconds: float = Field(default=10.0, ge=1.0)


class ReportConfig(BaseModel):
    """HTML report generation configuration."""

    enable: bool = True
    output_dir: str | None = None
    default_mode: ViewerMode = ViewerMode.SLIDER
    include_filmstrip: bool = True
    embed_images: bool = False
    auto_open: bool = True

    @field_validator("output_dir", mode="before")
    @classmethod
    def normalize_empty_string(cls, v: str | None) -> str | None:
        """Convert empty string to None for output_dir."""
        if v == "":
            return None
        return v


class DoviConfig(BaseModel):
    """Dolby Vision metadata extraction configuration."""

    enable: bool = True
    dovi_tool_path: Path | None = None
    cache_results: bool = True


class DiagnosticsConfig(BaseModel):
    """Optional diagnostic outputs for development and debugging."""

    per_frame_nits: bool = False
    show_hdr_info: bool = False
    frame_timing: bool = False


class LoggingConfig(BaseModel):
    """Logging configuration (level, format, optional file path)."""

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
            _TomlConfigSettingsSourceNoBOM(settings_cls),
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
