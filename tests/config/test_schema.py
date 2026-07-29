"""Tests for configuration schema validation."""

import tomllib
from fractions import Fraction
from pathlib import Path

import pytest
import tomli_w
from pydantic import BaseModel, ValidationError

from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import (
    AnalysisConfig,
    ColorConfig,
    ConfigSchema,
    ReportConfig,
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
    Visibility,
    VsScreenshotWriter,
)
from frame_compare.config.schema_models import (
    AudioAlignmentConfig,
    DiagnosticsConfig,
    LoggingConfig,
    PathsConfig,
    ScreenshotsConfig,
    SlowpicsConfig,
    SourceActiveRectConfig,
    SourceOverrideConfig,
    SourcesConfig,
    TmdbConfig,
)
from frame_compare.config.schema_sources import TomlConfigSettingsSourceNoBOM


def test_default_config_values() -> None:
    """Test that default config has expected values."""
    config = get_default_config()
    assert config.analysis.user_frames == []
    assert config.analysis.random_frame_count == 10
    assert config.analysis.dark_frame_count == 0
    assert config.analysis.bright_frame_count == 0
    assert config.analysis.motion_frame_count == 0
    assert config.analysis.performance_mode == AnalysisPerformanceMode.QUALITY
    assert config.analysis.ignore_lead_seconds == 0.0
    assert config.analysis.ignore_trail_seconds == 0.0
    assert config.analysis.min_window_seconds == 5.0
    assert config.color.target_nits == 100
    assert config.paths.input_dir == "comparison_videos"
    assert config.sources.reference is None
    assert config.sources.analysis_source == "reference"
    assert config.sources.match_fps == SourceMatchFpsMode.DISABLED
    assert config.sources.overrides == {}
    assert config.screenshots.geometry_mode == ScreenshotGeometryMode.NATIVE
    assert config.screenshots.active_rect_detection == ScreenshotActiveRectDetection.ASPECT_RATIO
    assert config.screenshots.aligned_scale_policy == ScreenshotAlignedScalePolicy.LARGEST_ACTIVE
    assert config.screenshots.aligned_target_width is None
    assert config.screenshots.aligned_target_height is None
    assert config.screenshots.vs_writer == VsScreenshotWriter.AUTO
    assert config.tmdb.year_tolerance == 2
    assert config.tmdb.category_preference is None
    assert config.audio_alignment.correlation_mode == "raw_fft"
    assert config.audio_alignment.preprocessing_mode == "none"
    assert config.audio_alignment.channel_strategy == "mono_downmix"
    assert config.audio_alignment.refinement_mode == "disabled"
    assert config.audio_alignment.previous_offsets == "disabled"
    assert config.audio_alignment.comparison_streams == {}
    assert config.slowpics.confirm_upload_after_report is False


def test_analysis_requires_at_least_one_requested_frame() -> None:
    with pytest.raises(ValidationError, match="at least one analysis frame selector"):
        AnalysisConfig(random_frame_count=0)


def test_analysis_rejects_total_requested_frame_count_above_cap() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        AnalysisConfig(user_frames=[0], random_frame_count=100)


@pytest.mark.parametrize(
    "payload",
    [
        {"user_frames": [-1]},
        {"random_frame_count": -1},
        {"dark_frame_count": -1},
        {"bright_frame_count": -1},
        {"motion_frame_count": -1},
    ],
)
def test_analysis_frame_selector_counts_reject_negative_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0|non-negative"):
        AnalysisConfig.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"ignore_lead_seconds": -0.1},
        {"ignore_trail_seconds": -0.1},
        {"min_window_seconds": -0.1},
    ],
)
def test_analysis_ignore_window_fields_reject_negative_values(
    payload: dict[str, float],
) -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        AnalysisConfig.model_validate(payload)


def test_color_target_nits_bounds_too_low() -> None:
    """Test target_nits lower bound."""
    with pytest.raises(ValidationError) as exc:
        ColorConfig(target_nits=99)
    assert "Input should be greater than or equal to 100" in str(exc.value)


