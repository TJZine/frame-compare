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
    RuntimeConfig,
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


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"random_frame_count": 0}, "at least one analysis frame selector"),
        ({"user_frames": [0], "random_frame_count": 100}, "less than or equal to 100"),
        ({"user_frames": [-1]}, "greater than or equal to 0|non-negative"),
        ({"random_frame_count": -1}, "greater than or equal to 0|non-negative"),
        ({"dark_frame_count": -1}, "greater than or equal to 0|non-negative"),
        ({"bright_frame_count": -1}, "greater than or equal to 0|non-negative"),
        ({"motion_frame_count": -1}, "greater than or equal to 0|non-negative"),
        ({"ignore_lead_seconds": -0.1}, "greater than or equal to 0"),
        ({"ignore_trail_seconds": -0.1}, "greater than or equal to 0"),
        ({"min_window_seconds": -0.1}, "greater than or equal to 0"),
    ],
)
def test_analysis_rejects_invalid_bounds(payload: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        AnalysisConfig.model_validate(payload)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (99, "Input should be greater than or equal to 100"),
        (1001, "Input should be less than or equal to 1000"),
    ],
)
def test_color_target_nits_rejects_out_of_bounds(value: int, message: str) -> None:
    with pytest.raises(ValidationError) as exc:
        ColorConfig(target_nits=value)
    assert message in str(exc.value)


@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        (AnalysisConfig, {"frame_count": 10}),
        (AnalysisConfig, {"selection_mode": 10}),
        (PathsConfig, {"unknown_future_key": True}),
        (SourcesConfig, {"unknown_future_key": True}),
        (SourceOverrideConfig, {"unknown_future_key": True}),
        (
            SourceActiveRectConfig,
            {**{"x": 0, "y": 0, "width": 1, "height": 1}, "unknown_future_key": True},
        ),
        (AnalysisConfig, {"unknown_future_key": True}),
        (AudioAlignmentConfig, {"unknown_future_key": True}),
        (ScreenshotsConfig, {"unknown_future_key": True}),
        (ColorConfig, {"unknown_future_key": True}),
        (SlowpicsConfig, {"unknown_future_key": True}),
        (TmdbConfig, {"unknown_future_key": True}),
        (ReportConfig, {"unknown_future_key": True}),
        (LoggingConfig, {"unknown_future_key": True}),
        (AnalysisConfig, {"save_frames_data": True}),
        (ScreenshotsConfig, {"directory_name": "screenshots"}),
        (LoggingConfig, {"file": "frame-compare.log"}),
        (PathsConfig, {"screenshots_dir": "screenshots"}),
        (PathsConfig, {"use_run_folders": True}),
        (ReportConfig, {"output_dir": "reports"}),
        (AudioAlignmentConfig, {"sample_rate": 1}),
        (AudioAlignmentConfig, {"correlation_mode": 1}),
        (AudioAlignmentConfig, {"preprocessing_mode": 1}),
        (AudioAlignmentConfig, {"confidence_threshold": 1}),
        (AudioAlignmentConfig, {"ambiguity_peak_ratio": 1}),
        (AudioAlignmentConfig, {"window_length_seconds": 1}),
        (AudioAlignmentConfig, {"window_stride_seconds": 1}),
        (AudioAlignmentConfig, {"minimum_valid_windows": 1}),
        (AudioAlignmentConfig, {"consensus_minimum_ratio": 1}),
        (AudioAlignmentConfig, {"refinement_mode": 1}),
        (AudioAlignmentConfig, {"refinement_sample_rate": 1}),
        (ConfigSchema, {"runtime": {"unknown": 1024}}),
    ],
)
def test_config_models_reject_unknown_and_retired_keys(
    model_type: type[BaseModel], payload: dict[str, object]
) -> None:
    message = None if model_type is ConfigSchema else "Extra inputs are not permitted"
    with pytest.raises(ValidationError, match=message):
        model_type.model_validate(payload)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("quality", AnalysisPerformanceMode.QUALITY),
        ("performance", AnalysisPerformanceMode.PERFORMANCE),
        ("turbo", None),
    ],
)
def test_analysis_performance_mode_validation(
    mode: str, expected: AnalysisPerformanceMode | None
) -> None:
    if expected is None:
        with pytest.raises(ValidationError):
            AnalysisConfig.model_validate({"performance_mode": mode})
    else:
        assert (
            AnalysisConfig.model_validate({"performance_mode": mode}).performance_mode == expected
        )


