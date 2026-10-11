from __future__ import annotations

import asyncio
import shutil
import signal
import ssl
import subprocess
import sys
import sysconfig
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from threading import Event
from typing import IO

import pytest

from frame_compare.services import slowpics_webhook as webhook
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
    assert "hooks.example.test" not in result.warning.text
    assert "localhost" not in result.warning.text


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
    assert "secret.example.test" not in result.warning.text
    assert "/path" not in result.warning.text


async def test_malformed_ipv6_url_returns_sanitized_validation_warning() -> None:
    result = await _deliver("https://[::1", connector=_unexpected_connector)

    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_VALIDATION_WARNING,
        failure_kind=WebhookFailureKind.VALIDATION,
    )
    assert result.warning is not None
    assert "::1" not in result.warning.text


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
        assert fragment not in result.warning.text


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
    assert "hooks.example.test" not in result.warning.text
    assert "/webhook/token" not in result.warning.text
    assert "secret=value" not in result.warning.text


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


async def test_cancellation_stops_retry_worker_before_next_attempt() -> None:
    first_attempt = Event()
    calls = 0

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        nonlocal calls
        calls += 1
        first_attempt.set()
        return WebhookResponse(status_code=503)

    task = asyncio.create_task(
        deliver_slowpics_webhook(
            webhook_url="https://hooks.example.test/path",
            slowpics_url="https://slow.pics/c/example",
            resolver=_public_resolver,
            connector=_connector,
        )
    )
    assert await asyncio.to_thread(first_attempt.wait, 1.0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls == 1
    await asyncio.sleep(0.05)
    assert calls == 1


async def test_repeated_cancellation_drains_blocked_worker_before_propagating() -> None:
    connector_started = Event()
    release_connector = Event()
    calls = 0

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        nonlocal calls
        calls += 1
        connector_started.set()
        assert release_connector.wait(1.0)
        return WebhookResponse(status_code=503)

    task = asyncio.create_task(
        deliver_slowpics_webhook(
            webhook_url="https://hooks.example.test/path",
            slowpics_url="https://slow.pics/c/example",
            resolver=_public_resolver,
            connector=_connector,
        )
    )
    assert await asyncio.to_thread(connector_started.wait, 1.0)

    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    try:
        assert not task.done()
    finally:
        release_connector.set()

    _done, pending = await asyncio.wait({task}, timeout=1.0)
    assert not pending
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == 1


async def test_repeated_cancellation_consumes_concurrent_worker_failure() -> None:
    connector_started = Event()
    release_connector = Event()
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    unhandled_contexts: list[dict[str, object]] = []

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        connector_started.set()
        assert release_connector.wait(1.0)
        raise RuntimeError("connector failed during cancellation")

    loop.set_exception_handler(lambda _loop, context: unhandled_contexts.append(context))
    try:
        task = asyncio.create_task(
            deliver_slowpics_webhook(
                webhook_url="https://hooks.example.test/path",
                slowpics_url="https://slow.pics/c/example",
                resolver=_public_resolver,
                connector=_connector,
            )
        )
        assert await asyncio.to_thread(connector_started.wait, 1.0)

        task.cancel()
        await asyncio.sleep(0)
        release_connector.set()
        task.cancel()

        _done, pending = await asyncio.wait({task}, timeout=1.0)
        assert not pending
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        assert unhandled_contexts == []
    finally:
        release_connector.set()
        loop.set_exception_handler(previous_handler)


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


@pytest.mark.parametrize("retry_after", [2.5, None, WEBHOOK_MAX_RETRY_AFTER_SECONDS + 0.1])
async def test_rate_limit_uses_only_bounded_server_delay(retry_after: float | None) -> None:
    calls = 0
    sleep_calls: list[float] = []

    def _connector(_request: WebhookDeliveryRequest) -> WebhookResponse:
        nonlocal calls
        calls += 1
        if retry_after == 2.5 and calls > 1:
            return WebhookResponse(status_code=204)
        return WebhookResponse(status_code=429, retry_after_seconds=retry_after)

    result = await _deliver(
        "https://hooks.example.test/path", connector=_connector, sleeper=sleep_calls.append
    )
    if retry_after == 2.5:
        assert result == SlowpicsWebhookResult(success=True, detail="HTTP 204")
        assert calls == 2
        assert sleep_calls == [2.5]
    else:
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
    assert "secret.example.test" not in result.warning.text
    assert "webhook" in result.warning.text
    assert "/webhook/token" not in result.warning.text
    assert "secret=value" not in result.warning.text


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


@pytest.fixture
def resolver_children(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[subprocess.Popen[bytes]]]:
    """Observe real owned children without replacing their process boundary."""
    children: list[subprocess.Popen[bytes]] = []
    popen = subprocess.Popen

    def start(
        args: list[str], *, stdin: int, stdout: IO[bytes], stderr: int, env: dict[str, str]
    ) -> subprocess.Popen[bytes]:
        child = popen(args, stdin=stdin, stdout=stdout, stderr=stderr, env=env, text=False)
        children.append(child)
        return child

    monkeypatch.setattr(webhook.subprocess, "Popen", start)
    try:
        yield children
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)


