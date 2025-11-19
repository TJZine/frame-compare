"""Protocols describing publisher I/O and service adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Callable, Protocol

from src.datatypes import ReportConfig, SlowpicsConfig
from src.frame_compare.analysis import SelectionDetail


class PublisherIO(Protocol):
    """Filesystem helpers consumed by publisher services."""

    def file_size(self, path: str | Path) -> int:
        """Return the size of *path* in bytes, or ``0`` when inaccessible."""
        ...

    def path_exists(self, path: Path) -> bool:
        """Return ``True`` when *path* exists on disk."""
        ...

    def resolve_report_dir(self, root: Path, relative: str, *, purpose: str) -> Path:
        """Resolve a report output directory under the provided *root*."""
        ...


class SlowpicsClientProtocol(Protocol):
    """Adapter for slow.pics uploads."""

    def upload(
        self,
        image_paths: Sequence[str],
        out_dir: Path,
        cfg: SlowpicsConfig,
        *,
        progress_callback: Callable[[int], None] | None = None,
    ) -> str:
        """Upload *image_paths* and return the canonical collection URL."""
        ...


class ReportRendererProtocol(Protocol):
    """Adapter for HTML report generation."""

    def generate(
        self,
        *,
        report_dir: Path,
        report_cfg: ReportConfig,
        frames: Sequence[int],
        selection_details: Mapping[int, SelectionDetail],
        image_paths: Sequence[str],
        plans: Sequence[Mapping[str, object]],
        metadata_title: str | None,
        include_metadata: str,
        slowpics_url: str | None,
    ) -> Path:
        """Generate the HTML report and return the index path."""
        ...
