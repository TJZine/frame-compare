from typing import cast
from unittest.mock import MagicMock

import pytest

from frame_compare.config.schema import ToneCurve, TonemapPreset
from frame_compare.vs.errors import TonemapError
from frame_compare.vs.tonemap import apply_tonemap, get_preset_settings
from frame_compare.vs.types import TonemapSettings


def test_get_preset_settings_unknown_raises_tonemap_error():
    with pytest.raises(TonemapError) as exc:
        get_preset_settings(cast(TonemapPreset, "invalid"))
    assert exc.value.context.code == "FC-4003"
    assert exc.value.context.hint is not None
    assert "reference, filmic" in exc.value.context.hint


def test_apply_tonemap_enabled_false_returns_clip_unchanged():
    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=False)

    result = apply_tonemap(mock_clip, settings)

    assert result.clip is mock_clip
    assert result.applied is None


@pytest.mark.parametrize(
    "preset, curve, nits, gamma",
    [
        pytest.param(TonemapPreset.REFERENCE, ToneCurve.BT2390, 100, False, id="reference"),
        pytest.param(TonemapPreset.FILMIC, ToneCurve.SPLINE, 203, False, id="filmic"),
        pytest.param(TonemapPreset.CONTRAST, ToneCurve.REINHARD, 203, False, id="contrast"),
        pytest.param(TonemapPreset.BT2390_SPEC, ToneCurve.BT2390, 100, False, id="bt2390_spec"),
        pytest.param(TonemapPreset.SPLINE, ToneCurve.SPLINE, 203, False, id="spline"),
        pytest.param(TonemapPreset.BRIGHT_LIFT, ToneCurve.BT2390, 250, True, id="bright_lift"),
        pytest.param(
            TonemapPreset.HIGHLIGHT_GUARD, ToneCurve.SPLINE, 180, False, id="highlight_guard"
        ),
        pytest.param(
            TonemapPreset.HIGHLIGHT_PRESERVE,
            ToneCurve.BT2390,
            100,
            False,
            id="highlight_preserve",
        ),
    ],
)
def test_tonemap_preset_settings(
    preset: TonemapPreset, curve: ToneCurve, nits: int, gamma: bool
) -> None:
    settings = get_preset_settings(preset)
    assert isinstance(settings, TonemapSettings)
    assert settings.preset == preset
    assert settings.tone_curve == curve
    assert settings.target_nits == nits
    assert settings.gamma_lift == gamma
    assert settings.enabled is True
