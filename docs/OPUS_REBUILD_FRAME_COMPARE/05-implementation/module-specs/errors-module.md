# Errors Module Implementation Spec

> **Module:** `frame_compare.errors`
> **Version:** 1.0
> **Priority:** P0 (Foundation)

---

## 1. Module Overview

The Errors module defines the core exception hierarchy and `ErrorContext` dataclass used throughout Frame Compare 2.0. This module is a **leaf** in the dependency graph and must not import any other `frame_compare` modules.

### 1.1 Responsibilities

- Define `ErrorContext` dataclass for structured error information
- Provide base `FrameCompareError` exception class
- Implement complete exception hierarchy by category (FC-xxxx codes)
- Provide helper functions for error formatting and exit code mapping

### 1.2 Module Structure

```text
src/frame_compare/
└── errors.py          # All error types in a single file
```

**Design Decision:** Single file module (not a package) for simplicity. All exceptions are lightweight and closely related.

---

## 2. Key Types

### 2.1 ErrorContext

```python
from dataclasses import dataclass
from typing import TypeAlias

# Type alias for JSON-safe values (no Any leakage in public API)
JSONValue: TypeAlias = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
ErrorDetails: TypeAlias = dict[str, JSONValue]

@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Structured error information for consistent error handling.

    Attributes:
        code: Machine-readable error code (e.g., "FC-1001")
        name: Short error name (e.g., "CONFIG_NOT_FOUND")
        message: Human-readable error description
        details: Optional structured data for debugging/logging
        hint: Optional recovery suggestion for the user
        cause: Optional underlying exception that caused this error

    Note: This is the canonical definition. The scaffold `errors.py`
    provides a reference implementation that aligns with this spec.
    """
    code: str
    name: str
    message: str
    details: ErrorDetails | None = None
    hint: str | None = None
    cause: BaseException | None = None

    def to_dict(self) -> dict[str, JSONValue]:
        """Convert to JSON-serializable dictionary."""
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
```

### 2.2 Base Exception

```python
class FrameCompareError(Exception):
    """Base exception for all Frame Compare errors.

    All subclasses MUST provide an ErrorContext with a valid FC-xxxx code.
    This enables structured logging, consistent exit codes, and user-friendly
    error messages.
    """

    def __init__(self, context: ErrorContext) -> None:
        self.context = context
        super().__init__(context.message)

    @property
    def code(self) -> str:
        """Machine-readable error code."""
        return self.context.code

    @property
    def name(self) -> str:
        """Short error name."""
        return self.context.name

    @property
    def hint(self) -> str | None:
        """Recovery suggestion."""
        return self.context.hint

    def __str__(self) -> str:
        base = f"[{self.code}] {self.context.message}"
        if self.hint:
            base += f"\nHint: {self.hint}"
        return base

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.context!r})"
```

---

## 3. Exception Hierarchy

### 3.1 Configuration Errors (FC-1xxx) — Exit Code 2

```python
class ConfigError(FrameCompareError):
    """Base class for configuration errors."""

class ConfigNotFoundError(ConfigError):
    """Config file not found (FC-1001)."""

    def __init__(self, path: Path) -> None:
        super().__init__(ErrorContext(
            code="FC-1001",
            name="CONFIG_NOT_FOUND",
            message=f"Configuration file not found: {path}",
            hint="Run 'frame-compare wizard' or create config/config.toml",
            details={"path": str(path)},
        ))
        self.path = path

class ConfigParseError(ConfigError):
    """TOML parsing failed (FC-1002)."""

    def __init__(self, path: Path, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-1002",
            name="CONFIG_PARSE_ERROR",
            message=f"Failed to parse {path}: {details}",
            hint="Check TOML syntax at the indicated line",
            details={"path": str(path), "parse_error": details},
        ))
        self.path = path

class ConfigValidationError(ConfigError):
    """Config validation failed (FC-1003)."""

    def __init__(self, errors: list[dict[str, JSONValue]]) -> None:
        fields = [str(e.get("loc", ["unknown"])[-1]) for e in errors]
        super().__init__(ErrorContext(
            code="FC-1003",
            name="CONFIG_VALIDATION_ERROR",
            message=f"Invalid configuration: {', '.join(fields)}",
            hint="Check field types and constraints",
            details={"validation_errors": errors},
        ))
        self.validation_errors = errors

class PresetNotFoundError(ConfigError):
    """Preset not found (FC-1004)."""

    def __init__(self, name: str) -> None:
        super().__init__(ErrorContext(
            code="FC-1004",
            name="PRESET_NOT_FOUND",
            message=f"Preset not found: {name}",
            hint="Run 'frame-compare preset list' to see available",
            details={"preset_name": name},
        ))
        self.preset_name = name

class PresetInvalidError(ConfigError):
    """Invalid preset file (FC-1005)."""

    def __init__(self, path: Path, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-1005",
            name="PRESET_INVALID",
            message=f"Invalid preset file: {path}",
            hint="Preset TOML syntax error",
            details={"path": str(path), "error": details},
        ))
        self.path = path
```

