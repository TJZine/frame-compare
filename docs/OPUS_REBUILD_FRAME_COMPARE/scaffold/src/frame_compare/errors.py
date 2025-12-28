"""Base error hierarchy for Frame Compare.

All Frame Compare errors inherit from FrameCompareError and include:
- A unique numeric error code (e.g., "FC-1001")
- A stable symbolic name (e.g., "CONFIG_NOT_FOUND")
- A human-readable message
- An optional hint for resolution
- Optional structured details

Example:
    try:
        load_config(path)
    except ConfigNotFoundError as e:
        print(f"Error [{e.code}]: {e.message}")
        if e.hint:
            print(f"Hint: {e.hint}")
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
type ErrorDetails = Mapping[str, JSONValue]

# Keys that should be redacted when serializing errors
SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "password",
        "token",
        "secret",
        "authorization",
        "auth",
        "bearer",
        "credential",
        "credentials",
    }
)


def _deep_redact(value: JSONValue, key: str | None = None) -> JSONValue:
    """Recursively redact sensitive values in nested structures."""
    # If the key is sensitive, redact regardless of value type
    if key is not None and key.lower() in SENSITIVE_KEYS:
        return "[REDACTED]"

    # Recursively process dicts
    if isinstance(value, dict):
        return {k: _deep_redact(v, k) for k, v in value.items()}

    # Recursively process lists
    if isinstance(value, list):
        return [_deep_redact(item) for item in value]

    return value


# Registry of all error classes that opt into registration via _REGISTER = True
ERROR_REGISTRY: dict[str, type[FrameCompareError]] = {}


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Structured error context.

    Attributes:
        code: Unique numeric error code (e.g., "FC-1001")
        name: Stable symbolic error name (e.g., "CONFIG_NOT_FOUND")
        message: Human-readable error message
        details: Optional structured details for debugging
        hint: Optional actionable hint for resolution
        cause: Optional underlying exception
    """

    code: str
    name: str
    message: str
    details: ErrorDetails | None = None
    hint: str | None = None
    cause: BaseException | None = None

    def to_dict(self) -> dict[str, JSONValue]:
        """Convert to JSON-serializable dictionary with secrets redacted."""
        result: dict[str, JSONValue] = {
            "code": self.code,
            "name": self.name,
            "message": self.message,
        }
        if self.hint:
            result["hint"] = self.hint
        if self.details:
            # Deep redact sensitive keys at any nesting level
            result["details"] = _deep_redact(dict(self.details))
        return result


class FrameCompareError(Exception):
    """Base exception for all Frame Compare errors.

    All errors in Frame Compare inherit from this class and include
    structured context via ErrorContext.

    Leaf error classes that set _REGISTER = True are auto-registered
    in ERROR_REGISTRY by their error code for contract enforcement.

    Example:
        raise FrameCompareError(ErrorContext(
            code="FC-9001",
            message="Something went wrong",
            hint="Try again or report this bug",
        ))
    """

    # Class-level identity (overridden by leaf classes that opt into registration)
    CODE: ClassVar[str | None] = None
    NAME: ClassVar[str | None] = None
    EXIT_CODE: ClassVar[int | None] = None
    _REGISTER: ClassVar[bool] = False

    def __init__(self, context: ErrorContext) -> None:
        self.context = context
        super().__init__(context.message)

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls._REGISTER:
            if cls.CODE is None or cls.EXIT_CODE is None:
                raise ValueError(
                    f"{cls.__name__} must define CODE and EXIT_CODE when _REGISTER=True"
                )
            if cls.CODE in ERROR_REGISTRY:
                raise ValueError(f"Duplicate error code: {cls.CODE}")
            ERROR_REGISTRY[cls.CODE] = cls

    @property
    def code(self) -> str:
        """Unique error code."""
        return self.context.code

    @property
    def name(self) -> str:
        """Stable symbolic error name."""
        return self.context.name

    @property
    def message(self) -> str:
        """Human-readable message."""
        return self.context.message

    @property
    def hint(self) -> str | None:
        """Optional resolution hint."""
        return self.context.hint

    @property
    def details(self) -> ErrorDetails | None:
        """Optional structured details."""
        return self.context.details


# =============================================================================
# Configuration Errors (FC-1xxx)
# =============================================================================


class ConfigError(FrameCompareError):
    """Base class for configuration errors."""


class ConfigNotFoundError(ConfigError):
    """Configuration file not found."""

    def __init__(self, path: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1001",
                name="CONFIG_NOT_FOUND",
                message=f"Configuration file not found: {path}",
                details={"path": path},
                hint="Run 'frame-compare wizard' or create config/config.toml",
            )
        )


class ConfigParseError(ConfigError):
    """Configuration file parsing failed."""

    def __init__(self, path: str, error: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1002",
                name="CONFIG_PARSE_ERROR",
                message=f"Failed to parse {path}: {error}",
                details={"path": path, "error": error},
                hint="Check TOML syntax at the indicated line",
            )
        )


