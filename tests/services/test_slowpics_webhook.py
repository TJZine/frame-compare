from __future__ import annotations

import ssl
from collections.abc import Callable

import pytest

from frame_compare.services.slowpics_webhook import (
    WEBHOOK_ATTEMPTS,
    WEBHOOK_CONTENT_TYPE,
    WEBHOOK_FAILURE_WARNING,
    WEBHOOK_MAX_RETRY_AFTER_SECONDS,
    WEBHOOK_RETRY_BASE_DELAY_SECONDS,
    WEBHOOK_TIMEOUT_SECONDS,
    WEBHOOK_USER_AGENT,
    WEBHOOK_VALIDATION_WARNING,
    SlowpicsWebhookResult,
    WebhookDeliveryRequest,
    WebhookDeliveryUncertainError,
    WebhookFailureKind,
    WebhookResponse,
    deliver_slowpics_webhook,
    send_pinned_https_webhook_request,
)

type Resolver = Callable[[str, int], tuple[str, ...]]
type Sleeper = Callable[[float], None]


def _public_resolver(_hostname: str, _port: int) -> tuple[str, ...]:
    return ("93.184.216.34",)


def _no_sleep(_delay_seconds: float) -> None:
    return


async def _deliver(
    webhook_url: str,
    *,
    resolver: Resolver = _public_resolver,
    connector: Callable[[WebhookDeliveryRequest], WebhookResponse],
    sleeper: Sleeper = _no_sleep,
) -> SlowpicsWebhookResult:
    return await deliver_slowpics_webhook(
        webhook_url=webhook_url,
        slowpics_url="https://slow.pics/c/example",
        resolver=resolver,
        connector=connector,
        sleeper=sleeper,
    )


def _unexpected_connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
    raise AssertionError("webhook connector should not be called")


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.test/path",
        "https://localhost/path",
        "https://worker.localhost/path",
        "https://hooks.example.test/path#secret-token",
    ],
)
async def test_rejects_non_https_and_localhost_names(url: str) -> None:
    result = await _deliver(url, connector=_unexpected_connector)

    assert result.success is False
    assert result.warning is not None
    assert "hooks.example.test" not in result.warning
    assert "localhost" not in result.warning


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.1.1",
        "224.0.0.1",
        "240.0.0.1",
        "0.0.0.0",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "::",
    ],
)
async def test_rejects_non_public_ip_literals(address: str) -> None:
    host = f"[{address}]" if ":" in address else address
    result = await _deliver(f"https://{host}/path", connector=_unexpected_connector)

    assert result.success is False
    assert result.warning is not None


@pytest.mark.parametrize(
    ("answers", "expected_called"),
    [
        ((), False),
        (("10.0.0.1",), False),
        (("93.184.216.34", "10.0.0.1"), False),
        (("93.184.216.34",), True),
    ],
)
async def test_dns_policy_rejects_empty_disallowed_or_mixed_answers(
    answers: tuple[str, ...],
    expected_called: bool,
) -> None:
    calls: list[WebhookDeliveryRequest] = []

    def _resolver(_hostname: str, _port: int) -> tuple[str, ...]:
        return answers

    def _connector(request: WebhookDeliveryRequest) -> WebhookResponse:
        calls.append(request)
        return WebhookResponse(status_code=204)

    result = await _deliver(
        "https://hooks.example.test/path",
        resolver=_resolver,
        connector=_connector,
    )

    assert result.success is expected_called
    assert len(calls) == (1 if expected_called else 0)


async def test_resolution_failure_is_rejected_without_connecting() -> None:
    def _resolver(_hostname: str, _port: int) -> tuple[str, ...]:
        return ()

    result = await _deliver(
        "https://secret.example.test/path",
        resolver=_resolver,
        connector=_unexpected_connector,
    )

    assert result.success is False
    assert result.warning is not None
    assert "secret.example.test" not in result.warning
    assert "/path" not in result.warning


async def test_malformed_ipv6_url_returns_sanitized_validation_warning() -> None:
    result = await _deliver("https://[::1", connector=_unexpected_connector)

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_VALIDATION_WARNING,
        failure_kind=WebhookFailureKind.VALIDATION,
    )
    assert result.warning is not None
    assert "::1" not in result.warning


