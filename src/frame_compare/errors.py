"""Stable facade for Frame Compare shared error types."""

from __future__ import annotations

from frame_compare.error_categories import (
    DependencyError,
    InputError,
    NetworkError,
    ProcessingError,
)
from frame_compare.error_context import (
    ErrorContext,
    ErrorDetails,
    FrameCompareError,
    JSONValue,
)
from frame_compare.error_formatting import normalize_pydantic_errors, redact_url_for_error
from frame_compare.error_input import PathEscapesRootError

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
