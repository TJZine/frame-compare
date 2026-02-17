import io
import logging
import sys
from collections.abc import Iterable
from contextvars import ContextVar
from types import TracebackType
from typing import Any, BinaryIO, TextIO
from uuid import uuid4

import structlog

_run_id: ContextVar[str] = ContextVar("run_id", default="")


class _StderrProxy(io.TextIOBase, TextIO):
    def __init__(self) -> None:
        super().__init__()
        # Keep a fallback reference for interpreter shutdown, when `sys` can be
        # partially torn down. During normal operation (including pytest
        # capturing), we prefer the current `sys.stderr`.
        self._fallback_stream = sys.stderr

    def _get_stream(self) -> object:
        """Return the active stderr-like stream, falling back safely."""
        try:
            current = sys.stderr
        except Exception:
            current = None
        return current if current is not None else self._fallback_stream

    def write(self, message: str) -> int:
        stream = self._get_stream()
        if stream is None:
            return 0
        try:
            return int(stream.write(message))  # type: ignore[attr-defined]
        except (ValueError, OSError):
            # E.g. pytest may close capture streams during teardown.
            return 0

    def flush(self) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        try:
            stream.flush()  # type: ignore[attr-defined]
        except (ValueError, OSError):
            return

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def isatty(self) -> bool:  # pragma: no cover - passthrough
        stream = self._get_stream()
        if stream is None:
            return False
        try:
            return bool(stream.isatty())  # type: ignore[attr-defined]
        except (ValueError, OSError):
            return False

    def fileno(self) -> int:  # pragma: no cover - passthrough
        stream = self._get_stream()
        if stream is None:
            raise io.UnsupportedOperation("stderr has no fileno")
        try:
            return int(stream.fileno())  # type: ignore[attr-defined]
        except (ValueError, OSError) as exc:
            raise io.UnsupportedOperation("stderr has no fileno") from exc

    def read(self, size: int | None = -1) -> str:  # pragma: no cover - not supported
        raise io.UnsupportedOperation("stderr is not readable")

    def readline(self, size: int | None = -1) -> str:  # pragma: no cover - not supported
        raise io.UnsupportedOperation("stderr is not readable")

    def readlines(self, hint: int | None = -1) -> list[str]:  # pragma: no cover - not supported
        raise io.UnsupportedOperation("stderr is not readable")

    def seek(self, offset: int, whence: int = 0) -> int:  # pragma: no cover - not supported
        raise io.UnsupportedOperation("stderr is not seekable")

    def tell(self) -> int:  # pragma: no cover - not supported
        raise io.UnsupportedOperation("stderr is not seekable")

    def truncate(self, size: int | None = None) -> int:  # pragma: no cover - not supported
        raise io.UnsupportedOperation("stderr is not seekable")

    def writelines(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.write(line)

    @property
    def buffer(self) -> BinaryIO:
        stream = self._get_stream()
        return getattr(stream, "buffer", io.BytesIO())

    @property
    def encoding(self) -> str:  # type: ignore[override]
        stream = self._get_stream()
        return getattr(stream, "encoding", "utf-8") or "utf-8"

    @property
    def errors(self) -> str | None:  # type: ignore[override]
        stream = self._get_stream()
        return getattr(stream, "errors", None)

    @property
    def line_buffering(self) -> bool:  # type: ignore[override]
        stream = self._get_stream()
        return bool(getattr(stream, "line_buffering", False))

    @property
    def newlines(self) -> Any:  # type: ignore[override]
        stream = self._get_stream()
        return getattr(stream, "newlines", None)

    @property
    def mode(self) -> str:  # type: ignore[override]
        stream = self._get_stream()
        return getattr(stream, "mode", "w")

    @property
    def name(self) -> str:  # type: ignore[override]
        stream = self._get_stream()
        return getattr(stream, "name", "<stderr>")

    @property
    def closed(self) -> bool:
        stream = self._get_stream()
        return bool(getattr(stream, "closed", False))

    def __enter__(self) -> "_StderrProxy":
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.flush()

    def close(self) -> None:  # pragma: no cover - avoid closing stderr
        self.flush()


_STDERR_PROXY = _StderrProxy()


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
    **kwargs: object,
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
    format_override = kwargs.pop("format", None)
    if format_override is not None:
        if isinstance(format_override, str):
            log_format = format_override
        else:
            raise TypeError("format must be str")
    if kwargs:
        unexpected = ", ".join(sorted(kwargs.keys()))
        raise TypeError(f"Unexpected keyword arguments: {unexpected}")
    # Map level string to logging constant; fallback to INFO for unknown
    level_num = getattr(logging, level.upper(), logging.INFO)

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
        logger_factory=structlog.PrintLoggerFactory(file=_StderrProxy()),
    )
