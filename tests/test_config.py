from pathlib import Path

import pytest

from src.config_loader import ConfigError, load_config
from src.datatypes import OddGeometryPolicy, RGBDither
from src.frame_compare.config_template import copy_default_config


def _copy_default_config(tmp_path: Path) -> Path:
    cfg_dst = tmp_path / "config.toml.template"
    return copy_default_config(cfg_dst)


def test_load_defaults(tmp_path: Path) -> None:
    cfg_path = _copy_default_config(tmp_path)
    app = load_config(str(cfg_path))
    assert app.analysis.frame_count_dark == 20
    assert app.analysis.downscale_height == 720
    assert app.screenshots.directory_name == "screens"
    assert app.screenshots.ffmpeg_timeout_seconds == 120.0
    assert app.screenshots.odd_geometry_policy is OddGeometryPolicy.AUTO
    assert app.screenshots.rgb_dither is RGBDither.ERROR_DIFFUSION
    assert app.naming.always_full_filename is True
    assert app.runtime.ram_limit_mb == 4000
    assert isinstance(app.runtime.vapoursynth_python_paths, list)
    assert app.analysis.ignore_lead_seconds == 0.0
    assert app.analysis.ignore_trail_seconds == 0.0
    assert app.analysis.min_window_seconds == 5.0
    assert app.color.enable_tonemap is True
    assert app.color.preset == "reference"
    assert app.color.target_nits == 100.0
    assert app.color.dst_min_nits == 0.18
    assert app.color.knee_offset == 0.5
    assert app.color.dpd_preset == "high_quality"
    assert app.color.dpd_black_cutoff == 0.01
    assert app.color.overlay_enabled is True
    assert app.color.verify_enabled is True
    assert app.color.post_gamma_enable is False
    assert app.color.post_gamma == pytest.approx(0.95)
    assert app.color.smoothing_period == pytest.approx(45.0)
    assert app.color.scene_threshold_low == pytest.approx(0.8)
    assert app.color.scene_threshold_high == pytest.approx(2.4)
    assert app.color.percentile == pytest.approx(99.995)
    assert app.color.contrast_recovery == pytest.approx(0.3)
    assert app.color.metadata == "auto"
    assert app.color.use_dovi is None
    assert app.color.visualize_lut is False
    assert app.color.show_clipping is False
    assert app.source.preferred == "lsmas"
    assert app.tmdb.api_key == ""
    assert app.tmdb.unattended is True
    assert app.tmdb.confirm_matches is False
    assert app.tmdb.year_tolerance == 2
    assert app.tmdb.enable_anime_parsing is True
    assert app.tmdb.cache_ttl_seconds == 86400
    assert app.tmdb.category_preference is None
    assert app.cli.emit_json_tail is True
    assert app.cli.progress.style == "fill"


