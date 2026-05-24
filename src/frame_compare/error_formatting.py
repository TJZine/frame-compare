"""Error payload normalization and redaction helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from urllib.parse import urlsplit, urlunsplit

from frame_compare.error_context import JSONValue


def redact_url_for_error(url: str) -> str:
    """Remove sensitive URL components before exposing them in public errors."""
    parts = urlsplit(url)
    host = parts.hostname
    if host is None:
        return urlunsplit((parts.scheme, "", parts.path, "", ""))

    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def normalize_pydantic_errors(
    errors: Sequence[dict[str, object]],
) -> list[dict[str, JSONValue]]:
    """Convert Pydantic validation error payloads to JSONValue-safe format."""
    result: list[dict[str, JSONValue]] = []
    for err in errors:
        safe_err: dict[str, JSONValue] = {}
        for key, value in err.items():
            safe_err[key] = _to_json_value(value)
        result.append(safe_err)
    return result


def _to_json_value(value: object) -> JSONValue:
    """Recursively convert a value to JSONValue."""
    if value is None:
        return None
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        val_list = cast("list[object]", value)
        return [_to_json_value(v) for v in val_list]
    if isinstance(value, dict):
        val_dict = cast("dict[object, object]", value)
        return {str(k): _to_json_value(v) for k, v in val_dict.items()}
    return str(value)


__all__ = [
    "normalize_pydantic_errors",
    "redact_url_for_error",
]
