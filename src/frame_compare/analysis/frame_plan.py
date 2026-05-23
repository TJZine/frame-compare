"""FramePlan module for deterministic frame selection."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from frame_compare.analysis.errors import InsufficientFramesError

__all__ = ["FramePlan", "select_uniform_seeded_frames", "create_frame_plan"]


@dataclass(frozen=True)
class FramePlan:
    """Deterministic frame selection result.

    Invariants:
    - len(frames) == count (always exactly count frames)
    - all(0 <= f < num_frames for f in frames)
    - frames are sorted ascending
    - frames are unique
    """

    frames: list[int]  # Selected frame indices, sorted ascending
    num_frames: int  # Total frames in source video
    count: int  # Requested frame count
    seed: int  # Seed used for selection
    method: str = "uniform_seeded"  # Selection method identifier


def create_frame_plan(
    num_frames: int,
    count: int,
    seed: int | None = None,
) -> FramePlan:
    """
    Create a FramePlan with optional auto-generated seed.

    Args:
        num_frames: Total frames in video
        count: Number of frames to select
        seed: Optional seed; if None, uses the default seed (42)

    Returns:
        FramePlan from select_uniform_seeded_frames()
    """
    if seed is None:
        seed = 42
    return select_uniform_seeded_frames(num_frames, count, seed)


def _select_from_bin(bin_start: int, bin_end: int, seed: int, bin_index: int) -> int:
    """Select one frame from a bin using blake2s hash.

    Args:
        bin_start: Inclusive start of bin
        bin_end: Exclusive end of bin
        seed: User-provided seed integer
        bin_index: Index of this bin (0-based)

    Returns:
        Frame index in [bin_start, bin_end)
    """
    bin_size = bin_end - bin_start
    if bin_size <= 0:
        raise ValueError("Empty bin")

    # Create deterministic hash from seed + bin index
    hash_input = f"{seed}:{bin_index}".encode()
    digest = hashlib.blake2s(hash_input, digest_size=8).digest()

    # Convert to integer and map to bin range
    hash_int = int.from_bytes(digest, "little")
    offset = hash_int % bin_size

    return bin_start + offset


def select_uniform_seeded_frames(
    num_frames: int,
    count: int,
    seed: int,
) -> FramePlan:
    """Select frames using deterministic uniform distribution."""
    # Validate
    if num_frames < 0:
        raise ValueError("num_frames must be >= 0")
    if count < 0:
        raise ValueError("count must be >= 0")
    if count > num_frames:
        raise InsufficientFramesError(
            path=Path("<frame-plan>"),
            count=num_frames,
            required=count,
        )

    if count == 0:
        return FramePlan(
            frames=[],
            num_frames=num_frames,
            count=0,
            seed=seed,
        )

    # Calculate bins
    bin_size = num_frames / count
    frames: list[int] = []

    for i in range(count):
        bin_start = int(i * bin_size)
        bin_end = int((i + 1) * bin_size)
        # Clamp end to num_frames for last bin
        if i == count - 1:
            bin_end = num_frames

        frame = _select_from_bin(bin_start, bin_end, seed, i)
        frames.append(frame)

    # Sort for stable output (required by contract)
    frames.sort()

    return FramePlan(
        frames=frames,
        num_frames=num_frames,
        count=count,
        seed=seed,
    )
