from pathlib import Path

import pytest

import pytest
from pathlib import Path

from src.config_loader import ConfigError, load_config


def _copy_default_config(tmp_path: Path) -> Path:
    cfg_src = Path(__file__).resolve().parents[1] / "config.toml.template"
    cfg_dst = tmp_path / "config.toml.template"
    cfg_dst.write_text(cfg_src.read_text(encoding="utf-8"), encoding="utf-8")
    return cfg_dst


def test_load_defaults(tmp_path: Path) -> None:
    cfg_path = _copy_default_config(tmp_path)
    app = load_config(str(cfg_path))
    assert app.analysis.frame_count_dark == 20
    assert app.analysis.downscale_height == 720
    assert app.screenshots.directory_name == "screens"
    assert app.naming.always_full_filename is True
    assert app.runtime.ram_limit_mb == 4000
    assert isinstance(app.runtime.vapoursynth_python_paths, list)
    assert app.analysis.ignore_lead_seconds == 0.0
    assert app.analysis.ignore_trail_seconds == 0.0
    assert app.analysis.min_window_seconds == 5.0
    assert app.tmdb.api_key == ""
    assert app.tmdb.unattended is True
    assert app.tmdb.year_tolerance == 2
    assert app.tmdb.enable_anime_parsing is True
    assert app.tmdb.cache_ttl_seconds == 86400
    assert app.tmdb.category_preference is None
    assert app.tonemap.tone_mapping == "bt2390"
    assert app.tonemap.target_nits == 100.0
    assert app.tonemap.dest_primaries == "bt709"
    assert app.tonemap.dest_transfer == "bt1886"
    assert app.tonemap.dest_matrix == "bt709"
    assert app.tonemap.dest_range == "limited"


@pytest.mark.parametrize(
    ("toml_snippet", "message"),
    [
        ("[analysis]\nstep = 0\n", "analysis.step"),
        ("[screenshots]\ncompression_level = 5\n", "screenshots.compression_level"),
        ("[analysis]\nignore_lead_seconds = -1\n", "analysis.ignore_lead_seconds"),
        ("[analysis]\nignore_trail_seconds = -2\n", "analysis.ignore_trail_seconds"),
        ("[analysis]\nmin_window_seconds = -0.5\n", "analysis.min_window_seconds"),
        ("[tmdb]\nyear_tolerance = -1\n", "tmdb.year_tolerance"),
        ("[tmdb]\ncache_ttl_seconds = -5\n", "tmdb.cache_ttl_seconds"),
        ("[tmdb]\ncategory_preference = \"documentary\"\n", "tmdb.category_preference"),
        ("[tonemap]\ntarget_nits = 0\n", "tonemap.target_nits"),
    ],
)
def test_validation_errors(tmp_path: Path, toml_snippet: str, message: str) -> None:
    cfg_path = tmp_path / "config.toml.template"
    cfg_path.write_text(toml_snippet, encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_config(str(cfg_path))
    assert message in str(exc_info.value)


def test_override_values(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.toml.template"
    cfg_path.write_text(
        """
[analysis]
frame_count_dark = 12
step = 3
ignore_lead_seconds = 4.5
ignore_trail_seconds = 1.25
min_window_seconds = 2.5

[screenshots]
compression_level = 2

[tonemap]
tone_mapping = "mobius"
target_nits = 140.5
dest_primaries = "dci-p3"
dest_transfer = "srgb"
dest_matrix = "dci-p3"
dest_range = "full"

[slowpics]
auto_upload = "1"
remove_after_days = 14

[naming]
always_full_filename = false

[tmdb]
unattended = false
year_tolerance = 1
cache_ttl_seconds = 120
category_preference = "tv"

[paths]
input_dir = "D:/comparisons"
        """.strip(),
        encoding="utf-8",
    )
    app = load_config(str(cfg_path))
    assert app.analysis.frame_count_dark == 12
    assert app.analysis.step == 3
    assert app.analysis.ignore_lead_seconds == 4.5
    assert app.analysis.ignore_trail_seconds == 1.25
    assert app.analysis.min_window_seconds == 2.5
    assert app.screenshots.compression_level == 2
    assert app.slowpics.auto_upload is True
    assert app.slowpics.remove_after_days == 14
    assert app.naming.always_full_filename is False
    assert app.paths.input_dir == "D:/comparisons"
    assert app.tmdb.unattended is False
    assert app.tmdb.year_tolerance == 1
    assert app.tmdb.cache_ttl_seconds == 120
    assert app.tmdb.category_preference == "TV"
    assert app.tonemap.tone_mapping == "mobius"
    assert app.tonemap.target_nits == 140.5
    assert app.tonemap.dest_primaries == "dci-p3"
    assert app.tonemap.dest_transfer == "srgb"
    assert app.tonemap.dest_matrix == "dci-p3"
    assert app.tonemap.dest_range == "full"
