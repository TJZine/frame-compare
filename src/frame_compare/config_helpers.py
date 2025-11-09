"""Shared helpers for interpreting configuration and environment flags."""

from __future__ import annotations

from typing import Any

__all__ = ["env_flag_enabled", "coerce_config_flag"]


def env_flag_enabled(value: str | None) -> bool:
    """Interpret typical truthy strings from environment variables."""

    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def coerce_config_flag(value: Any) -> bool:
    """Normalise booleans that may be provided as strings or numbers."""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "enabled", "on"}:
            return True
        if lowered in {"false", "no", "0", "disabled", "off"}:
            return False
    return bool(value)