def test_color_target_nits_bounds_too_high() -> None:
    """Test target_nits upper bound."""
    with pytest.raises(ValidationError) as exc:
        ColorConfig(target_nits=1001)
    assert "Input should be less than or equal to 1000" in str(exc.value)


@pytest.mark.parametrize("stale_key", ["frame_count", "selection_mode"])
def test_analysis_rejects_removed_public_keys(stale_key: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AnalysisConfig.model_validate({stale_key: 10})


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("quality", AnalysisPerformanceMode.QUALITY),
        ("performance", AnalysisPerformanceMode.PERFORMANCE),
    ],
)
def test_analysis_performance_mode_accepts_approved_values(
    mode: str,
    expected: AnalysisPerformanceMode,
) -> None:
    config = AnalysisConfig.model_validate({"performance_mode": mode})

    assert config.performance_mode == expected


@pytest.mark.parametrize("mode", ["turbo"])
def test_analysis_performance_mode_rejects_invalid_value(mode: str) -> None:
    with pytest.raises(ValidationError):
        AnalysisConfig.model_validate({"performance_mode": mode})


def test_report_output_dir_empty_string_to_none() -> None:
    """Test that empty string output_dir is normalized to None."""
    config = ReportConfig(output_dir="")
    assert config.output_dir is None


def test_report_auto_open_default_true() -> None:
    """Report should auto-open by default in interactive CLI runs."""
    config = ReportConfig()
    assert config.auto_open is True


def test_nested_model_defaults() -> None:
    """Test that root config initializes nested models with defaults."""
    config = get_default_config()
    assert config.paths.input_dir == "comparison_videos"
    assert config.analysis.random_seed == 42
    assert config.color.enable_tonemap is True


def test_schema_model_section_defaults_are_representative() -> None:
    """Extracted section models keep the documented runtime defaults."""
    paths = PathsConfig()
    analysis = AnalysisConfig()
    audio = AudioAlignmentConfig()
    screenshots = ScreenshotsConfig()
    color = ColorConfig()
    slowpics = SlowpicsConfig()
    sources = SourcesConfig()
    tmdb = TmdbConfig()
    report = ReportConfig()
    diagnostics = DiagnosticsConfig()
    logging = LoggingConfig()

    assert paths.model_dump() == {
        "input_dir": "comparison_videos",
        "screenshots_dir": "screenshots",
        "generated_dir": "generated",
        "config_dir": "config",
        "use_run_folders": True,
    }
    assert analysis.user_frames == []
    assert analysis.random_frame_count == 10
    assert analysis.dark_frame_count == 0
    assert analysis.bright_frame_count == 0
    assert analysis.motion_frame_count == 0
    assert analysis.performance_mode == AnalysisPerformanceMode.QUALITY
    assert analysis.ignore_lead_seconds == 0.0
    assert analysis.ignore_trail_seconds == 0.0
    assert analysis.min_window_seconds == 5.0
    assert analysis.dark_quantile == 0.05
    assert analysis.bright_quantile == 0.95
    assert audio.sample_rate == 8000
    assert audio.max_offset_seconds == 30.0
    assert audio.force_interactive is False
    assert audio.previous_offsets == "disabled"
    assert audio.correlation_mode == "raw_fft"
    assert audio.preprocessing_mode == "none"
    assert audio.channel_strategy == "mono_downmix"
    assert audio.confidence_threshold == 0.0
    assert audio.ambiguity_peak_ratio == 1.0
    assert audio.window_length_seconds == 0.0
    assert audio.window_stride_seconds == 0.0
    assert audio.minimum_valid_windows == 1
    assert audio.consensus_minimum_ratio == 1.0
    assert audio.refinement_mode == "disabled"
    assert audio.refinement_sample_rate is None
    assert audio.reference_stream is None
    assert audio.comparison_streams == {}
    assert screenshots.overlay_mode == OverlayMode.STANDARD
    assert screenshots.png_compression == 6
    assert screenshots.ffmpeg_timeout_seconds == 30.0
    assert screenshots.geometry_mode == ScreenshotGeometryMode.NATIVE
    assert screenshots.active_rect_detection == ScreenshotActiveRectDetection.ASPECT_RATIO
    assert screenshots.aligned_scale_policy == ScreenshotAlignedScalePolicy.LARGEST_ACTIVE
    assert screenshots.aligned_target_width is None
    assert screenshots.aligned_target_height is None
    assert screenshots.vs_writer == VsScreenshotWriter.AUTO
    assert color.target_nits == 100
    assert color.contrast_recovery == 0.3
    assert color.preset == "reference"
    assert slowpics.confirm_upload_after_report is False
    assert slowpics.visibility == Visibility.PUBLIC
    assert slowpics.max_retries == 3
    assert slowpics.copy_url_to_clipboard is True
    assert slowpics.open_in_browser is True
    assert slowpics.create_url_shortcut is True
    assert slowpics.webhook_url is None
    assert sources.reference is None
    assert sources.analysis_source == "reference"
    assert sources.match_fps == SourceMatchFpsMode.DISABLED
    assert sources.overrides == {}
    assert tmdb.enabled is True
    assert tmdb.api_key is None
    assert tmdb.timeout_seconds == 10.0
    assert tmdb.year_tolerance == 2
    assert tmdb.category_preference is None
    assert report.default_mode == "slider"
    assert report.embed_images is False
    assert diagnostics.model_dump() == {
        "per_frame_nits": False,
    }
    assert logging.level == LogLevel.INFO
    assert logging.format == LogFormat.CONSOLE


