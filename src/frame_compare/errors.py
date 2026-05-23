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


class FFmpegNotFoundError(DependencyError):
    """FFmpeg binary not found (FC-2005)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2005",
                name="FFMPEG_NOT_FOUND",
                message="FFmpeg binary not found in PATH",
                hint="Install FFmpeg and add to system PATH",
            )
        )


class FFmpegError(DependencyError):
    """FFmpeg execution failed (FC-2006)."""

    def __init__(self, stderr: str, returncode: int) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2006",
                name="FFMPEG_ERROR",
                message=f"FFmpeg failed with exit code {returncode}",
                hint="Check input file validity or codec support",
                details={"returncode": returncode, "stderr": stderr},
            )
        )


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


class NoVideosFoundError(InputError):
    """No video files found in directory (FC-3001)."""

    def __init__(self, path: Path, patterns: list[str] | None = None) -> None:
        self.path = path
        self.patterns: list[str] = patterns or []
        super().__init__(
            ErrorContext(
                code="FC-3001",
                name="NO_VIDEOS_FOUND",
                message=f"No video files found in: {path}",
                hint="Check directory path or file extensions",
                details={"path": str(path), "patterns": cast(JSONValue, self.patterns)},
            )
        )


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


class DirectoryNotFoundError(InputError):
    """Output/cache directory missing (FC-3006)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3006",
                name="DIRECTORY_NOT_FOUND",
                message=f"Directory not found: {path}",
                hint="Create directory or check path",
                details={"path": str(path)},
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


class InputDiscoveryError(InputError):
    """Failed to discover inputs due to filesystem error (FC-3010)."""

    def __init__(self, path: Path, cause: OSError) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3010",
                name="INPUT_DISCOVERY_ERROR",
                message=f"Failed to discover inputs in {path}: {cause}",
                hint="Check directory permissions and path existence",
                details={"path": str(path), "error": str(cause)},
                cause=cause,
            )
        )
        self.path = path


# ─── 3.4 Processing Errors (FC-4xxx) ───────────────────────────────────────────


class ProcessingError(FrameCompareError):
    """Base class for pipeline failures."""


class FrameExtractionError(ProcessingError):
    """Failed to extract specific frame (FC-4001)."""

    def __init__(self, frame_number: int, clip_name: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4001",
                name="FRAME_EXTRACTION_ERROR",
                message=f"Failed to extract frame {frame_number} from {clip_name}",
                hint="Check source reliability/seekability",
                details={"frame": frame_number, "clip": clip_name},
            )
        )


class MetricsCalculationError(ProcessingError):
    """Failed to calculate metrics (FC-4002)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4002",
                name="METRICS_CALCULATION_ERROR",
                message=f"Metrics calculation failed: {reason}",
                hint="Check input format compatibility",
                details={"reason": reason},
            )
        )


class RenderError(ProcessingError):
    """Composition/image encoding failure (FC-4004)."""

    def __init__(self, reason: str | None = None, details: ErrorDetails | None = None) -> None:
        message = "Final render composition failed"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(
            ErrorContext(
                code="FC-4004",
                name="RENDER_ERROR",
                message=message,
                hint=(
                    "Check clip pixel format/bit depth compatibility (screenshots require RGB24/RGBA8) "
                    "and verify the output path is writable"
                ),
                details=details,
            )
        )


class CacheCorruptionError(ProcessingError):
    """Cache file invalid/unreadable (FC-4006)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4006",
                name="CACHE_CORRUPTION",
                message=f"Cache file corrupted: {path}",
                hint="Clear cache directory",
                details={"path": str(path)},
            )
        )


class CacheVersionMismatchError(ProcessingError):
    """Cache schema version mismatch (FC-4007)."""

    def __init__(self, found: str, expected: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4007",
                name="CACHE_VERSION_MISMATCH",
                message=f"Cache version mismatch (found {found}, expected {expected})",
                hint="Clear cache directory",
                details={"found": found, "expected": expected},
            )
        )


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


class EncodingError(ProcessingError):
    """Output file encoding failed (FC-4013)."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4013",
                name="ENCODING_ERROR",
                message=f"Failed to encode output {path}: {reason}",
                hint="Check disk space or write permissions",
                details={"path": str(path), "reason": reason},
            )
        )


class OverlayError(ProcessingError):
    """Failed to render text overlay (FC-4014)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4014",
                name="OVERLAY_ERROR",
                message=f"Overlay rendering failed: {reason}",
                hint="Check font availability",
                details={"reason": reason},
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


class AnalysisError(ProcessingError):
    """Marker base for analysis failures."""


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
