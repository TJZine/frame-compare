"""Publishing services for Frame Compare."""

import asyncio
import random
from collections.abc import Awaitable, Callable
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import monotonic
from typing import cast
from urllib.parse import unquote
from uuid import uuid4

import httpx
import structlog

from frame_compare import __version__
from frame_compare.config.schema import SlowpicsConfig, Visibility
from frame_compare.services.errors import (
    SlowpicsError,
    SlowpicsRateLimitedError,
    SlowpicsUnavailableError,
)
from frame_compare.services.slowpics_upload_plan import SlowpicsUploadPlan
from frame_compare.services.types import SlowpicsCollectionMetadata
from frame_compare.utils.progress_protocol import ProgressReporter

log = structlog.get_logger()

SLOWPICS_BASE_URL = "https://slow.pics"
SLOWPICS_COMPARISON_URL = f"{SLOWPICS_BASE_URL}/comparison"
SLOWPICS_METADATA_UPLOAD_URL = f"{SLOWPICS_BASE_URL}/upload/comparison"
SLOWPICS_IMAGE_UPLOAD_URL_TEMPLATE = f"{SLOWPICS_BASE_URL}/upload/image/{{image_uuid}}"
SLOWPICS_RETRY_BASE_DELAY_SECONDS = 1.0
SLOWPICS_RETRY_MAX_DELAY_SECONDS = 30.0
SLOWPICS_RETRY_JITTER_FACTOR = 0.1
SLOWPICS_BROWSER_ID_SENTINEL = "eb80db10-97a7-11ee-8f6f-bfa69501bb51"
SLOWPICS_USER_AGENT = f"frame-compare/{__version__} slowpics-direct"
SLOWPICS_UPLOAD_HEADERS = {
    "Origin": SLOWPICS_BASE_URL,
    "Referer": SLOWPICS_COMPARISON_URL,
    "User-Agent": SLOWPICS_USER_AGENT,
}
SLOWPICS_NAVIGATION_HEADERS = {"User-Agent": SLOWPICS_USER_AGENT}

type _MultipartTextFields = list[tuple[str, tuple[None, str]]]


@dataclass(frozen=True)
class PublishResult:
    """Result of a successful publication."""

    url: str
    screenshot_count: int
    upload_duration_seconds: float
    uploaded_file_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class _SlowpicsMetadataResponse:
    """Validated slow.pics metadata response needed for image uploads."""

    key: str
    first_comparison_key: str | None
    collection_uuid: str
    image_uuids: tuple[tuple[str, ...], ...]