@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        (PathsConfig, {}),
        (SourcesConfig, {}),
        (SourceOverrideConfig, {}),
        (SourceActiveRectConfig, {"x": 0, "y": 0, "width": 1, "height": 1}),
        (AnalysisConfig, {}),
        (AudioAlignmentConfig, {}),
        (ScreenshotsConfig, {}),
        (ColorConfig, {}),
        (SlowpicsConfig, {}),
        (TmdbConfig, {}),
        (ReportConfig, {}),
        (DiagnosticsConfig, {}),
        (LoggingConfig, {}),
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else None,
)
def test_owned_nested_config_models_reject_unknown_keys(
    model_type: type[BaseModel],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model_type.model_validate({**payload, "unknown_future_key": True})


def test_root_config_ignores_unknown_keys() -> None:
    config = ConfigSchema.model_validate({"unknown_future_section": {"enabled": True}})

    assert "unknown_future_section" not in config.model_fields_set


@pytest.mark.parametrize(
    ("model_type", "removed_key", "value"),
    [
        (AnalysisConfig, "save_frames_data", True),
        (ScreenshotsConfig, "directory_name", "screenshots"),
        (LoggingConfig, "file", "frame-compare.log"),
    ],
)
def test_removed_inert_config_keys_fail_validation(
    model_type: type[BaseModel],
    removed_key: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model_type.model_validate({removed_key: value})


def test_screenshot_ffmpeg_timeout_keeps_five_second_minimum() -> None:
    assert ScreenshotsConfig(ffmpeg_timeout_seconds=5.0).ffmpeg_timeout_seconds == 5.0

    with pytest.raises(ValidationError, match="greater than or equal to 5"):
        ScreenshotsConfig(ffmpeg_timeout_seconds=4.9)


def test_sources_match_fps_accepts_majority() -> None:
    sources = SourcesConfig.model_validate({"match_fps": "majority"})

    assert sources.match_fps == SourceMatchFpsMode.MAJORITY


def test_sources_match_fps_rejects_invalid_value() -> None:
    with pytest.raises(ValidationError):
        SourcesConfig.model_validate({"match_fps": "nearest"})


def test_slowpics_config_public_surface_is_frozen_to_approved_fields_and_defaults() -> None:
    """slow.pics config remains the documented approved public surface."""
    expected_defaults = {
        "auto_upload": False,
        "confirm_upload_after_report": False,
        "visibility": "public",
        "delete_after_upload": False,
        "timeout_seconds": 60.0,
        "max_retries": 3,
        "title": "",
        "title_template": "",
        "title_suffix": "",
        "is_hentai": False,
        "tmdb_id": None,
        "tmdb_media_type": None,
        "remove_after_days": 0,
        "image_upload_timeout_seconds": 180.0,
        "copy_url_to_clipboard": True,
        "open_in_browser": True,
        "create_url_shortcut": True,
        "webhook_url": None,
    }

    assert list(SlowpicsConfig.model_fields) == list(expected_defaults)
    assert SlowpicsConfig().model_dump(mode="json") == expected_defaults
    assert get_default_config().slowpics.model_dump(mode="json") == expected_defaults


def test_slowpics_webhook_url_trims_values_and_treats_blank_as_disabled() -> None:
    assert SlowpicsConfig(webhook_url="  ").webhook_url is None
    assert (
        SlowpicsConfig(webhook_url="  https://discord.com/api/webhooks/id/token  ").webhook_url
        == "https://discord.com/api/webhooks/id/token"
    )


def test_sources_config_defaults_and_override_schema() -> None:
    config = SourcesConfig(
        reference="00-reference.mkv",
        match_fps="assume_reference",
        overrides={
            "01-encode.mkv": SourceOverrideConfig(
                trim_start_frames=12,
                trim_end_frames=3,
                effective_fps="24000/1001",
                active_rect=SourceActiveRectConfig(x=240, y=0, width=1440, height=1080),
            )
        },
    )

    override = config.overrides["01-encode.mkv"]
    assert config.reference == "00-reference.mkv"
    assert config.match_fps == SourceMatchFpsMode.ASSUME_REFERENCE
    assert override.trim_start_frames == 12
    assert override.trim_end_frames == 3
    assert override.effective_fps == Fraction(24000, 1001)
    assert override.active_rect == SourceActiveRectConfig(
        x=240,
        y=0,
        width=1440,
        height=1080,
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2997/125", Fraction(2997, 125)),
        ("24/1", Fraction(24, 1)),
    ],
)
def test_source_override_accepts_num_den_effective_fps(
    value: str,
    expected: Fraction,
) -> None:
    override = SourceOverrideConfig(effective_fps=value)

    assert override.effective_fps == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"trim_start_frames": -1},
        {"trim_end_frames": -1},
        {"active_rect": {"x": -1, "y": 0, "width": 100, "height": 100}},
        {"active_rect": {"x": 0, "y": 0, "width": 0, "height": 100}},
        {"active_rect": {"x": 0, "y": 0, "width": 100, "height": 0}},
    ],
)
def test_source_override_rejects_negative_trims_and_invalid_active_rect(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        SourceOverrideConfig.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"unknown": True},
        {"match_fps": "resample"},
        {"overrides": {"source.mkv": {"unknown": "value"}}},
        {
            "overrides": {
                "source.mkv": {"active_rect": {"x": 0, "y": 0, "width": 1, "height": 1, "extra": 1}}
            }
        },
    ],
)
def test_sources_config_rejects_unknown_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SourcesConfig.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"effective_fps": "not-a-rational"},
        {"effective_fps": "23.976"},
        {"effective_fps": "24"},
        {"effective_fps": "0"},
        {"effective_fps": "0/1"},
        {"effective_fps": "-24000/1001"},
        {"effective_fps": Fraction(0, 1)},
        {"effective_fps": Fraction(-24, 1)},
        {"effective_fps": 24},
    ],
)
def test_source_override_rejects_malformed_effective_fps(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="num/den|positive"):
        SourceOverrideConfig.model_validate(payload)


