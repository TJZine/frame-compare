"""Environment flag helpers."""

from __future__ import annotations

from typing import Any

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


def env_flag_enabled(value: Any) -> bool:
    """Return ``True`` when *value* represents an enabled environment flag."""
    if value is None:
        return False
    if isinstance(value, bytes):
        try:
            text = value.decode()
        except UnicodeDecodeError:
            text = value.decode(errors="ignore")
    else:
        text = str(value)
    normalized = text.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return False


__all__ = ["env_flag_enabled"]
