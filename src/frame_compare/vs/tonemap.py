"""HDR tonemapping module."""

from __future__ import annotations

import vapoursynth as vs

from frame_compare.errors import TonemapError
from frame_compare.vs.env import detect_plugins
from frame_compare.vs.source import _detect_hdr  # pyright: ignore[reportPrivateUsage]
from frame_compare.vs.types import HDRMetadata, TonemapSettings

# Private constants
_TONE_CURVE_MAP = {"bt2390": 2, "spline": 1, "reinhard": 4}

_TONEMAP_PRESETS: dict[str, TonemapSettings] = {
    "reference": TonemapSettings(
        preset="reference", tone_curve="bt2390", target_nits=203, gamma_lift=False
    ),
    "filmic": TonemapSettings(
        preset="filmic", tone_curve="spline", target_nits=203, gamma_lift=False
    ),
    "contrast": TonemapSettings(
        preset="contrast", tone_curve="reinhard", target_nits=203, gamma_lift=False
    ),
    "bt2390_spec": TonemapSettings(
        preset="bt2390_spec", tone_curve="bt2390", target_nits=100, gamma_lift=False
    ),
    "spline": TonemapSettings(
        preset="spline", tone_curve="spline", target_nits=203, gamma_lift=False
    ),
    "bright_lift": TonemapSettings(
        preset="bright_lift", tone_curve="bt2390", target_nits=250, gamma_lift=True
    ),
    "highlight_guard": TonemapSettings(
        preset="highlight_guard",
        tone_curve="spline",
        target_nits=180,
        gamma_lift=False,
    ),
}


def _to_rgbs(clip: vs.VideoNode) -> vs.VideoNode:
    """Convert clip to RGBS if needed."""
    try:
        if clip.format.id != vs.RGBS:  # type: ignore
            return clip.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")  # type: ignore
        return clip
    except Exception as e:
        raise TonemapError(
            reason=f"Failed to convert to RGBS: {e}",
            hint="Check input clip format compatibility",
        ) from e


def _apply_post_processing(clip: vs.VideoNode, settings: TonemapSettings) -> vs.VideoNode:
    """Apply unified post-processing (contrast recovery and gamma lift)."""
    try:
        if settings.contrast_recovery > 0.0:
            factor = 1 + settings.contrast_recovery
            expr = f"x 0.5 - {factor} * 0.5 + 0 max 1 min"
            clip = clip.std.Expr(expr=[expr, expr, expr])

        if settings.gamma_lift:
            clip = clip.std.Levels(gamma=0.9)

        return clip
    except Exception as e:
        raise TonemapError(
            reason=f"Post-processing failed: {e}",
            hint="Check post-processing parameters",
        ) from e


def _apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """Apply tonemapping using libplacebo."""
    if settings.tone_curve not in _TONE_CURVE_MAP:
        raise TonemapError(
            reason=f"Unsupported tone curve '{settings.tone_curve}'",
            hint="Supported: bt2390, spline, reinhard",
        )

    clip = _to_rgbs(clip)

    if hdr_metadata is None:
        props = dict(clip.get_frame(0).props)
        _, hdr_metadata = _detect_hdr(props)

    src_max = settings.source_peak
    if src_max is None:
        src_max = hdr_metadata.max_cll if hdr_metadata and hdr_metadata.max_cll else 1000

    try:
        # We need to type ignore because VS plugin properties are dynamic
        clip = core.placebo.Tonemap(  # type: ignore
            clip,
            src_max=src_max,
            dst_max=settings.target_nits,
            tone_mapping_function=_TONE_CURVE_MAP[settings.tone_curve],
        )
    except Exception as e:
        raise TonemapError(
            reason=f"libplacebo tonemap failed: {e}",
            hint="Check libplacebo plugin version",
        ) from e

    return _apply_post_processing(clip, settings)


def _fallback_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """Fallback tonemapping using Reinhard formula via std.Expr."""
    clip = _to_rgbs(clip)

    if hdr_metadata is None:
        props = dict(clip.get_frame(0).props)
        _, hdr_metadata = _detect_hdr(props)

    peak = settings.source_peak
    if peak is None:
        peak = hdr_metadata.max_cll if hdr_metadata and hdr_metadata.max_cll else 1000

    target_nits = settings.target_nits

    try:
        # Reinhard: output = (x / peak) / (1 + (x / peak)) * norm
        expr = f"x {peak} / dup 1 + / {target_nits} {peak} / * 0 max 1 min"
        clip = clip.std.Expr(expr=[expr, expr, expr])
    except Exception as e:
        raise TonemapError(
            reason=f"Fallback tonemap failed: {e}",
            hint="Check fallback parameters",
        ) from e

    return _apply_post_processing(clip, settings)


def get_preset_settings(preset: str) -> TonemapSettings:
    """Get settings for named preset."""
    if preset not in _TONEMAP_PRESETS:
        raise TonemapError(
            reason=f"Unknown preset '{preset}'",
            hint=f"Available: {', '.join(_TONEMAP_PRESETS.keys())}",
        )
    return _TONEMAP_PRESETS[preset]


def apply_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """Apply HDR to SDR tonemapping."""
    if not settings.enabled:
        return clip

    core = clip.std.core  # May raise AttributeError, let it propagate

    plugins = detect_plugins(core)

    if plugins.get("libplacebo", False):
        return _apply_libplacebo(clip, settings, core, hdr_metadata)
    else:
        return _fallback_tonemap(clip, settings, hdr_metadata)