class ConfigValidationError(ConfigError):
    """Configuration validation failed."""

    def __init__(self, errors: list[dict[str, JSONValue]]) -> None:
        fields = [str(e.get("loc", ["unknown"])[-1]) for e in errors]
        super().__init__(
            ErrorContext(
                code="FC-1003",
                name="CONFIG_VALIDATION_ERROR",
                message=f"Invalid configuration: {', '.join(fields)}",
                details={"errors": errors},
                hint="Check field types and constraints",
            )
        )


# =============================================================================
# Dependency Errors (FC-2xxx)
# =============================================================================


class DependencyError(FrameCompareError):
    """Base class for dependency errors."""


class VapourSynthNotFoundError(DependencyError):
    """VapourSynth not installed or importable."""

    def __init__(self, message: str = "VapourSynth not installed") -> None:
        super().__init__(
            ErrorContext(
                code="FC-2001",
                name="VAPOURSYNTH_NOT_FOUND",
                message=message,
                hint="Use Docker deployment or install VapourSynth R72+",
            )
        )


class VapourSynthError(DependencyError):
    """VapourSynth runtime error."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2002",
                name="VAPOURSYNTH_ERROR",
                message=f"VapourSynth error: {details}",
                details={"details": details},
                hint="Run 'frame-compare doctor' for diagnostics",
            )
        )


class PluginNotFoundError(DependencyError):
    """VapourSynth plugin not found."""

    def __init__(self, plugin: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2003",
                name="PLUGIN_NOT_FOUND",
                message=f"VapourSynth plugin not found: {plugin}",
                details={"plugin": plugin},
                hint=f"Install {plugin} or use Docker deployment",
            )
        )


class FFmpegNotFoundError(DependencyError):
    """FFmpeg not found in PATH."""

    def __init__(self, message: str = "FFmpeg not found in PATH") -> None:
        super().__init__(
            ErrorContext(
                code="FC-2005",
                name="FFMPEG_NOT_FOUND",
                message=message,
                hint="Install FFmpeg 6.0+",
            )
        )


class FFmpegError(DependencyError):
    """FFmpeg runtime error."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2006",
                name="FFMPEG_ERROR",
                message=f"FFmpeg error: {details}",
                details={"details": details},
                hint="Check FFmpeg output for details",
            )
        )


# =============================================================================
# Input Errors (FC-3xxx)
# =============================================================================


class InputError(FrameCompareError):
    """Base class for input errors."""


class NoVideosFoundError(InputError):
    """No video files found in input directory."""

    def __init__(self, path: str, patterns: list[str] | None = None) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3001",
                name="NO_VIDEOS_FOUND",
                message=f"No video files found in {path}",
                details={"path": path, "patterns": patterns or ["*.mkv", "*.mp4"]},
                hint="Place *.mkv, *.mp4 files in the input directory",
            )
        )


class VideoOpenError(InputError):
    """Failed to open video file."""

    def __init__(self, path: str, reason: str | None = None) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3002",
                name="VIDEO_OPEN_ERROR",
                message=f"Failed to open video: {path}",
                details={"path": path, "reason": reason},
                hint="Check file path and format",
            )
        )


class InvalidPathError(InputError):
    """Path contains invalid characters like null bytes (FC-3012)."""

    CODE: ClassVar[str] = "FC-3012"
    NAME: ClassVar[str] = "INVALID_PATH"
    EXIT_CODE: ClassVar[int] = 4
    _REGISTER: ClassVar[bool] = True

    def __init__(self, path: str, reason: str | None = None) -> None:
        super().__init__(
            ErrorContext(
                code=self.CODE,
                name=self.NAME,
                message=f"Invalid path: {path}",
                details={"path": path[:100], "reason": reason},
                hint="Remove invalid characters (null bytes, control chars) from path",
            )
        )


class PathEscapesRootError(InputError):
    """Path escapes workspace root via traversal or symlink (FC-3009)."""

    CODE: ClassVar[str] = "FC-3009"
    NAME: ClassVar[str] = "PATH_ESCAPES_ROOT"
    EXIT_CODE: ClassVar[int] = 4
    _REGISTER: ClassVar[bool] = True

    def __init__(self, candidate: str, root: str | None = None) -> None:
        super().__init__(
            ErrorContext(
                code=self.CODE,
                name=self.NAME,
                message=f"Path '{candidate}' escapes workspace root",
                details={"candidate": candidate, "root": root},
                hint="Use relative paths within workspace",
            )
        )


# =============================================================================
# Processing Errors (FC-4xxx)
# =============================================================================


class ProcessingError(FrameCompareError):
    """Base class for processing errors."""


