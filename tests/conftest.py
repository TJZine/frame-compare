"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# ─── Global Mocks (Run at import time for collection) ──────────────────────────


# Globally mock vapoursynth only if it is not installed.
# This prevents ImportError during test collection while preserving real VS when available.
def _vs_needs_mock() -> bool:
    """Check if vapoursynth needs to be mocked for test collection."""
    if "vapoursynth" in sys.modules:
        return False
    try:
        return importlib.util.find_spec("vapoursynth") is None
    except ValueError:
        # Raised when vapoursynth.__spec__ is not set (partial install)
        return True


if _vs_needs_mock():
    _global_mock_vs = MagicMock()
    _global_mock_vs.__spec__ = MagicMock()
    _global_mock_vs.RGBS = 0
    _global_mock_vs.RGB24 = 0
    _global_mock_vs.YUV = 1
    _global_mock_vs.GRAY = 2
    _global_mock_vs.INTEGER = 0
    _global_mock_vs.FLOAT = 1
    _global_mock_vs.MATRIX_BT2020_CL = 10
    _global_mock_vs.MATRIX_BT2020_NCL = 9
    sys.modules["vapoursynth"] = _global_mock_vs


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


# ─── VapourSynth Stubs ─────────────────────────────────────


@pytest.fixture
def mock_vs(mocker):
    """Mock VapourSynth for unit tests."""
    mock = mocker.MagicMock()
    mocker.patch.dict("sys.modules", {"vapoursynth": mock})
    return mock
