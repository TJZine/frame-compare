# pyright: standard

"""Shared networking helpers for configurable retries/backoff."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Iterable
from urllib.parse import urlsplit

import httpx
from urllib3.util import Retry

__all__ = [
    "BackoffError",
    "build_urllib3_retry",
    "default_requests_timeouts",
    "httpx_get_json_with_backoff",
    "redact_url_for_logs",
]

_DEFAULT_STATUS_FORCELIST = frozenset({429, 500, 502, 503, 504})
_DEFAULT_ALLOWED_METHODS = frozenset({"GET", "POST"})


class BackoffError(RuntimeError):
    """Raised when network retries are exhausted."""


def build_urllib3_retry(
    total: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: Iterable[int] | None = None,
    allowed_methods: Iterable[str] | None = None,
) -> Retry:
    """Return a configured urllib3 Retry object with project defaults."""

    statuses = frozenset(status_forcelist) if status_forcelist else _DEFAULT_STATUS_FORCELIST
    methods = frozenset(allowed_methods) if allowed_methods else _DEFAULT_ALLOWED_METHODS
    return Retry(
        total=total,
        backoff_factor=backoff_factor,
        status_forcelist=statuses,
        allowed_methods=methods,
        raise_on_status=False,
    )


def default_requests_timeouts(connect: float = 10.0, read: float = 30.0) -> tuple[float, float]:
    """Return standard connect/read timeout values for Requests sessions."""

    return (float(connect), float(read))


async def httpx_get_json_with_backoff(
    client: httpx.AsyncClient,
    path: str,
    params: Mapping[str, object],
    *,
    retries: int = 3,
    initial_backoff: float = 0.5,
    max_backoff: float = 4.0,
    retry_status: Iterable[int] | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> httpx.Response:
    """Perform a GET request with exponential backoff for transient status codes."""

    retry_codes = frozenset(retry_status) if retry_status else _DEFAULT_STATUS_FORCELIST
    backoff = max(0.1, initial_backoff)
    upper_backoff = max(0.1, max_backoff)
    sleep_impl = sleep or asyncio.sleep
    last_network_error: httpx.RequestError | None = None
    last_response: httpx.Response | None = None

    for _ in range(max(0, retries) + 1):
        try:
            response = await client.get(path, params=params)
        except httpx.RequestError as exc:
            last_network_error = exc
            last_response = None
        else:
            status = response.status_code
            if status in retry_codes:
                last_response = response
                await sleep_impl(_retry_delay_from_response(response, backoff, upper_backoff))
                backoff = min(backoff * 2, upper_backoff)
                continue
            return response

        await sleep_impl(backoff)
        backoff = min(backoff * 2, upper_backoff)

    if last_response is not None:
        raise BackoffError(f"Request failed with status {last_response.status_code}")
    if last_network_error is not None:
        raise last_network_error
    raise BackoffError("Request failed before receiving a response")


def redact_url_for_logs(url: str) -> str:
    """Return a safe identifier for URLs when logging sensitive endpoints."""

    try:
        parsed = urlsplit(url)
    except Exception:
        return "url"
    if parsed.netloc:
        return parsed.netloc
    return parsed.path or "url"


def _retry_delay_from_response(response: httpx.Response, fallback: float, cap: float) -> float:
    """Compute the delay for the next retry using Retry-After when available."""

    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            delay = float(retry_after)
        except ValueError:
            delay = fallback
    else:
        delay = fallback
    return max(0.1, min(delay, cap))