@pytest.mark.parametrize(
    ("url", "sensitive_fragments"),
    [
        ("https://éxample.test/path", ("éxample.test",)),
        ("https://hooks.example.test/påth", ("hooks.example.test", "påth")),
        (
            "https://hooks.example.test/path?secret=ø",
            ("hooks.example.test", "secret=ø"),
        ),
    ],
)
async def test_non_ascii_url_components_return_sanitized_validation_warning(
    url: str,
    sensitive_fragments: tuple[str, ...],
) -> None:
    result = await _deliver(url, connector=_unexpected_connector)

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_VALIDATION_WARNING,
        failure_kind=WebhookFailureKind.VALIDATION,
    )
    assert result.warning is not None
    for fragment in sensitive_fragments:
        assert fragment not in result.warning


async def test_delivery_connects_to_resolved_ip_preserving_hostname_sni_and_host_header() -> None:
    calls: list[WebhookDeliveryRequest] = []

    def _connector(request: WebhookDeliveryRequest) -> WebhookResponse:
        calls.append(request)
        return WebhookResponse(status_code=204)

    result = await _deliver(
        "https://hooks.example.test:8443/webhook/token?secret=value",
        connector=_connector,
    )

    assert result == SlowpicsWebhookResult(success=True, detail="HTTP 204")
    assert len(calls) == 1
    request = calls[0]
    assert request.resolved_ip == "93.184.216.34"
    assert request.hostname == "hooks.example.test"
    assert request.port == 8443
    assert request.host_header == "hooks.example.test:8443"
    assert request.target == "/webhook/token?secret=value"
    assert request.timeout_seconds == WEBHOOK_TIMEOUT_SECONDS
    assert request.body == b'{"content":"https://slow.pics/c/example"}'
    assert dict(request.headers) == {
        "Host": "hooks.example.test:8443",
        "User-Agent": WEBHOOK_USER_AGENT,
        "Content-Type": WEBHOOK_CONTENT_TYPE,
        "Content-Length": str(len(request.body)),
        "Connection": "close",
    }
    assert "Cookie" not in dict(request.headers)
    assert "Origin" not in dict(request.headers)
    assert "Referer" not in dict(request.headers)
    assert "X-XSRF-TOKEN" not in dict(request.headers)


async def test_connector_serialization_failure_returns_sanitized_warning() -> None:
    calls = 0

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        nonlocal calls
        calls += 1
        raise UnicodeEncodeError("ascii", "tøken", 1, 2, "ordinal not in range")

    result = await _deliver(
        "https://hooks.example.test/webhook/token?secret=value",
        connector=_connector,
    )

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.TRANSPORT,
    )
    assert calls == WEBHOOK_ATTEMPTS
    assert result.warning is not None
    assert "hooks.example.test" not in result.warning
    assert "/webhook/token" not in result.warning
    assert "secret=value" not in result.warning


def test_request_serialization_rejects_non_ascii_target_before_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_socket(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("socket should not be opened for invalid request bytes")

    monkeypatch.setattr("frame_compare.services.slowpics_webhook.socket.socket", _unexpected_socket)
    request = WebhookDeliveryRequest(
        hostname="hooks.example.test",
        port=443,
        resolved_ip="93.184.216.34",
        host_header="hooks.example.test",
        target="/webhook/tøken",
        headers=(
            ("Host", "hooks.example.test"),
            ("Content-Type", WEBHOOK_CONTENT_TYPE),
            ("Content-Length", "2"),
            ("Connection", "close"),
        ),
        body=b"{}",
        timeout_seconds=WEBHOOK_TIMEOUT_SECONDS,
    )

    with pytest.raises(OSError, match="Invalid webhook HTTP request"):
        send_pinned_https_webhook_request(request)


async def test_redirect_response_is_failure_without_followup_request() -> None:
    calls: list[WebhookDeliveryRequest] = []

    def _connector(request: WebhookDeliveryRequest) -> WebhookResponse:
        calls.append(request)
        return WebhookResponse(status_code=302)

    result = await _deliver("https://hooks.example.test/path", connector=_connector)

    assert result.success is False
    assert result.warning is not None
    assert result.failure_kind is WebhookFailureKind.HTTP_STATUS
    assert result.status_code == 302
    assert len(calls) == 1


@pytest.mark.parametrize(
    "failure",
    ["connection", "server"],
)
async def test_retryable_connection_and_server_failures_use_bounded_backoff(
    failure: str,
) -> None:
    calls: list[WebhookDeliveryRequest] = []
    sleep_calls: list[float] = []

    def _connector(request: WebhookDeliveryRequest) -> WebhookResponse:
        calls.append(request)
        if failure == "connection":
            raise OSError("connection failed")
        return WebhookResponse(status_code=503)

    result = await _deliver(
        "https://hooks.example.test/path",
        connector=_connector,
        sleeper=sleep_calls.append,
    )

    assert result.success is False
    assert result.warning is not None
    assert result.failure_kind is (
        WebhookFailureKind.TRANSPORT if failure == "connection" else WebhookFailureKind.HTTP_STATUS
    )
    assert result.status_code == (503 if failure == "server" else None)
    assert len(calls) == WEBHOOK_ATTEMPTS
    assert [request.timeout_seconds for request in calls] == [
        WEBHOOK_TIMEOUT_SECONDS,
        WEBHOOK_TIMEOUT_SECONDS,
        WEBHOOK_TIMEOUT_SECONDS,
    ]
    assert sleep_calls == [
        WEBHOOK_RETRY_BASE_DELAY_SECONDS,
        WEBHOOK_RETRY_BASE_DELAY_SECONDS * 2,
    ]


async def test_delivery_unknown_after_request_send_is_not_retried() -> None:
    calls = 0

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        nonlocal calls
        calls += 1
        raise WebhookDeliveryUncertainError("response timed out after request send")

    result = await _deliver("https://hooks.example.test/path", connector=_connector)

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.DELIVERY_UNCERTAIN,
    )
    assert calls == 1


