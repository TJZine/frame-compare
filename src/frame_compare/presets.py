"""Preset discovery helpers extracted from src.frame_compare.core."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict, Final

import click

from src.frame_compare.preflight import PROJECT_ROOT

__all__ = [
    "PRESETS_DIR",
    "PRESET_DESCRIPTIONS",
    "list_preset_paths",
    "load_preset_data",
]

PRESETS_DIR: Final[Path] = (PROJECT_ROOT / "presets").resolve()

PRESET_DESCRIPTIONS: Final[Dict[str, str]] = {
    "quick-compare": "Minimal runtime defaults with FFmpeg renderer and slow.pics disabled.",
    "hdr-vs-sdr": "Tonemap-first workflow with stricter verification thresholds.",
    "batch-qc": "Expanded sampling with slow.pics uploads enabled for review batches.",
}


def list_preset_paths() -> Dict[str, Path]:
    """Return available preset names mapped to their file paths."""

    if not PRESETS_DIR.exists():
        return {}
    presets: Dict[str, Path] = {}
    for path in PRESETS_DIR.glob("*.toml"):
        if path.is_file():
            presets[path.stem] = path
    return presets


def load_preset_data(name: str) -> Dict[str, Any]:
    """Load a preset TOML fragment by name."""

    presets = list_preset_paths()
    try:
        preset_path = presets[name]
    except KeyError as exc:
        raise click.ClickException(
            f"Unknown preset '{name}'. Use 'preset list' to inspect options."
        ) from exc
    try:
        text = preset_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Failed to read preset '{name}': {exc}") from exc
    try:
        data: Dict[str, Any] = tomllib.loads(text.lstrip("\ufeff"))
    except tomllib.TOMLDecodeError as exc:
        raise click.ClickException(f"Preset '{name}' is invalid TOML: {exc}") from exc
    return data