def test_sources_config_effective_fps_serializes_num_den_for_toml_round_trip() -> None:
    config = SourcesConfig(
        overrides={
            "source-24.mkv": SourceOverrideConfig(effective_fps=Fraction(24, 1)),
            "source-ntsc.mkv": SourceOverrideConfig(effective_fps=Fraction(24000, 1001)),
        }
    )

    toml_text = tomli_w.dumps({"sources": config.model_dump(mode="json", exclude_none=True)})
    data = tomllib.loads(toml_text)

    assert data["sources"]["overrides"]["source-24.mkv"]["effective_fps"] == "24/1"
    assert data["sources"]["overrides"]["source-ntsc.mkv"]["effective_fps"] == "24000/1001"


def test_schema_model_enums_accept_config_strings_and_reject_unknown_values() -> None:
    screenshots = ScreenshotsConfig.model_validate(
        {
            "geometry_mode": "aligned",
            "active_rect_detection": "dimension",
            "aligned_scale_policy": "smallest_active",
            "overlay_mode": "minimal",
            "vs_writer": "fpng",
        }
    )
    slowpics = SlowpicsConfig.model_validate({"visibility": "public"})
    logging = LoggingConfig.model_validate({"level": "DEBUG", "format": "json"})

    assert screenshots.geometry_mode == ScreenshotGeometryMode.ALIGNED
    assert screenshots.active_rect_detection == ScreenshotActiveRectDetection.DIMENSION
    assert screenshots.aligned_scale_policy == ScreenshotAlignedScalePolicy.SMALLEST_ACTIVE
    assert screenshots.overlay_mode == OverlayMode.MINIMAL
    assert screenshots.vs_writer == VsScreenshotWriter.FPNG
    assert slowpics.visibility == Visibility.PUBLIC
    assert logging.level == LogLevel.DEBUG
    assert logging.format == LogFormat.JSON

    auto_screenshots = ScreenshotsConfig.model_validate({"active_rect_detection": "auto"})
    assert auto_screenshots.active_rect_detection == ScreenshotActiveRectDetection.AUTO

    with pytest.raises(ValidationError):
        ScreenshotsConfig.model_validate({"overlay_mode": "verbose"})

    with pytest.raises(ValidationError):
        ScreenshotsConfig.model_validate({"geometry_mode": "legacy"})

    with pytest.raises(ValidationError):
        ScreenshotsConfig.model_validate({"active_rect_detection": "pixels"})

    with pytest.raises(ValidationError):
        ScreenshotsConfig.model_validate({"aligned_scale_policy": "largest_area"})

    with pytest.raises(ValidationError):
        ScreenshotsConfig.model_validate({"vs_writer": "vapoursynth"})

    with pytest.raises(ValidationError):
        LoggingConfig.model_validate({"level": "debug"})


