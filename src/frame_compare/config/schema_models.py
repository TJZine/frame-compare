"""Configuration schema section models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from frame_compare.config.schema_enums import (
    LogFormat,
    LogLevel,
    OverlayMode,
    SelectionMode,
    ToneCurve,
    TonemapPreset,
    ViewerMode,
    Visibility,
)


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

    auto_upload: bool = False
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
    year_tolerance: int = Field(default=2, ge=0, le=5)
    category_preference: Literal["movie", "tv"] | None = None


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


__all__ = [
    "AnalysisConfig",
    "AudioAlignmentConfig",
    "ColorConfig",
    "DiagnosticsConfig",
    "DoviConfig",
    "LoggingConfig",
    "PathsConfig",
    "ReportConfig",
    "ScreenshotsConfig",
    "SlowpicsConfig",
    "TmdbConfig",
]
