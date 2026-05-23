"""Tests for slow.pics publisher service."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from frame_compare.config.schema import SlowpicsConfig, Visibility
from frame_compare.services.errors import (
    SlowpicsError,
    SlowpicsRateLimitedError,
    SlowpicsUnavailableError,
)
from frame_compare.services.publishers import (
    SlowpicsPublisher,
    publish_to_slowpics,
)
from frame_compare.services.types import TmdbMetadata


def _multipart_field_value(request: httpx.Request, field_name: str) -> str:
    body = request.content.decode("utf-8", errors="replace")
    name_marker = f'name="{field_name}"'
    field_start = body.index(name_marker)
    value_start = body.index("\r\n\r\n", field_start) + len("\r\n\r\n")
    value_end = body.index("\r\n--", value_start)
    return body[value_start:value_end]


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
def mock_slowpics_success(respx_mock):
    respx_mock.post("https://slow.pics/api/comparison").mock(
        return_value=httpx.Response(200, json={"url": "https://slow.pics/c/abc123"})
    )
    return respx_mock


@pytest.fixture
def screenshot_dir(tmp_path: Path) -> Path:
    dir_path = tmp_path / "screenshots"
    dir_path.mkdir()
    (dir_path / "test_00001.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    (dir_path / "test_00002.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return dir_path


@pytest.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.mark.anyio
async def test_publish_to_slowpics_success_returns_url(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    mock_slowpics_success,
):
    config = SlowpicsConfig()
    result = await publish_to_slowpics(screenshot_dir, config, async_client)

    assert result.url == "https://slow.pics/c/abc123"
    assert result.screenshot_count == 2
    assert result.upload_duration_seconds >= 0.0


@pytest.mark.anyio
async def test_publish_to_slowpics_rate_limited_raises_error(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
):
    respx_mock.post("https://slow.pics/api/comparison").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "1"})
    )
    config = SlowpicsConfig(max_retries=1)

    with pytest.raises(SlowpicsRateLimitedError):
        await publish_to_slowpics(screenshot_dir, config, async_client)

    assert mock_sleep.await_count == 1


@pytest.mark.anyio
async def test_publish_to_slowpics_server_error_raises_unavailable(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
):
    respx_mock.post("https://slow.pics/api/comparison").mock(return_value=httpx.Response(503))
    config = SlowpicsConfig(max_retries=2)

    with pytest.raises(SlowpicsUnavailableError):
        await publish_to_slowpics(screenshot_dir, config, async_client)

    assert mock_sleep.await_count == 2


@pytest.mark.anyio
async def test_publish_to_slowpics_timeout_raises_error(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
):
    respx_mock.post("https://slow.pics/api/comparison").mock(
        side_effect=httpx.TimeoutException("Timeout")
    )
    config = SlowpicsConfig(max_retries=1)

    with pytest.raises(SlowpicsError) as exc:
        await publish_to_slowpics(screenshot_dir, config, async_client)

    assert "timed out" in str(exc.value)
    assert mock_sleep.await_count == 1


@pytest.mark.anyio
async def test_publish_to_slowpics_malformed_retry_after_uses_default_delay(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
):
    route = respx_mock.post("https://slow.pics/api/comparison")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "not-a-delay"}),
        httpx.Response(200, json={"url": "https://slow.pics/c/abc123"}),
    ]
    config = SlowpicsConfig(max_retries=1)

    result = await publish_to_slowpics(screenshot_dir, config, async_client)

    assert result.url == "https://slow.pics/c/abc123"
    mock_sleep.assert_awaited_once_with(60.0)


@pytest.mark.anyio
async def test_publish_to_slowpics_http_date_retry_after_sleeps_until_date(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
):
    retry_at = datetime.now(UTC) + timedelta(seconds=120)
    route = respx_mock.post("https://slow.pics/api/comparison")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": format_datetime(retry_at)}),
        httpx.Response(200, json={"url": "https://slow.pics/c/abc123"}),
    ]
    config = SlowpicsConfig(max_retries=1)

    result = await publish_to_slowpics(screenshot_dir, config, async_client)

    assert result.url == "https://slow.pics/c/abc123"
    delay = mock_sleep.await_args.args[0]
    assert isinstance(delay, float)
    assert 0.0 < delay <= 120.0


@pytest.mark.anyio
async def test_publish_to_slowpics_retry_success(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
):
    # First 503, then 200
    route = respx_mock.post("https://slow.pics/api/comparison")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json={"url": "https://slow.pics/c/abc123"}),
    ]

    config = SlowpicsConfig(max_retries=2)
    result = await publish_to_slowpics(screenshot_dir, config, async_client)

    assert result.url == "https://slow.pics/c/abc123"
    assert mock_sleep.await_count == 1


@pytest.mark.anyio
async def test_publish_to_slowpics_4xx_fails_immediately(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
):
    respx_mock.post("https://slow.pics/api/comparison").mock(
        return_value=httpx.Response(400, text="Bad Request")
    )
    config = SlowpicsConfig()

    with pytest.raises(SlowpicsError):
        await publish_to_slowpics(screenshot_dir, config, async_client)

    assert mock_sleep.await_count == 0


@pytest.mark.anyio
async def test_publish_to_slowpics_uses_metadata_title(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    mock_slowpics_success,
    mocker,
):
    spy = mocker.spy(SlowpicsPublisher, "_prepare_upload")
    metadata = TmdbMetadata(
        tmdb_id=1,
        title="My Movie",
        original_title="My Movie",
        year=2021,
        media_type="movie",
    )
    config = SlowpicsConfig()

    await publish_to_slowpics(screenshot_dir, config, async_client, metadata=metadata)

    # Check title argument
    assert spy.call_args[0][2] == "My Movie"


@pytest.mark.anyio
async def test_publish_to_slowpics_default_title_uses_directory_name(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    mock_slowpics_success,
    mocker,
):
    spy = mocker.spy(SlowpicsPublisher, "_prepare_upload")
    config = SlowpicsConfig()

    await publish_to_slowpics(screenshot_dir, config, async_client)

    # Check title argument
    assert spy.call_args[0][2] == screenshot_dir.name


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("visibility", "expected_public"),
    [
        (Visibility.PUBLIC, "true"),
        (Visibility.UNLISTED, "false"),
    ],
)
async def test_publish_to_slowpics_sends_supported_visibility_payload(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    visibility: Visibility,
    expected_public: str,
):
    requests: list[httpx.Request] = []

    def capture_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"url": "https://slow.pics/c/abc123"})

    respx_mock.post("https://slow.pics/api/comparison").mock(side_effect=capture_request)
    config = SlowpicsConfig(visibility=visibility)

    await publish_to_slowpics(screenshot_dir, config, async_client)

    assert len(requests) == 1
    assert _multipart_field_value(requests[0], "public") == expected_public
    body = requests[0].content.decode("utf-8", errors="replace")
    assert 'name="visibility"' not in body
    assert 'name="private"' not in body


@pytest.mark.anyio
async def test_publish_to_slowpics_empty_dir_raises_error(
    tmp_path: Path,
    async_client: httpx.AsyncClient,
):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    config = SlowpicsConfig()

    with pytest.raises(SlowpicsError) as exc:
        await publish_to_slowpics(empty_dir, config, async_client)

    assert "No PNG files found" in str(exc.value)


@pytest.mark.anyio
async def test_publish_to_slowpics_delete_after_upload_deletes_files_on_success(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    mock_slowpics_success,
):
    config = SlowpicsConfig(delete_after_upload=True)

    await publish_to_slowpics(screenshot_dir, config, async_client)

    # Check files are gone
    assert not any(screenshot_dir.glob("*.png"))


@pytest.mark.anyio
async def test_publish_to_slowpics_delete_after_upload_does_not_delete_on_error(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    respx_mock,
    mock_sleep,
    mock_jitter,
):
    # Setup: mock 503 to trigger SlowpicsUnavailableError after retries
    respx_mock.post("https://slow.pics/api/comparison").mock(return_value=httpx.Response(503))
    config = SlowpicsConfig(delete_after_upload=True, max_retries=1)

    # Act + Assert exception
    with pytest.raises(SlowpicsUnavailableError):
        await publish_to_slowpics(screenshot_dir, config, async_client)

    # Assert files remain after exception
    assert len(list(screenshot_dir.glob("*.png"))) == 2


@pytest.mark.anyio
async def test_slowpics_publisher_upload_returns_url(
    screenshot_dir: Path,
    async_client: httpx.AsyncClient,
    mock_slowpics_success,
):
    config = SlowpicsConfig()
    publisher = SlowpicsPublisher(config, async_client)
    files = sorted(screenshot_dir.glob("*.png"))

    url = await publisher.upload(files)
    assert url == "https://slow.pics/c/abc123"


@pytest.mark.anyio
async def test_slowpics_publisher_does_not_own_client(
    screenshot_dir: Path,
    mock_slowpics_success,
):
    config = SlowpicsConfig()
    async with httpx.AsyncClient() as client:
        publisher = SlowpicsPublisher(config, client)
        await publisher.upload(sorted(screenshot_dir.glob("*.png")))
        # Client should still be open
        assert not client.is_closed