class FrameExtractionError(ProcessingError):
    """Failed to extract frame from video."""

    def __init__(self, clip: str, frame: int, reason: str | None = None) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4001",
                name="FRAME_EXTRACTION_ERROR",
                message=f"Failed to extract frame {frame} from {clip}",
                details={"clip": clip, "frame": frame, "reason": reason},
                hint="Check video integrity",
            )
        )


class TonemapError(ProcessingError):
    """Tonemapping failed."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4003",
                name="TONEMAP_ERROR",
                message=f"Tonemapping failed: {reason}",
                details={"reason": reason},
                hint="Try different preset or disable tonemapping",
            )
        )


class AudioAlignmentError(ProcessingError):
    """Audio alignment failed."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4005",
                name="AUDIO_ALIGNMENT_ERROR",
                message=f"Audio alignment failed: {reason}",
                details={"reason": reason},
                hint="Try manual alignment or disable audio alignment",
            )
        )


# =============================================================================
# Network Errors (FC-5xxx)
# =============================================================================


class NetworkError(FrameCompareError):
    """Base class for network errors."""


class SlowpicsError(NetworkError):
    """slow.pics upload failed."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5002",
                name="SLOWPICS_ERROR",
                message=f"slow.pics upload failed: {reason}",
                details={"reason": reason},
                hint="Try again or use --no-upload",
            )
        )


class TmdbError(NetworkError):
    """TMDB API error."""

    def __init__(self, reason: str) -> None:
        # Sanitize reason to avoid leaking API keys in error messages
        # Replace anything that looks like an API key with [REDACTED]
        import re

        # Pattern: key=<value> or token=<value> with 16+ alnum chars
        pattern = r"(?i)(key|token|api_key|apikey)[=:]\s*['\"']?[-a-zA-Z0-9_]{16,}['\"']?"
        sanitized = re.sub(pattern, r"\1=[REDACTED]", reason)
        super().__init__(
            ErrorContext(
                code="FC-5005",
                name="TMDB_ERROR",
                message=f"TMDB API error: {sanitized}",
                details={"reason": sanitized},
                hint="Check API key or use --skip-metadata",
            )
        )


class NetworkTimeoutError(NetworkError):
    """Network request timed out."""

    def __init__(self, service: str, timeout: float) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5007",
                name="NETWORK_TIMEOUT",
                message=f"Request to {service} timed out after {timeout}s",
                details={"service": service, "timeout": timeout},
                hint="Check connection or increase timeout",
            )
        )


class HttpsRequiredError(NetworkError):
    """HTTPS required for external requests (security policy)."""

    CODE: ClassVar[str] = "FC-5010"
    NAME: ClassVar[str] = "HTTPS_REQUIRED"
    EXIT_CODE: ClassVar[int] = 6
    _REGISTER: ClassVar[bool] = True

    def __init__(self, url: str) -> None:
        super().__init__(
            ErrorContext(
                code=self.CODE,
                name=self.NAME,
                message="HTTPS required for external requests",
                details={"url": url},
                hint="External URLs must use https:// scheme",
            )
        )


class HostNotAllowedError(NetworkError):
    """Request to unauthorized host blocked (security policy)."""

    CODE: ClassVar[str] = "FC-5011"
    NAME: ClassVar[str] = "HOST_NOT_ALLOWED"
    EXIT_CODE: ClassVar[int] = 6
    _REGISTER: ClassVar[bool] = True

    def __init__(self, host: str) -> None:
        super().__init__(
            ErrorContext(
                code=self.CODE,
                name=self.NAME,
                message=f"Request blocked to unauthorized host: {host}",
                details={"host": host},
                hint="Only slow.pics and api.themoviedb.org are allowed",
            )
        )


# =============================================================================
# Internal Errors (FC-9xxx)
# =============================================================================


class InternalError(FrameCompareError):
    """Internal error - likely a bug."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-9001",
                name="INTERNAL_ERROR",
                message=f"Internal error: {details}",
                details={"error": details},
                hint="Please report this bug",
            )
        )


# =============================================================================
# Subprocess Error Aliases (for test compatibility)
# =============================================================================

# Import the actual error classes from subproc module for re-export
# These are defined in utils.subproc but tests expect them in errors module
from frame_compare.utils.subproc import (  # noqa: E402, I001
    ControlCharacterError as ControlCharInArgError,
    ShellMetacharacterError as InvalidSubprocessArgError,
)

__all__ = [
    "ERROR_REGISTRY",
    "ConfigError",
    "ConfigNotFoundError",
    "ControlCharInArgError",
    "DependencyError",
    "ErrorContext",
    "ErrorDetails",
    "FrameCompareError",
    "HostNotAllowedError",
    "HttpsRequiredError",
    "InputError",
    "InternalError",
    "InvalidPathError",
    "InvalidSubprocessArgError",
    "JSONValue",
    "NetworkError",
    "PathEscapesRootError",
    "ProcessingError",
]
