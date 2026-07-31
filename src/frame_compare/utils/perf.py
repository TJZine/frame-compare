"""Performance instrumentation utilities."""

from __future__ import annotations

import os
import time
from collections.abc import Generator
from contextlib import contextmanager

import structlog

log = structlog.get_logger()

SECONDS_TO_MILLISECONDS = 1000.0


def is_perf_enabled() -> bool:
    """Return True when perf timing logs are enabled.

    Enabled via environment variable:
      - FRAME_COMPARE_PERF in {"1", "true", "yes", "on"} (case-insensitive)
    """
    val = os.environ.get("FRAME_COMPARE_PERF", "").lower()
    return val in ("1", "true", "yes", "on")


@contextmanager
def perf_span(name: str, **fields: object) -> Generator[None]:
    """
    Record a timing span if enabled.

    Logs a 'perf' event with 'elapsed_ms' when the span completes.
    """
    if not is_perf_enabled():
        yield
        return

    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * SECONDS_TO_MILLISECONDS
        log.info("perf", span=name, elapsed_ms=round(elapsed_ms, 3), **fields)
