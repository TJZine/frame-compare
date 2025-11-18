from typing import Any, Dict

from src.config_loader import _sanitize_section
from src.datatypes import ColorConfig


def test_sanitize_section_drops_color_defaults() -> None:
    raw_color: Dict[str, Any] = {
        "enable_tonemap": True,
        "preset": "filmic",
        "tone_curve": "bt.2390",
        "dynamic_peak_detection": True,
        "target_nits": 100.0,
        "dst_min_nits": 0.18,
        "knee_offset": 0.50,
        "dpd_preset": "high_quality",
        "dpd_black_cutoff": 0.01,
        "smoothing_period": 45.0,
        "scene_threshold_low": 0.8,
        "scene_threshold_high": 2.4,
        "percentile": 99.995,
        "contrast_recovery": 0.3,
        "metadata": "auto",
        "use_dovi": "auto",
        "visualize_lut": False,
        "show_clipping": False,
        "post_gamma_enable": False,
        "post_gamma": 0.95,
        "overlay_enabled": True,
        "overlay_text_template": (
            "Tonemapping Algorithm: {tone_curve} dpd = {dynamic_peak_detection} dst = {target_nits} nits"
        ),
        "overlay_mode": "minimal",
        "verify_enabled": True,
        "verify_auto": True,
        "verify_start_seconds": 10.0,
        "verify_step_seconds": 10.0,
        "verify_max_seconds": 90.0,
        "verify_luma_threshold": 0.10,
        "strict": False,
        "debug_color": False,
    }

    color_cfg = _sanitize_section(raw_color, "color", ColorConfig)

    assert isinstance(color_cfg, ColorConfig)
    provided = getattr(color_cfg, "_provided_keys", set())
    assert {"preset", "post_gamma", "use_dovi"}.issubset(provided)
    assert color_cfg.preset == "filmic"
    assert "tone_curve" not in provided
    assert "target_nits" not in provided
    assert "knee_offset" not in provided
