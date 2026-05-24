"""Tonemap preset settings."""

from __future__ import annotations

from frame_compare.config.schema import ToneCurve, TonemapPreset
from frame_compare.vs.errors import TonemapError
from frame_compare.vs.types import TonemapSettings

TONEMAP_PRESETS: dict[TonemapPreset, TonemapSettings] = {
    TonemapPreset.REFERENCE: TonemapSettings(
        preset=TonemapPreset.REFERENCE,
        tone_curve=ToneCurve.BT2390,
        target_nits=203,
        gamma_lift=False,
    ),
    TonemapPreset.FILMIC: TonemapSettings(
        preset=TonemapPreset.FILMIC, tone_curve=ToneCurve.SPLINE, target_nits=203, gamma_lift=False
    ),
    TonemapPreset.CONTRAST: TonemapSettings(
        preset=TonemapPreset.CONTRAST,
        tone_curve=ToneCurve.REINHARD,
        target_nits=203,
        gamma_lift=False,
    ),
    TonemapPreset.BT2390_SPEC: TonemapSettings(
        preset=TonemapPreset.BT2390_SPEC,
        tone_curve=ToneCurve.BT2390,
        target_nits=100,
        gamma_lift=False,
    ),
    TonemapPreset.SPLINE: TonemapSettings(
        preset=TonemapPreset.SPLINE, tone_curve=ToneCurve.SPLINE, target_nits=203, gamma_lift=False
    ),
    TonemapPreset.BRIGHT_LIFT: TonemapSettings(
        preset=TonemapPreset.BRIGHT_LIFT,
        tone_curve=ToneCurve.BT2390,
        target_nits=250,
        gamma_lift=True,
    ),
    TonemapPreset.HIGHLIGHT_GUARD: TonemapSettings(
        preset=TonemapPreset.HIGHLIGHT_GUARD,
        tone_curve=ToneCurve.SPLINE,
        target_nits=180,
        gamma_lift=False,
    ),
}


def get_preset_settings(preset: TonemapPreset) -> TonemapSettings:
    """Get settings for named preset."""
    if preset not in TONEMAP_PRESETS:
        raise TonemapError(
            reason=f"Unknown preset '{preset}'",
            hint=f"Available: {', '.join(candidate.value for candidate in TONEMAP_PRESETS)}",
        )
    return TONEMAP_PRESETS[preset]
