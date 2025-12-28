"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_video_path() -> Path:
    """Path to test video file (placeholder)."""
    return Path(__file__).parent / "fixtures" / "sample.mkv"


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Generator[Path]:
    """Temporary workspace with standard structure."""
    (tmp_path / "comparison_videos").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "generated").mkdir()
    yield tmp_path
