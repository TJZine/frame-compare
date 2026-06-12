"""Shared alignment key helpers."""

from __future__ import annotations

from pathlib import Path

__all__ = ["alignment_key"]


def alignment_key(reference: Path, comparison: Path) -> str:
    return f"{reference.stem}:{comparison.stem}"
