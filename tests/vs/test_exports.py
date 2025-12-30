"""Tests for VapourSynth module exports."""

import importlib.util
import sys
from unittest.mock import MagicMock

# Mock vapoursynth if not installed, to allow import of frame_compare.vs
if importlib.util.find_spec("vapoursynth") is None:
    mock_vs = MagicMock()
    # Mock RGBS constant used at runtime in tonemap.py
    mock_vs.RGBS = 0
    sys.modules["vapoursynth"] = mock_vs

import frame_compare.vs  # noqa: E402

EXPECTED_EXPORTS = {
    "VSLoader",
    "DefaultVSLoader",
    "SourceInfo",
    "HDRMetadata",
    "TonemapSettings",
    "ColorProps",
    "is_vapoursynth_available",
    "ensure_vs_environment",
    "detect_plugins",
    "require_plugin",
    "load_source",
    "apply_trim",
    "get_color_props",
    "is_hdr",
    "infer_color_props",
    "apply_color_props",
    "expand_limited_rgb_to_full",
    "to_rgb24",
    "tonemap",
    "apply_tonemap",
    "get_preset_settings",
}


def test_public_api_symbols_are_exported():
    """Check that all expected symbols are present in vs module."""
    for name in EXPECTED_EXPORTS:
        assert hasattr(frame_compare.vs, name)


def test_all_property_is_complete():
    """Ensure __all__ contains exactly the expected set, sorted."""
    assert sorted(frame_compare.vs.__all__) == sorted(EXPECTED_EXPORTS)
