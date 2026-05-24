"""Tests for tonemapping module."""

import importlib.util
from typing import cast
from unittest.mock import MagicMock

import pytest

import frame_compare.vs.tonemap as tonemap_module  # noqa: E402, I001
from frame_compare.config.schema import ToneCurve, TonemapPreset  # noqa: E402, I001
from frame_compare.vs.errors import TonemapError  # noqa: E402, I001
from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings  # noqa: E402, I001
from frame_compare.vs.types import TonemapSettings  # noqa: E402, I001


def _vs_spec_available() -> bool:
    try:
        return importlib.util.find_spec("vapoursynth") is not None
    except ValueError:
        return False


def _reset_libplacebo_runtime_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tonemap_module,
        "_LIBPLACEBO_RUNTIME_STATE",
        tonemap_module._LibplaceboRuntimeState(),
    )


def test_get_preset_settings_unknown_raises_tonemap_error():
    """Verify unknown preset raises correct error."""
    with pytest.raises(TonemapError) as exc:
        get_preset_settings(cast(TonemapPreset, "invalid"))
    assert exc.value.context.code == "FC-4003"
    assert "reference, filmic" in exc.value.context.hint


@pytest.mark.parametrize(
    "preset, expected_curve, expected_nits, expected_gamma",
    [
        (TonemapPreset.REFERENCE, ToneCurve.BT2390, 203, False),
        (TonemapPreset.FILMIC, ToneCurve.SPLINE, 203, False),
        (TonemapPreset.CONTRAST, ToneCurve.REINHARD, 203, False),
        (TonemapPreset.BT2390_SPEC, ToneCurve.BT2390, 100, False),
        (TonemapPreset.SPLINE, ToneCurve.SPLINE, 203, False),
        (TonemapPreset.BRIGHT_LIFT, ToneCurve.BT2390, 250, True),
        (TonemapPreset.HIGHLIGHT_GUARD, ToneCurve.SPLINE, 180, False),
    ],
)
def test_tonemap_presets_have_correct_values(
    preset: TonemapPreset,
    expected_curve: ToneCurve,
    expected_nits: int,
    expected_gamma: bool,
):
    """Verify all presets match SSOT values."""
    settings = get_preset_settings(preset)
    assert settings.tone_curve == expected_curve
    assert settings.target_nits == expected_nits
    assert settings.gamma_lift == expected_gamma


def test_get_preset_settings_returns_valid_settings():
    """Verify default preset settings."""
    result = get_preset_settings(TonemapPreset.REFERENCE)
    assert isinstance(result, TonemapSettings)
    assert result.preset == TonemapPreset.REFERENCE
    assert result.tone_curve == ToneCurve.BT2390
    assert result.target_nits == 203


@pytest.mark.parametrize(
    "preset",
    [
        TonemapPreset.REFERENCE,
        TonemapPreset.FILMIC,
        TonemapPreset.CONTRAST,
        TonemapPreset.BT2390_SPEC,
        TonemapPreset.SPLINE,
        TonemapPreset.BRIGHT_LIFT,
        TonemapPreset.HIGHLIGHT_GUARD,
    ],
)
def test_get_preset_settings_all_presets_exist(preset: TonemapPreset):
    """Verify all defined presets can be retrieved."""
    result = get_preset_settings(preset)
    assert result.enabled is True


def test_apply_tonemap_enabled_false_returns_clip_unchanged():
    """Verify enabled=False is a no-op."""
    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=False)

    result = apply_tonemap(mock_clip, settings)

    assert result is mock_clip