async def test_certificate_verification_failure_is_not_retried() -> None:
    calls = 0

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        nonlocal calls
        calls += 1
        raise ssl.SSLCertVerificationError("certificate verification failed")

    result = await _deliver("https://hooks.example.test/path", connector=_connector)

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.CERTIFICATE,
    )
    assert calls == 1


async def test_rate_limit_retries_after_short_server_delay() -> None:
    calls = 0
    sleep_calls: list[float] = []

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return WebhookResponse(status_code=429, retry_after_seconds=2.5)
        return WebhookResponse(status_code=204)

    result = await _deliver(
        "https://hooks.example.test/path",
        connector=_connector,
        sleeper=sleep_calls.append,
    )

    assert result == SlowpicsWebhookResult(success=True, detail="HTTP 204")
    assert calls == 2
    assert sleep_calls == [2.5]


@pytest.mark.parametrize("retry_after", [None, WEBHOOK_MAX_RETRY_AFTER_SECONDS + 0.1])
async def test_rate_limit_without_usable_bounded_delay_is_not_retried(
    retry_after: float | None,
) -> None:
    calls = 0

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        nonlocal calls
        calls += 1
        return WebhookResponse(status_code=429, retry_after_seconds=retry_after)

    result = await _deliver("https://hooks.example.test/path", connector=_connector)

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.RATE_LIMITED,
        status_code=429,
    )
    assert calls == 1


async def test_retryable_failures_rotate_across_validated_addresses() -> None:
    calls: list[WebhookDeliveryRequest] = []

    def _resolver(_hostname: str, _port: int) -> tuple[str, ...]:
        return ("93.184.216.34", "1.1.1.1")

    def _connector(request: WebhookDeliveryRequest) -> WebhookResponse:
        calls.append(request)
        raise TimeoutError("timed out")

    result = await _deliver(
        "https://hooks.example.test/path",
        resolver=_resolver,
        connector=_connector,
    )

    assert result.success is False
    assert result.warning is not None
    assert result.failure_kind is WebhookFailureKind.TIMEOUT
    assert [request.resolved_ip for request in calls] == [
        "93.184.216.34",
        "1.1.1.1",
        "93.184.216.34",
    ]


async def test_warnings_redact_configured_webhook_url_details() -> None:
    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        return WebhookResponse(status_code=503)

    result = await _deliver(
        "https://secret.example.test/webhook/token?secret=value",
        connector=_connector,
    )

    assert result.success is False
    assert result.warning is not None
    assert "secret.example.test" not in result.warning
    assert "webhook" in result.warning
    assert "/webhook/token" not in result.warning
    assert "secret=value" not in result.warning


