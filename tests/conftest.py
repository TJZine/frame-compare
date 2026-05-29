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


_NON_UNIT_MARKERS = frozenset({"integration", "e2e", "vs_required", "slow", "network"})
_NON_UNIT_NODEID_PREFIXES = ("tests/integration/", "tests/e2e/")
_NON_UNIT_NODEID_SUFFIXES = ("_e2e.py", "test_integration.py")


def _should_default_to_unit(item: pytest.Item) -> bool:
    """Classify fast isolated tests as unit tests unless a heavier route is explicit."""
    if item.get_closest_marker("unit") is not None:
        return False
    if any(item.get_closest_marker(name) is not None for name in _NON_UNIT_MARKERS):
        return False

    nodeid = item.nodeid.split("::", 1)[0]
    return not nodeid.startswith(_NON_UNIT_NODEID_PREFIXES) and not nodeid.endswith(
        _NON_UNIT_NODEID_SUFFIXES
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Best-effort cleanup of pytest temp cache dirs in the repo root.

    Pytest's cache provider uses temporary directories named like
    `pytest-cache-files-*` and normally deletes them. If a run is interrupted
    or the OS denies cleanup, they can be left behind and clutter the repo.
    """
    root = Path(str(session.config.rootpath))
    for path in root.glob("pytest-cache-files-*"):
        try:
            # shutil import is local to keep import-time overhead minimal.
            import shutil

            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            # Never fail the test session because cleanup couldn't run.
            pass


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Route unmarked fast tests into the unit bucket for marker-based selection."""
    for item in items:
        if _should_default_to_unit(item):
            item.add_marker(pytest.mark.unit)


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
    _global_mock_vs.RANGE_LIMITED = 0
    _global_mock_vs.RANGE_FULL = 1
    _global_mock_vs.MATRIX_BT709 = 1
    _global_mock_vs.MATRIX_BT2020_CL = 10
    _global_mock_vs.MATRIX_BT2020_NCL = 9
    sys.modules["vapoursynth"] = _global_mock_vs


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def repo_root() -> Path:
    """Return repository root directory."""
    return Path(__file__).resolve().parents[1]


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
