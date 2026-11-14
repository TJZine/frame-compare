"""Configuration schema settings sources."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from contextlib import suppress
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, cast

from pydantic.fields import FieldInfo
from pydantic_settings import EnvSettingsSource, TomlConfigSettingsSource

from frame_compare.config.errors import ConfigParseError
from frame_compare.utils.serialized_decode import SERIALIZED_DECODE_FAILURES


class TomlConfigSettingsSourceNoBOM(TomlConfigSettingsSource):
    """TOML settings source that accepts UTF-8 BOM-prefixed files.

    Python's built-in `tomllib.load()` rejects UTF-8 BOM at the start of the file
    (common on Windows). We decode with 'utf-8-sig' and parse via `tomllib.loads()`.
    """

    def _read_file(self, file_path: Path | Traversable) -> dict[str, Any]:
        raw = file_path.read_bytes()
        text = raw.decode("utf-8-sig")
        try:
            return tomllib.loads(text)
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            raise
        except SERIALIZED_DECODE_FAILURES:
            raise ConfigParseError(
                Path(str(file_path)), "configuration exceeds TOML parser limits"
            ) from None


class EnvironmentSettingsSource(EnvSettingsSource):
    """Environment source with decoding for supported nested scalar settings.

    Pydantic-settings explodes ``FRAME_COMPARE_*__*`` variables into nested
    dictionaries, but leaves the resulting scalar values as strings.  The
    runtime and slow.pics models remain strict for TOML and constructor inputs.
    """

    def decode_complex_value(self, field_name: str, field: FieldInfo, value: Any) -> Any:
        try:
            return super().decode_complex_value(field_name, field, value)
        except RecursionError:
            # Settings sources translate ValueError into their typed SettingsError.
            raise ValueError("environment value exceeds JSON parser limits") from None

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

        prepared_values = cast(dict[str, object], prepared).copy()
        _decode_integer_fields(prepared_values, "memory_limit_mb")
        return prepared_values

    def explode_env_vars(
        self, field_name: str, field: FieldInfo, env_vars: Mapping[str, str | None]
    ) -> dict[str, Any]:
        values = super().explode_env_vars(field_name, field, env_vars)
        if field_name == "slowpics":
            # Decode only individual environment keys, before pydantic-settings
            # merges them over any whole-section JSON value.
            _decode_integer_fields(values, "tmdb_id", "remove_after_days")
            is_hentai = values.get("is_hentai")
            if is_hentai in ("true", "false"):
                values["is_hentai"] = is_hentai == "true"
        return values


def _decode_integer_fields(values: dict[str, object], *keys: str) -> None:
    for key in keys:
        raw_value = values.get(key)
        if isinstance(raw_value, str):
            # Let the strict model report invalid or overlong integers.
            with suppress(ValueError):
                values[key] = int(raw_value)


__all__ = ["EnvironmentSettingsSource", "TomlConfigSettingsSourceNoBOM"]
