"""Pure alignment math helpers."""

from __future__ import annotations

from fractions import Fraction

import numpy as np

from frame_compare.services.errors import AudioAlignmentError


def cross_correlate(
    reference: np.ndarray,
    comparison: np.ndarray,
    max_offset_samples: int | None = None,
) -> tuple[int, float]:
    """Find offset using cross-correlation."""
    if reference.size == 0 or comparison.size == 0:
        raise AudioAlignmentError("empty audio signal prevents correlation")

    correlation_size = reference.size + comparison.size - 1
    fft_size = 1 << (correlation_size - 1).bit_length()

    reference_fft = np.fft.rfft(reference, fft_size)
    comparison_fft = np.fft.rfft(comparison, fft_size)
    correlation_raw = np.fft.irfft(reference_fft * np.conj(comparison_fft), fft_size)
    correlation = np.concatenate(
        (
            correlation_raw[-(comparison.size - 1) :],
            correlation_raw[: reference.size],
        )
    )

    if max_offset_samples is not None:
        bounded = max(0, max_offset_samples)
        center = reference.size - 1
        start_idx = max(0, center - bounded)
        end_idx = min(correlation.size, center + bounded + 1)
        if start_idx >= end_idx:
            raise AudioAlignmentError("max_offset_seconds produced an empty search window")
        peak_idx = int(np.argmax(correlation[start_idx:end_idx])) + start_idx
    else:
        peak_idx = int(np.argmax(correlation))

    offset = reference.size - 1 - peak_idx

    norm_ref = np.linalg.norm(reference)
    norm_comp = np.linalg.norm(comparison)

    if norm_ref == 0 or norm_comp == 0:
        raise AudioAlignmentError("zero-norm audio signal prevents correlation")

    score = float(correlation[peak_idx] / (norm_ref * norm_comp))

    return offset, score


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
