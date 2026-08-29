"""Pure classification of bounded audio-alignment window evidence."""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise

from frame_compare.services.alignment_math import samples_to_frames
from frame_compare.services.types import (
    AlignmentStabilitySummary,
    AlignmentWindowEvidence,
)


def classify_alignment_stability(
    evidence: tuple[AlignmentWindowEvidence, ...],
    *,
    sample_rate: int,
    fps: Fraction,
) -> AlignmentStabilitySummary:
    """Classify ordered valid windows without influencing alignment selection."""
    ordered = tuple(sorted(evidence, key=lambda item: (item.start_sample, item.end_sample)))
    offsets = [samples_to_frames(item.sample_offset, sample_rate, fps) for item in ordered]
    if len(offsets) < 3:
        return AlignmentStabilitySummary(
            "insufficient_evidence", len(offsets), None, None, None, None, None, None
        )

    offset_min = min(offsets)
    offset_max = max(offsets)
    span = offset_max - offset_min
    changes = [right - left for left, right in pairwise(offsets)]
    jump_index, largest_jump = max(enumerate(changes), key=lambda item: abs(item[1]))
    largest_jump_frames = abs(largest_jump)

    classification = "variable"
    change_position: float | None = None
    if span <= 1:
        classification = "stable"
    elif largest_jump_frames >= 2 and largest_jump_frames >= 0.6 * span:
        classification = "possible_discontinuity"
        left = ordered[jump_index]
        right = ordered[jump_index + 1]
        change_position = (
            left.start_sample + left.end_sample + right.start_sample + right.end_sample
        ) / (4 * sample_rate)
    elif abs(offsets[-1] - offsets[0]) >= 2:
        direction = 1 if offsets[-1] > offsets[0] else -1
        meaningful = [change for change in changes if change != 0]
        agreeing = [change for change in meaningful if change * direction > 0 or abs(change) <= 1]
        if meaningful and len(agreeing) / len(meaningful) >= 0.75:
            classification = "possible_drift"

    return AlignmentStabilitySummary(
        classification=classification,
        valid_windows=len(offsets),
        offset_min_frames=offset_min,
        offset_max_frames=offset_max,
        first_offset_frames=offsets[0],
        last_offset_frames=offsets[-1],
        largest_adjacent_jump_frames=largest_jump_frames,
        change_position_seconds=change_position,
    )
