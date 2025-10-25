from __future__ import annotations

import inspect
import urllib.parse
from collections.abc import Awaitable, Mapping
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
    def handle_request(self, request: Any) -> Response: ...
    async def handle_async_request(self, request: Any) -> Response: ...
    async def request(self, request: Any) -> Response: ...


class MockTransport(BaseTransport):
    def __init__(self, handler: _TransportHandler) -> None:
        self.handler = handler

    def __call__(self, request: Any) -> Response:
        return self.handle_request(request)

    def handle_request(self, request: Any) -> Response:
        result = self.handler(request)
        if inspect.isawaitable(result):
            raise RuntimeError("MockTransport handler returned awaitable in sync context")
        return result

    async def handle_async_request(self, request: Any) -> Response:
        result = self.handler(request)
        if inspect.isawaitable(result):
            return await result
        return result

    async def request(self, request: Any) -> Response:
        return await self.handle_async_request(request)


class URL:
    def __init__(self, url: str) -> None:
        parsed = urllib.parse.urlsplit(url)
        self.path = parsed.path or "/"
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        self.params = {key: value for key, value in query}


class Request:
    def __init__(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        content: Any = None,
        data: Any = None,
        json: Any = None,
        **extra: Any,
    ) -> None:
        self.method = method.upper()
        self.url = URL(self._build_url(url, params=params))
        self.headers = dict(headers or {})
        self.params = dict(params or {})
        self.content = content
        self.data = data
        self.json = json
        self.extra = extra

    @staticmethod
    def _build_url(url: str, *, params: Mapping[str, Any] | None) -> str:
        if not params:
            return url
        parsed = urllib.parse.urlsplit(url)
        original_query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        combined = original_query + list(params.items())
        query = urllib.parse.urlencode(combined)
        rebuilt = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment)
        )
        return rebuilt


class AsyncClient:
    def __init__(
        self,
        *args: Any,
        transport: MockTransport | BaseTransport | None = None,
        **kwargs: Any,
    ) -> None:
        self.args = args
        self.kwargs = kwargs
        self.transport = transport or MockTransport(lambda request: Response())

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response:
        request = Request("GET", url, headers=headers, params=params, **kwargs)
        return await self.transport.request(request)

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        content: Any = None,
        data: Any = None,
        json: Any = None,
        **kwargs: Any,
    ) -> Response:
        request = Request(
            "POST",
            url,
            headers=headers,
            params=params,
            content=content,
            data=data,
            json=json,
            **kwargs,
        )
        return await self.transport.request(request)

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
    "Request",
    "RequestError",
    "Response",
    "Timeout",
    "URL",
]
