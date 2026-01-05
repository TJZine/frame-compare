"""Pytest configuration and fixtures for Frame Compare tests."""

from pathlib import Path

import pytest

# =============================================================================
# MARKERS
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "tier_a: marks tests runnable without VapourSynth or network"
    )
    config.addinivalue_line("markers", "vs_required: marks tests that require VapourSynth")
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "e2e: marks end-to-end tests")
    config.addinivalue_line("markers", "tier_b: marks tests that require VapourSynth or network")


# =============================================================================
# SKIP CONDITIONS
# =============================================================================


def vapoursynth_available() -> bool:
    """Check if VapourSynth is available."""
    try:
        import vapoursynth  # noqa: F401

        return True
    except ImportError:
        return False


def pytest_collection_modifyitems(config, items):
    """Skip VapourSynth tests if VS is not available."""
    if not vapoursynth_available():
        skip_vs = pytest.mark.skip(reason="VapourSynth not available")
        for item in items:
            if "vs_required" in item.keywords:
                item.add_marker(skip_vs)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with standard structure."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create standard directories
    (workspace / "comparison_videos").mkdir()
    (workspace / "config").mkdir()
    (workspace / "screenshots").mkdir()
    (workspace / "generated").mkdir()

    return workspace


@pytest.fixture
def sample_config_toml(tmp_workspace: Path) -> Path:
    """Create a sample config.toml file."""
    config_path = tmp_workspace / "config" / "config.toml"
    config_path.write_text("""
[analysis]
frame_count = 5
random_seed = 42

[slowpics]
auto_upload = false

[logging]
level = "DEBUG"
""")
    return config_path


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


# =============================================================================
# MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_vs(mocker):
    """Mock VapourSynth module."""
    mock_core = mocker.MagicMock()
    mock_core.version_number.return_value = 72

    mock_vs = mocker.MagicMock()
    mock_vs.core = mock_core

    mocker.patch.dict("sys.modules", {"vapoursynth": mock_vs})
    return mock_vs


@pytest.fixture
def mock_ffmpeg(mocker):
    """Mock FFmpeg subprocess calls."""
    mock = mocker.patch("subprocess.run")
    mock.return_value.returncode = 0
    mock.return_value.stdout = b""
    mock.return_value.stderr = b""
    return mock


# =============================================================================
# UTILITY FUNCTIONS FOR TESTS
# =============================================================================


def create_dummy_video(path: Path, frames: int = 100) -> None:
    """Create a dummy video file for testing.

    In real tests, this would create an actual test video.
    For unit tests, it just creates a placeholder.
    """
    path.write_bytes(b"DUMMY_VIDEO")


def create_dummy_png(path: Path, width: int = 100, height: int = 100) -> None:
    """Create a dummy PNG file for testing."""
    # Minimal valid PNG header + IHDR + IEND
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR"  # IHDR chunk
        b"\x00\x00\x00d"  # width (100)
        b"\x00\x00\x00d"  # height (100)
        b"\x08\x02"  # bit depth, color type
        b"\x00\x00\x00"  # compression, filter, interlace
        b"\x00\x00\x00\x00"  # CRC placeholder
        b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND chunk
    )
