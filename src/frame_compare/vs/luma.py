"""Shared VapourSynth luma conversion for analysis consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import vapoursynth as vs


def luma_plane(clip: vs.VideoNode) -> vs.VideoNode:
    """Return the first plane as gray, preserving source sample precision.

    RGB sources are converted with BT.709 coefficients and full-range output so
    normalized analysis values retain the expected RGB luminance scale. The
    VapourSynth import remains inside this helper because analysis and planning
    modules must stay importable without the optional native runtime.
    """
    import vapoursynth as vs

    color_family = clip.format.color_family
    if color_family == vs.GRAY:
        return clip
    if color_family == vs.YUV:
        return clip.std.ShufflePlanes(planes=0, colorfamily=vs.GRAY)
    if color_family == vs.RGB:
        source_format = clip.format
        gray_format = vs.core.query_video_format(
            color_family=vs.GRAY,
            sample_type=source_format.sample_type,
            bits_per_sample=source_format.bits_per_sample,
        )
        return clip.resize.Bicubic(
            format=gray_format.id,
            matrix_s="709",
            range_s="full",
        )
    raise ValueError(f"Unsupported VapourSynth color family: {color_family!r}")


__all__ = ["luma_plane"]
