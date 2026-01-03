"""Tests for tonemapping module."""

import importlib.util
import sys
from unittest.mock import MagicMock, patch

import pytest


# Mock vapoursynth only when it is not installed, to allow safe import.
def _vs_spec_available() -> bool:
    try:
        return importlib.util.find_spec("vapoursynth") is not None
    except ValueError:
        return False


if not _vs_spec_available() and "vapoursynth" not in sys.modules:
    mock_vs = MagicMock()
    mock_vs.VideoNode = MagicMock
    mock_vs.Core = MagicMock
    mock_vs.RGBS = 0
    sys.modules["vapoursynth"] = mock_vs
    mock_vs.VideoNode = MagicMock
    mock_vs.Core = MagicMock
    mock_vs.RGBS = 0
    sys.modules["vapoursynth"] = mock_vs

# Now import module under test
import vapoursynth as vs  # noqa: E402, I001
from frame_compare.errors import TonemapError  # noqa: E402, I001
from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings  # noqa: E402, I001
from frame_compare.vs.types import TonemapSettings  # noqa: E402, I001


def test_get_preset_settings_returns_valid_settings():
    """Verify default preset settings."""
    result = get_preset_settings("reference")
    assert isinstance(result, TonemapSettings)
    assert result.preset == "reference"
    assert result.tone_curve == "bt2390"
    assert result.target_nits == 203


@pytest.mark.parametrize(
    "preset_name",
    [
        "reference",
        "filmic",
        "contrast",
        "bt2390_spec",
        "spline",
        "bright_lift",
        "highlight_guard",
    ],
)
def test_get_preset_settings_all_presets_exist(preset_name):
    """Verify all defined presets can be retrieved."""
    result = get_preset_settings(preset_name)
    assert result.enabled is True


def test_get_preset_settings_unknown_raises_tonemap_error():
    """Verify unknown preset raises correct error."""
    with pytest.raises(TonemapError) as exc:
        get_preset_settings("invalid")
    assert exc.value.context.code == "FC-4003"
    assert "reference, filmic" in exc.value.context.hint


def test_apply_tonemap_enabled_false_returns_clip_unchanged():
    """Verify enabled=False is a no-op."""
    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=False)

    result = apply_tonemap(mock_clip, settings)

    assert result is mock_clip


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._apply_libplacebo")
@patch("frame_compare.vs.tonemap._fallback_tonemap")
def test_apply_tonemap_uses_libplacebo_when_available(mock_fallback, mock_libplacebo, mock_detect):
    """Verify libplacebo path is chosen when plugin is available."""
    mock_detect.return_value = {"libplacebo": True}
    mock_clip = MagicMock()
    # Ensure vs.core is used
    with patch("vapoursynth.core", MagicMock()) as mock_core:
        settings = TonemapSettings(enabled=True)

        apply_tonemap(mock_clip, settings)

        mock_libplacebo.assert_called_once_with(mock_clip, settings, mock_core, None)
        mock_fallback.assert_not_called()


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._apply_libplacebo")
@patch("frame_compare.vs.tonemap._fallback_tonemap")
def test_apply_tonemap_uses_fallback_when_libplacebo_missing(
    mock_fallback, mock_libplacebo, mock_detect
):
    """Verify fallback path is chosen when plugin is missing."""
    mock_detect.return_value = {"libplacebo": False}
    mock_clip = MagicMock()

    settings = TonemapSettings(enabled=True)

    apply_tonemap(mock_clip, settings)

    mock_fallback.assert_called_once_with(mock_clip, settings, None)
    mock_libplacebo.assert_not_called()


@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._apply_libplacebo")
@patch("frame_compare.vs.tonemap._fallback_tonemap")
def test_apply_tonemap_falls_back_on_libplacebo_runtime_failure(
    mock_fallback, mock_libplacebo, mock_detect
):
    """Verify runtime failure in libplacebo triggers fallback."""
    mock_detect.return_value = {"libplacebo": True}
    mock_libplacebo.return_value = None  # Signals runtime failure
    mock_fallback.return_value = MagicMock()

    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True)

    result = apply_tonemap(mock_clip, settings)

    mock_libplacebo.assert_called_once()
    mock_fallback.assert_called_once()
    assert result is mock_fallback.return_value


