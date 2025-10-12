"""Common configuration path helpers shared across the CLI and utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Final

_DATA_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "data"

DEFAULT_CONFIG_TEMPLATE_PATH: Final[Path] = _DATA_DIR / "config.toml.template"
"""Path to the packaged configuration template."""

DEFAULT_CONFIG_PATH: Final[Path] = DEFAULT_CONFIG_TEMPLATE_PATH
"""Default configuration consumed by the CLI (uses the packaged template)."""

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_CONFIG_TEMPLATE_PATH",
]
