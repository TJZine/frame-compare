"""Service-specific exception types for Frame Compare."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from threading import Event

    from frame_compare.services.types import AudioAlignmentCollectionRecord

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

    def __init__(
        self,
        reason: str,
        *,
        category: str = "correlation_failed",
        stage: str = "correlation",
        role: str | None = None,
        reference_sample_count: int | None = None,
        comparison_sample_count: int | None = None,
        collection_summaries: tuple[AudioAlignmentCollectionRecord, ...] = (),
    ) -> None:
        self.category = category
        self.stage = stage
        self.role = role
        self.reference_sample_count = reference_sample_count
        self.comparison_sample_count = comparison_sample_count
        self.collection_summaries = collection_summaries
        super().__init__(
            ErrorContext(
                code="FC-4005",
                name="AUDIO_ALIGNMENT_ERROR",
                message=f"Audio alignment failed: {reason}",
                hint="Ensure audio tracks exist and are similar",
                details={"reason": reason},
            )
        )


class AudioAlignmentCancellationError(AudioAlignmentError):
    """Internal cooperative cancellation raised by blocking alignment work."""


class AudioAlignmentCleanupError(AudioAlignmentError):
    """Fatal failure to release an alignment child, reader, pipe, or handle."""


def raise_if_alignment_cancelled(cancellation: Event | None) -> None:
    """Stop blocking alignment work at its next bounded cooperative boundary."""
    if cancellation is not None and cancellation.is_set():
        raise AudioAlignmentCancellationError(
            "audio alignment was cancelled",
            category="cancelled",
            stage="cancellation",
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
