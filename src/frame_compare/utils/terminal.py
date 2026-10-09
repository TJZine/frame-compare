"""Terminal capability and ANSI policy helpers."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from collections.abc import Generator
from contextlib import contextmanager
from threading import current_thread, main_thread

from typer import Abort

from frame_compare.utils.cancellation import (
    _RunInterrupt,  # pyright: ignore[reportPrivateUsage] - private coroutine-boundary marker
    raise_if_cancelling,
)


def no_color_requested(
    *,
    explicit_no_color: bool = False,
) -> bool:
    """Return whether ANSI color should be disabled for human output."""
    return explicit_no_color or "NO_COLOR" in os.environ


def stream_is_tty(stream: object) -> bool:
    """Return True when a stream behaves like an interactive TTY."""
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (OSError, TypeError, ValueError):
        return False


@contextmanager
def interruptible_prompt() -> Generator[None]:
    """Keep Runner cancellation observable while main-thread terminal input blocks.

    Foreign signal handlers and noninteractive/caller-owned input retain their
    behavior. Restore Runner's exact handler before leaving synchronous input.
    """
    raise_if_cancelling()
    saved = signal.getsignal(signal.SIGINT)
    runner_handler = getattr(saved, "func", None)
    owns_handler = getattr(runner_handler, "__name__", None) == "_on_sigint" and isinstance(
        getattr(runner_handler, "__self__", None), asyncio.Runner
    )
    if (
        current_thread() is not main_thread()
        or not stream_is_tty(sys.stdin)
        or not callable(saved)
        or not owns_handler
    ):
        yield
        raise_if_cancelling()
        return

    signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        try:
            yield
        except (KeyboardInterrupt, Abort) as error:
            if isinstance(error, Abort) and not isinstance(error.__context__, KeyboardInterrupt):
                raise
            saved(signal.SIGINT, None)
            raise _RunInterrupt() from None
        raise_if_cancelling()
    finally:
        signal.signal(signal.SIGINT, saved)
