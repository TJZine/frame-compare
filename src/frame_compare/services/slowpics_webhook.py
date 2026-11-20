"""Isolated slow.pics post-upload webhook delivery."""

from __future__ import annotations

import asyncio
import json
import ssl
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

import httpx

from frame_compare import __version__
from frame_compare.utils.run_warnings import RunWarning

WEBHOOK_TIMEOUT_SECONDS = 10.0
WEBHOOK_ATTEMPTS = 3
WEBHOOK_MAX_RETRY_AFTER_SECONDS = 10.0
WEBHOOK_USER_AGENT = (
    f"DiscordBot (https://github.com/TJZine/frame-compare, {__version__}) "
    f"frame-compare/{__version__}"
)
WEBHOOK_FAILURE_WARNING = RunWarning("slow.pics", "warning", "slow.pics webhook: delivery failed")
WEBHOOK_VALIDATION_WARNING = RunWarning(
    "slow.pics",
    "warning",
    "slow.pics webhook: delivery skipped",
    "because the configured webhook URL is not an HTTPS URL",
)


class WebhookFailureKind(StrEnum):
    """Safe diagnostic categories for webhook delivery failures."""

    VALIDATION = "validation"
    DELIVERY_UNCERTAIN = "delivery_uncertain"
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    RATE_LIMITED = "rate_limited"
    HTTP_STATUS = "http_status"


@dataclass(frozen=True)
class SlowpicsWebhookResult:
    """Result of a post-upload webhook delivery attempt."""

    success: bool
    detail: str | None = None
    warning: RunWarning | None = None
    failure_kind: WebhookFailureKind | None = None
    status_code: int | None = None


def _validate_webhook_url(webhook_url: str) -> httpx.URL | None:
    if not webhook_url.isascii():
        return None
    try:
        url = httpx.URL(webhook_url)
    except httpx.InvalidURL:
        return None

    if url.scheme != "https" or not url.host.rstrip(".") or url.userinfo:
        return None
    if url.port is not None and not 1 <= url.port <= 65535:
        return None

    authority_and_path, _, query = webhook_url.partition("://")[2].partition("?")
    authority, _, path = authority_and_path.partition("/")
    # The parsed properties do not distinguish empty userinfo or fragments from
    # absent ones. Reject their delimiters even when the components are empty.
    if "#" in webhook_url or authority.startswith("@"):
        return None
    # HTTPX percent-encodes raw spaces in the request target during parsing.
    if " " in path or " " in query:
        return None
    return url


async def _discard_redirect_location(response: httpx.Response) -> None:
    # HTTPX builds a redirect request even when following redirects is disabled.
    if response.is_redirect:
        response.headers.pop("Location", None)


def _retry_after(headers: httpx.Headers) -> float | None:
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if 0.0 <= seconds <= WEBHOOK_MAX_RETRY_AFTER_SECONDS else None


def _failure_result(
    failure_kind: WebhookFailureKind,
    *,
    warning: RunWarning = WEBHOOK_FAILURE_WARNING,
    status_code: int | None = None,
) -> SlowpicsWebhookResult:
    return SlowpicsWebhookResult(
        success=False,
        warning=warning,
        failure_kind=failure_kind,
        status_code=status_code,
    )


async def deliver_slowpics_webhook(
    *,
    webhook_url: str,
    slowpics_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> SlowpicsWebhookResult:
    """POST the upload URL with isolated HTTP state and sanitized results."""
    url = _validate_webhook_url(webhook_url)
    if url is None:
        return _failure_result(WebhookFailureKind.VALIDATION, warning=WEBHOOK_VALIDATION_WARNING)

    body = json.dumps({"content": slowpics_url}, separators=(",", ":")).encode("utf-8")
    async with httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(WEBHOOK_TIMEOUT_SECONDS),
        follow_redirects=False,
        trust_env=False,
        verify=ssl.create_default_context(),
        headers={"User-Agent": WEBHOOK_USER_AGENT, "Content-Type": "application/json"},
        event_hooks={"response": [_discard_redirect_location]},
    ) as client:
        for attempt in range(WEBHOOK_ATTEMPTS):
            can_retry = attempt + 1 < WEBHOOK_ATTEMPTS
            delay = 2.0**attempt
            try:
                async with client.stream("POST", url, content=body) as response:
                    status = response.status_code
                    headers = response.headers
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                if not can_retry:
                    return _failure_result(
                        WebhookFailureKind.TIMEOUT
                        if isinstance(error, httpx.ConnectTimeout)
                        else WebhookFailureKind.TRANSPORT
                    )
            except httpx.HTTPError:
                return _failure_result(WebhookFailureKind.DELIVERY_UNCERTAIN)
            else:
                if 200 <= status < 300:
                    return SlowpicsWebhookResult(success=True, detail=f"HTTP {status}")
                if status == 429:
                    retry_after = _retry_after(headers) if can_retry else None
                    if retry_after is None:
                        return _failure_result(WebhookFailureKind.RATE_LIMITED, status_code=status)
                    delay = retry_after
                elif not (can_retry and 500 <= status < 600):
                    return _failure_result(WebhookFailureKind.HTTP_STATUS, status_code=status)
            await sleep(delay)

    raise AssertionError("Webhook retry loop exhausted without a terminal result")
