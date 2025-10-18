from typing import Any

try:
    from rich.console import Console as _RichConsole
except Exception:  # pragma: no cover - rich not available during typing stubs
    _RichConsole = None


class Console:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        width = int(kwargs.get("width", 80))
        height = int(kwargs.get("height", 25))
        self.width = width
        self.height = height
        self.size = (width, height)
        forwarded_kwargs = dict(kwargs)
        forwarded_kwargs["width"] = width
        forwarded_kwargs["height"] = height
        try:
            self._rich_console = (
                _RichConsole(*args, **forwarded_kwargs) if _RichConsole is not None else None
            )
        except Exception:
            self._rich_console = None

    def print(self, *args: Any, **kwargs: Any) -> None:
        pass

    def rule(
        self,
        title: str | None = None,
        *,
        characters: str = "\u2500",
        style: str = "rule.line",
        align: str = "center",
        **kwargs: Any,
    ) -> None:
        if self._rich_console is not None:
            self._rich_console.width = self.width
            self._rich_console.height = self.height
            self._rich_console.rule(
                title if title is not None else "",
                characters=characters,
                style=style,
                align=align,
                **kwargs,
            )
        elif _RichConsole is not None:
            console = _RichConsole(width=self.width, height=self.height)
            console.rule(
                title if title is not None else "",
                characters=characters,
                style=style,
                align=align,
                **kwargs,
            )

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
