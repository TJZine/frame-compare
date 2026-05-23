"""Frame Compare base error types and common core exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    from collections.abc import Sequence

type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
type ErrorDetails = dict[str, JSONValue]


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
        # cast to list of objects to iterate safely
        val_list = cast("list[object]", value)
        return [_to_json_value(v) for v in val_list]
    if isinstance(value, dict):
        # cast to dict of objects to iterate safely
        val_dict = cast("dict[object, object]", value)
        return {str(k): _to_json_value(v) for k, v in val_dict.items()}
    return str(value)


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


# ─── 3.2 Dependency Errors (FC-2xxx) ───────────────────────────────────────────


class DependencyError(FrameCompareError):
    """Base class for dependency failures (VapourSynth, FFmpeg, plugins)."""


class DoviToolNotFoundError(DependencyError):
    """dovi_tool binary not found (FC-2007)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2007",
                name="DOVI_TOOL_NOT_FOUND",
                message="dovi_tool binary not found",
                hint="Install dovi_tool and add to PATH or config",
            )
        )


class PythonVersionError(DependencyError):
    """Unsupported Python version (FC-2010)."""

    def __init__(self, current_version: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2010",
                name="PYTHON_VERSION_ERROR",
                message=f"Python version {current_version} not supported",
                hint="Use Python 3.13+",
                details={"current_version": current_version},
            )
        )


# ─── 3.3 Input Errors (FC-3xxx) ────────────────────────────────────────────────


class InputError(FrameCompareError):
    """Base class for invalid input/arguments."""


class VideoOpenError(InputError):
    """Failed to open video file (FC-3002)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3002",
                name="VIDEO_OPEN_ERROR",
                message=f"Failed to open video: {path}",
                hint="Check file permissions and format",
                details={"path": str(path)},
            )
        )


class VideoCorruptError(InputError):
    """Video file is corrupt/unreadable (FC-3003)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3003",
                name="VIDEO_CORRUPT",
                message=f"Video file corrupt: {path}",
                hint="Re-encode or check source integrity",
                details={"path": str(path)},
            )
        )


class IncompatibleVideosError(InputError):
    """Videos differ in dimensions/format (FC-3005)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3005",
                name="INCOMPATIBLE_VIDEOS",
                message=f"Videos incompatible: {reason}",
                hint="Ensure all videos match dimensions/colorspace",
                details={"reason": reason},
            )
        )


class DirectoryNotWritableError(InputError):
    """Cannot write to directory (FC-3007)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3007",
                name="DIRECTORY_NOT_WRITABLE",
                message=f"Directory not writable: {path}",
                hint="Check filesystem permissions",
                details={"path": str(path)},
            )
        )


class FileTooLargeError(InputError):
    """File exceeds size limit (FC-3008)."""

    def __init__(self, path: Path, size: int, limit: int) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3008",
                name="FILE_TOO_LARGE",
                message=f"File {path} too large ({size} > {limit})",
                hint="Use smaller file or increase limit",
                details={"path": str(path), "size": size, "limit": limit},
            )
        )


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


# ─── 3.4 Processing Errors (FC-4xxx) ───────────────────────────────────────────


class ProcessingError(FrameCompareError):
    """Base class for pipeline failures."""


class ProcessingOutOfMemoryError(ProcessingError):
    """OOM during processing (FC-4010)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4010",
                name="MEMORY_ERROR",
                message="Out of memory during processing",
                hint="Reduce thread count or frame count",
            )
        )


class ProcessingTimeoutError(ProcessingError):
    """Operation timed out (FC-4011)."""

    def __init__(self, operation: str, timeout: float) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4011",
                name="TIMEOUT_ERROR",
                message=f"Operation '{operation}' timed out after {timeout}s",
                hint="Increase timeout in config",
                details={"operation": operation, "timeout": timeout},
            )
        )


class DoviError(ProcessingError):
    """Dolby Vision processing error (FC-4018)."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4018",
                name="DOVI_ERROR",
                message=f"Dolby Vision error for {path}: {reason}",
                hint="Check RPU validity or dovi_tool version",
                details={"path": str(path), "reason": reason},
            )
        )


# ─── 3.5 Network Errors (FC-5xxx) ──────────────────────────────────────────────


class NetworkError(FrameCompareError):
    """Base class for network failures."""


# ─── 3.6 Internal Errors (FC-9xxx) ─────────────────────────────────────────────


class InternalError(FrameCompareError):
    """Base class for bugs/invariants."""


class GenericInternalError(InternalError):
    """Unclassified internal error (FC-9001)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-9001",
                name="INTERNAL_ERROR",
                message=f"Internal error: {details}",
                hint="Report this bug",
                details={"reason": details},
            )
        )


class InvariantViolationError(InternalError):
    """Invariant violation (FC-9002)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-9002",
                name="ASSERTION_ERROR",
                message=f"Assertion failed: {details}",
                hint="Report this bug",
                details={"assertion": details},
            )
        )


class UnexpectedStateError(InternalError):
    """State machine violation (FC-9003)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-9003",
                name="UNEXPECTED_STATE",
                message=f"Unexpected state: {details}",
                hint="Report this bug",
                details={"state": details},
            )
        )
