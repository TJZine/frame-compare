"""Render batch result-slot accumulation."""

from __future__ import annotations

from pathlib import Path

__all__ = ["RenderBatchResults"]


class RenderBatchResults:
    """Collect rendered paths by original request index."""

    def __init__(self, count: int) -> None:
        self._results: list[Path | None] = [None] * count

    def record(self, index: int, rendered_path: Path) -> None:
        self._results[index] = rendered_path

    def ordered_paths(self) -> list[Path]:
        completed: list[Path] = []
        for result in self._results:
            if result is None:
                raise RuntimeError("render batch completed without a rendered path")
            completed.append(result)
        return completed