def test_screenshots_explicit_size_requires_even_target_pair_in_aligned_mode() -> None:
    config = ScreenshotsConfig.model_validate(
        {
            "geometry_mode": "aligned",
            "aligned_scale_policy": "explicit_size",
            "aligned_target_width": 3840,
            "aligned_target_height": 2160,
        }
    )

    assert config.aligned_scale_policy == ScreenshotAlignedScalePolicy.EXPLICIT_SIZE
    assert config.aligned_target_width == 3840
    assert config.aligned_target_height == 2160

    for payload in (
        {
            "geometry_mode": "aligned",
            "aligned_scale_policy": "explicit_size",
            "aligned_target_width": 3840,
        },
        {
            "geometry_mode": "aligned",
            "aligned_scale_policy": "explicit_size",
            "aligned_target_height": 2160,
        },
        {
            "geometry_mode": "aligned",
            "aligned_scale_policy": "largest_active",
            "aligned_target_width": 3840,
            "aligned_target_height": 2160,
        },
        {
            "geometry_mode": "aligned",
            "aligned_scale_policy": "explicit_size",
            "aligned_target_width": 3839,
            "aligned_target_height": 2160,
        },
        {
            "geometry_mode": "aligned",
            "aligned_scale_policy": "explicit_size",
            "aligned_target_width": 0,
            "aligned_target_height": 2160,
        },
    ):
        with pytest.raises(ValidationError):
            ScreenshotsConfig.model_validate(payload)


def test_screenshots_native_mode_accepts_inert_aligned_policy_but_validates_targets() -> None:
    config = ScreenshotsConfig.model_validate(
        {
            "geometry_mode": "native",
            "aligned_scale_policy": "explicit_size",
            "aligned_target_width": 3840,
        }
    )

    assert config.geometry_mode == ScreenshotGeometryMode.NATIVE
    assert config.aligned_scale_policy == ScreenshotAlignedScalePolicy.EXPLICIT_SIZE
    assert config.aligned_target_width == 3840
    assert config.aligned_target_height is None

    with pytest.raises(ValidationError):
        ScreenshotsConfig.model_validate(
            {
                "geometry_mode": "native",
                "aligned_target_width": 3839,
            }
        )


