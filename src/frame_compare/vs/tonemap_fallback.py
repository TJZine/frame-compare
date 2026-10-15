from __future__ import annotations

from typing import TYPE_CHECKING

from frame_compare.utils.cancellation import raise_if_cancelling
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
    target_nits = validate_target_nits(settings)
    inputs = resolve_hdr_tonemap_inputs(clip, hdr_metadata)
    clip = to_rgbs(
        clip,
        props=inputs.props,
        detected_is_hdr=inputs.detected_is_hdr,
    )
    hdr_metadata = inputs.hdr_metadata

    source_peak_nits = settings.source_peak
    if source_peak_nits is None:
        source_peak_nits = hdr_metadata.max_cll if hdr_metadata and hdr_metadata.max_cll else 1000

    try:
        # VapourSynth float RGB has a nominal 0–1 range.
        source_to_target_peak_ratio = float(source_peak_nits) / float(target_nits)
        formatted_peak_ratio = f"{source_to_target_peak_ratio:.10g}"
        peak_scaled_reinhard_expression = f"x {formatted_peak_ratio} * dup 1 + / 2 * 0 max 1 min"
        raise_if_cancelling()
        clip = clip.std.Expr(
            expr=[
                peak_scaled_reinhard_expression,
                peak_scaled_reinhard_expression,
                peak_scaled_reinhard_expression,
            ]
        )
    except Exception as e:
        raise TonemapError(
            reason=f"Fallback tonemap failed: {e}",
            hint="Check fallback parameters",
        ) from e

    return apply_post_processing(clip, settings)
