"""Configuration schema section models."""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from frame_compare.config.schema_enums import (
    AnalysisPerformanceMode,
    LogFormat,
    LogLevel,
    OverlayMode,
    ScreenshotActiveRectDetection,
    ScreenshotAlignedScalePolicy,
    ScreenshotGeometryMode,
    SourceMatchFpsMode,
    ToneCurve,
    TonemapPreset,
    ViewerMode,
    Visibility,
    VsScreenshotWriter,
)
from frame_compare.config.slowpics import validate_slowpics_title_template
from frame_compare.config.text_validation import reject_control_characters

_EFFECTIVE_FPS_PATTERN = re.compile(r"^[0-9]+/[0-9]+$")


class PathsConfig(BaseModel):
    """Filesystem paths relative to the workspace root."""

    model_config = ConfigDict(extra="forbid")

    input_dir: str = "comparison_videos"
    generated_dir: str = "generated"
    config_dir: str = "config"


class AnalysisConfig(BaseModel):
    """Frame selection and analysis settings."""

    model_config = ConfigDict(extra="forbid")

    user_frames: list[int] = Field(default_factory=list[int])
    random_frame_count: int = Field(default=10, ge=0)
    dark_frame_count: int = Field(default=0, ge=0)
    bright_frame_count: int = Field(default=0, ge=0)
    motion_frame_count: int = Field(default=0, ge=0)
    random_seed: int = 42
    performance_mode: AnalysisPerformanceMode = AnalysisPerformanceMode.QUALITY
    ignore_lead_seconds: float = Field(default=0.0, ge=0.0)
    ignore_trail_seconds: float = Field(default=0.0, ge=0.0)
    min_window_seconds: float = Field(default=5.0, ge=0.0)
    dark_quantile: float = Field(default=0.05, ge=0.0, le=0.5)
    bright_quantile: float = Field(default=0.95, ge=0.5, le=1.0)

    @field_validator("user_frames")
    @classmethod
    def validate_user_frames(cls, value: list[int]) -> list[int]:
        if any(frame < 0 for frame in value):
            raise ValueError("user_frames must contain non-negative integers")
        return value

    @model_validator(mode="after")
    def validate_requested_frame_total(self) -> AnalysisConfig:
        requested = (
            len(self.user_frames)
            + self.random_frame_count
            + self.dark_frame_count
            + self.bright_frame_count
            + self.motion_frame_count
        )
        if requested == 0:
            raise ValueError("at least one analysis frame selector must request a frame")
        if requested > 100:
            raise ValueError("total requested frame selectors must be less than or equal to 100")
        return self


class AudioAlignmentConfig(BaseModel):
    """Audio alignment and interactive alignment configuration."""

    model_config = ConfigDict(extra="forbid")

    enable: bool = True
    sample_rate: int = Field(default=8000, ge=4000, le=48000)
    max_offset_seconds: float = Field(default=30.0, ge=1.0, allow_inf_nan=False)
    use_vsview: bool = False
    force_interactive: bool = False
    cache_results: bool = True
    previous_offsets: Literal["disabled", "prompt", "always"] = "disabled"
    correlation_mode: Literal["raw_fft", "gcc_phat"] = "raw_fft"
    preprocessing_mode: Literal["none", "standard"] = "none"
    channel_strategy: Literal["mono_downmix", "best_channel"] = "mono_downmix"
    confidence_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity_peak_ratio: float = Field(default=1.0, ge=1.0)
    window_length_seconds: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    window_stride_seconds: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
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
    label: str | None = None

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        reject_control_characters(value, field_name="label")
        normalized = value.strip()
        if not normalized:
            raise ValueError("label must not be empty")
        return normalized

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
    analysis_source: str = "reference"
    match_fps: SourceMatchFpsMode = SourceMatchFpsMode.DISABLED
    label_mode: Literal["stem", "filename", "parsed"] = "stem"
    label_parser: Literal["auto", "guessit", "anitopy"] = "auto"
    overrides: dict[str, SourceOverrideConfig] = Field(default_factory=dict)


