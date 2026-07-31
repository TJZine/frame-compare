"""Shared configuration utilities."""

from __future__ import annotations

from typing import cast


def deep_merge(base: dict[str, object], updates: dict[str, object]) -> dict[str, object]:
    """Deep merge two dicts. Updates take precedence over base."""
    result: dict[str, object] = dict(base)
    for key, value in updates.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            result[key] = deep_merge(
                cast(dict[str, object], base_value),
                cast(dict[str, object], value),
            )
        else:
            result[key] = value
    return result
