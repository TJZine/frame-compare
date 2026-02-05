"""Frame Compare error types (minimal stub for config module).

Error Codes:
    FC-1001: CONFIG_NOT_FOUND
    FC-1002: CONFIG_PARSE_ERROR
    FC-1003: CONFIG_VALIDATION_ERROR
    FC-1004: PRESET_NOT_FOUND
    FC-1005: PRESET_INVALID
    FC-1006: PRESET_NAME_INVALID
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
type ErrorDetails = dict[str, JSONValue]


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


class ConfigError(FrameCompareError):
    """Base class for configuration errors."""


class ConfigNotFoundError(ConfigError):
    """Configuration file not found (FC-1001)."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1001",
                name="CONFIG_NOT_FOUND",
                message=f"Configuration file not found: {path}",
                hint="Run 'frame-compare wizard' or create config/config.toml",
                details={"path": str(path)},
            )
        )
        self.path = path


class ConfigParseError(ConfigError):
    """TOML parsing failed (FC-1002)."""

    def __init__(self, path: Path, parse_details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1002",
                name="CONFIG_PARSE_ERROR",
                message=f"Failed to parse {path}: {parse_details}",
                hint="Check TOML syntax at the indicated line",
                details={"path": str(path), "parse_error": parse_details},
            )
        )
        self.path = path


class ConfigValidationError(ConfigError):
    """Config validation failed (FC-1003)."""

    def __init__(self, errors: list[dict[str, JSONValue]]) -> None:
        fields: list[str] = []
        for e in errors:
            loc = e.get("loc")
            if isinstance(loc, list) and loc:
                fields.append(str(loc[-1]))
            else:
                fields.append("unknown")

        # Cast to avoid invariance issues with list[dict[str, JSONValue]] vs list[JSONValue]
        safe_errors = cast("JSONValue", errors)

        super().__init__(
            ErrorContext(
                code="FC-1003",
                name="CONFIG_VALIDATION_ERROR",
                message=f"Invalid configuration: {', '.join(fields)}",
                hint="Check field types and constraints",
                details={"validation_errors": safe_errors},
            )
        )
        self.validation_errors = errors


class PresetNotFoundError(ConfigError):
    """Preset not found (FC-1004)."""

    def __init__(self, name: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1004",
                name="PRESET_NOT_FOUND",
                message=f"Preset not found: {name}",
                hint="Run 'frame-compare preset list' to see available",
                details={"preset_name": name},
            )
        )
        self.preset_name = name


class PresetInvalidError(ConfigError):
    """Preset file has invalid TOML syntax (FC-1005)."""

    def __init__(self, path: Path, parse_details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1005",
                name="PRESET_INVALID",
                message=f"Invalid preset file: {path}",
                hint="Check TOML syntax in preset file",
                details={"path": str(path), "parse_error": parse_details},
            )
        )
        self.path = path


class PresetNameInvalidError(ConfigError):
    """Preset name is invalid (FC-1006)."""

    def __init__(self, name: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-1006",
                name="PRESET_NAME_INVALID",
                message=f"Invalid preset name: {name}",
                hint="Use only letters, numbers, '_' and '-'",
                details={"preset_name": name},
            )
        )
        self.preset_name = name


# ─── 3.2 Dependency Errors (FC-2xxx) ───────────────────────────────────────────


class DependencyError(FrameCompareError):
    """Base class for dependency failures (VapourSynth, FFmpeg, plugins)."""


class VapourSynthNotFoundError(DependencyError):
    """VapourSynth module not found (FC-2001)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2001",
                name="VAPOURSYNTH_NOT_FOUND",
                message="VapourSynth python module not found",
                hint="Install VapourSynth (pip install VapourSynth) or check PYTHONPATH",
            )
        )


class VapourSynthError(DependencyError):
    """VapourSynth core error (FC-2002)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2002",
                name="VAPOURSYNTH_ERROR",
                message=f"VapourSynth core error: {details}",
                hint="Check script syntax or plugin compatibility",
                details={"vs_error": details},
            )
        )


