from typing import Any, Mapping, Sequence


class MultipartEncoder:
    content_type: str
    len: int

    def __init__(self, fields: Mapping[str, Any] | Sequence[tuple[str, Any]], boundary: str | None = None) -> None:
        self.fields = dict(fields) if isinstance(fields, Mapping) else {k: v for k, v in fields}
        self.boundary = boundary
        self.content_type = "multipart/form-data"
        self.len = 0

    def to_string(self) -> bytes:
        return b""


__all__ = ["MultipartEncoder"]
