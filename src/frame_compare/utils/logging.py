import logging
import sys
from contextvars import ContextVar
from typing import Protocol, TextIO, cast
from uuid import uuid4

import structlog

_run_id: ContextVar[str] = ContextVar("run_id", default="")


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


def new_run_id() -> str:
    """Generate and set a correlation ID for the current run.

    Returns the generated ID (format: first 8 chars of UUID4).
    Also binds the run_id into structlog contextvars so it appears in all logs.
    """
    run_id = uuid4().hex[:8]
    _run_id.set(run_id)
    structlog.contextvars.bind_contextvars(run_id=run_id)
    return run_id


def get_run_id() -> str:
    """Get the current run's correlation ID."""
    return _run_id.get() or "unknown"


def configure_logging(
    level: str = "INFO",
    log_format: str = "console",
) -> None:
    """Configure structlog with either console or JSON output.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Case-insensitive. Unknown values fall back to INFO.
        log_format: "console" for human-readable, "json" for structured.
               Unknown values fall back to "console".

    Notes:
        - Level filtering uses stdlib logging level constants (10, 20, 30, 40, 50).
        - Unknown level strings silently fall back to INFO (20).
        - Unknown format strings silently fall back to console renderer.
        - Safe to call multiple times; later calls reconfigure structlog globally.
    """
    # Map level string to logging constant; fallback to INFO for unknown
    level_num = getattr(logging, level.upper(), logging.INFO)

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        processors.append(structlog.processors.dict_tracebacks)
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
        logger_factory=structlog.PrintLoggerFactory(
            file=cast(TextIO, _StderrStream()),
        ),
    )
