"""Fallback HDR tonemap implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from frame_compare.vs.errors import TonemapError
from frame_compare.vs.tonemap_conversion import (
    apply_post_processing,
    resolve_hdr_tonemap_inputs,
    to_rgbs,
    validate_target_nits,
)
from frame_compare.vs.types import HDRMetadata, TonemapSettings

if TYPE_CHECKING:
    import vapoursynth as vs


def fallback_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """Fallback tonemapping using a scaled Reinhard-style curve via std.Expr."""
    target_nits = validate_target_nits(settings)
    inputs = resolve_hdr_tonemap_inputs(clip, hdr_metadata)
    clip = to_rgbs(
        clip,
        props=inputs.props,
        detected_is_hdr=inputs.detected_is_hdr,
    )
    hdr_metadata = inputs.hdr_metadata

    peak = settings.source_peak
    if peak is None:
        peak = hdr_metadata.max_cll if hdr_metadata and hdr_metadata.max_cll else 1000

    try:
        # Heuristic fallback when libplacebo is unavailable or fails at runtime.
        #
        # Notes:
        # - VS float RGB clips are typically normalized, and we want to avoid producing
        #   near-zero output (black screenshots). We therefore operate on a relative
        #   scale and normalize roughly around the configured target nits.
        #
        # Define:
        #   x_rel = x * (peak / target_nits)
        #   y = 2 * x_rel / (1 + x_rel)
        # which maps x_rel=1 -> y~=1 (after the 2x), and compresses highlights.
        scale = float(peak) / float(target_nits)
        scale_s = f"{scale:.10g}"
        expr = f"x {scale_s} * dup 1 + / 2 * 0 max 1 min"
        clip = clip.std.Expr(expr=[expr, expr, expr])
    except Exception as e:
        raise TonemapError(
            reason=f"Fallback tonemap failed: {e}",
            hint="Check fallback parameters",
        ) from e

    return apply_post_processing(clip, settings)