### 3.2 Dependency Errors (FC-2xxx) — Exit Code 3

```python
class DependencyError(FrameCompareError):
    """Base class for dependency errors."""

class VapourSynthNotFoundError(DependencyError):
    """VapourSynth not installed (FC-2001)."""

    def __init__(self) -> None:
        super().__init__(ErrorContext(
            code="FC-2001",
            name="VAPOURSYNTH_NOT_FOUND",
            message="VapourSynth not installed",
            hint="Use Docker deployment or install VapourSynth R72+",
        ))

class VapourSynthError(DependencyError):
    """VapourSynth runtime error (FC-2002)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-2002",
            name="VAPOURSYNTH_ERROR",
            message=f"VapourSynth error: {details}",
            hint="Run 'frame-compare doctor' for diagnostics",
            details={"error": details},
        ))

class PluginNotFoundError(DependencyError):
    """VapourSynth plugin not found (FC-2003)."""

    def __init__(self, plugin: str) -> None:
        super().__init__(ErrorContext(
            code="FC-2003",
            name="PLUGIN_NOT_FOUND",
            message=f"VapourSynth plugin not found: {plugin}",
            hint=f"Install {plugin} or use Docker deployment",
            details={"plugin": plugin},
        ))
        self.plugin = plugin

class LibplaceboError(DependencyError):
    """libplacebo error (FC-2004)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-2004",
            name="LIBPLACEBO_ERROR",
            message=f"libplacebo error: {details}",
            hint="Verify libplacebo installation or use FFmpeg fallback",
            details={"error": details},
        ))

class FFmpegNotFoundError(DependencyError):
    """FFmpeg not found (FC-2005)."""

    def __init__(self) -> None:
        super().__init__(ErrorContext(
            code="FC-2005",
            name="FFMPEG_NOT_FOUND",
            message="FFmpeg not found in PATH",
            hint="Install FFmpeg 6.0+",
        ))

class FFmpegError(DependencyError):
    """FFmpeg error (FC-2006)."""

    def __init__(self, details: str, returncode: int | None = None) -> None:
        super().__init__(ErrorContext(
            code="FC-2006",
            name="FFMPEG_ERROR",
            message=f"FFmpeg error: {details}",
            hint="Check FFmpeg output for details",
            details={"error": details, "returncode": returncode},
        ))

class DoviToolNotFoundError(DependencyError):
    """dovi_tool not found (FC-2007)."""

    def __init__(self) -> None:
        super().__init__(ErrorContext(
            code="FC-2007",
            name="DOVI_TOOL_NOT_FOUND",
            message="dovi_tool not found",
            hint="Install dovi_tool for Dolby Vision support",
        ))

class VSPreviewNotFoundError(DependencyError):
    """VSPreview not found (FC-2008)."""

    def __init__(self) -> None:
        super().__init__(ErrorContext(
            code="FC-2008",
            name="VSPREVIEW_NOT_FOUND",
            message="VSPreview not installed",
            hint="Install vspreview (and a Qt backend) for interactive alignment verification",
        ))

class PythonVersionError(DependencyError):
    """Python version not supported (FC-2010)."""

    def __init__(self, version: str) -> None:
        super().__init__(ErrorContext(
            code="FC-2010",
            name="PYTHON_VERSION_ERROR",
            message=f"Python version {version} not supported",
            hint="Use Python 3.13+",
            details={"version": version},
        ))
```

### 3.3 Input Errors (FC-3xxx) — Exit Code 4

