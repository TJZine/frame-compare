"""Secret-safe serialization for generated configuration files."""

from __future__ import annotations

from typing import Literal, cast

from frame_compare.config.schema import ConfigSchema


def strip_nonpersistable_config_values(payload: object) -> None:
    """Remove secret values that generated configuration must never contain."""
    if not isinstance(payload, dict):
        return
    config_payload = cast("dict[object, object]", payload)
    slowpics = config_payload.get("slowpics")
    if isinstance(slowpics, dict):
        cast("dict[object, object]", slowpics).pop("webhook_url", None)
    tmdb = config_payload.get("tmdb")
    if isinstance(tmdb, dict):
        cast("dict[object, object]", tmdb).pop("api_key", None)


def dump_config_with_explicit_color(
    config: ConfigSchema,
    *,
    mode: Literal["python", "json"] = "python",
    exclude_none: bool = False,
) -> dict[str, object]:
    """Dump full defaults while preserving preset-controlled color field presence.

    These four defaults are placeholders for the selected tonemap preset, rather
    than overrides, unless authored explicitly (even when equal to the default).
    Use the same representation for merging and persistence so revalidation does
    not turn those placeholders into manual overrides.
    """
    data = cast("dict[str, object]", config.model_dump(mode=mode, exclude_none=exclude_none))
    color = cast("dict[str, object]", data["color"])
    for field in ("target_nits", "tone_curve", "gamma_lift", "contrast_recovery"):
        if field not in config.color.model_fields_set:
            color.pop(field, None)
    return data


def dump_config_for_persistence(config: ConfigSchema) -> dict[str, object]:
    """Return TOML-ready config data without runtime secret values."""
    data = dump_config_with_explicit_color(config, mode="json", exclude_none=True)
    strip_nonpersistable_config_values(data)
    return data


__all__ = [
    "dump_config_for_persistence",
    "dump_config_with_explicit_color",
    "strip_nonpersistable_config_values",
]
