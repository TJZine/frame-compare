"""Isolated slow.pics post-upload webhook delivery."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

WEBHOOK_TIMEOUT_SECONDS = 10.0
WEBHOOK_ATTEMPTS = 3
WEBHOOK_CONTENT_TYPE = "application/json"
WEBHOOK_FAILURE_WARNING = "slow.pics webhook: delivery failed after 3 attempts"
WEBHOOK_VALIDATION_WARNING = (
    "slow.pics webhook: delivery skipped because the configured webhook URL "
    "is not an allowed external HTTPS endpoint"
)

type WebhookResolver = Callable[[str, int], tuple[str, ...]]
type WebhookConnector = Callable[["WebhookDeliveryRequest"], "WebhookResponse"]


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
) -> SlowpicsWebhookResult:
    """Deliver a slow.pics URL to a configured webhook with isolated HTTP state."""
    resolved_resolver = resolve_webhook_addresses if resolver is None else resolver
    resolved_connector = send_pinned_https_webhook_request if connector is None else connector
    return await asyncio.to_thread(
        _deliver_slowpics_webhook_sync,
        webhook_url=webhook_url,
        slowpics_url=slowpics_url,
        resolver=resolved_resolver,
        connector=resolved_connector,
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
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(request.timeout_seconds)
    try:
        connect_address: tuple[str, int] | tuple[str, int, int, int]
        if address.version == 6:
            connect_address = (request.resolved_ip, request.port, 0, 0)
        else:
            connect_address = (request.resolved_ip, request.port)
        sock.connect(connect_address)
        context = ssl.create_default_context()
        with context.wrap_socket(sock, server_hostname=request.hostname) as tls_sock:
            tls_sock.settimeout(request.timeout_seconds)
            tls_sock.sendall(request_bytes)
            status_line = tls_sock.makefile("rb").readline(65536)
    except OSError:
        sock.close()
        raise

    return WebhookResponse(status_code=_parse_status_code(status_line))


def _deliver_slowpics_webhook_sync(
    *,
    webhook_url: str,
    slowpics_url: str,
    resolver: WebhookResolver,
    connector: WebhookConnector,
) -> SlowpicsWebhookResult:
    target = _validate_webhook_url(webhook_url, resolver)
    if target is None:
        return SlowpicsWebhookResult(success=False, warning=WEBHOOK_VALIDATION_WARNING)

    body = json.dumps({"content": slowpics_url}, separators=(",", ":")).encode("utf-8")
    headers = (
        ("Host", target.host_header),
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
        except TimeoutError:
            if attempt == WEBHOOK_ATTEMPTS:
                return SlowpicsWebhookResult(success=False, warning=WEBHOOK_FAILURE_WARNING)
            continue
        except (OSError, UnicodeError, ValueError):
            if attempt == WEBHOOK_ATTEMPTS:
                return SlowpicsWebhookResult(success=False, warning=WEBHOOK_FAILURE_WARNING)
            continue

        last_status = response.status_code
        if 200 <= response.status_code <= 299:
            return SlowpicsWebhookResult(success=True, detail=f"HTTP {response.status_code}")
        if 500 <= response.status_code <= 599 and attempt < WEBHOOK_ATTEMPTS:
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

    if parsed.scheme != "https":
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


def _parse_status_code(status_line: bytes) -> int:
    try:
        text = status_line.decode("iso-8859-1")
        _version, status, _reason = text.split(" ", 2)
        return int(status)
    except (ValueError, UnicodeDecodeError):
        raise OSError("Invalid webhook HTTP response") from None