class SlowpicsPublisher:
    """Handles uploading screenshots to slow.pics."""

    def __init__(self, config: SlowpicsConfig, client: httpx.AsyncClient) -> None:
        self.config = config
        self._client = client

    async def upload(
        self,
        upload_plan: SlowpicsUploadPlan,
        collection_metadata: SlowpicsCollectionMetadata,
    ) -> str:
        """Upload screenshots to slow.pics.

        Args:
            upload_plan: Planned rows/images to upload.
            collection_metadata: Resolved collection title and optional TMDB association.

        Returns:
            The URL of the uploaded comparison.

        Raises:
            SlowpicsError: For general errors (e.g. 4xx, bad response).
            SlowpicsRateLimitedError: If rate limited after retries.
            SlowpicsUnavailableError: If service is down after retries.
        """
        files = upload_plan.file_paths
        if not files:
            raise SlowpicsError("No PNG files found to upload")
        _validate_upload_files(files)

        visibility = self.config.visibility
        log.info(
            "slowpics_upload_start",
            file_count=len(files),
            title=collection_metadata.title,
            visibility=visibility.value,
        )

        try:
            await self._get_comparison_page_with_retry()
            xsrf_token = _xsrf_token_from_cookies(self._client)
            browser_id = _browser_id_from_cookies(self._client)
            metadata_response = await self._create_metadata_with_retry(
                upload_plan=upload_plan,
                collection_metadata=collection_metadata,
                xsrf_token=xsrf_token,
                browser_id=browser_id,
            )
            await self._upload_planned_images_with_retry(
                upload_plan=upload_plan,
                metadata_response=metadata_response,
                xsrf_token=xsrf_token,
                browser_id=browser_id,
            )
            url_key = metadata_response.first_comparison_key or metadata_response.key
            url = f"{SLOWPICS_BASE_URL}/c/{url_key}"
            log.info("slowpics_upload_complete")
            return url

        except Exception as exc:
            if isinstance(
                exc,
                SlowpicsError | SlowpicsRateLimitedError | SlowpicsUnavailableError,
            ):
                raise
            raise SlowpicsError("Upload failed for slow.pics") from None

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

        raise SlowpicsError(f"Upload failed with status {response.status_code}")

    async def _handle_timeout(
        self, error: httpx.TimeoutException, attempt: int, max_retries: int
    ) -> None:
        if not self._has_retry_budget(attempt, max_retries):
            raise SlowpicsError(f"Upload timed out after {max_retries} retries") from None

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
            raise SlowpicsUnavailableError() from None

        sleep_time = await self._sleep_with_backoff(attempt)
        log.warning(
            "slowpics_connection_error",
            attempt=attempt,
            retry_in=sleep_time,
        )

    async def _get_comparison_page_with_retry(self) -> None:
        response = await self._request_with_retry(
            step="comparison_page",
            request=lambda: self._client.get(
                SLOWPICS_COMPARISON_URL,
                timeout=self.config.timeout_seconds,
                headers=SLOWPICS_NAVIGATION_HEADERS,
            ),
            max_retries=self.config.max_retries,
            retry_timeout=True,
            retry_request_error=True,
        )
        if not response.is_success:
            raise SlowpicsError(f"Comparison page failed with status {response.status_code}")

    async def _create_metadata_with_retry(
        self,
        *,
        upload_plan: SlowpicsUploadPlan,
        collection_metadata: SlowpicsCollectionMetadata,
        xsrf_token: str,
        browser_id: str,
    ) -> _SlowpicsMetadataResponse:
        response = await self._request_with_retry(
            step="metadata",
            request=lambda: self._client.post(
                SLOWPICS_METADATA_UPLOAD_URL,
                timeout=self.config.timeout_seconds,
                headers=_slowpics_upload_headers(xsrf_token),
                files=_metadata_multipart_fields(
                    upload_plan=upload_plan,
                    collection_metadata=collection_metadata,
                    config=self.config,
                    browser_id=browser_id,
                ),
            ),
            max_retries=self.config.max_retries,
            retry_timeout=False,
            retry_request_error=False,
        )
        if not response.is_success:
            raise SlowpicsError(f"Metadata upload failed with status {response.status_code}")
        return _parse_metadata_response(response, upload_plan)

    async def _upload_planned_images_with_retry(
        self,
        *,
        upload_plan: SlowpicsUploadPlan,
        metadata_response: _SlowpicsMetadataResponse,
        xsrf_token: str,
        browser_id: str,
    ) -> None:
        for row, image_uuids in zip(upload_plan.rows, metadata_response.image_uuids, strict=True):
            for image, image_uuid in zip(row.images, image_uuids, strict=True):
                await self._upload_image_with_retry(
                    image_path=image.screenshot_path,
                    image_uuid=image_uuid,
                    collection_uuid=metadata_response.collection_uuid,
                    xsrf_token=xsrf_token,
                    browser_id=browser_id,
                )

    async def _upload_image_with_retry(
        self,
        *,
        image_path: Path,
        image_uuid: str,
        collection_uuid: str,
        xsrf_token: str,
        browser_id: str,
    ) -> None:
        response = await self._request_with_retry(
            step="image",
            request=lambda: self._post_image_attempt(
                image_path=image_path,
                image_uuid=image_uuid,
                collection_uuid=collection_uuid,
                xsrf_token=xsrf_token,
                browser_id=browser_id,
            ),
            max_retries=self.config.max_retries,
            retry_timeout=True,
            retry_request_error=True,
        )
        if response.status_code == 200:
            return
        if (
            response.status_code == 400
            and response.headers.get("X-Error-Message") == "IMAGE_IS_COMPLETE"
        ):
            return
        raise SlowpicsError(f"Image upload failed with status {response.status_code}")

    async def _post_image_attempt(
        self,
        *,
        image_path: Path,
        image_uuid: str,
        collection_uuid: str,
        xsrf_token: str,
        browser_id: str,
    ) -> httpx.Response:
        with ExitStack() as stack:
            file_handle = stack.enter_context(image_path.open("rb"))
            return await self._client.post(
                SLOWPICS_IMAGE_UPLOAD_URL_TEMPLATE.format(image_uuid=image_uuid),
                timeout=_image_upload_timeout(
                    general_timeout_seconds=self.config.timeout_seconds,
                    image_upload_timeout_seconds=self.config.image_upload_timeout_seconds,
                    file_size_bytes=image_path.stat().st_size,
                ),
                headers=_slowpics_upload_headers(xsrf_token),
                data={
                    "collectionUuid": collection_uuid,
                    "imageUuid": image_uuid,
                    "browserId": browser_id,
                },
                files={"file": (image_path.name, file_handle, "image/png")},
            )

    async def _request_with_retry(
        self,
        *,
        step: str,
        request: Callable[[], Awaitable[httpx.Response]],
        max_retries: int,
        retry_timeout: bool,
        retry_request_error: bool,
    ) -> httpx.Response:
        """Run one slow.pics HTTP step with step-specific retry policy."""
        attempt = 0

        while True:
            attempt += 1
            try:
                response = await request()

                if response.is_success or _is_complete_image_response(step, response):
                    return response

                await self._handle_retryable_status(response, attempt, max_retries)

            except httpx.TimeoutException as e:
                if not retry_timeout:
                    raise SlowpicsError(
                        "Metadata upload failed; remote slow.pics state is unknown"
                    ) from None
                await self._handle_timeout(e, attempt, max_retries)

            except httpx.RequestError as e:
                if not retry_request_error:
                    raise SlowpicsError(
                        "Metadata upload failed; remote slow.pics state is unknown"
                    ) from None
                await self._handle_request_error(e, attempt, max_retries)


