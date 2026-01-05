"""Analysis package for frame metrics and selection.

This package provides:
- Frame-level metrics calculation (luminance, motion)
- Frame selection algorithms (quantile, motion, random, mixed)
- FramePlan contract for deterministic screenshots-only mode
"""

from frame_compare.analysis.frame_plan import (
    FramePlan,
    create_uniform_seeded_plan,
    select_uniform_seeded_frames,
)

__all__ = [
    "FramePlan",
    "create_uniform_seeded_plan",
    "select_uniform_seeded_frames",
]
