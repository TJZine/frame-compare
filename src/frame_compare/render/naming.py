"""Screenshot file naming utilities."""

import os
import re
from pathlib import Path

INVALID_LABEL_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename_stem(label: str) -> str:
    """Return a legacy-compatible filesystem-safe screenshot label."""
    sanitized = INVALID_LABEL_PATTERN.sub("_", label)
    if os.name == "nt":
        sanitized = sanitized.rstrip(" .")
    sanitized = sanitized.strip()
    return sanitized or "comparison"


def generate_screenshot_name(filename_label: str, frame_number: int, extension: str = "png") -> str:
    """Return a stable screenshot filename as ``{frame} - {safe label}.{extension}``."""
    if frame_number < 0:
        raise ValueError("frame_number must be non-negative")
    extension = extension.lstrip(".")
    if not extension:
        raise ValueError("extension must not be empty")

    sanitized = sanitize_filename_stem(filename_label)
    return f"{frame_number} - {sanitized}.{extension}"


def generate_screenshot_path(output_dir: Path, filename_label: str, frame_number: int) -> Path:
    filename = generate_screenshot_name(filename_label, frame_number)
    return output_dir / filename
