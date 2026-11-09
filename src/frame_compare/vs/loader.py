"""VapourSynth loader protocol and implementation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.vs.env import ensure_vs_environment
from frame_compare.vs.source import load_source
from frame_compare.vs.types import SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs

    from frame_compare.vs.source_index_cache import ManagedSourceIndexCache


class VSLoader(Protocol):
    """Protocol for loading VapourSynth clips."""

    def load(self, path: Path) -> SourceInfo:
        """Load a video source, returning clip and metadata."""
        ...

    def ensure_core(self) -> vs.Core:
        """Get or create a VapourSynth core."""
        ...


class DefaultVSLoader:
    """LWLibavSource loader with an optional frame-cache cap in MiB."""

    def __init__(
        self,
        memory_limit_mb: int | None = None,
        *,
        index_cache: ManagedSourceIndexCache | None = None,
    ) -> None:
        self._memory_limit_mb = memory_limit_mb
        self._index_cache = index_cache
        self._core: vs.Core | None = None

    def ensure_core(self) -> vs.Core:
        if self._core is None:
            self._core = ensure_vs_environment()
            if self._memory_limit_mb is not None:
                self._core.max_cache_size = self._memory_limit_mb
        return self._core

    def load(
        self, path: Path, *, abort_check: Callable[[], None] = raise_if_cancelling
    ) -> SourceInfo:
        core = self.ensure_core()
        return load_source(path, core, index_cache=self._index_cache, abort_check=abort_check)

    def validated_index(self, path: Path) -> Path | None:
        """Return the workspace's committed index for a read-only session."""
        if self._index_cache is None:
            return None
        return self._index_cache.validated_index(path)