async def publish_to_slowpics(
    collection_metadata: SlowpicsCollectionMetadata,
    config: SlowpicsConfig,
    client: httpx.AsyncClient,
    progress: ProgressReporter | None = None,
    upload_plan: SlowpicsUploadPlan | None = None,
) -> PublishResult:
    """Publish screenshots through the browser-compatible slow.pics upload flow.

    Args:
        collection_metadata: Resolved collection title and optional TMDB association.
        config: Slowpics configuration.
        client: HTTP client to use.
        progress: Optional progress reporter.
        upload_plan: Explicit row-major upload plan.

    Returns:
        PublishResult containing the URL.
    """
    start_time = monotonic()

    if upload_plan is None:
        raise SlowpicsError("No slow.pics upload plan available")
    files = upload_plan.file_paths
    if not files:
        raise SlowpicsError("No PNG files found to upload")
    _validate_upload_files(files)

    if progress:
        progress.set_description(f"Uploading {collection_metadata.title} to slow.pics")

    publisher = SlowpicsPublisher(config, client)
    url = await publisher.upload(upload_plan, collection_metadata)

    duration = monotonic() - start_time

    return PublishResult(
        url=url,
        screenshot_count=len(files),
        upload_duration_seconds=duration,
        uploaded_file_paths=tuple(files),
    )


def _validate_upload_files(files: list[Path]) -> None:
    for file_path in files:
        if not file_path.is_file():
            raise SlowpicsError(f"PNG file planned for slow.pics upload is missing: {file_path}")


def _xsrf_token_from_cookies(client: httpx.AsyncClient) -> str:
    raw_token = client.cookies.get("XSRF-TOKEN")
    if raw_token is None or not raw_token:
        raise SlowpicsError("Missing slow.pics XSRF token")
    return unquote(raw_token)


def _browser_id_from_cookies(client: httpx.AsyncClient) -> str:
    browser_id = client.cookies.get("BROWSER-ID")
    if browser_id is None or browser_id == SLOWPICS_BROWSER_ID_SENTINEL or not browser_id:
        browser_id = str(uuid4())
        client.cookies.set("BROWSER-ID", browser_id, domain="slow.pics", path="/")
    return browser_id


def _slowpics_upload_headers(xsrf_token: str) -> dict[str, str]:
    return {**SLOWPICS_UPLOAD_HEADERS, "X-XSRF-TOKEN": xsrf_token}


