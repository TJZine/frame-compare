from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import Any, Protocol


class Response:
    def __init__(
        self,
        status_code: int = 200,
        *,
        json: Any | None = None,
        text: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text if text is not None else ""
        self.headers: dict[str, str] = {}
        self._json_data: Any = json if json is not None else {}

    def json(self) -> Any:
        return self._json_data


class RequestError(Exception):
    """Base exception for HTTPX failures."""

    def __init__(self, *args: Any, request: Any | None = None, **kwargs: Any) -> None:
        if "request" in kwargs:
            if request is not None:
                raise TypeError("request provided twice")
            request = kwargs.pop("request")
        self.request: Any | None = request
        super().__init__(*args, **kwargs)


class Timeout:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


class _TransportHandler(Protocol):
    def __call__(self, request: Any) -> Response | Awaitable[Response]: ...


class BaseTransport(Protocol):
    def __call__(self, request: Any) -> Response: ...

    async def handle_async_request(self, request: Any) -> Response: ...


class MockTransport(BaseTransport):
    def __init__(self, handler: _TransportHandler) -> None:
        self.handler = handler

    def __call__(self, request: Any) -> Response:
        result = self.handler(request)
        if inspect.isawaitable(result):
            raise RuntimeError("MockTransport handler returned awaitable in sync context")
        return result

    async def handle_async_request(self, request: Any) -> Response:
        result = self.handler(request)
        if inspect.isawaitable(result):
            return await result
        return result


class AsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    async def get(self, *args: Any, **kwargs: Any) -> Response:
        return Response()

    async def post(self, *args: Any, **kwargs: Any) -> Response:
        return Response()

    async def aclose(self) -> None:
        return None

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        return None


__all__ = [
    "AsyncClient",
    "BaseTransport",
    "MockTransport",
    "RequestError",
    "Response",
    "Timeout",
]
