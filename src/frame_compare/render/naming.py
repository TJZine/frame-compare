"""Screenshot file naming utilities."""

import re
from pathlib import Path


def generate_screenshot_name(label: str, frame_number: int, extension: str = "png") -> str:
    """Return a stable screenshot filename as ``{label}_{frame:05d}.{extension}``."""
    if frame_number < 0:
        raise ValueError("frame_number must be non-negative")
    extension = extension.lstrip(".")
    if not extension:
        raise ValueError("extension must not be empty")

    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", label)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = sanitized.strip("_")
    sanitized = sanitized or "unnamed"
    return f"{sanitized}_{frame_number:05d}.{extension}"


def generate_screenshot_path(output_dir: Path, label: str, frame_number: int) -> Path:
    filename = generate_screenshot_name(label, frame_number)
    return output_dir / filename
