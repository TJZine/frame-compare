"""Shared Frame Compare error types and formatting helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit, urlunsplit

type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
type ErrorDetails = dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Structured error information."""

    code: str
    name: str
    message: str
    details: ErrorDetails | None = None
    hint: str | None = None
    cause: BaseException | None = None

    def to_dict(self) -> dict[str, JSONValue]:
        result: dict[str, JSONValue] = {
            "code": self.code,
            "name": self.name,
            "message": self.message,
        }
        if self.hint:
            result["hint"] = self.hint
        if self.details:
            result["details"] = self.details
        return result


class FrameCompareError(Exception):
    """Base exception for all Frame Compare errors."""

    def __init__(self, context: ErrorContext) -> None:
        self.context = context
        super().__init__(context.message)

    @property
    def code(self) -> str:
        return self.context.code

    @property
    def name(self) -> str:
        return self.context.name

    @property
    def hint(self) -> str | None:
        return self.context.hint

    def __str__(self) -> str:
        base = f"[{self.code}] {self.context.message}"
        if self.hint:
            base += f"\nHint: {self.hint}"
        return base

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.context!r})"


class DependencyError(FrameCompareError):
    """Base class for dependency failures (VapourSynth, FFmpeg, plugins)."""


class InputError(FrameCompareError):
    """Base class for invalid input/arguments."""


class ProcessingError(FrameCompareError):
    """Base class for pipeline failures."""


class NetworkError(FrameCompareError):
    """Base class for network failures."""


class PathEscapesRootError(InputError):
    """Path traversal attempt detected (FC-3009)."""

    def __init__(self, path: Path, root: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3009",
                name="PATH_ESCAPES_ROOT",
                message=f"Path {path} escapes root {root}",
                hint="Do not use .. in paths",
                details={"path": str(path), "root": str(root)},
            )
        )


# Diagnostic values need little nesting. Leave ample recursion headroom for
# owner-specific redaction and the final JSON encoder, regardless of input depth.
_MAX_ERROR_VALUE_DEPTH = 16


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


def _to_json_value(value: object, *, depth: int = 0) -> JSONValue:
    """Convert a diagnostic value, omitting contents beyond a bounded depth."""
    if depth >= _MAX_ERROR_VALUE_DEPTH:
        return "<nested value omitted>"
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        val_list = cast("list[object]", value)
        return [_to_json_value(v, depth=depth + 1) for v in val_list]
    if isinstance(value, dict):
        val_dict = cast("dict[object, object]", value)
        return {str(k): _to_json_value(v, depth=depth + 1) for k, v in val_dict.items()}
    return str(value)


__all__ = [
    "DependencyError",
    "ErrorContext",
    "ErrorDetails",
    "FrameCompareError",
    "InputError",
    "JSONValue",
    "NetworkError",
    "PathEscapesRootError",
    "ProcessingError",
    "normalize_pydantic_errors",
    "redact_url_for_error",
]
