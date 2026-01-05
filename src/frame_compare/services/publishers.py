"""Publishing services for Frame Compare."""

import asyncio
import random
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import httpx
import structlog

from frame_compare.config.schema import SlowpicsConfig
from frame_compare.errors import (
    SlowpicsError,
    SlowpicsRateLimitedError,
    SlowpicsUnavailableError,
)
from frame_compare.services.types import TmdbMetadata
from frame_compare.utils.progress import ProgressReporter

log = structlog.get_logger()

SLOWPICS_UPLOAD_URL = "https://slow.pics/api/comparison"


@dataclass(frozen=True)
class PublishResult:
    """Result of a successful publication."""

    url: str
    screenshot_count: int
    upload_duration_seconds: float


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

        # Prepare payload
        visibility = self.config.visibility.value  # "public", "unlisted", etc.
        data = await self._prepare_upload(files, title, visibility)
        log.info(
            "slowpics_upload_start",
            file_count=len(files),
            title=title,
            visibility=visibility,
        )

        try:
            # Upload with retry
            response = await self._upload_with_retry(
                self._client,
                data,
                self.config.max_retries,
                self.config.timeout_seconds,
            )

            # Parse result
            try:
                result = response.json()
                url = str(result["url"])
            except (ValueError, KeyError) as e:
                raise SlowpicsError(f"Invalid response from slow.pics: {e}") from e

            log.info("slowpics_upload_complete", url=url)
            return url

        except Exception as e:
            # Re-raise known errors, wrap others
            if isinstance(
                e,
                SlowpicsError | SlowpicsRateLimitedError | SlowpicsUnavailableError,
            ):
                raise
            raise SlowpicsError(f"Upload failed: {e}") from e

    async def _prepare_upload(
        self, files: list[Path], title: str | None, visibility: str
    ) -> dict[str, object]:
        """Prepare the multipart upload payload."""
        # Note: In a real implementation with multipart/form-data, we'd handle
        # file opening differently. However, slow.pics API expects a JSON-like
        # structure or multipart where keys matter.
        # Based on typical usage, we construct the request.
        # BUT, since we need to send files, we can't just return a dict for JSON.
        # We need to structure this for httpx's files/data parameters.
        # Wait, the plan says:
        # "async def _prepare_upload(files: list[Path], title: str | None, visibility: str) -> dict"
        # And "_upload_with_retry(client: httpx.AsyncClient, data: dict, ...)"
        #
        # Re-reading the plan/SSOT:
        # The plan abstractly says "data: dict".
        # However, for file uploads, we usually need `files` and `data`.
        # I will assume `_prepare_upload` returns the keyword arguments for `client.post`.
        # OR, I'll stick to the signature but make it return the kwargs dictionary.

        # Let's look at how slow.pics expects data. Usually it's multipart/form-data.
        # fields: 'collectionName', 'public' (true/false or string?), 'optimize' (true/false)
        # files: 'images[]'

        # Implementation Detail:
        # To match the plan's signature `-> dict`, I will return a dict that contains
        # arguments suitable for `client.post(..., **data)`.
        # But wait, the plan says `_upload_with_retry(..., data: dict, ...)`
        # This implies `data` is the payload.

        # Let's adjust slightly to be practical:
        # I will make `_prepare_upload` read the files into memory (they are screenshots, usually small enough)
        # or prepare open file handles.
        # Since I cannot easily pass open file handles around in a simple dict without management,
        # I will read them into memory.

        file_list: list[tuple[str, tuple[str, bytes, str]]] = []
        for f in files:
            # We must use the filename as the key or part of the tuple
            # httpx format: ('field_name', ('filename', file_content, 'content_type'))
            # slow.pics expects 'images' field.
            content = f.read_bytes()
            file_list.append(("images", (f.name, content, "image/png")))

        # If visibility is passed as a string value from the config:
        # 'public' -> public=true
        # 'unlisted' -> public=false
        # 'private' -> public=false?

        form_data = {
            "collectionName": title or "Comparison",
            "optimize": "true",
            "lossy": "true",
        }

        if visibility == "public":
            form_data["public"] = "true"
        else:
            form_data["public"] = "false"

        return {"files": file_list, "data": form_data}

    async def _upload_with_retry(
        self,
        client: httpx.AsyncClient,
        kwargs: dict[str, object],
        max_retries: int,
        timeout_seconds: float,
    ) -> httpx.Response:
        """Upload with exponential backoff."""
        attempt = 0
        base_delay = 1.0
        max_delay = 30.0
        jitter_factor = 0.1

        while True:
            attempt += 1
            try:
                response = await client.post(
                    SLOWPICS_UPLOAD_URL,
                    timeout=timeout_seconds,
                    **kwargs,  # type: ignore
                )

                if response.is_success:
                    return response

                # Handle 429 Rate Limit
                if response.status_code == 429:
                    if attempt >= max_retries:
                        raise SlowpicsRateLimitedError()

                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 60.0
                    log.warning(
                        "slowpics_rate_limited",
                        retry_after=delay,
                        attempt=attempt,
                    )
                    await asyncio.sleep(delay)
                    continue

                # Handle 5xx Server Errors
                if 500 <= response.status_code < 600:
                    if attempt >= max_retries:
                        raise SlowpicsUnavailableError()

                    # Exponential backoff
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    # Add jitter
                    jitter = delay * random.uniform(-jitter_factor, jitter_factor)
                    sleep_time = max(0, delay + jitter)

                    log.warning(
                        "slowpics_server_error",
                        status=response.status_code,
                        attempt=attempt,
                        retry_in=sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                    continue

                # Handle 4xx Client Errors (Fail Fast)
                # 429 was handled above
                raise SlowpicsError(
                    f"Upload failed with status {response.status_code}: {response.text}"
                )

            except httpx.TimeoutException as e:
                if attempt >= max_retries:
                    raise SlowpicsError(f"Upload timed out after {max_retries} retries") from e

                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                jitter = delay * random.uniform(-jitter_factor, jitter_factor)
                sleep_time = max(0, delay + jitter)

                log.warning(
                    "slowpics_timeout",
                    attempt=attempt,
                    retry_in=sleep_time,
                )
                await asyncio.sleep(sleep_time)
                continue

            except httpx.RequestError as e:
                # Connection errors etc.
                if attempt >= max_retries:
                    raise SlowpicsUnavailableError() from e

                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                jitter = delay * random.uniform(-jitter_factor, jitter_factor)
                sleep_time = max(0, delay + jitter)

                log.warning(
                    "slowpics_connection_error",
                    error=str(e),
                    attempt=attempt,
                    retry_in=sleep_time,
                )
                await asyncio.sleep(sleep_time)
                continue


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

    # Collect files deterministically
    files = sorted(screenshot_dir.glob("*.png"))
    if not files:
        raise SlowpicsError(f"No PNG files found in {screenshot_dir}")

    # Determine title
    title = metadata.title if metadata else screenshot_dir.name

    if progress:
        progress.start_phase("Uploading to slow.pics", total=1)

    try:
        publisher = SlowpicsPublisher(config, client)
        url = await publisher.upload(files, title)
    finally:
        if progress:
            progress.advance(1)
            progress.complete_phase()

    # Deletion semantics
    if config.delete_after_upload:
        try:
            for f in files:
                f.unlink()
            log.info("slowpics_files_deleted", count=len(files))
        except OSError as e:
            log.warning("slowpics_deletion_failed", error=str(e))

    duration = monotonic() - start_time

    return PublishResult(
        url=url,
        screenshot_count=len(files),
        upload_duration_seconds=duration,
    )
