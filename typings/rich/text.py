from typing import Any


class Text:
    def __init__(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        self.plain = text

    def append(self, text: str, *args: Any, **kwargs: Any) -> None:
        self.plain += text

    def __str__(self) -> str:
        return self.plain


__all__ = ["Text"]