def _metadata_multipart_fields(
    *,
    upload_plan: SlowpicsUploadPlan,
    collection_metadata: SlowpicsCollectionMetadata,
    config: SlowpicsConfig,
    browser_id: str,
) -> _MultipartTextFields:
    fields: list[tuple[str, str]] = [
        ("collectionName", collection_metadata.title),
        ("browserId", browser_id),
        ("optimizeImages", "true"),
        ("desiredFileType", "image/png"),
        ("hentai", _lowercase_bool(config.is_hentai)),
        ("public", _lowercase_bool(config.visibility is Visibility.PUBLIC)),
        ("visibility", "PUBLIC" if config.visibility is Visibility.PUBLIC else "LINK_ONLY"),
        ("removeAfter", str(config.remove_after_days) if config.remove_after_days else ""),
    ]
    if collection_metadata.tmdb_id is not None and collection_metadata.tmdb_media_type is not None:
        fields.append(
            (
                "tmdbId",
                f"{collection_metadata.tmdb_media_type.upper()}_{collection_metadata.tmdb_id}",
            )
        )
    for row in upload_plan.rows:
        row_prefix = f"comparisons[{row.row_index}]"
        fields.extend(
            [
                (f"{row_prefix}.name", row.row_name),
                (f"{row_prefix}.hentai", _lowercase_bool(config.is_hentai)),
                (f"{row_prefix}.sortOrder", str(row.sort_order)),
            ]
        )
        for image in row.images:
            image_prefix = f"{row_prefix}.images[{image.image_index}]"
            fields.extend(
                [
                    (f"{image_prefix}.name", image.image_name),
                    (f"{image_prefix}.sortOrder", str(image.sort_order)),
                ]
            )
    return [(name, (None, value)) for name, value in fields]


def _lowercase_bool(value: bool) -> str:
    return "true" if value else "false"


def _image_upload_timeout(
    *,
    general_timeout_seconds: float,
    image_upload_timeout_seconds: float,
    file_size_bytes: int,
) -> httpx.Timeout:
    estimated_write_seconds = file_size_bytes / (256 * 1024) + 15.0
    write_timeout = max(image_upload_timeout_seconds, estimated_write_seconds)
    return httpx.Timeout(general_timeout_seconds, write=write_timeout)


def _parse_metadata_response(
    response: httpx.Response, upload_plan: SlowpicsUploadPlan
) -> _SlowpicsMetadataResponse:
    try:
        payload = cast(object, response.json())
    except ValueError:
        raise SlowpicsError("Invalid metadata response from slow.pics") from None
    if not isinstance(payload, dict):
        raise SlowpicsError("Invalid metadata response from slow.pics")
    response_payload = cast(dict[object, object], payload)

    key = _required_response_string(response_payload, "key")
    first_comparison_key = _optional_response_string(response_payload, "firstComparisonKey")
    collection_uuid = _required_response_string(response_payload, "collectionUuid")
    image_uuids = _response_image_matrix(response_payload.get("images"), upload_plan)
    return _SlowpicsMetadataResponse(
        key=key,
        first_comparison_key=first_comparison_key,
        collection_uuid=collection_uuid,
        image_uuids=image_uuids,
    )


def _required_response_string(payload: dict[object, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SlowpicsError("Invalid metadata response from slow.pics")
    return value


def _optional_response_string(payload: dict[object, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SlowpicsError("Invalid metadata response from slow.pics")
    return value


def _response_image_matrix(
    raw_images: object, upload_plan: SlowpicsUploadPlan
) -> tuple[tuple[str, ...], ...]:
    if not isinstance(raw_images, list):
        raise SlowpicsError("Invalid metadata response from slow.pics")
    raw_rows = cast(list[object], raw_images)
    if len(raw_rows) != len(upload_plan.rows):
        raise SlowpicsError("Invalid metadata response from slow.pics")

    rows: list[tuple[str, ...]] = []
    for raw_row, planned_row in zip(raw_rows, upload_plan.rows, strict=True):
        if not isinstance(raw_row, list):
            raise SlowpicsError("Invalid metadata response from slow.pics")
        raw_image_uuids = cast(list[object], raw_row)
        if len(raw_image_uuids) != len(planned_row.images):
            raise SlowpicsError("Invalid metadata response from slow.pics")
        image_uuids: list[str] = []
        for raw_image_uuid in raw_image_uuids:
            if not isinstance(raw_image_uuid, str) or not raw_image_uuid:
                raise SlowpicsError("Invalid metadata response from slow.pics")
            image_uuids.append(raw_image_uuid)
        rows.append(tuple(image_uuids))
    return tuple(rows)


def _is_complete_image_response(step: str, response: httpx.Response) -> bool:
    return (
        step == "image"
        and response.status_code == 400
        and response.headers.get("X-Error-Message") == "IMAGE_IS_COMPLETE"
    )
