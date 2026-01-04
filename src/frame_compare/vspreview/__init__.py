"""VSPreview integration module for Frame Compare 2.0.

This module provides optional interactive alignment verification and override
capabilities using the VSPreview application.

Public API:
    - is_vspreview_available(): Check if VSPreview can be launched
    - launch_alignment_verification_session(): Generate and launch VSPreview session
    - load_manual_overrides(): Load persisted manual overrides from cache
    - save_manual_override(): Persist a manual override to cache
    - ManualOverride: User-provided alignment override dataclass
    - VSPreviewConfig: Configuration for VSPreview integration
"""

from frame_compare.vspreview.adapter import (
    VSPreviewConfig,
    is_vspreview_available,
    launch_alignment_verification_session,
)
from frame_compare.vspreview.overrides import (
    ManualOverride,
    load_manual_overrides,
    save_manual_override,
)

__all__ = [
    "ManualOverride",
    "VSPreviewConfig",
    "is_vspreview_available",
    "launch_alignment_verification_session",
    "load_manual_overrides",
    "save_manual_override",
]
