"""Configuration schema settings sources."""

from __future__ import annotations

import tomllib
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, cast

from pydantic.fields import FieldInfo
from pydantic_settings import EnvSettingsSource, TomlConfigSettingsSource


class TomlConfigSettingsSourceNoBOM(TomlConfigSettingsSource):
    """TOML settings source that accepts UTF-8 BOM-prefixed files.

    Python's built-in `tomllib.load()` rejects UTF-8 BOM at the start of the file
    (common on Windows). We decode with 'utf-8-sig' and parse via `tomllib.loads()`.
    """

    def _read_file(self, file_path: Path | Traversable) -> dict[str, Any]:
        raw = file_path.read_bytes()
        text = raw.decode("utf-8-sig")
        return tomllib.loads(text)


class EnvironmentSettingsSource(EnvSettingsSource):
    """Environment source with decoding for supported nested scalar settings.

    Pydantic-settings explodes ``FRAME_COMPARE_*__*`` variables into nested
    dictionaries, but leaves the resulting scalar values as strings.  The
    runtime memory limit is strict by design for TOML and constructor inputs;
    decode its environment representation here, at the source boundary, so
    that the strict model still rejects non-integer strings, floats, and bools.
    """

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        prepared = super().prepare_field_value(field_name, field, value, value_is_complex)
        if field_name != "runtime" or not isinstance(prepared, dict):
            return prepared

        prepared_values = cast(dict[str, object], prepared)
        memory_limit = prepared_values.get("memory_limit_mb")
        if isinstance(memory_limit, str):
            try:
                decoded_memory_limit = int(memory_limit)
            except ValueError:
                # Keep an overlong decimal as a string so strict model
                # validation reports the ordinary typed configuration error.
                return prepared_values
            prepared_values = {**prepared_values, "memory_limit_mb": decoded_memory_limit}
        return prepared_values


__all__ = ["EnvironmentSettingsSource", "TomlConfigSettingsSourceNoBOM"]
