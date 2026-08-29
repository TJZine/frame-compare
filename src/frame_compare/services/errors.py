"""Service-specific exception types for Frame Compare."""

from __future__ import annotations

from pathlib import Path

from frame_compare.errors import (
    ErrorContext,
    ErrorDetails,
    InputError,
    NetworkError,
    ProcessingError,
)


class HistoryAccessError(InputError):
    """History folder or run-name access failed (FC-3016)."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3016",
                name="HISTORY_ACCESS_ERROR",
                message=message,
                hint=hint,
            )
        )


class HistoryOpenError(ProcessingError):
    """A recorded report cannot be opened safely (FC-4020)."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(
            ErrorContext(
                code="FC-4020",
                name="HISTORY_OPEN_ERROR",
                message=message,
                hint=hint,
            )
        )


class GeneratedDataReservationError(InputError):
    """The configured generated-data root cannot reserve a run folder (FC-3018)."""

    def __init__(self, path: Path, cause: OSError | RuntimeError) -> None:
        details: ErrorDetails = {
            "path": str(path),
            "error": str(cause),
        }
        super().__init__(
            ErrorContext(
                code="FC-3018",
                name="GENERATED_DATA_RESERVATION_ERROR",
                message=f"Unable to reserve a run folder under generated-data location: {path}",
                hint=(
                    "Reconnect the selected location, repair its permissions or "
                    "link/junction, or choose another paths.generated_dir"
                ),
                details=details,
                cause=cause,
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
