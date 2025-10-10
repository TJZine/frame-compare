from typing import Any, Mapping, Sequence

class MultipartEncoder:
    content_type: str
    len: int

    def __init__(self, fields: Mapping[str, Any] | Sequence[tuple[str, Any]], boundary: str | None = ...) -> None: ...

__all__ = ["MultipartEncoder"]
