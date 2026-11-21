import logging
import sys
from contextlib import suppress
from threading import Lock
from typing import Protocol, TextIO, cast

import structlog
from rich.console import Console
from rich.text import Text

from frame_compare.utils.terminal_theme import FAIL, WARN, glyphs_for_console, human_console

_console_lock = Lock()
_active_console: Console | None = None


def register_log_console(console: Console) -> None:
    """Route Rich log events through the console that owns live progress."""
    global _active_console
    with _console_lock:
        _active_console = console


def release_log_console(console: Console) -> None:
    """Release only the console owned by the stopping reporter."""
    global _active_console
    with _console_lock:
        if _active_console is console:
            _active_console = None


class _RichLogRenderer:
    def __init__(self, *, no_color: bool) -> None:
        self._console = human_console(stderr=True, no_color=no_color)

    def __call__(
        self,
        logger: structlog.typing.WrappedLogger,
        name: str,
        event_dict: structlog.typing.EventDict,
        *,
        event_is_identifier: bool = True,
    ) -> str:
        with _console_lock:
            console = _active_console or self._console
        level = event_dict.pop("level", name)
        event = str(event_dict.pop("event", ""))
        if event_is_identifier:
            event = event.replace("_", " ")
        event_dict.pop("timestamp", None)
        diagnostics = {
            key: event_dict.pop(key)
            for key in ("stack", "exception", "exc_info")
            if key in event_dict
        }
        glyphs = glyphs_for_console(console)
        line = Text()
        if level == "warning":
            line.append(f"{glyphs.warning} ", style=WARN)
        elif level in {"error", "critical"}:
            line.append(f"{glyphs.failed} ", style=FAIL)
        else:
            line.style = "dim"
        line.append(event)
        for key, value in sorted(event_dict.items()):
            line.append(f" · {key}={value}", style="dim")
        if diagnostics:
            # Keep structlog's existing stack/exception formatter, including its
            # traceback layout, below the new event line.
            renderer = structlog.dev.ConsoleRenderer(colors=not console.no_color)
            traceback = renderer(logger, name, {"event": "", **diagnostics})
            line.append_text(Text.from_ansi(traceback))
        console.print(line, width=min(console.width, 120))
        raise structlog.DropEvent


class _RichLoggingHandler(logging.Handler):
    """Adapt propagated stdlib warnings to the same human renderer."""

    def __init__(self, renderer: _RichLogRenderer, level: int) -> None:
        super().__init__(max(logging.WARNING, level))
        self._renderer = renderer

    def emit(self, record: logging.LogRecord) -> None:
        event: structlog.typing.EventDict = {
            "event": record.getMessage(),
            "level": record.levelname.lower(),
        }
        if record.exc_info:
            event["exc_info"] = record.exc_info
        if record.stack_info:
            event["stack"] = record.stack_info
        with suppress(structlog.DropEvent):
            # getMessage() is formatted text, including literal paths, rather
            # than a structlog event identifier to normalize for human output.
            self._renderer(record.name, record.levelname.lower(), event, event_is_identifier=False)


_stdlib_handler: _RichLoggingHandler | None = None


class _WritableStream(Protocol):
    def write(self, message: str, /) -> int | None: ...

    def flush(self) -> None: ...


class _StderrStream:
    def __init__(self) -> None:
        # Keep a fallback reference for interpreter shutdown, when `sys` can be
        # partially torn down. During normal operation (including pytest
        # capturing), we prefer the current `sys.stderr`.
        self._fallback_stream = sys.stderr

    def _get_stream(self) -> _WritableStream | None:
        """Return the active stderr-like stream, falling back safely."""
        try:
            current = sys.stderr
        except AttributeError:
            current = None
        return current if current is not None else self._fallback_stream

    def write(self, message: str) -> int:
        stream = self._get_stream()
        if stream is None:
            return 0
        try:
            written = stream.write(message)
            if written is None:
                return len(message)
            return written
        except (ValueError, OSError):
            # E.g. pytest may close capture streams during teardown.
            return 0

    def flush(self) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        try:
            stream.flush()
        except (ValueError, OSError):
            return


def configure_logging(
    level: str = "INFO",
    log_format: str = "console",
    *,
    rich_output: bool = False,
    no_color: bool = False,
) -> None:
    """Configure structlog with either console or JSON output.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Case-insensitive. Unknown values fall back to INFO.
        log_format: "console" for human-readable, "json" for structured.
               Unknown values fall back to "console".
        rich_output: Use the human run format and active progress console.
        no_color: Disable color for Rich human output.

    Notes:
        - Level filtering uses stdlib logging level constants (10, 20, 30, 40, 50).
        - Unknown level strings silently fall back to INFO (20).
        - Unknown format strings silently fall back to console renderer.
        - Safe to call multiple times; later calls reconfigure structlog globally.
    """
    global _stdlib_handler
    if _stdlib_handler is not None:
        logging.getLogger().removeHandler(_stdlib_handler)
        _stdlib_handler.close()
        _stdlib_handler = None

    # Map level string to logging constant; fallback to INFO for unknown
    level_num = getattr(logging, level.upper(), logging.INFO)

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        processors.append(
            structlog.processors.ExceptionRenderer(
                structlog.tracebacks.ExceptionDictTransformer(show_locals=False)
            )
        )
        processors.append(structlog.processors.JSONRenderer())
    elif rich_output:
        renderer = _RichLogRenderer(no_color=no_color)
        processors.append(renderer)
        _stdlib_handler = _RichLoggingHandler(renderer, level_num)
        logging.getLogger().addHandler(_stdlib_handler)
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
        logger_factory=structlog.PrintLoggerFactory(
            file=cast(TextIO, _StderrStream()),
        ),
    )