class PluginNotFoundError(DependencyError):
    """VapourSynth plugin missing (FC-2003)."""

    def __init__(self, namespace: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2003",
                name="PLUGIN_NOT_FOUND",
                message=f"Required VapourSynth plugin missing: {namespace}",
                hint=f"Install plugin providing namespace '{namespace}'",
                details={"namespace": namespace},
            )
        )


class LibplaceboError(DependencyError):
    """vs-placebo specific error (FC-2004)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2004",
                name="LIBPLACEBO_ERROR",
                message=f"Libplacebo error: {details}",
                hint="Check Vulkan drivers or shader support",
                details={"libplacebo_error": details},
            )
        )


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


class VSPreviewNotFoundError(DependencyError):
    """VSPreview not found (FC-2008)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-2008",
                name="VSPREVIEW_NOT_FOUND",
                message="VSPreview not installed",
                hint="Install vspreview (and a Qt backend) for interactive alignment verification",
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


class InsufficientFramesError(InputError):
    """Video too short for requested frames (FC-3004)."""

    def __init__(self, path: Path, count: int, required: int) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3004",
                name="INSUFFICIENT_FRAMES",
                message=f"Video has {count} frames, need at least {required}",
                hint="Use a longer video or reduce frame_count",
                details={
                    "path": str(path),
                    "count": count,
                    "required": required,
                },
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


class TonemapError(ProcessingError):
    """Tonemapping failure (FC-4003)."""

    def __init__(self, reason: str, hint: str | None = None) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4003",
                name="TONEMAP_ERROR",
                message=f"Tonemapping failed: {reason}",
                hint=hint or "Check libplacebo support or config",
                details={"reason": reason},
            )
        )


class RenderError(ProcessingError):
    """Composition/image encoding failure (FC-4004)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4004",
                name="RENDER_ERROR",
                message="Final render composition failed",
                hint="Check memory usage or output path",
            )
        )


class AudioAlignmentError(ProcessingError):
    """Audio sync calculation failure (FC-4005)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4005",
                name="AUDIO_ALIGNMENT_ERROR",
                message=f"Audio alignment failed: {reason}",
                hint="Ensure audio tracks exist and are similar",
                details={"reason": reason},
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


class MemoryError_(ProcessingError):
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


class TimeoutError_(ProcessingError):
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


class SelectionError(ProcessingError):
    """Frame selection algorithm failure (FC-4012)."""

    def __init__(self, reason: str, requested: int, found: int) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4012",
                name="SELECTION_ERROR",
                message=f"Frame selection failed: {reason}",
                hint="Adjust selection criteria",
                details={"reason": reason, "requested": requested, "found": found},
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


class SourceLoadError(ProcessingError):
    """Failed to initialize source engine (FC-4015)."""

    def __init__(self, path: Path, engine_error: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4015",
                name="SOURCE_LOAD_ERROR",
                message=f"Failed to load source {path}: {engine_error}",
                hint="Check file integrity or engine support",
                details={"path": str(path), "engine_error": engine_error},
            )
        )


class MetadataError(ProcessingError):
    """Failed to parse video metadata (FC-4016)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4016",
                name="METADATA_ERROR",
                message=f"Metadata parsing failed: {reason}",
                hint="Check file format specs",
                details={"reason": reason},
            )
        )


class ReportError(ProcessingError):
    """Failed to generate report (FC-4017)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4017",
                name="REPORT_ERROR",
                message=f"Report generation failed: {reason}",
                hint="Check template validity",
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


class VSPreviewError(ProcessingError):
    """VSPreview failed to launch or run (FC-4019)."""

    def __init__(self, details: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4019",
                name="VSPREVIEW_ERROR",
                message=f"VSPreview error: {details}",
                hint="Install a Qt backend (PySide6/PyQt5) and ensure a GUI backend is available",
                details={"error": details},
            )
        )


class AnalysisError(ProcessingError):
    """Marker base for analysis failures."""


# ─── 3.5 Network Errors (FC-5xxx) ──────────────────────────────────────────────


