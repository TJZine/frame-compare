from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Mapping, cast

import httpx
import pytest
from _pytest.logging import LogCaptureFixture

from src.frame_compare import net


class StubAsyncClient:
    def __init__(self, responses: list[httpx.Response], base_url: str = "https://example.com") -> None:
        self._responses = list(responses)
        self.calls = 0
        self.base_url = base_url

    async def get(
        self,
        path: str,
        params: dict[str, object],
        timeout: float | httpx.Timeout | None = None,
    ) -> httpx.Response:
        self.calls += 1
        response = self._responses.pop(0)
        return response


class SleepRecorder:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, duration: float) -> None:
        self.calls.append(duration)


class _FakeResponse:
    def __init__(self, status_code: int, headers: Mapping[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = dict(headers or {})


def _response(status_code: int, *, retry_after: str | None = None) -> httpx.Response:
    headers: dict[str, str] | None = None
    if retry_after is not None:
        headers = {"Retry-After": retry_after}
    return cast(httpx.Response, _FakeResponse(status_code, headers))


def _run(coro: Coroutine[Any, Any, httpx.Response]) -> httpx.Response:
    return asyncio.run(coro)


def test_httpx_backoff_retries_then_succeeds() -> None:
    stub_client = StubAsyncClient([_response(503), _response(200)])
    client = cast(httpx.AsyncClient, stub_client)
    sleeper = SleepRecorder()

    response = _run(
        net.httpx_get_json_with_backoff(
            client,
            path="https://example.com/api",
            params={"q": "value"},
            retries=2,
            sleep=sleeper,
        )
    )

    assert response.status_code == 200
    assert sleeper.calls == [0.5]
    assert stub_client.calls == 2


def test_httpx_backoff_exhausts_budget() -> None:
    stub_client = StubAsyncClient([_response(503, retry_after="1"), _response(503)])
    client = cast(httpx.AsyncClient, stub_client)
    sleeper = SleepRecorder()

    with pytest.raises(net.BackoffError) as excinfo:
        _run(
            net.httpx_get_json_with_backoff(
                client,
                path="https://example.com/api",
                params={},
                retries=1,
                sleep=sleeper,
            )
        )

    assert "503" in str(excinfo.value)
    assert sleeper.calls == [1.0]
    assert stub_client.calls == 2


def test_httpx_backoff_invokes_callback_before_sleep() -> None:
    stub_client = StubAsyncClient([_response(503), _response(200)])
    client = cast(httpx.AsyncClient, stub_client)
    sleeper = SleepRecorder()
    recorded: list[tuple[float, int]] = []

    async def on_backoff(delay: float, attempt_index: int) -> None:
        recorded.append((delay, attempt_index))

    _run(
        net.httpx_get_json_with_backoff(
            client,
            path="https://api.example.com/endpoint",
            params={},
            retries=2,
            initial_backoff=0.2,
            sleep=sleeper,
            on_backoff=on_backoff,
        )
    )

    assert recorded == [(0.2, 1)]
    assert sleeper.calls == [0.2]


def test_httpx_backoff_logs_success(caplog: LogCaptureFixture) -> None:
    stub_client = StubAsyncClient([_response(200)])
    client = cast(httpx.AsyncClient, stub_client)
    caplog.set_level(logging.INFO, logger="src.frame_compare.net")

    _run(
        net.httpx_get_json_with_backoff(
            client,
            path="https://api.example.com/endpoint",
            params={},
        )
    )

    assert any("completed after 1 attempt" in record.getMessage() for record in caplog.records)