def test_schema_model_section_defaults_are_representative() -> None:
    """Section models keep the canonical runtime defaults."""
    paths = PathsConfig()
    analysis = AnalysisConfig()
    audio = AudioAlignmentConfig()
    screenshots = ScreenshotsConfig()
    color = ColorConfig()
    sources = SourcesConfig()
    tmdb = TmdbConfig()
    report = ReportConfig()
    logging = LoggingConfig()

    assert paths.model_dump() == {
        "input_dir": "comparison_videos",
        "generated_dir": "generated",
        "config_dir": "config",
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
    assert analysis.random_seed == 42
    assert analysis.dark_quantile == 0.05
    assert analysis.bright_quantile == 0.95
    assert audio.enable is True
    assert audio.max_offset_seconds == 30.0
    assert audio.use_vsview is False
    assert audio.force_interactive is False
    assert audio.cache_results is True
    assert audio.previous_offsets == "disabled"
    assert audio.channel_strategy == "mono_downmix"
    assert audio.reference_stream is None
    assert audio.comparison_streams == {}
    assert screenshots.overlay_mode == OverlayMode.STANDARD
    assert screenshots.png_compression == 6
    assert screenshots.ffmpeg_timeout_seconds == 30.0
    assert screenshots.geometry_mode == ScreenshotGeometryMode.NATIVE
    assert screenshots.active_rect_detection == ScreenshotActiveRectDetection.AUTO
    assert screenshots.aligned_scale_policy == ScreenshotAlignedScalePolicy.LARGEST_ACTIVE
    assert screenshots.aligned_target_width is None
    assert screenshots.aligned_target_height is None
    assert screenshots.vs_writer == VsScreenshotWriter.AUTO
    assert color.target_nits == 100
    assert color.enable_tonemap is True
    assert color.contrast_recovery == 0.3
    assert color.preset == "reference"
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
    assert report.auto_open is True
    assert logging.level == LogLevel.INFO
    assert logging.format == LogFormat.CONSOLE


def test_root_config_ignores_unknown_keys() -> None:
    config = ConfigSchema.model_validate({"unknown_future_section": {"enabled": True}})

    assert "unknown_future_section" not in config.model_fields_set


def test_root_config_ignores_removed_diagnostics_section() -> None:
    config = ConfigSchema.model_validate({"diagnostics": {"per_frame_nits": True}})

    assert "diagnostics" not in config.model_fields_set
    assert not hasattr(config, "diagnostics")


def test_screenshot_ffmpeg_timeout_keeps_five_second_minimum() -> None:
    assert ScreenshotsConfig(ffmpeg_timeout_seconds=5.0).ffmpeg_timeout_seconds == 5.0

    with pytest.raises(ValidationError, match="greater than or equal to 5"):
        ScreenshotsConfig(ffmpeg_timeout_seconds=4.9)


@pytest.mark.parametrize("mode", ["majority", "nearest"])
def test_sources_match_fps_validation(mode: str) -> None:
    if mode == "nearest":
        with pytest.raises(ValidationError):
            SourcesConfig.model_validate({"match_fps": mode})
    else:
        assert (
            SourcesConfig.model_validate({"match_fps": mode}).match_fps
            == SourceMatchFpsMode.MAJORITY
        )


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
    ("payload", "message"),
    [
        ({"trim_start_frames": -1}, None),
        ({"trim_end_frames": -1}, None),
        ({"active_rect": {"x": -1, "y": 0, "width": 100, "height": 100}}, None),
        ({"active_rect": {"x": 0, "y": 0, "width": 0, "height": 100}}, None),
        ({"active_rect": {"x": 0, "y": 0, "width": 100, "height": 0}}, None),
        ({"effective_fps": "not-a-rational"}, "num/den|positive"),
        ({"effective_fps": "23.976"}, "num/den|positive"),
        ({"effective_fps": "24"}, "num/den|positive"),
        ({"effective_fps": "0"}, "num/den|positive"),
        ({"effective_fps": "0/1"}, "num/den|positive"),
        ({"effective_fps": "-24000/1001"}, "num/den|positive"),
        ({"effective_fps": Fraction(0, 1)}, "num/den|positive"),
        ({"effective_fps": Fraction(-24, 1)}, "num/den|positive"),
        ({"effective_fps": 24}, "num/den|positive"),
    ],
)
def test_source_override_rejects_invalid_payloads(
    payload: dict[str, object], message: str | None
) -> None:
    with pytest.raises(ValidationError, match=message):
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