class NetworkError(FrameCompareError):
    """Base class for network failures."""


class NetworkUnreachableError(NetworkError):
    """No internet connection (FC-5001)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5001",
                name="NETWORK_UNREACHABLE",
                message="Network unreachable",
                hint="Check internet connection",
            )
        )


class SlowpicsError(NetworkError):
    """General slow.pics API failure (FC-5002)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5002",
                name="SLOWPICS_ERROR",
                message=f"slow.pics error: {reason}",
                hint="Check service status",
                details={"reason": reason},
            )
        )


class SlowpicsRateLimitedError(NetworkError):
    """Too many requests to slow.pics (FC-5003)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5003",
                name="SLOWPICS_RATE_LIMITED",
                message="slow.pics rate limit exceeded",
                hint="Wait before retrying",
            )
        )


class SlowpicsUnavailableError(NetworkError):
    """slow.pics service down (FC-5004)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5004",
                name="SLOWPICS_UNAVAILABLE",
                message="slow.pics service unavailable",
                hint="Try again later",
            )
        )


class TmdbError(NetworkError):
    """TMDB API failure (FC-5005)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5005",
                name="TMDB_ERROR",
                message=f"TMDB error: {reason}",
                hint="Check API key",
                details={"reason": reason},
            )
        )


class TmdbRateLimitedError(NetworkError):
    """Too many requests to TMDB (FC-5006)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5006",
                name="TMDB_RATE_LIMITED",
                message="TMDB rate limit exceeded",
                hint="Wait before retrying",
            )
        )


class NetworkTimeoutError(NetworkError):
    """Request timed out (FC-5007)."""

    def __init__(self, url: str, timeout: float) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5007",
                name="NETWORK_TIMEOUT",
                message=f"Request to {url} timed out after {timeout}s",
                hint="Check connection speed",
                details={"url": url, "timeout": timeout},
            )
        )


class SSLError(NetworkError):
    """Certificate verification failed (FC-5008)."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-5008",
                name="SSL_ERROR",
                message=f"SSL verification failed: {reason}",
                hint="Check system certificates",
                details={"reason": reason},
            )
        )


class ServiceError(NetworkError):
    """Marker base for service failures."""


class PublishError(NetworkError):
    """Marker base for publishing failures."""


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


class AssertionError_(InternalError):
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


# ─── 4. Exit Code Mapping ──────────────────────────────────────────────────────


class ExitCode(IntEnum):
    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIG_ERROR = 2
    DEPENDENCY_ERROR = 3
    INPUT_ERROR = 4
    PROCESSING_ERROR = 5
    NETWORK_ERROR = 6
    INTERRUPTED = 130


def get_exit_code(error: FrameCompareError) -> ExitCode:
    """Map exception to exit code."""
    code = error.code
    if code.startswith("FC-"):
        category = code.split("-", 1)[1][:1]
        if category == "1":
            return ExitCode.CONFIG_ERROR
        if category == "2":
            return ExitCode.DEPENDENCY_ERROR
        if category == "3":
            return ExitCode.INPUT_ERROR
        if category == "4":
            return ExitCode.PROCESSING_ERROR
        if category == "5":
            return ExitCode.NETWORK_ERROR
    # InternalError and unknown FrameCompareErrors map to 1
    return ExitCode.GENERAL_ERROR


# ─── 5. Error Formatting Utilities ─────────────────────────────────────────────


def format_error_console(error: FrameCompareError, *, verbose: bool = False) -> str:
    """Format error for console output."""
    output = f"✗ Error [{error.code}]: {error.context.message}\n"
    if error.hint:
        output += f"  Hint: {error.hint}\n"

    if verbose and error.context.details:
        output += "\n  Details:\n"
        for k, v in error.context.details.items():
            output += f"    {k}: {v}\n"
    elif not verbose and error.context.details:
        output += "\n  For more details, run with --verbose"

    return output.rstrip()


def format_error_json(error: FrameCompareError) -> dict[str, JSONValue]:
    """Format error for JSON output."""
    return {
        "success": False,
        "error": error.context.to_dict(),
    }
