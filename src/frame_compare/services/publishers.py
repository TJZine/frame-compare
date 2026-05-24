"""Publishing services for Frame Compare."""

import asyncio
import random
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import monotonic
from typing import BinaryIO

import httpx
import structlog

from frame_compare.config.schema import SlowpicsConfig, Visibility
from frame_compare.services.errors import (
    SlowpicsError,
    SlowpicsRateLimitedError,
    SlowpicsUnavailableError,
)
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.progress_protocol import ProgressReporter

log = structlog.get_logger()

SLOWPICS_UPLOAD_URL = "https://slow.pics/api/comparison"
SLOWPICS_RETRY_BASE_DELAY_SECONDS = 1.0
SLOWPICS_RETRY_MAX_DELAY_SECONDS = 30.0
SLOWPICS_RETRY_JITTER_FACTOR = 0.1


@dataclass(frozen=True)
class PublishResult:
    """Result of a successful publication."""

    url: str
    screenshot_count: int
    upload_duration_seconds: float


@dataclass(frozen=True)
class _SlowpicsUploadRequest:
    """Prepared slow.pics multipart payload for httpx.

    Notes:
        This uses `data=` + `files=` to send multipart form data. Image paths are
        persisted here, and file handles are opened per-attempt during upload so retry
        logic can stream fresh handles without retaining image bytes in memory.
    """

    data: dict[str, str]
    file_paths: list[Path]


class SlowpicsPublisher:
    """Handles uploading screenshots to slow.pics."""

    def __init__(self, config: SlowpicsConfig, client: httpx.AsyncClient) -> None:
        self.config = config
        self._client = client

    async def upload(
        self,
        files: list[Path],
        title: str | None = None,
    ) -> str:
        """Upload screenshots to slow.pics.

        Args:
            files: List of PNG files to upload.
            title: Optional title for the comparison.

        Returns:
            The URL of the uploaded comparison.

        Raises:
            SlowpicsError: For general errors (e.g. 4xx, bad response).
            SlowpicsRateLimitedError: If rate limited after retries.
            SlowpicsUnavailableError: If service is down after retries.
        """
        if not files:
            raise SlowpicsError("No PNG files found to upload")

        visibility = self.config.visibility
        request = self._prepare_upload(files, title, visibility)
        log.info(
            "slowpics_upload_start",
            file_count=len(files),
            title=title,
            visibility=visibility.value,
        )

        try:
            response = await self._upload_with_retry(
                self._client,
                request,
                self.config.max_retries,
                self.config.timeout_seconds,
            )

            try:
                result = response.json()
                url = str(result["url"])
            except (ValueError, KeyError) as e:
                raise SlowpicsError(f"Invalid response from slow.pics: {e}") from e

            log.info("slowpics_upload_complete", url=url)
            return url

        except Exception as e:
            if isinstance(
                e,
                SlowpicsError | SlowpicsRateLimitedError | SlowpicsUnavailableError,
            ):
                raise
            raise SlowpicsError(f"Upload failed: {e}") from e

    def _prepare_upload(
        self, files: list[Path], title: str | None, visibility: Visibility
    ) -> _SlowpicsUploadRequest:
        """Prepare the slow.pics multipart payload for upload."""
        form_data: dict[str, str] = {
            "collectionName": title or "Comparison",
            "optimize": "true",
            "lossy": "true",
        }

        form_data["public"] = "true" if visibility is Visibility.PUBLIC else "false"

        return _SlowpicsUploadRequest(file_paths=list(files), data=form_data)

    async def _sleep_with_backoff(
        self,
        attempt: int,
        base_delay: float = SLOWPICS_RETRY_BASE_DELAY_SECONDS,
        max_delay: float = SLOWPICS_RETRY_MAX_DELAY_SECONDS,
        jitter_factor: float = SLOWPICS_RETRY_JITTER_FACTOR,
    ) -> float:
        """Calculate exponential backoff with jitter and sleep, returning sleep duration."""
        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
        # Retry jitter does not protect secrets or authorization decisions.
        jitter = delay * random.uniform(-jitter_factor, jitter_factor)  # nosec B311
        sleep_time = max(0.0, delay + jitter)
        await asyncio.sleep(sleep_time)
        return sleep_time

    def _retry_after_delay(self, retry_after: str | None, default_delay: float = 60.0) -> float:
        if retry_after is None:
            return default_delay

        retry_after_seconds = self._parse_retry_after_seconds(retry_after)
        if retry_after_seconds is not None:
            return retry_after_seconds

        retry_at = self._parse_retry_after_date(retry_after)
        if retry_at is None:
            return default_delay

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())

    def _parse_retry_after_seconds(self, retry_after: str) -> float | None:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            return None

    def _parse_retry_after_date(self, retry_after: str) -> datetime | None:
        try:
            return parsedate_to_datetime(retry_after)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None

    def _has_retry_budget(self, attempt: int, max_retries: int) -> bool:
        return attempt <= max_retries

    async def _post_upload_attempt(
        self,
        client: httpx.AsyncClient,
        request: _SlowpicsUploadRequest,
        timeout_seconds: float,
    ) -> httpx.Response:
        # Stream files per-attempt to avoid keeping all PNG bytes in memory and
        # to ensure retries always read fresh file handles.
        with ExitStack() as stack:
            multipart_files: list[tuple[str, tuple[str, BinaryIO, str]]] = []
            for file_path in request.file_paths:
                file_handle = stack.enter_context(file_path.open("rb"))
                multipart_files.append(("images", (file_path.name, file_handle, "image/png")))

            return await client.post(
                SLOWPICS_UPLOAD_URL,
                timeout=timeout_seconds,
                data=request.data,
                files=multipart_files,
            )

    async def _handle_retryable_status(
        self, response: httpx.Response, attempt: int, max_retries: int
    ) -> None:
        if response.status_code == 429:
            if not self._has_retry_budget(attempt, max_retries):
                raise SlowpicsRateLimitedError()

            retry_after = response.headers.get("Retry-After")
            delay = self._retry_after_delay(retry_after)
            log.warning(
                "slowpics_rate_limited",
                retry_after=delay,
                attempt=attempt,
            )
            await asyncio.sleep(delay)
            return

        if 500 <= response.status_code < 600:
            if not self._has_retry_budget(attempt, max_retries):
                raise SlowpicsUnavailableError()

            sleep_time = await self._sleep_with_backoff(attempt)
            log.warning(
                "slowpics_server_error",
                status=response.status_code,
                attempt=attempt,
                retry_in=sleep_time,
            )
            return

        raise SlowpicsError(f"Upload failed with status {response.status_code}: {response.text}")

    async def _handle_timeout(
        self, error: httpx.TimeoutException, attempt: int, max_retries: int
    ) -> None:
        if not self._has_retry_budget(attempt, max_retries):
            raise SlowpicsError(f"Upload timed out after {max_retries} retries") from error

        sleep_time = await self._sleep_with_backoff(attempt)
        log.warning(
            "slowpics_timeout",
            attempt=attempt,
            retry_in=sleep_time,
        )

    async def _handle_request_error(
        self, error: httpx.RequestError, attempt: int, max_retries: int
    ) -> None:
        if not self._has_retry_budget(attempt, max_retries):
            raise SlowpicsUnavailableError() from error

        sleep_time = await self._sleep_with_backoff(attempt)
        log.warning(
            "slowpics_connection_error",
            error=str(error),
            attempt=attempt,
            retry_in=sleep_time,
        )

    async def _upload_with_retry(
        self,
        client: httpx.AsyncClient,
        request: _SlowpicsUploadRequest,
        max_retries: int,
        timeout_seconds: float,
    ) -> httpx.Response:
        """Upload with exponential backoff."""
        attempt = 0

        while True:
            attempt += 1
            try:
                response = await self._post_upload_attempt(client, request, timeout_seconds)

                if response.is_success:
                    return response

                await self._handle_retryable_status(response, attempt, max_retries)

            except httpx.TimeoutException as e:
                await self._handle_timeout(e, attempt, max_retries)

            except httpx.RequestError as e:
                await self._handle_request_error(e, attempt, max_retries)


