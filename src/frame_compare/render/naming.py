"""Screenshot file naming utilities."""

import re
from pathlib import Path


def generate_screenshot_name(label: str, frame_number: int, extension: str = "png") -> str:
    """
    Generate consistent screenshot filename.

    Format: {sanitized_label}_{frame:05d}.{ext}
    Example: "Source_00100.png"

    Algorithm:
    1. Sanitize label: replace any character not in [A-Za-z0-9_-] with _.
    2. Collapse consecutive underscores to a single underscore.
    3. Strip leading/trailing underscores.
    4. If sanitized label is empty, use "unnamed".
    5. Format: f"{sanitized_label}_{frame_number:05d}.{extension}".

    Args:
        label: Video label
        frame_number: Frame index
        extension: File extension (default: "png")

    Returns:
        Formatted filename string

    Raises:
        ValueError: If frame_number is negative or extension is empty.
    """
    if frame_number < 0:
        raise ValueError("frame_number must be non-negative")
    if not extension:
        raise ValueError("extension must not be empty")

    # 1. Sanitize label
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", label)

    # 2. Collapse consecutive underscores
    sanitized = re.sub(r"_+", "_", sanitized)

    # 3. Strip leading/trailing underscores
    sanitized = sanitized.strip("_")

    # 4. If empty, use "unnamed"
    sanitized = sanitized or "unnamed"

    # 5. Format
    return f"{sanitized}_{frame_number:05d}.{extension}"


def generate_screenshot_path(output_dir: Path, label: str, frame_number: int) -> Path:
    """
    Generate full output path for a screenshot.

    Args:
        output_dir: Target directory
        label: Video label
        frame_number: Frame index

    Returns:
        Full path to the screenshot
    """
    filename = generate_screenshot_name(label, frame_number)
    return output_dir / filename
