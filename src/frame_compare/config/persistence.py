"""Secret-safe serialization for generated configuration files."""

from __future__ import annotations

from typing import cast

from frame_compare.config.schema import ConfigSchema


def strip_nonpersistable_config_values(payload: object) -> None:
    """Remove secret values that generated configuration must never contain."""
    if not isinstance(payload, dict):
        return
    slowpics = cast("dict[object, object]", payload).get("slowpics")
    if isinstance(slowpics, dict):
        cast("dict[object, object]", slowpics).pop("webhook_url", None)


def dump_config_for_persistence(config: ConfigSchema) -> dict[str, object]:
    """Return TOML-ready config data without runtime secret values."""
    data = cast(
        "dict[str, object]",
        config.model_dump(mode="json", exclude_none=True),
    )
    strip_nonpersistable_config_values(data)
    return data


__all__ = ["dump_config_for_persistence", "strip_nonpersistable_config_values"]
