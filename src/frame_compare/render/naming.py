from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path

SAFE_LABEL_META_KEY = "_safe_label"

__all__ = [
    "INVALID_LABEL_PATTERN",
    "SAFE_LABEL_META_KEY",
    "derive_labels",
    "prepare_filename",
    "sanitise_label",
]


INVALID_LABEL_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitise_label(label: str) -> str:
    """Return a filesystem-safe label while preserving user intent when possible."""

    cleaned = INVALID_LABEL_PATTERN.sub("_", label)
    if os.name == "nt":
        cleaned = cleaned.rstrip(" .")
    cleaned = cleaned.strip()
    return cleaned or "comparison"


def derive_labels(source: str, metadata: Mapping[str, str]) -> tuple[str, str]:
    """Return the raw+cleaned labels for *source* using optional metadata."""

    raw = metadata.get("label") or Path(source).stem
    override = metadata.get(SAFE_LABEL_META_KEY)
    if isinstance(override, str) and override.strip():
        cleaned = sanitise_label(override)
    else:
        cleaned = sanitise_label(raw)
    return raw.strip() or cleaned, cleaned


def prepare_filename(frame: int, label: str) -> str:
    """Return the canonical screenshot filename for *frame* and *label*."""

    return f"{frame} - {label}.png"
