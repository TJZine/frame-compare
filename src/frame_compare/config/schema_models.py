"""Configuration schema section models."""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from frame_compare.config.schema_enums import (
    LogFormat,
    LogLevel,
    OverlayMode,
    ScreenshotGeometryMode,
    SelectionMode,
    ToneCurve,
    TonemapPreset,
    ViewerMode,
    Visibility,
    VsScreenshotWriter,
)

_EFFECTIVE_FPS_PATTERN = re.compile(r"^[0-9]+/[0-9]+$")


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
    correlation_mode: Literal["raw_fft", "gcc_phat"] = "raw_fft"
    preprocessing_mode: Literal["none", "standard"] = "none"
    channel_strategy: Literal["mono_downmix", "best_channel"] = "mono_downmix"
    confidence_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity_peak_ratio: float = Field(default=1.0, ge=1.0)
    window_length_seconds: float = Field(default=0.0, ge=0.0)
    window_stride_seconds: float = Field(default=0.0, ge=0.0)
    minimum_valid_windows: int = Field(default=1, ge=1)
    consensus_minimum_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    refinement_mode: Literal["disabled", "local"] = "disabled"
    refinement_sample_rate: int | None = Field(default=None, ge=4000, le=48000)
    reference_stream: int | None = Field(default=None, ge=0)
    comparison_streams: dict[str, Annotated[int, Field(ge=0)]] = Field(default_factory=dict)


class SourceActiveRectConfig(BaseModel):
    """Explicit source-frame active image rectangle."""

    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class SourceOverrideConfig(BaseModel):
    """Per-source overrides keyed by source selector."""

    model_config = ConfigDict(extra="forbid")

    trim_start_frames: int = Field(default=0, ge=0)
    trim_end_frames: int = Field(default=0, ge=0)
    active_rect: SourceActiveRectConfig | None = None
    effective_fps: Fraction | None = None

    @field_validator("effective_fps", mode="before")
    @classmethod
    def parse_effective_fps(cls, value: object) -> object:
        if value is None:
            return value
        if isinstance(value, Fraction):
            if value <= 0:
                raise ValueError("effective_fps must be positive")
            return value
        if not isinstance(value, str) or _EFFECTIVE_FPS_PATTERN.fullmatch(value) is None:
            raise ValueError('effective_fps must be a positive "num/den" string')
        try:
            parsed = Fraction(value)
        except ZeroDivisionError as exc:
            raise ValueError('effective_fps must be a positive "num/den" string') from exc
        if parsed <= 0:
            raise ValueError("effective_fps must be positive")
        return parsed

    @field_serializer("effective_fps")
    def serialize_effective_fps(self, value: Fraction | None) -> str | None:
        if value is None:
            return None
        return f"{value.numerator}/{value.denominator}"


class SourcesConfig(BaseModel):
    """Source identity, reference selection, and per-source overrides."""

    model_config = ConfigDict(extra="forbid")

    reference: str | None = None
    overrides: dict[str, SourceOverrideConfig] = Field(default_factory=dict)


class ScreenshotsConfig(BaseModel):
    """Screenshot rendering settings (encoder choice, overlays, compression)."""

    use_ffmpeg: bool = False
    directory_name: str = "screenshots"
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    include_frame_number: bool = True
    png_compression: int = Field(default=6, ge=0, le=9)
    ffmpeg_timeout_seconds: float = Field(default=30.0, ge=5.0)
    geometry_mode: ScreenshotGeometryMode = ScreenshotGeometryMode.NATIVE
    vs_writer: VsScreenshotWriter = VsScreenshotWriter.AUTO


class ColorConfig(BaseModel):
    """Tonemapping configuration for HDR sources."""

    enable_tonemap: bool = True
    preset: TonemapPreset = TonemapPreset.REFERENCE
    target_nits: int = Field(default=100, ge=100, le=1000)
    tone_curve: ToneCurve = ToneCurve.BT2390
    gamma_lift: bool = False
    contrast_recovery: float = Field(default=0.3, ge=0.0, le=1.0)


class SlowpicsConfig(BaseModel):
    """slow.pics upload configuration and retry policy."""

    auto_upload: bool = False
    confirm_upload_after_report: bool = False
    visibility: Visibility = Visibility.UNLISTED
    delete_after_upload: bool = False
    timeout_seconds: float = Field(default=60.0, ge=10.0)
    max_retries: int = Field(default=3, ge=1, le=10)
    copy_url_to_clipboard: bool = True
    open_in_browser: bool = True
    create_url_shortcut: bool = True
    webhook_url: str | None = None


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
    "SourceActiveRectConfig",
    "SourceOverrideConfig",
    "SourcesConfig",
    "TmdbConfig",
]