```python
class InputError(FrameCompareError):
    """Base class for input errors."""

class NoVideosFoundError(InputError):
    """No videos found (FC-3001)."""

    def __init__(self, path: Path, patterns: list[str] | None = None) -> None:
        super().__init__(ErrorContext(
            code="FC-3001",
            name="NO_VIDEOS_FOUND",
            message=f"No video files found in {path}",
            hint="Place *.mkv, *.mp4 files in the input directory",
            details={"path": str(path), "patterns": patterns or []},
        ))
        self.path = path

class VideoOpenError(InputError):
    """Failed to open video (FC-3002)."""

    def __init__(self, path: Path, reason: str | None = None) -> None:
        msg = f"Failed to open video: {path}"
        if reason:
            msg += f" ({reason})"
        super().__init__(ErrorContext(
            code="FC-3002",
            name="VIDEO_OPEN_ERROR",
            message=msg,
            hint="Check file path and format",
            details={"path": str(path), "reason": reason},
        ))
        self.path = path

class VideoCorruptError(InputError):
    """Video file appears corrupt (FC-3003)."""

    def __init__(self, path: Path) -> None:
        super().__init__(ErrorContext(
            code="FC-3003",
            name="VIDEO_CORRUPT",
            message=f"Video file appears corrupt: {path}",
            hint="Try re-encoding or different source",
            details={"path": str(path)},
        ))
        self.path = path

class InsufficientFramesError(InputError):
    """Video has insufficient frames (FC-3004)."""

    def __init__(self, path: Path, count: int, required: int) -> None:
        super().__init__(ErrorContext(
            code="FC-3004",
            name="INSUFFICIENT_FRAMES",
            message=f"Video has {count} frames, need at least {required}",
            hint="Use a longer video or reduce frame_count",
            details={"path": str(path), "count": count, "required": required},
        ))
        self.path = path

class IncompatibleVideosError(InputError):
    """Videos have incompatible properties (FC-3005)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-3005",
            name="INCOMPATIBLE_VIDEOS",
            message=f"Videos have incompatible properties: {details}",
            hint="All videos must have same frame count and fps",
            details={"error": details},
        ))

class DirectoryNotFoundError(InputError):
    """Directory not found (FC-3006)."""

    def __init__(self, path: Path) -> None:
        super().__init__(ErrorContext(
            code="FC-3006",
            name="DIR_NOT_FOUND",
            message=f"Directory not found: {path}",
            hint="Create the directory or check the path",
            details={"path": str(path)},
        ))
        self.path = path

class DirectoryNotWritableError(InputError):
    """Cannot write to directory (FC-3007)."""

    def __init__(self, path: Path) -> None:
        super().__init__(ErrorContext(
            code="FC-3007",
            name="DIR_NOT_WRITABLE",
            message=f"Cannot write to directory: {path}",
            hint="Check permissions",
            details={"path": str(path)},
        ))
        self.path = path

class FileTooLargeError(InputError):
    """File exceeds size limit (FC-3008)."""

    def __init__(self, path: Path, size: int, limit: int) -> None:
        super().__init__(ErrorContext(
            code="FC-3008",
            name="FILE_TOO_LARGE",
            message=f"File exceeds size limit: {path}",
            hint="Use smaller video or increase limit",
            details={"path": str(path), "size": size, "limit": limit},
        ))
        self.path = path

class PathEscapesRootError(InputError):
    """Path escapes workspace root (FC-3009)."""

    def __init__(self, root: Path, candidate: Path) -> None:
        super().__init__(ErrorContext(
            code="FC-3009",
            name="PATH_ESCAPES_ROOT",
            message=f"Path '{candidate}' escapes workspace root '{root}'",
            hint="Use relative paths within the workspace",
            details={"root": str(root), "candidate": str(candidate)},
        ))
        self.root = root
        self.candidate = candidate
```

### 3.4 Processing Errors (FC-4xxx) — Exit Code 5

