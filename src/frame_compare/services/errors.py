"""Network and publisher service error classes."""

from __future__ import annotations

from frame_compare.errors import ErrorContext, NetworkError


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
