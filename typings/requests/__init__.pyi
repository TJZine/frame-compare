from collections.abc import MutableMapping
from typing import Any, Mapping


class RequestException(Exception):
    ...


class HTTPError(RequestException):
    def __init__(self, message: str = ..., *, response: Response | None = ...) -> None: ...


class Response:
    status_code: int
    text: str
    content: bytes
    headers: Mapping[str, str]

    def __init__(self, status_code: int = ..., *, text: str = ..., content: bytes = ..., json: Any | None = ...) -> None: ...
    def json(self) -> Any: ...


class CookieJar(MutableMapping[str, str]):
    def get_dict(self) -> dict[str, str]: ...


class Session:
    cookies: CookieJar

    def __init__(self) -> None: ...
    def get(self, url: str, *args: Any, **kwargs: Any) -> Response: ...
    def post(self, url: str, *args: Any, **kwargs: Any) -> Response: ...
    def close(self) -> None: ...
    def mount(self, prefix: str, adapter: Any) -> None: ...


def request(method: str, url: str, *args: Any, **kwargs: Any) -> Response: ...