@pytest.mark.parametrize(
    ("valid", "expected", "invalid"),
    [
        (
            {
                "geometry_mode": "aligned",
                "aligned_scale_policy": "explicit_size",
                "aligned_target_width": 3840,
                "aligned_target_height": 2160,
            },
            {
                "aligned_scale_policy": ScreenshotAlignedScalePolicy.EXPLICIT_SIZE,
                "aligned_target_width": 3840,
                "aligned_target_height": 2160,
            },
            (
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
            ),
        ),
        (
            {
                "geometry_mode": "native",
                "aligned_scale_policy": "explicit_size",
                "aligned_target_width": 3840,
            },
            {
                "geometry_mode": ScreenshotGeometryMode.NATIVE,
                "aligned_scale_policy": ScreenshotAlignedScalePolicy.EXPLICIT_SIZE,
                "aligned_target_width": 3840,
                "aligned_target_height": None,
            },
            (
                {
                    "geometry_mode": "native",
                    "aligned_target_width": 3839,
                },
            ),
        ),
    ],
)
def test_screenshot_geometry_validates_target_pairs(
    valid: dict[str, object], expected: dict[str, object], invalid: tuple[dict[str, object], ...]
) -> None:
    config = ScreenshotsConfig.model_validate(valid)
    for field, value in expected.items():
        if value is None:
            assert getattr(config, field) is None
        else:
            assert getattr(config, field) == value
    for payload in invalid:
        with pytest.raises(ValidationError):
            ScreenshotsConfig.model_validate(payload)


def test_slowpics_confirm_upload_after_report_accepts_explicit_bool() -> None:
    slowpics = SlowpicsConfig.model_validate({"confirm_upload_after_report": True})

    assert slowpics.confirm_upload_after_report is True


def test_audio_alignment_new_config_controls_validate_and_reject_unknown_values() -> None:
    audio = AudioAlignmentConfig.model_validate(
        {
            "enable": False,
            "max_offset_seconds": 10.0,
            "use_vsview": True,
            "force_interactive": True,
            "cache_results": False,
            "previous_offsets": "always",
            "channel_strategy": "best_channel",
            "reference_stream": 1,
            "comparison_streams": {"encode": 2},
        }
    )

    assert audio.enable is False
    assert audio.max_offset_seconds == 10.0
    assert audio.use_vsview is True
    assert audio.force_interactive is True
    assert audio.cache_results is False
    assert audio.previous_offsets == "always"
    assert audio.channel_strategy == "best_channel"
    assert audio.reference_stream == 1
    assert audio.comparison_streams == {"encode": 2}

    for invalid in (
        {"channel_strategy": "first_channel"},
        {"max_offset_seconds": float("inf")},
        {"max_offset_seconds": 0.5},
        {"reference_stream": -1},
        {"previous_offsets": "reuse"},
        {"comparison_streams": {"encode": -1}},
    ):
        with pytest.raises(ValidationError):
            AudioAlignmentConfig.model_validate(invalid)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (0, None),
        (5, None),
        (-1, "Input should be greater than or equal to 0"),
        (6, "Input should be less than or equal to 5"),
    ],
)
def test_tmdb_year_tolerance_bounds(value: int, message: str | None) -> None:
    if message is None:
        assert TmdbConfig.model_validate({"year_tolerance": value}).year_tolerance == value
    else:
        with pytest.raises(ValidationError) as exc:
            TmdbConfig.model_validate({"year_tolerance": value})
        assert message in str(exc.value)


@pytest.mark.parametrize("category", ["movie", "tv", None, "documentary"])
def test_tmdb_category_preference_validation(category: str | None) -> None:
    if category == "documentary":
        with pytest.raises(ValidationError):
            TmdbConfig.model_validate({"category_preference": category})
    else:
        assert (
            TmdbConfig.model_validate({"category_preference": category}).category_preference
            == category
        )


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


def test_runtime_memory_limit_defaults_and_integer_boundaries() -> None:
    assert get_default_config().runtime.memory_limit_mb is None
    for value in (None, 512, 1024, 4096):
        assert RuntimeConfig(memory_limit_mb=value).memory_limit_mb == value


@pytest.mark.parametrize("value", [511, 0, -1, 512.0, 512.5, "512", True, False])
def test_runtime_memory_limit_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValidationError):
        RuntimeConfig.model_validate({"memory_limit_mb": value})
