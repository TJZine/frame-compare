from typing import Any

class Console:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        width = int(kwargs.get("width", 80))
        height = int(kwargs.get("height", 25))
        self.width = width
        self.size = (width, height)

    def print(self, *args: Any, **kwargs: Any) -> None:
        pass

    def status(self, *args: Any, **kwargs: Any) -> "Status":
        return Status()

    def log(self, *args: Any, **kwargs: Any) -> None:
        pass

    def push_theme(self, *args: Any, **kwargs: Any) -> None:
        pass

    def pop_theme(self) -> None:
        pass

    def capture(self) -> "ConsoleCapture":
        return ConsoleCapture()

    def export_text(self, *, clear: bool = False) -> str:
        return ""


class Status:
    def update(self, *args: Any, **kwargs: Any) -> None:
        pass

    def stop(self) -> None:
        pass


class ConsoleCapture:
    def __enter__(self) -> str:
        return ""

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    def get(self) -> str:
        return ""


__all__ = ["Console", "Status", "ConsoleCapture"]
