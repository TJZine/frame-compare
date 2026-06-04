"""Analysis phase policy helpers."""

from __future__ import annotations

from frame_compare.config.schema import AnalysisConfig


def needs_analysis(config: AnalysisConfig) -> bool:
    """Return whether requested frame selectors require metric analysis."""
    return (
        config.dark_frame_count > 0
        or config.bright_frame_count > 0
        or config.motion_frame_count > 0
    )
