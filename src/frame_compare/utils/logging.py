import logging
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

import structlog

_run_id: ContextVar[str] = ContextVar("run_id", default="")


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
    format: str = "console",
    log_file: Path | None = None,
) -> None:
    """Configure structlog with either console or JSON output.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Case-insensitive. Unknown values fall back to INFO.
        format: "console" for human-readable, "json" for structured.
               Unknown values fall back to "console".
        log_file: Optional file path for logging output (not yet implemented).

    Notes:
        - Level filtering uses stdlib logging level constants (10, 20, 30, 40, 50).
        - Unknown level strings silently fall back to INFO (20).
        - Unknown format strings silently fall back to console renderer.
        - Safe to call multiple times; later calls reconfigure structlog globally.
    """
    # TODO: File handler implementation deferred
    # Map level string to logging constant; fallback to INFO for unknown
    level_num = getattr(logging, level.upper(), logging.INFO)

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
    )
