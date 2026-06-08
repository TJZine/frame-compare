"""Stable facade for Frame Compare shared error types."""

from __future__ import annotations

from frame_compare.error_categories import (
    DependencyError,
    InputError,
    InternalError,
    NetworkError,
    ProcessingError,
)
from frame_compare.error_context import (
    ErrorContext,
    ErrorDetails,
    FrameCompareError,
    JSONValue,
)
from frame_compare.error_dependency import PythonVersionError
from frame_compare.error_formatting import normalize_pydantic_errors, redact_url_for_error
from frame_compare.error_input import (
    DirectoryNotWritableError,
    FileTooLargeError,
    IncompatibleVideosError,
    PathEscapesRootError,
    VideoCorruptError,
    VideoOpenError,
)
from frame_compare.error_internal import (
    GenericInternalError,
    InvariantViolationError,
    UnexpectedStateError,
)
from frame_compare.error_processing import ProcessingOutOfMemoryError, ProcessingTimeoutError

__all__ = [
    "DependencyError",
    "DirectoryNotWritableError",
    "ErrorContext",
    "ErrorDetails",
    "FileTooLargeError",
    "FrameCompareError",
    "GenericInternalError",
    "IncompatibleVideosError",
    "InputError",
    "InternalError",
    "InvariantViolationError",
    "JSONValue",
    "NetworkError",
    "PathEscapesRootError",
    "ProcessingError",
    "ProcessingOutOfMemoryError",
    "ProcessingTimeoutError",
    "PythonVersionError",
    "UnexpectedStateError",
    "VideoCorruptError",
    "VideoOpenError",
    "normalize_pydantic_errors",
    "redact_url_for_error",
]
