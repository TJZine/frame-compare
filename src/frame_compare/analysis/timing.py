"""Optional detailed timing collection for analysis diagnostics and benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

type AnalysisCacheState = Literal["hit", "miss"]
type AnalysisCacheWriteState = Literal["not_attempted", "written", "failed"]


def _empty_timing_spans() -> dict[str, float]:
    return {}


@dataclass(slots=True)
class AnalysisTimingRecorder:
    """Collect additive timing spans without affecting normal analysis callers."""

    spans_seconds: dict[str, float] = field(default_factory=_empty_timing_spans)
    cache_state: AnalysisCacheState = "miss"
    cache_write_state: AnalysisCacheWriteState = "not_attempted"

    def add_seconds(self, name: str, elapsed_seconds: float) -> None:
        """Add an observed duration to a named span."""
        self.spans_seconds[name] = self.spans_seconds.get(name, 0.0) + elapsed_seconds

    def as_dict(self) -> dict[str, float]:
        """Return timing spans in deterministic key order."""
        return {name: self.spans_seconds[name] for name in sorted(self.spans_seconds)}


__all__ = ["AnalysisCacheState", "AnalysisCacheWriteState", "AnalysisTimingRecorder"]
