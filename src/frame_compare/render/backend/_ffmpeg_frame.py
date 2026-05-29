"""Shared FFmpeg frame extraction command policy for render owners."""

from __future__ import annotations

from pathlib import Path


def build_extract_frame_argv(
    *,
    video: Path,
    frame_num: int,
    output: Path,
    overwrite: bool,
) -> list[str]:
    """Build the canonical FFmpeg argv for single-frame extraction."""
    if frame_num < 0:
        raise ValueError("frame_num must be non-negative")

    argv = ["ffmpeg"]
    if overwrite:
        argv.append("-y")
    argv.extend(
        [
            "-i",
            str(video),
            "-vf",
            f"select=eq(n\\,{frame_num})",
            "-frames:v",
            "1",
            "-q:v",
            "1",
            str(output),
        ]
    )
    return argv