def test_pinned_transport_parses_retry_after_and_preserves_sni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[bytes] = []
    connected: list[tuple[str, int]] = []
    server_names: list[str] = []

    class FakeSocket:
        def __init__(self, _family: int, _socket_type: int) -> None:
            return

        def settimeout(self, _timeout: float) -> None:
            return

        def connect(self, address: tuple[str, int]) -> None:
            connected.append(address)

        def close(self) -> None:
            return

    class FakeTlsSocket:
        def __init__(self) -> None:
            self._response = bytearray(
                b"HTTP/1.1 429 Too Many Requests\r\n"
                b"Content-Type: application/json\r\n"
                b"Retry-After: 2.5\r\n\r\n"
            )

        def __enter__(self) -> FakeTlsSocket:
            return self

        def __exit__(self, *_args: object) -> None:
            return

        def settimeout(self, _timeout: float) -> None:
            return

        def sendall(self, request_bytes: bytes) -> None:
            sent.append(request_bytes)

        def recv(self, bufsize: int) -> bytes:
            chunk = bytes(self._response[:bufsize])
            del self._response[:bufsize]
            return chunk

    class FakeContext:
        def wrap_socket(
            self,
            _socket: FakeSocket,
            *,
            server_hostname: str,
        ) -> FakeTlsSocket:
            server_names.append(server_hostname)
            return FakeTlsSocket()

    monkeypatch.setattr("frame_compare.services.slowpics_webhook.socket.socket", FakeSocket)
    monkeypatch.setattr(
        "frame_compare.services.slowpics_webhook.ssl.create_default_context",
        FakeContext,
    )
    request = WebhookDeliveryRequest(
        hostname="hooks.example.test",
        port=443,
        resolved_ip="93.184.216.34",
        host_header="hooks.example.test",
        target="/webhook/token",
        headers=(("Host", "hooks.example.test"), ("User-Agent", WEBHOOK_USER_AGENT)),
        body=b"{}",
        timeout_seconds=WEBHOOK_TIMEOUT_SECONDS,
    )

    response = send_pinned_https_webhook_request(request)

    assert response == WebhookResponse(status_code=429, retry_after_seconds=2.5)
    assert connected == [("93.184.216.34", 443)]
    assert server_names == ["hooks.example.test"]
    assert sent == [
        b"POST /webhook/token HTTP/1.1\r\n"
        b"Host: hooks.example.test\r\n"
        + f"User-Agent: {WEBHOOK_USER_AGENT}\r\n\r\n".encode("ascii")
        + b"{}"
    ]


def test_pinned_transport_enforces_absolute_response_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [0.0]
    sent = 0
    recv_calls = 0

    class FakeSocket:
        def __init__(self, _family: int, _socket_type: int) -> None:
            return

        def settimeout(self, _timeout: float) -> None:
            return

        def connect(self, _address: tuple[str, int]) -> None:
            return

        def close(self) -> None:
            return

    class FakeTlsSocket:
        def __init__(self) -> None:
            self._response = bytearray(b"HTTP/1.1 204 No Content\r\n\r\n")

        def __enter__(self) -> FakeTlsSocket:
            return self

        def __exit__(self, *_args: object) -> None:
            return

        def settimeout(self, _timeout: float) -> None:
            return

        def sendall(self, _request_bytes: bytes) -> None:
            nonlocal sent
            sent += 1

        def recv(self, _bufsize: int) -> bytes:
            nonlocal recv_calls
            recv_calls += 1
            clock[0] += 4.0
            if not self._response:
                return b""
            return bytes((self._response.pop(0),))

    class FakeContext:
        def wrap_socket(
            self,
            _socket: FakeSocket,
            *,
            server_hostname: str,
        ) -> FakeTlsSocket:
            assert server_hostname == "hooks.example.test"
            return FakeTlsSocket()

    monkeypatch.setattr("frame_compare.services.slowpics_webhook.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("frame_compare.services.slowpics_webhook.socket.socket", FakeSocket)
    monkeypatch.setattr(
        "frame_compare.services.slowpics_webhook.ssl.create_default_context",
        FakeContext,
    )
    request = WebhookDeliveryRequest(
        hostname="hooks.example.test",
        port=443,
        resolved_ip="93.184.216.34",
        host_header="hooks.example.test",
        target="/webhook/token",
        headers=(("Host", "hooks.example.test"),),
        body=b"{}",
        timeout_seconds=WEBHOOK_TIMEOUT_SECONDS,
    )

    with pytest.raises(WebhookDeliveryUncertainError):
        send_pinned_https_webhook_request(request)

    assert sent == 1
    assert recv_calls == 3
