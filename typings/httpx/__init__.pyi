from typing import Any, Callable, Mapping, Protocol


class URL(Protocol):
    path: str
    params: Mapping[str, str]


class Request(Protocol):
    url: URL


class Response:
    status_code: int

    def __init__(self, status_code: int, *, json: Any | None = ..., text: str | None = ...) -> None: ...
    def json(self) -> Any: ...


class MockTransport:
    def __init__(self, handler: Callable[[Request], Response]) -> None: ...
    def __call__(self, request: Request) -> Response: ...
