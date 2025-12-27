"""Logging utilities with structured output and secrets redaction.

Provides a configured structlog-based logger with automatic redaction of
sensitive fields like API keys, passwords, and tokens.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

import structlog

# Keys that should be redacted in log output
SENSITIVE_KEYS = frozenset({
    "api_key",
    "apikey",
    "password",
    "token",
    "secret",
    "authorization",
    "auth",
    "bearer",
    "credential",
    "credentials",
})

def _redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_mapping(data: Mapping[str, object]) -> dict[str, object]:
    """Recursively redact sensitive keys in a mapping."""
    result: dict[str, object] = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_KEYS:
            result[key] = "[REDACTED]"
        else:
            result[key] = _redact_value(value)
    return result


def redact_secrets_processor(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, object],
) -> dict[str, object]:
    """Structlog processor that redacts sensitive fields."""
    return _redact_mapping(event_dict)


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
) -> None:
    """Configure structlog with redaction and appropriate formatting.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON; else console format
    """
    processors: list[structlog.types.Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        redact_secrets_processor,  # Redact before output
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper()),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named logger with redaction enabled.

    Args:
        name: Logger name (typically module name)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
