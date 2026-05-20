"""Shared FFmpeg frame extraction command policy for render owners."""

from __future__ import annotations

import math
from pathlib import Path


def frame_seek_time_seconds(frame_num: int, fps: float) -> str:
    """Return the repo-standard deterministic seek timestamp for a frame number."""
    if frame_num < 0:
        raise ValueError("frame_num must be non-negative")
    if not math.isfinite(fps) or fps <= 0.0:
        raise ValueError("fps must be finite and positive")
    return f"{math.floor((frame_num / fps) * 1000) / 1000:.3f}"


def build_extract_frame_argv(
    *,
    video: Path,
    seek_time: str,
    output: Path,
    overwrite: bool,
) -> list[str]:
    """Build the canonical FFmpeg argv for single-frame extraction."""
    argv = ["ffmpeg"]
    if overwrite:
        argv.append("-y")
    argv.extend(
        [
            "-ss",
            seek_time,
            "-i",
            str(video),
            "-vframes",
            "1",
            "-q:v",
            "1",
            str(output),
        ]
    )
    return argv
