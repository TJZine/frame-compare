"""Configuration schema using Pydantic v2."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from frame_compare.config.schema_enums import (
    AnalysisPerformanceMode,
    LogFormat,
    LogLevel,
    OverlayMode,
    ToneCurve,
    TonemapPreset,
    ViewerMode,
    Visibility,
)
from frame_compare.config.schema_models import (
    AnalysisConfig,
    AudioAlignmentConfig,
    ColorConfig,
    LoggingConfig,
    PathsConfig,
    ReportConfig,
    ScreenshotsConfig,
    SlowpicsConfig,
    SourceActiveRectConfig,
    SourceOverrideConfig,
    SourcesConfig,
    TmdbConfig,
)
from frame_compare.config.schema_sources import TomlConfigSettingsSourceNoBOM

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
            TomlConfigSettingsSourceNoBOM(settings_cls),
            file_secret_settings,
        )

    paths: PathsConfig = Field(default_factory=PathsConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    audio_alignment: AudioAlignmentConfig = Field(default_factory=AudioAlignmentConfig)
    screenshots: ScreenshotsConfig = Field(default_factory=ScreenshotsConfig)
    color: ColorConfig = Field(default_factory=ColorConfig)
    slowpics: SlowpicsConfig = Field(default_factory=SlowpicsConfig)
    tmdb: TmdbConfig = Field(default_factory=TmdbConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


__all__ = [
    "AnalysisPerformanceMode",
    "AnalysisConfig",
    "AudioAlignmentConfig",
    "ColorConfig",
    "ConfigSchema",
    "LogFormat",
    "LogLevel",
    "LoggingConfig",
    "OverlayMode",
    "PathsConfig",
    "ReportConfig",
    "ScreenshotsConfig",
    "SlowpicsConfig",
    "SourceActiveRectConfig",
    "SourceOverrideConfig",
    "SourcesConfig",
    "TmdbConfig",
    "ToneCurve",
    "TonemapPreset",
    "ViewerMode",
    "Visibility",
]
