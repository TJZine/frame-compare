"""Observe run cancellation without delivering it into awaited resource cleanup."""

from __future__ import annotations

import asyncio


class _RunInterrupt(BaseException):
    """Synchronous owner stopped; its async caller must deliver cancellation."""


def is_cancelling() -> bool:
    """Return whether the current task has a pending cancellation request."""
    try:
        task = asyncio.current_task()
    except RuntimeError:
        return False
    return task is not None and task.cancelling() > 0


def raise_if_cancelling() -> None:
    """Stop synchronous admission/publication without consuming queued cancellation."""
    if is_cancelling():
        raise _RunInterrupt()


async def cancellation_checkpoint() -> None:
    """Deliver queued cancellation here, before any awaited owned cleanup."""
    await asyncio.sleep(0)
    # Also respect a cancellation already delivered and caught by a collaborator.
    if is_cancelling():
        raise asyncio.CancelledError()