def _blocked_resolver_code(marker: Path) -> str:
    # Run the production protocol, replacing only getaddrinfo inside the real
    # isolated interpreter. The marker proves the child reached blocked DNS.
    setup = f"""
import pathlib
import time
def blocked(*args, **kwargs):
    pathlib.Path({str(marker)!r}).touch()
    time.sleep(60)
socket.getaddrinfo = blocked
"""
    return webhook._WEBHOOK_RESOLVER_CODE.replace("try:\n", setup + "\ntry:\n", 1)


async def _wait_for_resolver_marker(marker: Path) -> None:
    deadline = time.monotonic() + 2
    while not marker.exists():
        assert time.monotonic() < deadline, "resolver child did not start"
        await asyncio.sleep(0.01)


def test_default_resolver_runs_isolated_current_interpreter(
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    assert webhook.resolve_webhook_addresses("127.0.0.1", 443) == ("127.0.0.1",)
    assert len(resolver_children) == 1
    child = resolver_children[0]
    assert child.returncode == 0
    assert child.args == [
        sys.executable,
        "-I",
        "-S",
        "-c",
        webhook._WEBHOOK_RESOLVER_CODE,
        "127.0.0.1",
        "443",
    ]


@pytest.mark.parametrize("ignore_termination", [False, True])
async def test_default_resolution_timeout_reaps_child_without_transport(
    ignore_termination: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    marker = tmp_path / "resolving"
    code = _blocked_resolver_code(marker)
    if ignore_termination:
        code = "import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" + code
    monkeypatch.setattr(webhook, "_WEBHOOK_RESOLVER_CODE", code)
    monkeypatch.setattr(webhook, "WEBHOOK_TIMEOUT_SECONDS", 1.0)
    started = time.monotonic()
    result = await deliver_slowpics_webhook(
        webhook_url="https://hooks.example.test/secret-path?token=secret-query",
        slowpics_url="https://slow.pics/c/example",
        connector=_unexpected_connector,
    )
    assert marker.exists()
    assert time.monotonic() - started < 3
    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_FAILURE_WARNING,
        failure_kind=WebhookFailureKind.TIMEOUT,
    )
    assert len(resolver_children) == 1
    assert resolver_children[0].returncode is not None
    if ignore_termination and sys.platform != "win32":
        assert resolver_children[0].returncode == -signal.SIGKILL
    args = resolver_children[0].args
    assert isinstance(args, list)
    assert args[-2:] == ["hooks.example.test", "443"]


@pytest.mark.parametrize("when", ["early", "blocked", "repeated"])
async def test_default_resolution_cancellation_reaps_child_without_transport(
    when: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    calls: list[WebhookDeliveryRequest] = []

    def connector(request: WebhookDeliveryRequest) -> WebhookResponse:
        calls.append(request)
        return WebhookResponse(status_code=503)

    marker = tmp_path / "resolving"
    monkeypatch.setattr(webhook, "_WEBHOOK_RESOLVER_CODE", _blocked_resolver_code(marker))
    task = asyncio.create_task(
        deliver_slowpics_webhook(
            webhook_url="https://hooks.example.test/path",
            slowpics_url="https://slow.pics/c/example",
            connector=connector,
        )
    )
    if when != "early":
        await _wait_for_resolver_marker(marker)
    task.cancel()
    if when == "repeated":
        for _ in range(5):
            await asyncio.sleep(0)
            task.cancel()
    done, pending = await asyncio.wait({task}, timeout=2)
    assert done and not pending
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == []
    assert all(child.returncode is not None for child in resolver_children)
    if when != "early":
        assert len(resolver_children) == 1


@pytest.mark.parametrize(
    "output",
    [
        b"invalid-json",
        b"[123]",
        b"{}",
        b'["93.184.216.34"]' * 1000,
        b"[" + b'"93.184.216.34",' * 64 + b'"93.184.216.34"]',
        b'["93.184.216.34", "10.0.0.1"]',
        b'["not-an-address"]',
    ],
    ids=["invalid-json", "non-string", "non-list", "oversized", "too-many", "mixed", "invalid-ip"],
)
async def test_default_resolver_rejects_invalid_process_output(
    output: bytes,
    monkeypatch: pytest.MonkeyPatch,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    monkeypatch.setattr(
        webhook, "_WEBHOOK_RESOLVER_CODE", f"import sys; sys.stdout.buffer.write({output!r})"
    )
    result = await deliver_slowpics_webhook(
        webhook_url="https://hooks.example.test/path",
        slowpics_url="https://slow.pics/c/example",
        connector=_unexpected_connector,
    )
    assert result.failure_kind is WebhookFailureKind.VALIDATION
    assert resolver_children[0].returncode == 0


async def test_default_resolver_process_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    monkeypatch.setattr(
        webhook,
        "_WEBHOOK_RESOLVER_CODE",
        "import sys; sys.stderr.write('secret diagnostic'); sys.exit(1)",
    )
    result = await deliver_slowpics_webhook(
        webhook_url="https://hooks.example.test/path",
        slowpics_url="https://slow.pics/c/example",
        connector=_unexpected_connector,
    )
    assert result == SlowpicsWebhookResult(
        success=False,
        warning=WEBHOOK_VALIDATION_WARNING,
        failure_kind=WebhookFailureKind.VALIDATION,
    )
    assert resolver_children[0].returncode == 1


@pytest.mark.parametrize(
    ("hostname", "port"),
    [("a" * 254, 443), ("host\nname", 443), ("host", 0), ("host", 65536), ("host", True)],
)
def test_default_resolver_rejects_unbounded_input_before_starting_child(
    hostname: str,
    port: int,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    assert webhook.resolve_webhook_addresses(hostname, port) == ()
    assert resolver_children == []


async def test_default_resolution_termination_error_still_kills_and_reaps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    marker = tmp_path / "resolving"
    monkeypatch.setattr(webhook, "_WEBHOOK_RESOLVER_CODE", _blocked_resolver_code(marker))
    calls: list[WebhookDeliveryRequest] = []

    def connector(request: WebhookDeliveryRequest) -> WebhookResponse:
        calls.append(request)
        return WebhookResponse(status_code=503)

    task = asyncio.create_task(
        deliver_slowpics_webhook(
            webhook_url="https://hooks.example.test/path",
            slowpics_url="https://slow.pics/c/example",
            connector=connector,
        )
    )
    await _wait_for_resolver_marker(marker)
    child = resolver_children[0]
    wait = child.wait
    waits: list[float | None] = []
    termination_attempts: list[bool] = []

    def fail_terminate() -> None:
        termination_attempts.append(True)
        raise OSError("simulated signal failure")

    def observed_wait(timeout: float | None = None) -> int:
        waits.append(timeout)
        return wait(timeout=timeout)

    monkeypatch.setattr(child, "terminate", fail_terminate)
    monkeypatch.setattr(child, "wait", observed_wait)
    task.cancel()
    done, pending = await asyncio.wait({task}, timeout=2)
    assert done and not pending
    with pytest.raises(asyncio.CancelledError):
        await task
    assert termination_attempts == [True]
    assert child.returncode is not None
    assert calls == []
    assert waits and all(timeout is not None and 0 < timeout <= 1 for timeout in waits)
    if sys.platform != "win32":
        assert child.returncode == -signal.SIGKILL


def test_default_resolver_excludes_application_and_proxy_environment(
    monkeypatch: pytest.MonkeyPatch,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    secret_keys = (
        "FRAME_COMPARE_SLOWPICS__WEBHOOK_URL",
        "FRAME_COMPARE_TMDB__API_KEY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "PYTHONPATH",
        "PYTHONHOME",
        "UNRELATED_SECRET",
    )
    for key in secret_keys:
        monkeypatch.setenv(key, "synthetic-secret-sentinel")
    # Observe exclusion inside the real interpreter, without emitting any values.
    code = f"import os; assert not any(k in os.environ for k in {secret_keys!r})\n"
    monkeypatch.setattr(webhook, "_WEBHOOK_RESOLVER_CODE", code + webhook._WEBHOOK_RESOLVER_CODE)
    assert webhook.resolve_webhook_addresses("127.0.0.1", 443) == ("127.0.0.1",)
    assert resolver_children[0].returncode == 0


@pytest.mark.parametrize(
    "environment",
    [
        {"SystemRoot": "C:\\Windows", "UNRELATED_SECRET": "synthetic-secret"},
        {"sYsTeMrOoT": "C:\\Windows", "HTTPS_PROXY": "synthetic-proxy"},
        {"UNRELATED_SECRET": "synthetic-secret"},
    ],
)
def test_windows_resolver_environment_keeps_only_system_root(
    environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This is environment policy proof, not Windows interpreter acceptance.
    with monkeypatch.context() as patch:
        patch.setattr(webhook.sys, "platform", "win32")
        patch.setattr(webhook.os, "environ", environment)
        actual = webhook._webhook_resolver_environment()
    expected = next((v for k, v in environment.items() if k.casefold() == "systemroot"), None)
    assert actual == ({"SystemRoot": expected} if expected else {})


@pytest.fixture
def copied_pth_interpreter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Host POSIX CPython startup proof; does not model the portable Windows bundle."""
    if sys.platform == "win32" or sys.implementation.name != "cpython":
        pytest.skip("copied ._pth fixture requires the host POSIX CPython interpreter")
    source = Path(sys.executable).resolve()
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    executable = binary_dir / source.name
    shutil.copy2(source, executable)
    # Preserve the copied executable's relative shared-library lookup, without
    # changing any original runtime files. Stdlib paths are pinned in exact ._pth.
    (tmp_path / "lib").symlink_to(source.parent.parent / "lib", target_is_directory=True)
    stdlib = sysconfig.get_path("stdlib")
    extensions = sysconfig.get_config_var("DESTSHARED")
    assert isinstance(extensions, str)
    executable.with_name(executable.name + "._pth").write_text(
        "\n".join((stdlib, extensions, str(tmp_path), "import site")) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(webhook.sys, "executable", str(executable))
    return tmp_path


async def test_exact_pth_startup_output_is_rejected_without_connector(
    copied_pth_interpreter: Path,
    monkeypatch: pytest.MonkeyPatch,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    marker = copied_pth_interpreter / "startup-ran"
    (copied_pth_interpreter / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\nprint('startup-output')\n",
        encoding="utf-8",
    )
    # Supply valid fixed address output without any DNS/network access. Startup
    # noise alone must invalidate the otherwise valid child result.
    monkeypatch.setattr(
        webhook, "_WEBHOOK_RESOLVER_CODE", """import sys; sys.stdout.write('["93.184.216.34"]')"""
    )
    result = await deliver_slowpics_webhook(
        webhook_url="https://hooks.example.test/path",
        slowpics_url="https://slow.pics/c/example",
        connector=_unexpected_connector,
    )
    assert marker.exists(), "exact ._pth did not enable site startup on this host"
    assert result.failure_kind is WebhookFailureKind.VALIDATION
    assert resolver_children[0].returncode == 0


@pytest.mark.parametrize("stop", ["timeout", "cancel"])
async def test_exact_pth_blocked_startup_is_bounded_and_reaped(
    stop: str,
    copied_pth_interpreter: Path,
    monkeypatch: pytest.MonkeyPatch,
    resolver_children: list[subprocess.Popen[bytes]],
) -> None:
    marker = copied_pth_interpreter / "startup-ran"
    (copied_pth_interpreter / "sitecustomize.py").write_text(
        f"from pathlib import Path\nimport time\nPath({str(marker)!r}).touch()\ntime.sleep(60)\n",
        encoding="utf-8",
    )
    if stop == "timeout":
        monkeypatch.setattr(webhook, "WEBHOOK_TIMEOUT_SECONDS", 1.0)
    calls: list[WebhookDeliveryRequest] = []

    def connector(request: WebhookDeliveryRequest) -> WebhookResponse:
        calls.append(request)
        return WebhookResponse(503)

    task = asyncio.create_task(
        deliver_slowpics_webhook(
            webhook_url="https://hooks.example.test/path",
            slowpics_url="https://slow.pics/c/example",
            connector=connector,
        )
    )
    await _wait_for_resolver_marker(marker)
    if stop == "cancel":
        task.cancel()
        for _ in range(5):
            await asyncio.sleep(0)
            task.cancel()
    done, pending = await asyncio.wait({task}, timeout=2)
    assert done and not pending
    if stop == "cancel":
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        assert (await task).failure_kind is WebhookFailureKind.TIMEOUT
    assert calls == []
    assert len(resolver_children) == 1 and resolver_children[0].returncode is not None
