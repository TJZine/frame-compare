"""Offline checks for isolated slow.pics webhook delivery."""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest

from frame_compare import __version__
from frame_compare.services.slowpics_webhook import (
    WEBHOOK_FAILURE_WARNING,
    WEBHOOK_VALIDATION_WARNING,
    SlowpicsWebhookResult,
    WebhookFailureKind,
    deliver_slowpics_webhook,
)

_WEBHOOK_URL = "https://hooks.example.test/notify"
_SLOWPICS_URL = "https://slow.pics/c/café"


class WebhookProbe:
    def __init__(self, *outcomes: httpx.Response | httpx.HTTPError) -> None:
        self.outcomes = outcomes
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        index = len(self.requests)
        self.requests.append(request)
        assert index < len(self.outcomes), "Unexpected webhook request"
        outcome = self.outcomes[index]
        if isinstance(outcome, httpx.HTTPError):
            raise outcome
        return outcome

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)

    async def deliver(
        self,
        url: str = _WEBHOOK_URL,
        *,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> SlowpicsWebhookResult:
        return await deliver_slowpics_webhook(
            webhook_url=url,
            slowpics_url=_SLOWPICS_URL,
            transport=httpx.MockTransport(self.handle),
            sleep=self.sleep if sleep is None else sleep,
        )


class UnreadableBody(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    def __aiter__(self) -> AsyncIterator[bytes]:
        raise AssertionError("Webhook response body was read")

    async def aclose(self) -> None:
        self.closed = True


async def test_success_posts_exact_payload_and_headers_without_reading_body() -> None:
    url = f"{_WEBHOOK_URL}/encoded%20space?mode=encoded%20space"
    body = UnreadableBody()
    probe = WebhookProbe(httpx.Response(204, stream=body))

    result = await probe.deliver(url)

    assert result == SlowpicsWebhookResult(success=True, detail="HTTP 204")
    (request,) = probe.requests
    assert request.method == "POST"
    assert str(request.url) == url
    assert request.content == rb'{"content":"https://slow.pics/c/caf\u00e9"}'
    assert request.headers["User-Agent"] == (
        f"DiscordBot (https://github.com/TJZine/frame-compare, {__version__}) "
        f"frame-compare/{__version__}"
    )
    assert request.headers["Content-Type"] == "application/json"
    assert body.closed
    assert probe.sleeps == []


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.test/notify",
        "ftp://hooks.example.test/notify",
        "https://",
        "https://user:pass@hooks.example.test/notify",
        "https://@hooks.example.test/notify",
        f"{_WEBHOOK_URL}#fragment",
        f"{_WEBHOOK_URL}#",
        "https://hóoks.example.test/notify",
        "https://hooks.example.test/café",
        "https://hooks.example.test:invalid/notify",
        "https://hooks.example.test:0/notify",
        "https://hooks.example.test:65536/notify",
        "https://.../notify",
        f"{_WEBHOOK_URL}/raw space",
        f"{_WEBHOOK_URL}?mode=raw space",
    ],
)
async def test_invalid_url_skips_delivery(url: str) -> None:
    probe = WebhookProbe()

    result = await probe.deliver(url)

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_VALIDATION_WARNING,
        failure_kind=WebhookFailureKind.VALIDATION,
    )
    assert result.warning is not None
    assert result.warning.text == (
        "slow.pics webhook: delivery skipped because the configured webhook URL is not an HTTPS URL"
    )
    assert probe.requests == []
    assert probe.sleeps == []


async def test_lan_https_url_is_attempted() -> None:
    url = "https://192.168.1.10/hook"
    probe = WebhookProbe(httpx.Response(204))

    result = await probe.deliver(url)

    assert result == SlowpicsWebhookResult(success=True, detail="HTTP 204")
    (request,) = probe.requests
    assert str(request.url) == url
    assert probe.sleeps == []


async def test_dotted_hostname_is_normalized_in_request() -> None:
    probe = WebhookProbe(httpx.Response(204))

    result = await probe.deliver(
        "https://hooks.example.test..:8443/notify%20me?mode=encoded%20space"
    )

    assert result == SlowpicsWebhookResult(success=True, detail="HTTP 204")
    (request,) = probe.requests
    assert request.url.host == "hooks.example.test"
    assert request.headers["Host"] == "hooks.example.test:8443"
    assert request.url.raw_path == b"/notify%20me?mode=encoded%20space"
    assert probe.sleeps == []


