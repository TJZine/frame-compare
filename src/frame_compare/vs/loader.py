"""VapourSynth loader protocol and implementation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Protocol

from frame_compare.vs.env import ensure_vs_environment
from frame_compare.vs.types import SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore


class VSLoader(Protocol):
    """Protocol for loading VapourSynth clips."""

    def load(self, path: Path) -> SourceInfo:
        """Load a video source, returning clip and metadata."""
        ...

    def ensure_core(self) -> vs.Core:
        """Get or create a VapourSynth core."""
        ...


class DefaultVSLoader:
    """Default VapourSynth loader implementation using LWLibavSource."""

    _core: ClassVar[vs.Core | None] = None  # Singleton pattern

    def ensure_core(self) -> vs.Core:
        cls = type(self)
        if cls._core is None:
            cls._core = ensure_vs_environment()
        return cls._core

    def load(self, path: Path) -> SourceInfo:
        from frame_compare.vs.source import load_source

        core = self.ensure_core()
        return load_source(path, core)
