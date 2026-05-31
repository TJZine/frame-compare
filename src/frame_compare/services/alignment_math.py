"""Pure alignment math helpers."""

from __future__ import annotations

from fractions import Fraction

import numpy as np

from frame_compare.services.alignment_correlation import correlate_audio
from frame_compare.services.errors import AudioAlignmentError


def cross_correlate(
    reference: np.ndarray,
    comparison: np.ndarray,
    max_offset_samples: int | None = None,
) -> tuple[int, float]:
    """Find offset using cross-correlation."""
    estimate = correlate_audio(
        reference,
        comparison,
        max_offset_samples=max_offset_samples,
        correlation_mode="raw_fft",
        preprocessing_mode="none",
    )
    return estimate.sample_offset, estimate.score


def samples_to_frames(
    sample_offset: int,
    sample_rate: int,
    fps: Fraction,
) -> int:
    """Convert sample offset to frame offset."""
    time_offset = sample_offset / sample_rate
    return int(round(time_offset * float(fps)))


def calculate_alignment_trims(
    ref_num_frames: int,
    comp_offsets: list[int | None],
    comp_num_frames: list[int],
) -> tuple[tuple[int, int], list[tuple[int, int]]]:
    """Calculate trim start and end (inclusive) frames for reference and comparisons.

    Returns:
        A tuple where the first element is (ref_trim_start, ref_trim_end)
        and the second element is a list of (comp_trim_start, comp_trim_end) for each comparison.
    """
    if len(comp_offsets) != len(comp_num_frames):
        raise ValueError(
            "comp_offsets and comp_num_frames must have matching lengths "
            f"({len(comp_offsets)} != {len(comp_num_frames)})"
        )

    offsets = [offset for offset in comp_offsets if offset is not None]
    if not offsets:
        return (0, ref_num_frames - 1), [(0, num - 1) for num in comp_num_frames]

    baseline = max(0, max(offsets))
    ref_len = ref_num_frames - baseline

    trimmed_comp_lens: list[int] = []
    trim_starts: list[int] = []
    for offset, num_frames in zip(comp_offsets, comp_num_frames, strict=True):
        relative_offset = offset if offset is not None else 0
        trim_start = baseline - relative_offset
        if trim_start < 0:
            raise ValueError(f"trim_start_frames {trim_start} must be >= 0")
        trim_starts.append(trim_start)
        trimmed_comp_lens.append(num_frames - trim_start)

    common_length = min([ref_len, *trimmed_comp_lens])
    if common_length <= 0:
        raise AudioAlignmentError("No overlapping frames after alignment normalization.")

    ref_trim_start = baseline
    ref_trim_end = baseline + common_length - 1

    comp_trims = [(trim_start, trim_start + common_length - 1) for trim_start in trim_starts]

    return (ref_trim_start, ref_trim_end), comp_trims
