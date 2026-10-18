"""Progress protocol shared across reporters and subsystems.

This module is intentionally dependency-light (no Rich imports) so it can be used
from low-level modules without pulling UI dependencies at import time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ProgressPhaseStatus(StrEnum):
    """Terminal status for a reported phase."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    WARNED = "warned"
    FAILED = "failed"


@dataclass(frozen=True)
class AlignmentSummaryEntry:
    """One final source offset for human output only."""

    name: str
    offset: int | None
    origin: str
    audio_candidate: int | None = None

    @property
    def value(self) -> str:
        if self.offset is None:
            return "not applied (kept)" if self.origin == "kept" else "not applied"
        value = f"{self.offset:+d}f"
        if self.audio_candidate is not None and self.audio_candidate != self.offset:
            value += f" (audio {self.audio_candidate:+d}f)"
        return value


@dataclass(frozen=True)
class AlignmentSummary:
    """Memory-only final alignment facts; never a wire or authority contract."""

    entries: tuple[AlignmentSummaryEntry, ...]
    extra_footage: str | None = None

    @property
    def common_origin(self) -> str | None:
        origins = {entry.origin for entry in self.entries}
        return (
            next(iter(origins))
            if len(origins) == 1 and all(entry.offset is not None for entry in self.entries)
            else None
        )


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting progress of long-running operations."""

    def set_phase_steps(self, labels: list[str]) -> None:
        """Set the enabled run phases in execution order for the Rich footer."""
        ...

    def start_phase(self, name: str, total: int, *, presentation: str | None = None) -> None:
        """Start a new phase of the operation.

        ``presentation`` selects reporter-specific styling for the live task
        (for example the slow.pics upload bar). ``None`` keeps the reporter's
        default presentation. Non-interactive reporters may ignore it.
        """
        ...

    def start_indeterminate(self, name: str) -> None:
        """Start a phase with activity but no measurable total."""
        ...

    def advance(self, amount: int = 1) -> None:
        """Advance the progress of the current phase."""
        ...

    def set_description(self, desc: str) -> None:
        """Set the description for the current phase."""
        ...

    def complete_phase(
        self,
        status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
        *,
        retain: bool | None = None,
        summary: str | None = None,
        duration_text: str | None = None,
        alignment_summary: AlignmentSummary | None = None,
    ) -> None:
        """Mark the current phase as complete.

        ``retain`` is only a human TTY presentation hint. ``None`` applies the
        reporter's normal retention policy, ``True`` forces a durable line, and
        ``False`` suppresses a successful completion line. Non-interactive
        reporters may ignore the hint.
        ``summary`` is a short human outcome shown on the durable line (only
        the Rich reporter renders it; other reporters keep their current
        content and ignore it). ``duration_text`` overrides the measured
        duration on the durable line (likewise Rich-only). ``alignment_summary``
        carries final alignment rows and the extra-footage note for human output.
        """
        ...

    def suspend(self) -> None:
        """Temporarily hide interactive progress UI during blocking user interaction."""
        ...

    def resume(self) -> None:
        """Restore interactive progress UI after a temporary suspension."""
        ...
