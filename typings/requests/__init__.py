from __future__ import annotations

from __future__ import annotations

from typing import Any, Dict


class RequestException(Exception):
    """Base class for request errors."""


class HTTPError(RequestException):
    def __init__(self, *args: Any, response: Response | None = None, **kwargs: Any) -> None:
        super().__init__(*args)
        self.response = response


class Response:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.text = ""
        self.content = b""
        self.headers: Dict[str, str] = {}

    def json(self) -> Dict[str, Any]:
        return {}


class CookieJar(Dict[str, str]):
    def get_dict(self) -> Dict[str, str]:
        return dict(self)


class Session:
    def __init__(self) -> None:
        self.cookies = CookieJar()

    def get(self, *args: Any, **kwargs: Any) -> Response:
        return Response()

    def post(self, *args: Any, **kwargs: Any) -> Response:
        return Response()

    def close(self) -> None:
        return None


def request(*args: Any, **kwargs: Any) -> Response:
    return Response()


__all__ = [
    "CookieJar",
    "HTTPError",
    "RequestException",
    "Response",
    "Session",
    "request",
]