```python
class ProcessingError(FrameCompareError):
    """Base class for processing errors."""

class FrameExtractionError(ProcessingError):
    """Failed to extract frame (FC-4001)."""

    def __init__(self, frame: int, clip: str | Path) -> None:
        super().__init__(ErrorContext(
            code="FC-4001",
            name="FRAME_EXTRACTION_ERROR",
            message=f"Failed to extract frame {frame} from {clip}",
            hint="Check video integrity",
            details={"frame": frame, "clip": str(clip)},
        ))

class TonemapError(ProcessingError):
    """Tonemapping failed (FC-4003)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4003",
            name="TONEMAP_ERROR",
            message=f"Tonemapping failed: {details}",
            hint="Try different preset or disable tonemapping",
            details={"error": details},
        ))

class VSPreviewError(ProcessingError):
    """VSPreview failed to launch or run (FC-4019)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4019",
            name="VSPREVIEW_ERROR",
            message=f"VSPreview error: {details}",
            hint="Install a Qt backend (PySide6/PyQt5) and ensure a GUI backend is available",
            details={"error": details},
        ))

class AudioAlignmentError(ProcessingError):
    """Audio alignment failed (FC-4005)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4005",
            name="AUDIO_ALIGNMENT_ERROR",
            message=f"Audio alignment failed: {details}",
            hint="Try manual alignment or disable audio alignment",
            details={"error": details},
        ))

class CacheCorruptionError(ProcessingError):
    """Cache file corrupt (FC-4006)."""

    def __init__(self, path: Path) -> None:
        super().__init__(ErrorContext(
            code="FC-4006",
            name="CACHE_CORRUPTION_ERROR",
            message=f"Cache file corrupt: {path}",
            hint="Delete cache file and retry",
            details={"path": str(path)},
        ))
        self.path = path

class MetricsCalculationError(ProcessingError):
    """Failed to calculate metrics (FC-4002)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4002",
            name="METRICS_CALCULATION_ERROR",
            message=f"Failed to calculate metrics: {details}",
            hint="Check VapourSynth logs",
            details={"error": details},
        ))

class RenderError(ProcessingError):
    """Screenshot rendering failed (FC-4004)."""

    def __init__(self, details: str | None = None) -> None:
        msg = "Screenshot rendering failed"
        if details:
            msg += f": {details}"
        super().__init__(ErrorContext(
            code="FC-4004",
            name="RENDER_ERROR",
            message=msg,
            hint="Check disk space and permissions",
            details={"error": details} if details else {},
        ))

class CacheVersionMismatchError(ProcessingError):
    """Cache version mismatch (FC-4007)."""

    def __init__(self, expected: str, found: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4007",
            name="CACHE_VERSION_MISMATCH",
            message=f"Cache version mismatch (expected {expected}, found {found})",
            hint="Clear cache with --no-cache",
            details={"expected": expected, "found": found},
        ))

class MemoryError_(ProcessingError):
    """Out of memory during processing (FC-4010)."""

    def __init__(self) -> None:
        super().__init__(ErrorContext(
            code="FC-4010",
            name="MEMORY_ERROR",
            message="Out of memory during processing",
            hint="Reduce frame count or video resolution",
        ))

class TimeoutError_(ProcessingError):
    """Processing timed out (FC-4011)."""

    def __init__(self, operation: str, timeout: float) -> None:
        super().__init__(ErrorContext(
            code="FC-4011",
            name="TIMEOUT_ERROR",
            message=f"Processing timed out after {timeout}s",
            hint="Check for infinite loops or increase timeout",
            details={"operation": operation, "timeout": timeout},
        ))
```

#### Module-Level Error Aliases (FC-4xxx)

The following are convenience aliases grouping related ProcessingError subclasses by module:

```python
# Analysis module errors
class AnalysisError(ProcessingError):
    """Base class for analysis errors (FC-4xxx)."""

class SelectionError(AnalysisError):
    """Frame selection failed (FC-4012)."""

    def __init__(self, reason: str, requested: int, available: int) -> None:
        super().__init__(ErrorContext(
            code="FC-4012",
            name="SELECTION_ERROR",
            message=f"Frame selection failed: {reason}",
            hint="Reduce frame count or use different selection mode",
            details={"requested": requested, "available": available},
        ))

# Render module errors
class EncodingError(RenderError):
    """Failed to encode image (FC-4013)."""

    def __init__(self, output_path: Path, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4013",
            name="ENCODING_ERROR",
            message=f"Failed to encode image: {output_path}",
            hint="Check disk space and file permissions",
            details={"path": str(output_path), "error": details},
        ))

class OverlayError(RenderError):
    """Failed to apply overlay (FC-4014)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4014",
            name="OVERLAY_ERROR",
            message=f"Failed to apply overlay: {details}",
            hint="Check font path and image format",
            details={"error": details},
        ))

# VS module errors
class SourceLoadError(ProcessingError):
    """Failed to load video source (FC-4015)."""

    def __init__(self, path: Path, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4015",
            name="SOURCE_LOAD_ERROR",
            message=f"Failed to load video source: {path}",
            hint="Check file format and VapourSynth plugins",
            details={"path": str(path), "error": details},
        ))
```

#### Service-Level Error Aliases (FC-4xxx/FC-5xxx)

