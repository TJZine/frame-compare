"""Explicit applied-transform fixtures for render and report contracts."""

from frame_compare.vs.types import (
    AppliedTonemap,
    LibplaceboTonemap,
    ResolvedSourcePeak,
    TonemapSettings,
)


def libplacebo_tonemap(settings: TonemapSettings) -> AppliedTonemap:
    return AppliedTonemap(
        settings,
        LibplaceboTonemap(settings.tone_curve, settings, ResolvedSourcePeak(1000, "default")),
    )
