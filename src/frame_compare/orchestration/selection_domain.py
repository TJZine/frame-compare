"""Selection-window and cache-domain helpers for orchestration.

These helpers are pure and deterministic so production preparation logic and
tests can share the same owner seam without importing private preparation
helpers.
"""

from __future__ import annotations

from frame_compare.analysis.window import (
    ClipWindowInput,
    SelectionWindow,
    compute_shared_selection_window,
)
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import ClipState


def compute_selection_window_for_clips(
    *,
    clips: list[ClipState],
    config: ConfigSchema,
) -> SelectionWindow:
    """Compute the shared selection window across prepared clips."""
    return compute_shared_selection_window(
        [
            ClipWindowInput(frame_count=clip.effective_num_frames(), fps=clip.effective_fps)
            for clip in clips
        ],
        ignore_lead_seconds=config.analysis.ignore_lead_seconds,
        ignore_trail_seconds=config.analysis.ignore_trail_seconds,
        min_window_seconds=config.analysis.min_window_seconds,
    )


def build_analysis_selection_domain_token(
    *,
    clips: list[ClipState],
    config: ConfigSchema,
    selection_window: SelectionWindow,
) -> str:
    """Build the stable cache-domain token for analysis selection."""
    source_tokens: list[str] = []
    for clip in clips:
        trim_end = (
            ""
            if clip.trim.trim_end_frame_inclusive is None
            else str(clip.trim.trim_end_frame_inclusive)
        )
        source_tokens.append(
            "|".join(
                [
                    f"path={clip.path}",
                    f"size={clip.probe.fingerprint.size_bytes}",
                    f"mtime_ns={clip.probe.fingerprint.mtime_ns}",
                    f"trim_start={clip.trim.trim_start_frames}",
                    f"trim_end_inclusive={trim_end}",
                    f"effective_fps={clip.effective_fps.numerator}/{clip.effective_fps.denominator}",
                ]
            )
        )
    analysis = config.analysis
    return "||".join(
        [
            "sources=[" + ";".join(source_tokens) + "]",
            f"ignore_lead_seconds={analysis.ignore_lead_seconds}",
            f"ignore_trail_seconds={analysis.ignore_trail_seconds}",
            f"min_window_seconds={analysis.min_window_seconds}",
            (
                "selection_window="
                f"{selection_window.start_frame}:{selection_window.end_frame_exclusive}"
            ),
        ]
    )
