"""Tests for configuration schema validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import (
    AnalysisConfig,
    ColorConfig,
    DoviConfig,
    ReportConfig,
    SelectionMode,
)
from frame_compare.config.schema_enums import LogFormat, LogLevel, OverlayMode, Visibility
from frame_compare.config.schema_models import (
    AudioAlignmentConfig,
    DiagnosticsConfig,
    LoggingConfig,
    PathsConfig,
    ScreenshotsConfig,
    SlowpicsConfig,
    TmdbConfig,
)
from frame_compare.config.schema_sources import TomlConfigSettingsSourceNoBOM


def test_default_config_values() -> None:
    """Test that default config has expected values."""
    config = get_default_config()
    assert config.analysis.frame_count == 10
    assert config.analysis.selection_mode == SelectionMode.MIXED
    assert config.color.target_nits == 100
    assert config.paths.input_dir == "comparison_videos"
    assert config.tmdb.year_tolerance == 2
    assert config.tmdb.category_preference is None


def test_analysis_frame_count_bounds_too_low() -> None:
    """Test frame_count lower bound."""
    with pytest.raises(ValidationError) as exc:
        AnalysisConfig(frame_count=0)
    assert "Input should be greater than or equal to 1" in str(exc.value)


def test_analysis_frame_count_bounds_too_high() -> None:
    """Test frame_count upper bound."""
    with pytest.raises(ValidationError) as exc:
        AnalysisConfig(frame_count=101)
    assert "Input should be less than or equal to 100" in str(exc.value)


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


def test_enum_lowercase_only_accepted() -> None:
    """Test that enums accept lowercase values only."""
    # Valid
    config = AnalysisConfig(selection_mode=SelectionMode.MIXED)
    assert config.selection_mode == "mixed"

    # Invalid uppercase (Pydantic enums are strict by default or follow enum rules)
    # Since our Enum inherits from str and Enum, "MIXED" is not "mixed".
    with pytest.raises(ValidationError):
        AnalysisConfig(selection_mode="MIXED")  # type: ignore


def test_optional_path_accepts_none() -> None:
    """Test that optional path fields accept None."""
    config = DoviConfig(dovi_tool_path=None)
    assert config.dovi_tool_path is None


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
    tmdb = TmdbConfig()
    report = ReportConfig()
    dovi = DoviConfig()
    diagnostics = DiagnosticsConfig()
    logging = LoggingConfig()

    assert paths.model_dump() == {
        "input_dir": "comparison_videos",
        "screenshots_dir": "screenshots",
        "generated_dir": "generated",
        "config_dir": "config",
        "use_run_folders": True,
    }
    assert analysis.frame_count == 10
    assert analysis.selection_mode == SelectionMode.MIXED
    assert analysis.dark_quantile == 0.05
    assert analysis.bright_quantile == 0.95
    assert audio.sample_rate == 8000
    assert audio.max_offset_seconds == 30.0
    assert audio.force_interactive is False
    assert screenshots.overlay_mode == OverlayMode.STANDARD
    assert screenshots.png_compression == 6
    assert screenshots.ffmpeg_timeout_seconds == 30.0
    assert color.target_nits == 100
    assert color.contrast_recovery == 0.3
    assert color.preset == "reference"
    assert slowpics.visibility == Visibility.UNLISTED
    assert slowpics.max_retries == 3
    assert tmdb.enabled is True
    assert tmdb.api_key is None
    assert tmdb.timeout_seconds == 10.0
    assert tmdb.year_tolerance == 2
    assert tmdb.category_preference is None
    assert report.default_mode == "slider"
    assert report.embed_images is False
    assert dovi.dovi_tool_path is None
    assert dovi.cache_results is True
    assert diagnostics.model_dump() == {
        "per_frame_nits": False,
        "show_hdr_info": False,
        "frame_timing": False,
    }
    assert logging.level == LogLevel.INFO
    assert logging.format == LogFormat.CONSOLE
    assert logging.file is None


def test_schema_model_enums_accept_config_strings_and_reject_unknown_values() -> None:
    screenshots = ScreenshotsConfig.model_validate({"overlay_mode": "minimal"})
    slowpics = SlowpicsConfig.model_validate({"visibility": "public"})
    logging = LoggingConfig.model_validate({"level": "DEBUG", "format": "json"})

    assert screenshots.overlay_mode == OverlayMode.MINIMAL
    assert slowpics.visibility == Visibility.PUBLIC
    assert logging.level == LogLevel.DEBUG
    assert logging.format == LogFormat.JSON

    with pytest.raises(ValidationError):
        ScreenshotsConfig.model_validate({"overlay_mode": "verbose"})

    with pytest.raises(ValidationError):
        LoggingConfig.model_validate({"level": "debug"})


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
        b'\xef\xbb\xbf[analysis]\nframe_count = 24\n[logging]\nlevel = "DEBUG"\n'
    )
    source = TomlConfigSettingsSourceNoBOM(get_default_config().__class__)

    data = source._read_file(config_file)

    assert data == {
        "analysis": {"frame_count": 24},
        "logging": {"level": "DEBUG"},
    }
