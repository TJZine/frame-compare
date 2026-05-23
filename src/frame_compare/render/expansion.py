"""Compatibility import path for batch render request expansion."""

from frame_compare.render.batch.expansion import (
    expand_batch_render_requests,
    render_batch_results_by_label,
    resolve_batch_ffmpeg_runner,
    resolve_target_renderer,
    validate_batch_requests,
    validate_ffmpeg_batch_tonemap_gate,
)

__all__ = [
    "expand_batch_render_requests",
    "render_batch_results_by_label",
    "resolve_batch_ffmpeg_runner",
    "resolve_target_renderer",
    "validate_batch_requests",
    "validate_ffmpeg_batch_tonemap_gate",
]