@pytest.mark.parametrize("error_type", [FileNotFoundError, ssl.SSLError])
async def test_tls_context_setup_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, error_type: type[OSError]
) -> None:
    def fail_tls_context() -> ssl.SSLContext:
        raise error_type("private TLS configuration details")

    monkeypatch.setattr(ssl, "create_default_context", fail_tls_context)
    probe = WebhookProbe()

    result = await probe.deliver()

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.TRANSPORT,
    )
    assert result.warning is not None
    assert result.warning.text == "slow.pics webhook: delivery failed"
    assert probe.requests == []
    assert probe.sleeps == []


@pytest.mark.parametrize(
    "location",
    ["https://redirect.example.test/notify", "https://redirect.example.test:invalid/notify"],
    ids=["valid-location", "malformed-location"],
)
async def test_redirect_is_failure_without_following_location(location: str) -> None:
    body = UnreadableBody()
    probe = WebhookProbe(httpx.Response(302, headers={"Location": location}, stream=body))

    result = await probe.deliver()

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.HTTP_STATUS,
        status_code=302,
    )
    assert len(probe.requests) == 1
    assert probe.sleeps == []
    assert body.closed


async def test_connect_errors_retry_with_backoff_then_succeed() -> None:
    probe = WebhookProbe(
        httpx.ConnectError("connection failed"),
        httpx.ConnectError("connection failed"),
        httpx.Response(204),
    )

    result = await probe.deliver()

    assert result == SlowpicsWebhookResult(success=True, detail="HTTP 204")
    assert len(probe.requests) == 3
    assert probe.sleeps == [1.0, 2.0]


async def test_connect_timeouts_exhaust_attempts() -> None:
    probe = WebhookProbe(*(httpx.ConnectTimeout("connect timed out") for _ in range(3)))

    result = await probe.deliver()

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.TIMEOUT,
    )
    assert len(probe.requests) == 3
    assert probe.sleeps == [1.0, 2.0]


async def test_server_errors_exhaust_attempts() -> None:
    probe = WebhookProbe(*(httpx.Response(503) for _ in range(3)))

    result = await probe.deliver()

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.HTTP_STATUS,
        status_code=503,
    )
    assert len(probe.requests) == 3
    assert probe.sleeps == [1.0, 2.0]


async def test_read_timeout_is_uncertain_without_retry() -> None:
    probe = WebhookProbe(httpx.ReadTimeout("read timed out"))

    result = await probe.deliver()

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.DELIVERY_UNCERTAIN,
    )
    assert len(probe.requests) == 1
    assert probe.sleeps == []


@pytest.mark.parametrize("delay", [0, 2, 10])
async def test_rate_limit_retries_after_bounded_delay(delay: int) -> None:
    probe = WebhookProbe(
        httpx.Response(429, headers={"Retry-After": str(delay)}), httpx.Response(204)
    )

    result = await probe.deliver()

    assert result == SlowpicsWebhookResult(success=True, detail="HTTP 204")
    assert len(probe.requests) == 2
    assert probe.sleeps == [float(delay)]


@pytest.mark.parametrize("value", [None, "11", "soon", "-1", "nan", "inf"])
async def test_rate_limit_without_bounded_delay_does_not_retry(value: str | None) -> None:
    headers = {} if value is None else {"Retry-After": value}
    probe = WebhookProbe(httpx.Response(429, headers=headers))

    result = await probe.deliver()

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.RATE_LIMITED,
        status_code=429,
    )
    assert len(probe.requests) == 1
    assert probe.sleeps == []


async def test_cancellation_during_backoff_stops_delivery() -> None:
    probe = WebhookProbe(httpx.Response(503))

    async def cancel_sleep(delay: float) -> None:
        await probe.sleep(delay)
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await probe.deliver(sleep=cancel_sleep)

    assert len(probe.requests) == 1
    assert probe.sleeps == [1.0]


async def test_final_connect_error_redacts_url_and_exception_text() -> None:
    url = f"{_WEBHOOK_URL}/private-token?secret-query"
    probe = WebhookProbe(*(httpx.ConnectError(f"failed to connect to {url}") for _ in range(3)))

    result = await probe.deliver(url)

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.TRANSPORT,
    )
    assert result.warning is not None
    for text in (repr(result), result.warning.text):
        assert "private-token" not in text
        assert "secret-query" not in text
        assert "failed to connect" not in text
    assert len(probe.requests) == 3
    assert probe.sleeps == [1.0, 2.0]