async def publish_to_slowpics(
    screenshot_dir: Path,
    config: SlowpicsConfig,
    client: httpx.AsyncClient,
    metadata: TmdbMetadata | None = None,
    progress: ProgressReporter | None = None,
) -> PublishResult:
    """Convenience function to publish screenshots from a directory.

    Args:
        screenshot_dir: Directory containing PNG screenshots.
        config: Slowpics configuration.
        client: HTTP client to use.
        metadata: Optional metadata for title.
        progress: Optional progress reporter.

    Returns:
        PublishResult containing the URL.
    """
    start_time = monotonic()

    files = sorted(screenshot_dir.glob("*.png"))
    if not files:
        raise SlowpicsError(f"No PNG files found in {screenshot_dir}")

    title = metadata.title if metadata else screenshot_dir.name

    if progress:
        progress.set_description("Uploading screenshots to slow.pics")

    publisher = SlowpicsPublisher(config, client)
    url = await publisher.upload(files, title)

    # Deletion semantics
    if config.delete_after_upload:
        try:
            for f in files:
                f.unlink()
            log.info("slowpics_files_deleted", count=len(files))
        except OSError as e:
            import warnings

            warnings.warn(
                f"Failed to delete files after upload: {e}",
                RuntimeWarning,
                stacklevel=2,
            )
            log.warning("slowpics_deletion_failed", error=str(e))

    duration = monotonic() - start_time

    return PublishResult(
        url=url,
        screenshot_count=len(files),
        upload_duration_seconds=duration,
    )
