"""Regression coverage for the committed benchmark configuration fixture."""

from pathlib import Path

from frame_compare.config.loader import load_config
from frame_compare.config.schema_enums import ScreenshotActiveRectDetection

BENCHMARK_CONFIG = Path(__file__).resolve().parents[2] / "config" / "benchmark.config.toml"


def test_benchmark_config_is_loader_compatible() -> None:
    config = load_config(BENCHMARK_CONFIG)

    assert config.sources.analysis_source == "reference"
    assert config.sources.match_fps == "disabled"
    assert config.screenshots.active_rect_detection == ScreenshotActiveRectDetection.ASPECT_RATIO
    assert config.analysis.random_frame_count == 20
    assert config.analysis.dark_frame_count == 10
    assert config.analysis.bright_frame_count == 10
    assert config.analysis.motion_frame_count == 10