class ScreenshotsConfig(BaseModel):
    """Screenshot rendering settings (encoder choice, overlays, compression)."""

    model_config = ConfigDict(extra="forbid")

    use_ffmpeg: bool = False
    overlay_mode: OverlayMode = OverlayMode.STANDARD
    include_frame_number: bool = True
    png_compression: int = Field(default=6, ge=0, le=9)
    ffmpeg_timeout_seconds: float = Field(default=30.0, ge=5.0)
    geometry_mode: ScreenshotGeometryMode = ScreenshotGeometryMode.NATIVE
    active_rect_detection: ScreenshotActiveRectDetection = (
        ScreenshotActiveRectDetection.ASPECT_RATIO
    )
    aligned_scale_policy: ScreenshotAlignedScalePolicy = ScreenshotAlignedScalePolicy.LARGEST_ACTIVE
    aligned_target_width: int | None = None
    aligned_target_height: int | None = None
    vs_writer: VsScreenshotWriter = VsScreenshotWriter.AUTO

    @field_validator("aligned_target_width", "aligned_target_height")
    @classmethod
    def validate_aligned_target_dimension(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value <= 0:
            raise ValueError("aligned target dimensions must be positive")
        if value % 2 != 0:
            raise ValueError("aligned target dimensions must be even")
        return value

    @model_validator(mode="after")
    def validate_aligned_target_policy(self) -> ScreenshotsConfig:
        if self.geometry_mode != ScreenshotGeometryMode.ALIGNED:
            return self

        has_width = self.aligned_target_width is not None
        has_height = self.aligned_target_height is not None
        if self.aligned_scale_policy == ScreenshotAlignedScalePolicy.EXPLICIT_SIZE:
            if not has_width or not has_height:
                raise ValueError(
                    "aligned_target_width and aligned_target_height are required "
                    "when aligned_scale_policy is explicit_size"
                )
            return self

        if has_width or has_height:
            raise ValueError(
                "aligned_target_width and aligned_target_height must be omitted unless "
                "aligned_scale_policy is explicit_size"
            )
        return self


class ColorConfig(BaseModel):
    """Tonemapping configuration for HDR sources."""

    model_config = ConfigDict(extra="forbid")

    enable_tonemap: bool = True
    preset: TonemapPreset = TonemapPreset.REFERENCE
    target_nits: int = Field(default=100, ge=100, le=1000)
    tone_curve: ToneCurve = ToneCurve.BT2390
    gamma_lift: bool = False
    contrast_recovery: float = Field(default=0.3, ge=0.0, le=1.0)


class SlowpicsConfig(BaseModel):
    """slow.pics upload configuration and retry policy."""

    model_config = ConfigDict(extra="forbid")

    auto_upload: bool = False
    confirm_upload_after_report: bool = False
    visibility: Visibility = Visibility.PUBLIC
    delete_after_upload: bool = False
    timeout_seconds: float = Field(default=60.0, ge=10.0)
    max_retries: int = Field(default=3, ge=1, le=10)
    title: str = ""
    title_template: str = ""
    title_suffix: str = ""
    is_hentai: Annotated[bool, Field(strict=True)] = False
    tmdb_id: Annotated[int, Field(strict=True, gt=0)] | None = None
    tmdb_media_type: Literal["movie", "tv"] | None = None
    remove_after_days: Annotated[int, Field(strict=True, ge=0, le=999999)] = 0
    image_upload_timeout_seconds: float = Field(default=180.0, ge=10.0)
    copy_url_to_clipboard: bool = True
    open_in_browser: bool = True
    create_url_shortcut: bool = True
    webhook_url: str | None = None

    @field_validator("webhook_url", mode="before")
    @classmethod
    def normalize_webhook_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("title", "title_template", "title_suffix")
    @classmethod
    def validate_title_text(cls, value: str, info: ValidationInfo) -> str:
        field_name = info.field_name or "slowpics title"
        reject_control_characters(value, field_name=field_name)
        normalized = value.strip()
        if field_name == "title_template" and normalized:
            validate_slowpics_title_template(normalized)
        return normalized

    @model_validator(mode="after")
    def validate_title_and_tmdb_pairs(self) -> SlowpicsConfig:
        if self.title and self.title_template:
            raise ValueError("title and title_template are mutually exclusive")
        if (self.tmdb_id is None) != (self.tmdb_media_type is None):
            raise ValueError("tmdb_id and tmdb_media_type must be configured together")
        return self


class TmdbConfig(BaseModel):
    """TMDB metadata lookup configuration."""

    model_config = ConfigDict(extra="forbid")

    api_key: str | None = None
    enabled: bool = True
    unattended: bool = False
    timeout_seconds: float = Field(default=10.0, ge=1.0)
    year_tolerance: int = Field(default=2, ge=0, le=5)
    category_preference: Literal["movie", "tv"] | None = None


class ReportConfig(BaseModel):
    """HTML report generation configuration."""

    model_config = ConfigDict(extra="forbid")

    enable: bool = True
    default_mode: ViewerMode = ViewerMode.SLIDER
    include_filmstrip: bool = True
    embed_images: bool = False
    auto_open: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration (level and format)."""

    model_config = ConfigDict(extra="forbid")

    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.CONSOLE


__all__ = [
    "AnalysisConfig",
    "AudioAlignmentConfig",
    "ColorConfig",
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
