"""Media discovery helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Final, List

from natsort import os_sorted

SUPPORTED_EXTS: Final[tuple[str, ...]] = (
    ".mkv",
    ".m2ts",
    ".mp4",
    ".webm",
    ".ogm",
    ".mpg",
    ".vob",
    ".iso",
    ".ts",
    ".mts",
    ".mov",
    ".qv",
    ".yuv",
    ".flv",
    ".avi",
    ".rm",
    ".rmvb",
    ".m2v",
    ".m4v",
    ".mp2",
    ".mpeg",
    ".mpe",
    ".mpv",
    ".wmv",
    ".avc",
    ".hevc",
    ".264",
    ".265",
    ".av1",
)

__all__ = ["SUPPORTED_EXTS", "_discover_media"]


def _discover_media(root: Path) -> List[Path]:
    """Return supported media files within *root*, sorted naturally."""

    return [p for p in os_sorted(root.iterdir()) if p.suffix.lower() in SUPPORTED_EXTS]

