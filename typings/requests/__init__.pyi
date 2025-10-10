from typing import Any


class HTTPError(Exception):
    def __init__(self, message: str = ..., response: Any | None = ...) -> None: ...
