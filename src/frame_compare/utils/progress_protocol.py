"""Progress protocol shared across reporters and subsystems.

This module is intentionally dependency-light (no Rich imports) so it can be used
from low-level modules without pulling UI dependencies at import time.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting progress of long-running operations."""

    def start_phase(self, name: str, total: int) -> None:
        """Start a new phase of the operation."""
        ...

    def advance(self, amount: int = 1) -> None:
        """Advance the progress of the current phase."""
        ...

    def set_description(self, desc: str) -> None:
        """Set the description for the current phase."""
        ...

    def complete_phase(self) -> None:
        """Mark the current phase as complete."""
        ...

    def suspend(self) -> None:
        """Temporarily hide interactive progress UI during blocking user interaction."""
        ...

    def resume(self) -> None:
        """Restore interactive progress UI after a temporary suspension."""
        ...