@pytest.mark.parametrize(
    ("toml_snippet", "message"),
    [
        ("[analysis]\nstep = 0\n", "analysis.step"),
        ("[screenshots]\ncompression_level = 5\n", "screenshots.compression_level"),
        ("[analysis]\nignore_lead_seconds = -1\n", "analysis.ignore_lead_seconds"),
        ("[analysis]\nignore_trail_seconds = -2\n", "analysis.ignore_trail_seconds"),
        ("[analysis]\nmin_window_seconds = -0.5\n", "analysis.min_window_seconds"),
        ("[color]\nverify_luma_threshold = 1.5\n", "color.verify_luma_threshold"),
        ("[color]\nverify_step_seconds = 0\n", "color.verify_step_seconds"),
        ("[color]\ntarget_nits = -10\n", "color.target_nits"),
        ("[color]\ndst_min_nits = -0.1\n", "color.dst_min_nits"),
        ("[color]\nknee_offset = 1.5\n", "color.knee_offset"),
        ("[color]\ndpd_preset = \"invalid\"\n", "color.dpd_preset"),
        ("[color]\ndpd_black_cutoff = 0.5\n", "color.dpd_black_cutoff"),
        ("[color]\npost_gamma = 0.5\n", "color.post_gamma"),
        ("[color]\nsmoothing_period = -1\n", "color.smoothing_period"),
        ("[color]\nscene_threshold_low = -0.5\n", "color.scene_threshold_low"),
        ("[color]\npercentile = 120\n", "color.percentile"),
        ("[color]\ncontrast_recovery = -0.1\n", "color.contrast_recovery"),
        ("[color]\nmetadata = \"invalid\"\n", "color.metadata"),
        ("[screenshots]\nodd_geometry_policy = \"bogus\"\n", "screenshots.odd_geometry_policy"),
        ("[screenshots]\nrgb_dither = \"invalid\"\n", "screenshots.rgb_dither"),
        ("[source]\npreferred = \"bogus\"\n", "source.preferred"),
        ("[tmdb]\nyear_tolerance = -1\n", "tmdb.year_tolerance"),
        ("[tmdb]\ncache_ttl_seconds = -5\n", "tmdb.cache_ttl_seconds"),
        ("[tmdb]\ncategory_preference = \"documentary\"\n", "tmdb.category_preference"),
        ("[cli.progress]\nstyle = \"blink\"\n", "cli.progress.style"),
    ],
)
def test_validation_errors(tmp_path: Path, toml_snippet: str, message: str) -> None:
    cfg_path = tmp_path / "config.toml.template"
    cfg_path.write_text(toml_snippet, encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        load_config(str(cfg_path))
    assert message in str(exc_info.value)


def test_ffmpeg_timeout_zero_is_allowed(tmp_path: Path) -> None:
    cfg_path = _copy_default_config(tmp_path)
    original = cfg_path.read_text(encoding="utf-8")
    cfg_path.write_text(
        original.replace("ffmpeg_timeout_seconds = 120.0", "ffmpeg_timeout_seconds = 0.0", 1),
        encoding="utf-8",
    )

    app = load_config(str(cfg_path))
    assert app.screenshots.ffmpeg_timeout_seconds == 0.0


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
ffmpeg_timeout_seconds = 45.5
odd_geometry_policy = "force_full_chroma"
rgb_dither = "ordered"

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

[cli]
emit_json_tail = false

[cli.progress]
style = "DOT"

[paths]
input_dir = "D:/comparisons"

[color]
target_nits = 120.0
tone_curve = "mobius"
verify_enabled = false
overlay_enabled = false

[source]
preferred = "ffms2"
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
    assert app.screenshots.ffmpeg_timeout_seconds == 45.5
    assert (
        app.screenshots.odd_geometry_policy is OddGeometryPolicy.FORCE_FULL_CHROMA
    )
    assert app.screenshots.rgb_dither is RGBDither.ORDERED
    assert app.slowpics.auto_upload is True
    assert app.slowpics.remove_after_days == 14
    assert app.naming.always_full_filename is False
    assert app.paths.input_dir == "D:/comparisons"
    assert app.color.target_nits == 120.0
    assert app.color.tone_curve == "mobius"
    assert app.color.verify_enabled is False
    assert app.color.overlay_enabled is False
    assert app.source.preferred == "ffms2"
    assert app.tmdb.unattended is False
    assert app.tmdb.year_tolerance == 1
    assert app.tmdb.cache_ttl_seconds == 120
    assert app.tmdb.category_preference == "TV"
    assert app.cli.emit_json_tail is False
    assert app.cli.progress.style == "dot"


def test_dynamic_peak_detection_override_disables_dpd_fields(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.toml.template"
    cfg_path.write_text(
        """
[color]
dynamic_peak_detection = false
dpd_preset = "high_quality"
dpd_black_cutoff = 0.02
        """.strip(),
        encoding="utf-8",
    )
    app = load_config(str(cfg_path))
    assert app.color.dynamic_peak_detection is False
    assert app.color.dpd_preset == "off"
    assert app.color.dpd_black_cutoff == 0.0
