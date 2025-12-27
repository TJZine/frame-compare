"""Deterministic frame selection for screenshots-only mode.

This module provides the FramePlan contract and uniform seeded frame selection
for --skip-analysis mode. When analysis is skipped, frames are selected using
a deterministic blake2s-based algorithm.

IMPORTANT: FramePlan.frames must ALWAYS contain concrete frame indices.
Do not create FramePlan instances with empty frames lists.

Reference outputs (locked for contract testing):
- (num_frames=240, count=5, seed=42) => [12, 59, 115, 151, 233]
- (num_frames=240, count=10, seed=42) => [12, 35, 67, 79, 113, 124, 156, 168, 196, 231]
- (num_frames=240, count=1, seed=42) => [60]
- (num_frames=10, count=5, seed=42) => [0, 3, 5, 7, 9]
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class FramePlan:
    """Stable contract for frame selection results.

    Attributes:
        frames: 0-based frame indices, sorted ascending
        method: How frames were selected ("analysis" or "uniform_seeded")
        seed: Random seed used for selection
        num_frames: Total frames in source video
    """
    frames: list[int]
    method: Literal["analysis", "uniform_seeded"]
    seed: int
    num_frames: int

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("FramePlan.frames must not be empty")


def _blake2s_u32(data: str) -> int:
    """Generate a 32-bit unsigned integer from blake2s hash of string."""
    digest = hashlib.blake2s(data.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "little")


def select_uniform_seeded_frames(
    *,
    num_frames: int,
    count: int,
    seed: int,
) -> list[int]:
    """Deterministically pick `count` unique frames across `num_frames` using `seed`.

    Algorithm:
    1. Partition [0, num_frames) into `count` disjoint bins:
       - bin_start = floor(i * num_frames / count)
       - bin_end = floor((i + 1) * num_frames / count) - 1
    2. Pick exactly one frame per bin using blake2s hash:
       - offset = blake2s_u32(f"{seed}:{i}") % (bin_end - bin_start + 1)
       - frame_i = bin_start + offset
    3. Return frames sorted ascending.

    Args:
        num_frames: Total number of frames in video (post-trim, post-alignment)
        count: Number of frames to select
        seed: Random seed for reproducibility

    Returns:
        List of frame indices, 0-based, sorted ascending

    Raises:
        ValueError: If count > num_frames or count/num_frames <= 0
    """
    if num_frames <= 0:
        raise ValueError(f"num_frames must be positive, got {num_frames}")
    if count <= 0:
        raise ValueError(f"count must be positive, got {count}")
    if count > num_frames:
        # FC-3004: INSUFFICIENT_FRAMES
        raise ValueError(
            f"Cannot select {count} frames from video with only {num_frames} frames"
        )

    frames: list[int] = []

    for i in range(count):
        bin_start = (i * num_frames) // count
        bin_end = ((i + 1) * num_frames) // count - 1

        # Non-empty bin guaranteed when count <= num_frames
        bin_size = bin_end - bin_start + 1
        offset = _blake2s_u32(f"{seed}:{i}") % bin_size
        frame = bin_start + offset

        frames.append(frame)

    return sorted(frames)


def create_uniform_seeded_plan(
    *,
    num_frames: int,
    count: int,
    seed: int,
) -> FramePlan:
    """Create a FramePlan using uniform seeded selection (for --skip-analysis mode).

    This function is the ONLY way to create a FramePlan when analysis is skipped.
    It guarantees that frames list is always populated with concrete indices.

    Args:
        num_frames: Total frames in aligned reference clip
        count: Number of frames to select
        seed: Random seed for selection

    Returns:
        FramePlan with method="uniform_seeded" and concrete frame indices
    """
    frames = select_uniform_seeded_frames(
        num_frames=num_frames, count=count, seed=seed
    )
    return FramePlan(
        frames=frames,
        method="uniform_seeded",
        seed=seed,
        num_frames=num_frames,
    )
