"""Configuration schema settings sources."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic_settings import TomlConfigSettingsSource


class TomlConfigSettingsSourceNoBOM(TomlConfigSettingsSource):
    """TOML settings source that accepts UTF-8 BOM-prefixed files.

    Python's built-in `tomllib.load()` rejects UTF-8 BOM at the start of the file
    (common on Windows). We decode with 'utf-8-sig' and parse via `tomllib.loads()`.
    """

    def _read_file(self, file_path: Path) -> dict[str, Any]:
        raw = file_path.read_bytes()
        text = raw.decode("utf-8-sig")
        return tomllib.loads(text)


__all__ = ["TomlConfigSettingsSourceNoBOM"]
