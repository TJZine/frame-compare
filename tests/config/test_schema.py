"""Tests for configuration schema validation."""

import pytest
from pydantic import ValidationError

from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import (
    AnalysisConfig,
    ColorConfig,
    ConfigSchema,
    DoviConfig,
    ReportConfig,
    SelectionMode,
)


def test_default_config_values() -> None:
    """Test that default config has expected values."""
    config = get_default_config()
    assert config.analysis.frame_count == 10
    assert config.analysis.selection_mode == SelectionMode.MIXED
    assert config.color.target_nits == 203
    assert config.paths.input_dir == "comparison_videos"


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
    config = ConfigSchema()
    assert config.paths.input_dir == "comparison_videos"
    assert config.analysis.random_seed == 42
    assert config.color.enable_tonemap is True
