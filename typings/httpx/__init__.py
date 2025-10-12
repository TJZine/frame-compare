from __future__ import annotations

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


class Timeout:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


class _TransportHandler(Protocol):
    def __call__(self, request: Any) -> Response: ...


class BaseTransport:
    async def handle_async_request(self, request: Any) -> Response:
        return Response()


class MockTransport:
    def __init__(self, handler: _TransportHandler) -> None:
        self.handler = handler

    def __call__(self, request: Any) -> Response:
        return self.handler(request)

    async def handle_async_request(self, request: Any) -> Response:
        return self.handler(request)


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