```python
# Services module errors - aliases for clearer module organization
class ServiceError(FrameCompareError):
    """Base class for service layer errors."""

class MetadataError(ServiceError):
    """Metadata extraction/lookup failed (FC-4016)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4016",
            name="METADATA_ERROR",
            message=f"Metadata operation failed: {details}",
            hint="Check file format or try --skip-metadata",
            details={"error": details},
        ))

class PublishError(ServiceError):
    """Marker base for publishing errors. Never instantiated directly.

    Concrete publish errors use NetworkError subclasses:
    - SlowpicsError (FC-5002)
    - SlowpicsRateLimitedError (FC-5003)
    - SlowpicsUnavailableError (FC-5004)
    """

class ReportError(ServiceError):
    """Report generation failed (FC-4017)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4017",
            name="REPORT_ERROR",
            message=f"Report generation failed: {details}",
            hint="Check disk space and permissions",
            details={"error": details},
        ))

class DoviError(ServiceError):
    """Dolby Vision extraction failed (FC-4018)."""

    def __init__(self, path: Path, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-4018",
            name="DOVI_ERROR",
            message=f"Dolby Vision extraction failed: {details}",
            hint="Check dovi_tool installation or use --skip-dovi",
            details={"path": str(path), "error": details},
        ))
```

### 3.5 Network Errors (FC-5xxx) — Exit Code 6

```python
class NetworkError(FrameCompareError):
    """Base class for network errors."""

class SlowpicsError(NetworkError):
    """slow.pics upload failed (FC-5002)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-5002",
            name="SLOWPICS_ERROR",
            message=f"slow.pics upload failed: {details}",
            hint="Try again or use --no-upload",
            details={"error": details},
        ))

class TmdbError(NetworkError):
    """TMDB API error (FC-5005)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-5005",
            name="TMDB_ERROR",
            message=f"TMDB API error: {details}",
            hint="Check API key or use --skip-metadata",
            details={"error": details},
        ))

class NetworkTimeoutError(NetworkError):
    """Request timed out (FC-5007)."""

    def __init__(self, service: str, timeout: float) -> None:
        super().__init__(ErrorContext(
            code="FC-5007",
            name="NETWORK_TIMEOUT",
            message=f"Request to {service} timed out after {timeout}s",
            hint="Check connection or increase timeout",
            details={"service": service, "timeout": timeout},
        ))

class NetworkUnreachableError(NetworkError):
    """Network unreachable (FC-5001)."""

    def __init__(self) -> None:
        super().__init__(ErrorContext(
            code="FC-5001",
            name="NETWORK_UNREACHABLE",
            message="Network unreachable",
            hint="Check internet connection",
        ))

class SlowpicsRateLimitedError(NetworkError):
    """slow.pics rate limited (FC-5003)."""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(ErrorContext(
            code="FC-5003",
            name="SLOWPICS_RATE_LIMITED",
            message="slow.pics rate limited",
            hint="Wait and retry",
            details={"retry_after": retry_after} if retry_after else {},
        ))

class SlowpicsUnavailableError(NetworkError):
    """slow.pics service unavailable (FC-5004)."""

    def __init__(self) -> None:
        super().__init__(ErrorContext(
            code="FC-5004",
            name="SLOWPICS_UNAVAILABLE",
            message="slow.pics service unavailable",
            hint="Try again later",
        ))

class TmdbRateLimitedError(NetworkError):
    """TMDB rate limited (FC-5006)."""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(ErrorContext(
            code="FC-5006",
            name="TMDB_RATE_LIMITED",
            message="TMDB rate limited",
            hint="Wait and retry",
            details={"retry_after": retry_after} if retry_after else {},
        ))

class SSLError(NetworkError):
    """SSL certificate error (FC-5008)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-5008",
            name="SSL_ERROR",
            message=f"SSL certificate error: {details}",
            hint="Check system time and certificates",
            details={"error": details},
        ))
```

### 3.6 Internal Errors (FC-9xxx) — Exit Code 1

