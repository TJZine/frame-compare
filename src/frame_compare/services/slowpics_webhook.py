"""Isolated slow.pics post-upload webhook delivery."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from frame_compare import __version__

WEBHOOK_TIMEOUT_SECONDS = 10.0
WEBHOOK_ATTEMPTS = 3
WEBHOOK_CONTENT_TYPE = "application/json"
WEBHOOK_RETRY_BASE_DELAY_SECONDS = 1.0
WEBHOOK_MAX_RETRY_AFTER_SECONDS = 10.0
WEBHOOK_USER_AGENT = (
    f"DiscordBot (https://github.com/TJZine/frame-compare, {__version__}) "
    f"frame-compare/{__version__}"
)
WEBHOOK_FAILURE_WARNING = "slow.pics webhook: delivery failed"
WEBHOOK_VALIDATION_WARNING = (
    "slow.pics webhook: delivery skipped because the configured webhook URL "
    "is not an allowed external HTTPS endpoint"
)

type WebhookResolver = Callable[[str, int], tuple[str, ...]]
type WebhookConnector = Callable[["WebhookDeliveryRequest"], "WebhookResponse"]
type WebhookSleeper = Callable[[float], None]


class _WebhookResponseSocket(Protocol):
    def settimeout(self, value: float | None, /) -> None: ...

    def recv(self, bufsize: int, flags: int = 0, /) -> bytes: ...


class WebhookDeliveryUncertainError(OSError):
    """The request may have reached the endpoint, so retrying could duplicate it."""


@dataclass(frozen=True)
class SlowpicsWebhookResult:
    """Result of a post-upload webhook delivery attempt."""

    success: bool
    detail: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class WebhookDeliveryRequest:
    """Pinned-address HTTPS request data for a webhook delivery attempt."""

    hostname: str
    port: int
    resolved_ip: str
    host_header: str
    target: str
    headers: tuple[tuple[str, str], ...]
    body: bytes
    timeout_seconds: float


@dataclass(frozen=True)
class WebhookResponse:
    """Minimal HTTP response data needed by webhook retry policy."""

    status_code: int
    retry_after_seconds: float | None = None


@dataclass(frozen=True)
class _ValidatedWebhookTarget:
    hostname: str
    port: int
    host_header: str
    target: str
    resolved_ips: tuple[str, ...]


async def deliver_slowpics_webhook(
    *,
    webhook_url: str,
    slowpics_url: str,
    resolver: WebhookResolver | None = None,
    connector: WebhookConnector | None = None,
    sleeper: WebhookSleeper | None = None,
) -> SlowpicsWebhookResult:
    """Deliver a slow.pics URL to a configured webhook with isolated HTTP state."""
    resolved_resolver = resolve_webhook_addresses if resolver is None else resolver
    resolved_connector = send_pinned_https_webhook_request if connector is None else connector
    resolved_sleeper = time.sleep if sleeper is None else sleeper
    return await asyncio.to_thread(
        _deliver_slowpics_webhook_sync,
        webhook_url=webhook_url,
        slowpics_url=slowpics_url,
        resolver=resolved_resolver,
        connector=resolved_connector,
        sleeper=resolved_sleeper,
    )


def resolve_webhook_addresses(hostname: str, port: int) -> tuple[str, ...]:
    """Resolve a webhook hostname to candidate IP address strings."""
    try:
        results = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except (OSError, UnicodeError, ValueError):
        return ()

    addresses: list[str] = []
    seen: set[str] = set()
    for result in results:
        sockaddr = result[4]
        if len(sockaddr) < 1:
            continue
        address = str(sockaddr[0])
        if address not in seen:
            addresses.append(address)
            seen.add(address)
    return tuple(addresses)


def send_pinned_https_webhook_request(request: WebhookDeliveryRequest) -> WebhookResponse:
    """Send one HTTPS POST to a prevalidated IP while verifying the original hostname."""
    request_bytes = _http_request_bytes(request)
    address = ipaddress.ip_address(request.resolved_ip)
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    deadline = time.monotonic() + request.timeout_seconds
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(_remaining_timeout_seconds(deadline))
    try:
        connect_address: tuple[str, int] | tuple[str, int, int, int]
        if address.version == 6:
            connect_address = (request.resolved_ip, request.port, 0, 0)
        else:
            connect_address = (request.resolved_ip, request.port)
        sock.connect(connect_address)
        context = ssl.create_default_context()
        sock.settimeout(_remaining_timeout_seconds(deadline))
        tls_sock = context.wrap_socket(sock, server_hostname=request.hostname)
    except (OSError, ValueError):
        sock.close()
        raise

    with tls_sock:
        try:
            tls_sock.settimeout(_remaining_timeout_seconds(deadline))
            tls_sock.sendall(request_bytes)
            return _read_http_response(tls_sock, deadline)
        except (OSError, UnicodeError, ValueError) as exc:
            raise WebhookDeliveryUncertainError(
                "Webhook delivery outcome is unknown after request transmission"
            ) from exc


def _deliver_slowpics_webhook_sync(
    *,
    webhook_url: str,
    slowpics_url: str,
    resolver: WebhookResolver,
    connector: WebhookConnector,
    sleeper: WebhookSleeper,
) -> SlowpicsWebhookResult:
    target = _validate_webhook_url(webhook_url, resolver)
    if target is None:
        return SlowpicsWebhookResult(success=False, warning=WEBHOOK_VALIDATION_WARNING)

    body = json.dumps({"content": slowpics_url}, separators=(",", ":")).encode("utf-8")
    headers = (
        ("Host", target.host_header),
        ("User-Agent", WEBHOOK_USER_AGENT),
        ("Content-Type", WEBHOOK_CONTENT_TYPE),
        ("Content-Length", str(len(body))),
        ("Connection", "close"),
    )
    last_status: int | None = None
    for attempt in range(1, WEBHOOK_ATTEMPTS + 1):
        resolved_ip = target.resolved_ips[(attempt - 1) % len(target.resolved_ips)]
        request = WebhookDeliveryRequest(
            hostname=target.hostname,
            port=target.port,
            resolved_ip=resolved_ip,
            host_header=target.host_header,
            target=target.target,
            headers=headers,
            body=body,
            timeout_seconds=WEBHOOK_TIMEOUT_SECONDS,
        )
        try:
            response = connector(request)
        except WebhookDeliveryUncertainError:
            return SlowpicsWebhookResult(success=False, warning=WEBHOOK_FAILURE_WARNING)
        except ssl.SSLCertVerificationError:
            return SlowpicsWebhookResult(success=False, warning=WEBHOOK_FAILURE_WARNING)
        except TimeoutError:
            if attempt == WEBHOOK_ATTEMPTS:
                return SlowpicsWebhookResult(success=False, warning=WEBHOOK_FAILURE_WARNING)
            sleeper(_retry_backoff_seconds(attempt))
            continue
        except (OSError, UnicodeError, ValueError):
            if attempt == WEBHOOK_ATTEMPTS:
                return SlowpicsWebhookResult(success=False, warning=WEBHOOK_FAILURE_WARNING)
            sleeper(_retry_backoff_seconds(attempt))
            continue

        last_status = response.status_code
        if 200 <= response.status_code <= 299:
            return SlowpicsWebhookResult(success=True, detail=f"HTTP {response.status_code}")
        if response.status_code == 429:
            retry_after = response.retry_after_seconds
            if (
                attempt < WEBHOOK_ATTEMPTS
                and retry_after is not None
                and 0.0 <= retry_after <= WEBHOOK_MAX_RETRY_AFTER_SECONDS
            ):
                sleeper(retry_after)
                continue
            return SlowpicsWebhookResult(success=False, warning=WEBHOOK_FAILURE_WARNING)
        if 500 <= response.status_code <= 599 and attempt < WEBHOOK_ATTEMPTS:
            sleeper(_retry_backoff_seconds(attempt))
            continue
        return SlowpicsWebhookResult(success=False, warning=WEBHOOK_FAILURE_WARNING)

    detail = f"HTTP {last_status}" if last_status is not None else None
    return SlowpicsWebhookResult(success=False, detail=detail, warning=WEBHOOK_FAILURE_WARNING)


def _validate_webhook_url(
    webhook_url: str,
    resolver: WebhookResolver,
) -> _ValidatedWebhookTarget | None:
    try:
        parsed = urlparse(webhook_url)
    except ValueError:
        return None

    if parsed.scheme != "https" or parsed.fragment:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None

    try:
        parsed_hostname = parsed.hostname
        parsed_port = parsed.port
    except ValueError:
        return None
    if parsed_hostname is None:
        return None

    hostname = parsed_hostname.rstrip(".")
    if not hostname:
        return None
    if not _is_ascii_text(hostname):
        return None
    if _is_localhost_name(hostname):
        return None

    port = parsed_port or 443
    if not 1 <= port <= 65535:
        return None
    host_header = _host_header(hostname, port)
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    if not _is_safe_http_target(target):
        return None
    if not _is_safe_http_header_value(host_header):
        return None

    literal_address = _parse_ip_literal(hostname)
    if literal_address is not None:
        if not _is_allowed_public_address(literal_address):
            return None
        return _ValidatedWebhookTarget(
            hostname=hostname,
            port=port,
            host_header=host_header,
            target=target,
            resolved_ips=(str(literal_address),),
        )

    try:
        resolved_ips = resolver(hostname, port)
    except (OSError, UnicodeError, ValueError):
        return None
    if not resolved_ips:
        return None

    parsed_addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for resolved_ip in resolved_ips:
        address = _parse_ip_literal(resolved_ip)
        if address is None:
            return None
        parsed_addresses.append(address)
    if not parsed_addresses:
        return None
    if any(not _is_allowed_public_address(address) for address in parsed_addresses):
        return None

    return _ValidatedWebhookTarget(
        hostname=hostname,
        port=port,
        host_header=host_header,
        target=target,
        resolved_ips=tuple(str(address) for address in parsed_addresses),
    )


def _is_localhost_name(hostname: str) -> bool:
    normalized = hostname.lower().rstrip(".")
    return normalized == "localhost" or normalized.endswith(".localhost")


def _is_ascii_text(value: str) -> bool:
    try:
        value.encode("ascii")
    except UnicodeError:
        return False
    return True


def _is_safe_http_target(value: str) -> bool:
    if not _is_ascii_text(value):
        return False
    return all(32 < ord(char) < 127 for char in value)


def _is_safe_http_header_name(value: str) -> bool:
    if not _is_ascii_text(value) or not value:
        return False
    return all(32 < ord(char) < 127 and char != ":" for char in value)


def _is_safe_http_header_value(value: str) -> bool:
    if not _is_ascii_text(value):
        return False
    return all(char == "\t" or 32 <= ord(char) < 127 for char in value)


def _parse_ip_literal(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return None


def _is_allowed_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_global
        and not address.is_loopback
        and not address.is_private
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )


def _host_header(hostname: str, port: int) -> str:
    host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    if port == 443:
        return host
    return f"{host}:{port}"


def _http_request_bytes(request: WebhookDeliveryRequest) -> bytes:
    if not _is_safe_http_target(request.target):
        raise OSError("Invalid webhook HTTP request")
    for name, value in request.headers:
        if not _is_safe_http_header_name(name) or not _is_safe_http_header_value(value):
            raise OSError("Invalid webhook HTTP request")

    lines = [f"POST {request.target} HTTP/1.1"]
    lines.extend(f"{name}: {value}" for name, value in request.headers)
    try:
        header_bytes = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")
    except UnicodeError:
        raise OSError("Invalid webhook HTTP request") from None
    return header_bytes + request.body


def _retry_backoff_seconds(attempt: int) -> float:
    return WEBHOOK_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))


def _remaining_timeout_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        raise TimeoutError("Webhook delivery deadline exceeded")
    return remaining


def _read_http_response(
    response_socket: _WebhookResponseSocket,
    deadline: float,
) -> WebhookResponse:
    buffered = bytearray()
    for _informational_response in range(5):
        response_head = _read_response_head(response_socket, deadline, buffered)
        response_lines = response_head.splitlines()
        if not response_lines:
            raise OSError("Invalid webhook HTTP response")
        status_code = _parse_status_code(response_lines[0])
        retry_after_seconds = _parse_response_headers(response_lines[1:])
        if status_code >= 200:
            return WebhookResponse(
                status_code=status_code,
                retry_after_seconds=retry_after_seconds,
            )
    raise OSError("Invalid webhook HTTP response")


def _read_response_head(
    response_socket: _WebhookResponseSocket,
    deadline: float,
    buffered: bytearray,
) -> bytes:
    while True:
        separator = _response_head_separator(buffered)
        if separator is not None:
            head_end, separator_length = separator
            if head_end > 65536:
                raise OSError("Invalid webhook HTTP response")
            response_head = bytes(buffered[:head_end])
            del buffered[: head_end + separator_length]
            return response_head
        if len(buffered) > 65536:
            raise OSError("Invalid webhook HTTP response")

        response_socket.settimeout(_remaining_timeout_seconds(deadline))
        chunk = response_socket.recv(4096)
        if not chunk:
            raise OSError("Invalid webhook HTTP response")
        buffered.extend(chunk)


def _response_head_separator(buffered: bytearray) -> tuple[int, int] | None:
    candidates = (
        (buffered.find(b"\r\n\r\n"), 4),
        (buffered.find(b"\n\n"), 2),
    )
    present = [(index, length) for index, length in candidates if index >= 0]
    return min(present) if present else None


def _parse_response_headers(header_lines: list[bytes]) -> float | None:
    retry_after_seconds: float | None = None
    retry_after_seen = False
    total_bytes = 0
    for line in header_lines:
        total_bytes += len(line)
        if total_bytes > 65536:
            raise OSError("Invalid webhook HTTP response")

        try:
            name, value = line.decode("iso-8859-1").split(":", 1)
        except (ValueError, UnicodeDecodeError):
            raise OSError("Invalid webhook HTTP response") from None
        if name.strip().lower() == "retry-after":
            if retry_after_seen:
                raise OSError("Invalid webhook HTTP response")
            retry_after_seen = True
            retry_after_seconds = _parse_retry_after_seconds(value.strip())
    return retry_after_seconds


def _parse_retry_after_seconds(value: str) -> float | None:
    try:
        seconds = float(value)
    except ValueError:
        return None
    if not math.isfinite(seconds) or seconds < 0.0:
        return None
    return seconds


def _parse_status_code(status_line: bytes) -> int:
    try:
        text = status_line.decode("iso-8859-1").rstrip("\r\n")
        version, status, *_reason = text.split(" ", 2)
        status_code = int(status)
    except (ValueError, UnicodeDecodeError):
        raise OSError("Invalid webhook HTTP response") from None
    if version not in {"HTTP/1.0", "HTTP/1.1"} or not 100 <= status_code <= 599:
        raise OSError("Invalid webhook HTTP response")
    return status_code
