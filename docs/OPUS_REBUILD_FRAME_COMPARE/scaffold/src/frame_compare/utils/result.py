"""Result type pattern for error handling without exceptions.

This module provides Ok and Err types for returning results that may fail,
allowing callers to handle errors without try/except blocks.

Example:
    def load_video(path: Path) -> Result[VideoClip, str]:
        if not path.exists():
            return Err(f"File not found: {path}")
        return Ok(VideoClip(path))

    match load_video(path):
        case Ok(clip):
            process(clip)
        case Err(msg):
            log.warning(f"Skipping: {msg}")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class Ok[T]:
    """Success result containing a value.

    Attributes:
        value: The success value
    """

    value: T

    def is_ok(self) -> bool:
        """Return True if this is a success result."""
        return True

    def is_err(self) -> bool:
        """Return False since this is a success result."""
        return False

    def unwrap(self) -> T:
        """Return the success value."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Return the success value (default ignored)."""
        return self.value

    def map[U](self, fn: Callable[[T], U]) -> Ok[U]:
        """Apply function to the value."""
        return Ok(fn(self.value))


@dataclass(frozen=True, slots=True)
class Err[E]:
    """Error result containing an error.

    Attributes:
        error: The error value
    """

    error: E

    def is_ok(self) -> bool:
        """Return False since this is an error result."""
        return False

    def is_err(self) -> bool:
        """Return True if this is an error result."""
        return True

    def unwrap(self) -> NoReturn:
        """Raise ValueError since this is an error result."""
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_or[T](self, default: T) -> T:
        """Return the default value since this is an error."""
        return default

    def map(self, fn: Callable[[object], object]) -> Err[E]:
        """Return self unchanged since this is an error."""
        return self


# Type alias for Result
type Result[T, E] = Ok[T] | Err[E]


def ok[T](value: T) -> Ok[T]:
    """Create a success result."""
    return Ok(value)


def err[E](error: E) -> Err[E]:
    """Create an error result."""
    return Err(error)
