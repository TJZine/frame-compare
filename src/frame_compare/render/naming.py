"""Screenshot file naming utilities."""

import hashlib
import os
import re
from pathlib import Path

INVALID_LABEL_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_LEGACY_WINDOWS_PATH_CHARS = 259
_SHORT_NAME_DIGEST_CHARS = 12


def _windows_path_units(path: Path) -> int:
    return len(os.path.abspath(path).encode("utf-16-le")) // 2


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
    output_path = output_dir / filename
    if _windows_path_units(output_path) <= _MAX_LEGACY_WINDOWS_PATH_CHARS:
        return output_path

    sanitized = sanitize_filename_stem(filename_label)
    digest = hashlib.sha256(sanitized.encode("utf-8")).hexdigest()[:_SHORT_NAME_DIGEST_CHARS]
    prefix = f"{frame_number} - "
    suffix = f"~{digest}.png"
    available_label_units = (
        _MAX_LEGACY_WINDOWS_PATH_CHARS
        - _windows_path_units(output_dir)
        - 1
        - len(prefix)
        - len(suffix)
    )
    shortened: list[str] = []
    used_units = 0
    for character in sanitized:
        character_units = len(character.encode("utf-16-le")) // 2
        if used_units + character_units > available_label_units:
            break
        shortened.append(character)
        used_units += character_units
    shortened_label = "".join(shortened).rstrip(" .")
    if available_label_units < 1 or not shortened_label:
        raise ValueError("screenshot output directory is too long for a browser-safe filename")
    return output_dir / f"{prefix}{shortened_label}{suffix}"
