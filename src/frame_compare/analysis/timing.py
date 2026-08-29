"""Optional detailed timing collection for analysis diagnostics and benchmarks."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

type AnalysisCacheState = Literal["hit", "miss"]
type AnalysisCacheWriteState = Literal["not_attempted", "written", "failed"]


@dataclass(slots=True)
class AnalysisTimingRecorder:
    """Collect additive timing spans without affecting normal analysis callers."""

    spans_seconds: dict[str, float] = field(default_factory=dict[str, float])
    cache_state: AnalysisCacheState = "miss"
    cache_write_state: AnalysisCacheWriteState = "not_attempted"

    def add_seconds(self, name: str, elapsed_seconds: float) -> None:
        """Add an observed duration to a named span."""
        self.spans_seconds[name] = self.spans_seconds.get(name, 0.0) + elapsed_seconds

    def as_dict(self) -> dict[str, float]:
        """Return timing spans in deterministic key order."""
        return {name: self.spans_seconds[name] for name in sorted(self.spans_seconds)}


@contextmanager
def record_span(
    recorder: AnalysisTimingRecorder | None,
    name: str,
) -> Generator[None]:
    """Record a coarse additive span, including time elapsed before failures.

    Per-frame metric loops intentionally use direct ``perf_counter`` calls so
    context-manager overhead does not contaminate their smallest measurements.
    """
    if recorder is None:
        yield
        return

    started = perf_counter()
    try:
        yield
    finally:
        recorder.add_seconds(name, perf_counter() - started)


__all__ = [
    "AnalysisCacheState",
    "AnalysisCacheWriteState",
    "AnalysisTimingRecorder",
    "record_span",
]
