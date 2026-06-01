"""Tests for slow.pics publisher service."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest

from frame_compare.config.schema import SlowpicsConfig, Visibility
from frame_compare.services.errors import (
    SlowpicsError,
    SlowpicsUnavailableError,
)
from frame_compare.services.publishers import (
    SLOWPICS_BROWSER_ID_SENTINEL,
    SLOWPICS_USER_AGENT,
    SlowpicsPublisher,
    publish_to_slowpics,
)
from frame_compare.services.slowpics_upload_plan import (
    SlowpicsPlannedImage,
    SlowpicsUploadPlan,
    SlowpicsUploadRow,
)
from frame_compare.services.types import TmdbMetadata


def _png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return path


def _plan(tmp_path: Path, *, rows: int = 2, cols: int = 2) -> SlowpicsUploadPlan:
    upload_rows: list[SlowpicsUploadRow] = []
    for row_index in range(rows):
        images: list[SlowpicsPlannedImage] = []
        for image_index in range(cols):
            clip_label = "Reference" if image_index == 0 else f"Encode {image_index}"
            image_name = "reference-source" if image_index == 0 else f"encode-source-{image_index}"
            path = _png(tmp_path / "screenshots" / f"{row_index}-{image_index}.png")
            images.append(
                SlowpicsPlannedImage(
                    row_index=row_index,
                    selected_frame=10 + row_index,
                    image_index=image_index,
                    clip_label=clip_label,
                    image_name=image_name,
                    screenshot_path=path,
                    sort_order=image_index,
                )
            )
        upload_rows.append(
            SlowpicsUploadRow(
                row_index=row_index,
                selected_frame=10 + row_index,
                row_name=str(10 + row_index),
                sort_order=row_index,
                images=tuple(images),
            )
        )
    return SlowpicsUploadPlan(rows=tuple(upload_rows))


def _metadata_payload(
    *,
    rows: int = 2,
    cols: int = 2,
    first_comparison_key: str | None = "first-key",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "key": "collection-key",
        "collectionUuid": "collection-uuid-secret",
        "images": [[f"image-{row}-{col}-secret" for col in range(cols)] for row in range(rows)],
    }
    if first_comparison_key is not None:
        payload["firstComparisonKey"] = first_comparison_key
    return payload


def _multipart_field_value(request: httpx.Request, field_name: str) -> str:
    body = request.content.decode("utf-8", errors="replace")
    name_marker = f'name="{field_name}"'
    field_start = body.index(name_marker)
    value_start = body.index("\r\n\r\n", field_start) + len("\r\n\r\n")
    value_end = body.index("\r\n--", value_start)
    return body[value_start:value_end]


def _multipart_filenames(request: httpx.Request) -> list[str]:
    body = request.content.decode("utf-8", errors="replace")
    filenames: list[str] = []
    for part in body.split("\r\n"):
        marker = 'filename="'
        if marker in part:
            start = part.index(marker) + len(marker)
            end = part.index('"', start)
            filenames.append(part[start:end])
    return filenames


def _assert_generated_multipart_content_type(request: httpx.Request) -> None:
    content_type = request.headers["Content-Type"]
    assert content_type.startswith("multipart/form-data; boundary=")


def _request_cookie_value(request: httpx.Request, cookie_name: str) -> str:
    cookie_header = request.headers["Cookie"]
    parsed = SimpleCookie[str]()
    parsed.load(cookie_header)
    return parsed[cookie_name].value


@pytest.fixture
def mock_sleep(mocker):
    return mocker.patch(
        "frame_compare.services.publishers.asyncio.sleep",
        new_callable=lambda: AsyncMock(return_value=None),
    )


@pytest.fixture
def mock_jitter(mocker):
    return mocker.patch(
        "frame_compare.services.publishers.random.uniform",
        return_value=0.0,
    )


@pytest.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


def _mock_successful_browser_flow(respx_mock, *, rows: int = 2, cols: int = 2) -> None:
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token%2Bdecoded; Domain=.slow.pics; Path=/"},
        )
    )
    respx_mock.post("https://slow.pics/upload/comparison").mock(
        return_value=httpx.Response(200, json=_metadata_payload(rows=rows, cols=cols))
    )
    for row in range(rows):
        for col in range(cols):
            respx_mock.post(f"https://slow.pics/upload/image/image-{row}-{col}-secret").mock(
                return_value=httpx.Response(200)
            )


@pytest.mark.anyio
async def test_publish_to_slowpics_success_returns_url(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path)
    _mock_successful_browser_flow(respx_mock)

    result = await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    assert result.url == "https://slow.pics/c/first-key"
    assert result.screenshot_count == 4
    assert result.upload_duration_seconds >= 0.0


@pytest.mark.anyio
async def test_publish_to_slowpics_get_comparison_precedes_metadata_upload(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    events: list[str] = []

    def comparison_page(_request: httpx.Request) -> httpx.Response:
        events.append("get")
        return httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
        )

    def metadata_upload(_request: httpx.Request) -> httpx.Response:
        events.append("metadata")
        return httpx.Response(200, json=_metadata_payload(rows=1, cols=1))

    respx_mock.get("https://slow.pics/comparison").mock(side_effect=comparison_page)
    respx_mock.post("https://slow.pics/upload/comparison").mock(side_effect=metadata_upload)
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(
        return_value=httpx.Response(200)
    )

    await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    assert events == ["get", "metadata"]


@pytest.mark.anyio
async def test_publish_to_slowpics_sends_decoded_xsrf_browser_id_headers_and_user_agent(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    requests: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/comparison":
            return httpx.Response(
                200,
                headers={
                    "Set-Cookie": "XSRF-TOKEN=token%2Bdecoded; Domain=.slow.pics; Path=/"
                },
            )
        if request.url.path == "/upload/comparison":
            return httpx.Response(200, json=_metadata_payload(rows=1, cols=1))
        return httpx.Response(200)

    respx_mock.get("https://slow.pics/comparison").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/comparison").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(side_effect=capture)

    await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    metadata_request = requests[1]
    image_request = requests[2]
    browser_id = _multipart_field_value(metadata_request, "browserId")
    assert requests[0].headers["User-Agent"] == SLOWPICS_USER_AGENT
    assert metadata_request.headers["User-Agent"] == SLOWPICS_USER_AGENT
    assert image_request.headers["User-Agent"] == SLOWPICS_USER_AGENT
    assert metadata_request.headers["X-XSRF-TOKEN"] == "token+decoded"
    assert image_request.headers["X-XSRF-TOKEN"] == "token+decoded"
    assert metadata_request.headers["Origin"] == "https://slow.pics"
    assert metadata_request.headers["Referer"] == "https://slow.pics/comparison"
    assert image_request.headers["Origin"] == "https://slow.pics"
    assert image_request.headers["Referer"] == "https://slow.pics/comparison"
    assert browser_id
    assert _multipart_field_value(image_request, "browserId") == browser_id
    assert f"BROWSER-ID={browser_id}" in metadata_request.headers["Cookie"]
    assert async_client.cookies.get("BROWSER-ID") == browser_id
    _assert_generated_multipart_content_type(metadata_request)
    _assert_generated_multipart_content_type(image_request)


@pytest.mark.anyio
async def test_publish_to_slowpics_reuses_existing_browser_id_cookie(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    async_client.cookies.set("BROWSER-ID", "existing-browser-id", domain="slow.pics", path="/")
    requests: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/comparison":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
            )
        if request.url.path == "/upload/comparison":
            return httpx.Response(200, json=_metadata_payload(rows=1, cols=1))
        return httpx.Response(200)

    respx_mock.get("https://slow.pics/comparison").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/comparison").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(side_effect=capture)

    await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    assert _multipart_field_value(requests[1], "browserId") == "existing-browser-id"
    assert _multipart_field_value(requests[2], "browserId") == "existing-browser-id"


@pytest.mark.anyio
async def test_publish_to_slowpics_replaces_sentinel_browser_id_cookie(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    async_client.cookies.set(
        "BROWSER-ID",
        SLOWPICS_BROWSER_ID_SENTINEL,
        domain="slow.pics",
        path="/",
    )
    requests: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/comparison":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
            )
        if request.url.path == "/upload/comparison":
            return httpx.Response(200, json=_metadata_payload(rows=1, cols=1))
        return httpx.Response(200)

    respx_mock.get("https://slow.pics/comparison").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/comparison").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(side_effect=capture)

    await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    browser_id = _multipart_field_value(requests[1], "browserId")
    assert browser_id
    assert browser_id != SLOWPICS_BROWSER_ID_SENTINEL
    assert UUID(browser_id).version == 4
    assert _multipart_field_value(requests[2], "browserId") == browser_id
    assert _request_cookie_value(requests[1], "BROWSER-ID") == browser_id
    assert _request_cookie_value(requests[2], "BROWSER-ID") == browser_id
    assert SLOWPICS_BROWSER_ID_SENTINEL not in requests[1].headers["Cookie"]
    assert SLOWPICS_BROWSER_ID_SENTINEL not in requests[2].headers["Cookie"]
    assert async_client.cookies.get("BROWSER-ID") == browser_id
    assert all(
        cookie.value != SLOWPICS_BROWSER_ID_SENTINEL
        for cookie in async_client.cookies.jar
        if cookie.name == "BROWSER-ID"
    )


@pytest.mark.anyio
async def test_publish_to_slowpics_metadata_uses_plan_names_sort_order_and_visibility(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=2, cols=2)
    metadata_requests: list[httpx.Request] = []
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
        )
    )

    def capture_metadata(request: httpx.Request) -> httpx.Response:
        metadata_requests.append(request)
        return httpx.Response(200, json=_metadata_payload())

    respx_mock.post("https://slow.pics/upload/comparison").mock(side_effect=capture_metadata)
    for row in range(2):
        for col in range(2):
            respx_mock.post(f"https://slow.pics/upload/image/image-{row}-{col}-secret").mock(
                return_value=httpx.Response(200)
            )

    metadata = TmdbMetadata(
        tmdb_id=1,
        title="My Movie",
        original_title="My Movie",
        year=2021,
        media_type="movie",
    )
    await publish_to_slowpics(
        tmp_path / "screenshots",
        SlowpicsConfig(visibility=Visibility.PUBLIC),
        async_client,
        metadata=metadata,
        upload_plan=upload_plan,
    )

    request = metadata_requests[0]
    assert _multipart_field_value(request, "collectionName") == "My Movie"
    assert _multipart_field_value(request, "optimizeImages") == "true"
    assert _multipart_field_value(request, "desiredFileType") == "image/png"
    assert _multipart_field_value(request, "hentai") == "false"
    assert _multipart_field_value(request, "public") == "true"
    assert _multipart_field_value(request, "visibility") == "PUBLIC"
    assert _multipart_field_value(request, "removeAfter") == ""
    assert _multipart_field_value(request, "comparisons[0].name") == "10"
    assert _multipart_field_value(request, "comparisons[0].hentai") == "false"
    assert _multipart_field_value(request, "comparisons[0].sortOrder") == "0"
    assert _multipart_field_value(request, "comparisons[0].images[0].name") == "reference-source"
    assert _multipart_field_value(request, "comparisons[0].images[0].sortOrder") == "0"
    assert _multipart_field_value(request, "comparisons[1].name") == "11"
    assert _multipart_field_value(request, "comparisons[1].sortOrder") == "1"
    assert _multipart_field_value(request, "comparisons[1].images[1].name") == "encode-source-1"
    assert _multipart_field_value(request, "comparisons[1].images[1].sortOrder") == "1"


@pytest.mark.anyio
async def test_publish_to_slowpics_response_matrix_maps_to_matching_image_uploads(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=2, cols=2)
    image_requests: list[httpx.Request] = []
    _mock_successful_browser_flow(respx_mock)
    for row in range(2):
        for col in range(2):
            respx_mock.post(f"https://slow.pics/upload/image/image-{row}-{col}-secret").mock(
                side_effect=lambda request: image_requests.append(request) or httpx.Response(200)
            )

    await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    assert [request.url.path for request in image_requests] == [
        "/upload/image/image-0-0-secret",
        "/upload/image/image-0-1-secret",
        "/upload/image/image-1-0-secret",
        "/upload/image/image-1-1-secret",
    ]
    assert [_multipart_filenames(request) for request in image_requests] == [
        ["0-0.png"],
        ["0-1.png"],
        ["1-0.png"],
        ["1-1.png"],
    ]
    assert _multipart_field_value(image_requests[3], "collectionUuid") == "collection-uuid-secret"
    assert _multipart_field_value(image_requests[3], "imageUuid") == "image-1-1-secret"


@pytest.mark.anyio
async def test_publish_to_slowpics_metadata_response_count_mismatch_fails_before_image_upload(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=2, cols=2)
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
        )
    )
    respx_mock.post("https://slow.pics/upload/comparison").mock(
        return_value=httpx.Response(200, json=_metadata_payload(rows=1, cols=2))
    )
    image_route = respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(
        return_value=httpx.Response(200)
    )

    with pytest.raises(SlowpicsError, match="Invalid metadata response"):
        await publish_to_slowpics(
            tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
        )

    assert image_route.call_count == 0


@pytest.mark.anyio
async def test_publish_to_slowpics_returned_url_falls_back_to_key(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
        )
    )
    respx_mock.post("https://slow.pics/upload/comparison").mock(
        return_value=httpx.Response(
            200, json=_metadata_payload(rows=1, cols=1, first_comparison_key=None)
        )
    )
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(
        return_value=httpx.Response(200)
    )

    result = await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    assert result.url == "https://slow.pics/c/collection-key"


@pytest.mark.anyio
async def test_publish_to_slowpics_does_not_request_legacy_api_endpoint(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    _mock_successful_browser_flow(respx_mock, rows=1, cols=1)
    legacy_route = respx_mock.post("https://slow.pics/api/comparison").mock(
        return_value=httpx.Response(500)
    )

    await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    assert legacy_route.call_count == 0


@pytest.mark.anyio
async def test_publish_to_slowpics_missing_xsrf_token_fails_before_metadata_post(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    respx_mock.get("https://slow.pics/comparison").mock(return_value=httpx.Response(200))
    metadata_route = respx_mock.post("https://slow.pics/upload/comparison").mock(
        return_value=httpx.Response(200, json=_metadata_payload(rows=1, cols=1))
    )

    with pytest.raises(SlowpicsError, match="Missing slow.pics XSRF token"):
        await publish_to_slowpics(
            tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
        )

    assert metadata_route.call_count == 0


@pytest.mark.anyio
async def test_publish_to_slowpics_malformed_metadata_response_fails_before_image_upload(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
        )
    )
    respx_mock.post("https://slow.pics/upload/comparison").mock(
        return_value=httpx.Response(200, text="not json")
    )
    image_route = respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(
        return_value=httpx.Response(200)
    )

    with pytest.raises(SlowpicsError, match="Invalid metadata response"):
        await publish_to_slowpics(
            tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
        )

    assert image_route.call_count == 0


@pytest.mark.anyio
async def test_publish_to_slowpics_partial_image_failure_does_not_delete_files(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=2)
    files = upload_plan.file_paths
    _mock_successful_browser_flow(respx_mock, rows=1, cols=2)
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(
        return_value=httpx.Response(200)
    )
    respx_mock.post("https://slow.pics/upload/image/image-0-1-secret").mock(
        return_value=httpx.Response(503)
    )

    with pytest.raises(SlowpicsUnavailableError):
        await publish_to_slowpics(
            tmp_path / "screenshots",
            SlowpicsConfig(delete_after_upload=True, max_retries=1),
            async_client,
            upload_plan=upload_plan,
        )

    assert all(path.exists() for path in files)
    assert mock_sleep.await_count == 1


@pytest.mark.anyio
async def test_publish_to_slowpics_image_is_complete_response_is_success(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    _mock_successful_browser_flow(respx_mock, rows=1, cols=1)
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(
        return_value=httpx.Response(400, headers={"X-Error-Message": "IMAGE_IS_COMPLETE"})
    )

    result = await publish_to_slowpics(
        tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
    )

    assert result.url == "https://slow.pics/c/first-key"


@pytest.mark.anyio
async def test_publish_to_slowpics_retry_policy_is_step_specific(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    comparison_route = respx_mock.get("https://slow.pics/comparison")
    comparison_route.side_effect = [
        httpx.Response(503),
        httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
        ),
    ]
    respx_mock.post("https://slow.pics/upload/comparison").mock(
        return_value=httpx.Response(200, json=_metadata_payload(rows=1, cols=1))
    )
    image_route = respx_mock.post("https://slow.pics/upload/image/image-0-0-secret")
    image_route.side_effect = [httpx.TimeoutException("timeout"), httpx.Response(200)]

    await publish_to_slowpics(
        tmp_path / "screenshots",
        SlowpicsConfig(max_retries=1),
        async_client,
        upload_plan=upload_plan,
    )

    assert comparison_route.call_count == 2
    assert image_route.call_count == 2
    assert mock_sleep.await_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "metadata_error",
    [
        httpx.TimeoutException("timeout with token-secret"),
        httpx.ConnectError("connect failed with browser-secret"),
    ],
)
async def test_publish_to_slowpics_metadata_timeout_and_request_error_do_not_retry(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    metadata_error: Exception,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token-secret; Domain=.slow.pics; Path=/"},
        )
    )
    metadata_route = respx_mock.post("https://slow.pics/upload/comparison").mock(
        side_effect=metadata_error
    )

    with pytest.raises(SlowpicsError) as exc:
        await publish_to_slowpics(
            tmp_path / "screenshots",
            SlowpicsConfig(max_retries=3),
            async_client,
            upload_plan=upload_plan,
        )

    assert "remote slow.pics state is unknown" in str(exc.value)
    assert "token-secret" not in str(exc.value)
    assert "browser-secret" not in str(exc.value)
    assert metadata_route.call_count == 1
    assert mock_sleep.await_count == 0


@pytest.mark.anyio
async def test_publish_to_slowpics_metadata_retries_response_rate_limit(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    retry_at = datetime.now(UTC) + timedelta(seconds=120)
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
        )
    )
    metadata_route = respx_mock.post("https://slow.pics/upload/comparison")
    metadata_route.side_effect = [
        httpx.Response(429, headers={"Retry-After": format_datetime(retry_at)}),
        httpx.Response(200, json=_metadata_payload(rows=1, cols=1)),
    ]
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(
        return_value=httpx.Response(200)
    )

    result = await publish_to_slowpics(
        tmp_path / "screenshots",
        SlowpicsConfig(max_retries=1),
        async_client,
        upload_plan=upload_plan,
    )

    assert result.url == "https://slow.pics/c/first-key"
    assert metadata_route.call_count == 2
    mock_sleep.assert_awaited_once()


@pytest.mark.anyio
async def test_publish_to_slowpics_metadata_retries_response_server_error(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
        )
    )
    metadata_route = respx_mock.post("https://slow.pics/upload/comparison")
    metadata_route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json=_metadata_payload(rows=1, cols=1)),
    ]
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(
        return_value=httpx.Response(200)
    )

    result = await publish_to_slowpics(
        tmp_path / "screenshots",
        SlowpicsConfig(max_retries=1),
        async_client,
        upload_plan=upload_plan,
    )

    assert result.url == "https://slow.pics/c/first-key"
    assert metadata_route.call_count == 2
    assert mock_sleep.await_count == 1


@pytest.mark.anyio
async def test_publish_to_slowpics_does_not_delete_local_files_after_upload(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=2)
    stale = _png(tmp_path / "screenshots" / "stale.png")
    requests: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/comparison":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "XSRF-TOKEN=token; Domain=.slow.pics; Path=/"},
            )
        if request.url.path == "/upload/comparison":
            assert all(path.exists() for path in upload_plan.file_paths)
            return httpx.Response(200, json=_metadata_payload(rows=1, cols=2))
        assert all(path.exists() for path in upload_plan.file_paths)
        return httpx.Response(200)

    respx_mock.get("https://slow.pics/comparison").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/comparison").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/image/image-0-0-secret").mock(side_effect=capture)
    respx_mock.post("https://slow.pics/upload/image/image-0-1-secret").mock(side_effect=capture)

    await publish_to_slowpics(
        tmp_path / "screenshots",
        SlowpicsConfig(delete_after_upload=True),
        async_client,
        upload_plan=upload_plan,
    )

    assert all(path.exists() for path in upload_plan.file_paths)
    assert stale.exists()
    assert _multipart_field_value(requests[1], "removeAfter") == ""


@pytest.mark.anyio
async def test_publish_to_slowpics_sensitive_values_redacted_from_exceptions(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    respx_mock.get("https://slow.pics/comparison").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "XSRF-TOKEN=xsrf-secret; Domain=.slow.pics; Path=/"},
        )
    )
    respx_mock.post("https://slow.pics/upload/comparison").mock(
        return_value=httpx.Response(
            200,
            json={
                "key": "private-key-secret",
                "firstComparisonKey": "first-key-secret",
                "collectionUuid": "collection-uuid-secret",
                "images": [["image-uuid-secret"]],
            },
        )
    )
    respx_mock.post("https://slow.pics/upload/image/image-uuid-secret").mock(
        return_value=httpx.Response(
            400,
            text=(
                "raw body xsrf-secret browser-secret collection-uuid-secret "
                "image-uuid-secret private-key-secret https://webhook.example/path"
            ),
        )
    )

    with pytest.raises(SlowpicsError) as exc:
        await publish_to_slowpics(
            tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
        )

    message = str(exc.value)
    assert "status 400" in message
    assert "xsrf-secret" not in message
    assert "browser-secret" not in message
    assert "collection-uuid-secret" not in message
    assert "image-uuid-secret" not in message
    assert "private-key-secret" not in message
    assert "webhook.example" not in message


@pytest.mark.anyio
async def test_publish_to_slowpics_empty_plan_raises_error(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
) -> None:
    with pytest.raises(SlowpicsError, match="No PNG files found"):
        await publish_to_slowpics(
            tmp_path / "screenshots",
            SlowpicsConfig(),
            async_client,
            upload_plan=SlowpicsUploadPlan(rows=()),
        )


@pytest.mark.anyio
async def test_publish_to_slowpics_rejects_missing_planned_file_before_request(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    upload_plan.file_paths[0].unlink()
    route = respx_mock.get("https://slow.pics/comparison").mock(return_value=httpx.Response(200))

    with pytest.raises(SlowpicsError, match="planned for slow.pics upload is missing"):
        await publish_to_slowpics(
            tmp_path / "screenshots", SlowpicsConfig(), async_client, upload_plan=upload_plan
        )

    assert route.call_count == 0


@pytest.mark.anyio
async def test_slowpics_publisher_upload_returns_url(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    _mock_successful_browser_flow(respx_mock, rows=1, cols=1)
    publisher = SlowpicsPublisher(SlowpicsConfig(), async_client)

    url = await publisher.upload(upload_plan)

    assert url == "https://slow.pics/c/first-key"


@pytest.mark.anyio
async def test_slowpics_publisher_does_not_own_client(
    tmp_path: Path,
    respx_mock,
) -> None:
    upload_plan = _plan(tmp_path, rows=1, cols=1)
    _mock_successful_browser_flow(respx_mock, rows=1, cols=1)

    async with httpx.AsyncClient() as client:
        publisher = SlowpicsPublisher(SlowpicsConfig(), client)
        await publisher.upload(upload_plan)
        assert not client.is_closed