```python
class InternalError(FrameCompareError):
    """Base class for internal errors."""

class GenericInternalError(InternalError):
    """Internal error (FC-9001)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-9001",
            name="INTERNAL_ERROR",
            message=f"Internal error: {details}",
            hint="Please report this bug",
            details={"error": details},
        ))

class AssertionError_(InternalError):
    """Assertion failed (FC-9002)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-9002",
            name="ASSERTION_FAILED",
            message=f"Assertion failed: {details}",
            hint="Please report this bug",
            details={"assertion": details},
        ))

class UnexpectedStateError(InternalError):
    """Unexpected state (FC-9003)."""

    def __init__(self, details: str) -> None:
        super().__init__(ErrorContext(
            code="FC-9003",
            name="UNEXPECTED_STATE",
            message=f"Unexpected state: {details}",
            hint="Please report this bug",
            details={"state": details},
        ))
```

---

## 4. Exit Code Mapping

```python
from enum import IntEnum

class ExitCode(IntEnum):
    """CLI exit codes mapped to error categories."""
    SUCCESS = 0
    GENERAL_ERROR = 1      # FC-9xxx or unknown
    CONFIG_ERROR = 2       # FC-1xxx
    DEPENDENCY_ERROR = 3   # FC-2xxx
    INPUT_ERROR = 4        # FC-3xxx
    PROCESSING_ERROR = 5   # FC-4xxx
    NETWORK_ERROR = 6      # FC-5xxx
    INTERRUPTED = 130      # Ctrl+C

def get_exit_code(error: FrameCompareError) -> ExitCode:
    """Map error to appropriate exit code."""
    code = error.code
    if code.startswith("FC-1"):
        return ExitCode.CONFIG_ERROR
    if code.startswith("FC-2"):
        return ExitCode.DEPENDENCY_ERROR
    if code.startswith("FC-3"):
        return ExitCode.INPUT_ERROR
    if code.startswith("FC-4"):
        return ExitCode.PROCESSING_ERROR
    if code.startswith("FC-5"):
        return ExitCode.NETWORK_ERROR
    return ExitCode.GENERAL_ERROR
```

---

## 5. Error Formatting Utilities

```python
def format_error_console(error: FrameCompareError, *, verbose: bool = False) -> str:
    """Format error for console output.

    Example output:
        ✗ Error [FC-3001]: No video files found in comparison_videos

          Hint: Place *.mkv, *.mp4 files in the input directory

          For more details, run with --verbose
    """
    lines = [f"✗ Error [{error.code}]: {error.context.message}"]
    if error.hint:
        lines.append(f"\n  Hint: {error.hint}")
    if verbose and error.context.details:
        lines.append(f"\n  Details: {error.context.details}")
    elif not verbose:
        lines.append("\n  For more details, run with --verbose")
    return "\n".join(lines)

def format_error_json(error: FrameCompareError) -> dict[str, JSONValue]:
    """Format error for JSON output."""
    return {
        "success": False,
        "error": error.context.to_dict(),
    }
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
def test_error_context_to_dict():
    ctx = ErrorContext(
        code="FC-1001",
        name="CONFIG_NOT_FOUND",
        message="Config not found",
        hint="Create config file",
    )
    result = ctx.to_dict()
    assert result["code"] == "FC-1001"
    assert result["hint"] == "Create config file"

def test_config_not_found_error():
    error = ConfigNotFoundError(Path("/test/config.toml"))
    assert error.code == "FC-1001"
    assert "/test/config.toml" in str(error)
    assert error.hint is not None

def test_get_exit_code_mapping():
    assert get_exit_code(ConfigNotFoundError(Path("."))) == ExitCode.CONFIG_ERROR
    assert get_exit_code(VapourSynthNotFoundError()) == ExitCode.DEPENDENCY_ERROR
    assert get_exit_code(NoVideosFoundError(Path("."))) == ExitCode.INPUT_ERROR
```

---

## 7. AI Agent Implementation Prompt

```markdown
# Task: Implement Errors Module

## Context
Implement the errors module for Frame Compare 2.0.
This is a foundation module that must be completed before all others.

## Files to Create
1. `src/frame_compare/errors.py` - Complete module

## Key Requirements
- ErrorContext dataclass (frozen, slots)
- FrameCompareError base class
- Complete exception hierarchy by category
- ExitCode enum
- get_exit_code() function
- format_error_console() and format_error_json() utilities

## Import Constraints
- This is a LEAF module
- May only import: Python stdlib, typing
- Must NOT import any other frame_compare modules

## Testing
- Test ErrorContext serialization
- Test each exception type has correct code
- Test exit code mapping
- Test error formatting

## Acceptance Criteria
- `.venv/bin/pyright --warnings src/frame_compare/errors.py` passes
- All error codes match error-codes.md registry
- Exit codes match documented values
```