@patch("frame_compare.vs.tonemap.detect_plugins")
def test_apply_tonemap_unsupported_tone_curve_raises_error(mock_detect):
    """Verify unsupported tone curve raises error in libplacebo path."""
    mock_detect.return_value = {"libplacebo": True}
    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True, tone_curve="invalid")

    with pytest.raises(TonemapError) as exc:
        apply_tonemap(mock_clip, settings)

    assert exc.value.context.code == "FC-4003"
    assert "bt2390, spline, reinhard" in exc.value.context.hint


@pytest.mark.parametrize(
    "preset, expected_curve, expected_nits, expected_gamma",
    [
        ("reference", "bt2390", 203, False),
        ("filmic", "spline", 203, False),
        ("contrast", "reinhard", 203, False),
        ("bt2390_spec", "bt2390", 100, False),
        ("spline", "spline", 203, False),
        ("bright_lift", "bt2390", 250, True),
        ("highlight_guard", "spline", 180, False),
    ],
)
def test_tonemap_presets_have_correct_values(preset, expected_curve, expected_nits, expected_gamma):
    """Verify all presets match SSOT values."""
    settings = get_preset_settings(preset)
    assert settings.tone_curve == expected_curve
    assert settings.target_nits == expected_nits
    assert settings.gamma_lift == expected_gamma


def test_to_rgbs_no_op_when_already_rgbs_real():
    """Verify _to_rgbs is no-op if format is already RGBS (real function)."""
    from frame_compare.vs.tonemap import _to_rgbs

    mock_clip = MagicMock()
    mock_clip.format.id = vs.RGBS

    result = _to_rgbs(mock_clip)

    assert result is mock_clip
    mock_clip.resize.Bicubic.assert_not_called()


def test_to_rgbs_converts_non_rgbs():
    """Verify _to_rgbs converts to RGBS when needed."""
    from frame_compare.vs.tonemap import _to_rgbs

    mock_clip = MagicMock()
    # Something different from mock_vs.RGBS (which is 0)
    mock_clip.format.id = 1

    # Setup resize return
    mock_resized = MagicMock()
    mock_clip.resize.Bicubic.return_value = mock_resized

    result = _to_rgbs(mock_clip)

    assert result is mock_resized
    mock_clip.resize.Bicubic.assert_called_once_with(format=vs.RGBS, matrix_in_s="709")


@patch("frame_compare.vs.tonemap._detect_hdr")
@patch("frame_compare.vs.tonemap.detect_plugins")
def test_apply_tonemap_detects_metadata_when_missing_libplacebo(mock_detect, mock_detect_hdr):
    """Verify metadata extraction is attempted in libplacebo path if missing."""
    mock_detect.return_value = {"libplacebo": True}

    mock_clip = MagicMock()
    mock_clip.format.id = vs.RGBS

    # Mock _detect_hdr return
    mock_metadata = MagicMock()
    mock_metadata.max_cll = 1234
    mock_detect_hdr.return_value = (True, mock_metadata)

    settings = TonemapSettings(enabled=True, tone_curve="bt2390")

    with patch("vapoursynth.core", MagicMock()) as mock_core:
        apply_tonemap(mock_clip, settings, hdr_metadata=None)

        # Verify _detect_hdr called
        mock_detect_hdr.assert_called_once()

        # Verify max_cll was used in placebo call (src_max)
        mock_core.placebo.Tonemap.assert_called_once()
        _, kwargs = mock_core.placebo.Tonemap.call_args
        assert kwargs["src_max"] == 1234


@patch("frame_compare.vs.tonemap._detect_hdr")
@patch("frame_compare.vs.tonemap.detect_plugins")
def test_apply_tonemap_detects_metadata_when_missing_fallback(mock_detect, mock_detect_hdr):
    """Verify metadata extraction is attempted in fallback path if missing."""
    mock_detect.return_value = {"libplacebo": False}

    mock_clip = MagicMock()
    # Mock fallback needs std.Expr
    mock_clip.std.Expr = MagicMock()
    mock_clip.format.id = vs.RGBS

    # Mock _detect_hdr return
    mock_metadata = MagicMock()
    mock_metadata.max_cll = 5678
    mock_detect_hdr.return_value = (True, mock_metadata)

    settings = TonemapSettings(enabled=True, tone_curve="reinhard")

    apply_tonemap(mock_clip, settings, hdr_metadata=None)

    # Verify _detect_hdr called
    mock_detect_hdr.assert_called_once()

    # Verify max_cll was used in expression
    mock_clip.std.Expr.assert_called_once()
    call_args = mock_clip.std.Expr.call_args
    # Check that 5678 is in the expression string
    assert "5678" in call_args.kwargs["expr"][0]
