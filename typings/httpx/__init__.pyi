from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Mapping, Protocol


class URL(Protocol):
    path: str
    params: Mapping[str, str]


class Request(Protocol):
    url: URL


class Response:
    status_code: int
    text: str
    headers: Mapping[str, str]

    def __init__(self, status_code: int, *, json: Any | None = ..., text: str | None = ...) -> None: ...
    def json(self) -> Any: ...


class BaseTransport(Protocol):
    async def handle_async_request(self, request: Request) -> Response: ...


class Timeout:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class RequestError(Exception):
    request: Request

    def __init__(self, message: str = ..., *, request: Request | None = ...) -> None: ...


class MockTransport(BaseTransport):
    def __init__(self, handler: Callable[[Request], Response]) -> None: ...
    async def handle_async_request(self, request: Request) -> Response: ...
    def __call__(self, request: Request) -> Response: ...


class AsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    async def get(self, url: str, *args: Any, **kwargs: Any) -> Response: ...
    async def post(self, url: str, *args: Any, **kwargs: Any) -> Response: ...
    async def aclose(self) -> None: ...
    async def __aenter__(self) -> "AsyncClient": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