def test_slowpics_confirm_upload_after_report_accepts_explicit_bool() -> None:
    slowpics = SlowpicsConfig.model_validate({"confirm_upload_after_report": True})

    assert slowpics.confirm_upload_after_report is True


def test_audio_alignment_new_config_controls_validate_and_reject_unknown_values() -> None:
    audio = AudioAlignmentConfig.model_validate(
        {
            "correlation_mode": "gcc_phat",
            "preprocessing_mode": "standard",
            "channel_strategy": "best_channel",
            "confidence_threshold": 0.25,
            "ambiguity_peak_ratio": 1.5,
            "window_length_seconds": 10.0,
            "window_stride_seconds": 2.5,
            "minimum_valid_windows": 2,
            "consensus_minimum_ratio": 0.75,
            "refinement_mode": "local",
            "refinement_sample_rate": 16000,
            "reference_stream": 1,
            "previous_offsets": "always",
            "comparison_streams": {"encode": 2},
        }
    )

    assert audio.correlation_mode == "gcc_phat"
    assert audio.preprocessing_mode == "standard"
    assert audio.channel_strategy == "best_channel"
    assert audio.confidence_threshold == 0.25
    assert audio.ambiguity_peak_ratio == 1.5
    assert audio.window_length_seconds == 10.0
    assert audio.window_stride_seconds == 2.5
    assert audio.minimum_valid_windows == 2
    assert audio.consensus_minimum_ratio == 0.75
    assert audio.refinement_mode == "local"
    assert audio.refinement_sample_rate == 16000
    assert audio.reference_stream == 1
    assert audio.previous_offsets == "always"
    assert audio.comparison_streams == {"encode": 2}

    for invalid in (
        {"correlation_mode": "normalized"},
        {"preprocessing_mode": "aggressive"},
        {"channel_strategy": "first_channel"},
        {"confidence_threshold": -0.1},
        {"confidence_threshold": 1.1},
        {"ambiguity_peak_ratio": 0.99},
        {"window_length_seconds": -1.0},
        {"window_stride_seconds": -1.0},
        {"minimum_valid_windows": 0},
        {"consensus_minimum_ratio": -0.1},
        {"consensus_minimum_ratio": 1.1},
        {"refinement_mode": "global"},
        {"refinement_sample_rate": 3999},
        {"refinement_sample_rate": 48001},
        {"reference_stream": -1},
        {"previous_offsets": "reuse"},
        {"comparison_streams": {"encode": -1}},
    ):
        with pytest.raises(ValidationError):
            AudioAlignmentConfig.model_validate(invalid)


@pytest.mark.parametrize("year_tolerance", [0, 5])
def test_tmdb_year_tolerance_accepts_config_bounds(year_tolerance: int) -> None:
    config = TmdbConfig.model_validate({"year_tolerance": year_tolerance})

    assert config.year_tolerance == year_tolerance


@pytest.mark.parametrize(
    ("year_tolerance", "message"),
    [
        (-1, "Input should be greater than or equal to 0"),
        (6, "Input should be less than or equal to 5"),
    ],
)
def test_tmdb_year_tolerance_rejects_out_of_bounds_values(
    year_tolerance: int, message: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        TmdbConfig.model_validate({"year_tolerance": year_tolerance})

    assert message in str(exc.value)


@pytest.mark.parametrize("category_preference", ["movie", "tv", None])
def test_tmdb_category_preference_accepts_supported_values(
    category_preference: str | None,
) -> None:
    config = TmdbConfig.model_validate({"category_preference": category_preference})

    assert config.category_preference == category_preference


def test_tmdb_category_preference_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError):
        TmdbConfig.model_validate({"category_preference": "documentary"})


def test_toml_settings_source_accepts_utf8_bom_directly(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_bytes(
        b'\xef\xbb\xbf[analysis]\nrandom_frame_count = 24\n[logging]\nlevel = "DEBUG"\n'
    )
    source = TomlConfigSettingsSourceNoBOM(get_default_config().__class__)

    data = source._read_file(config_file)

    assert data == {
        "analysis": {"random_frame_count": 24},
        "logging": {"level": "DEBUG"},
    }
