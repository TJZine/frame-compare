"""Tests for VapourSynth loader."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from frame_compare.vs.loader import DefaultVSLoader


def test_default_vs_loader_load_calls_load_source(tmp_path: Path) -> None:
    """Verify DefaultVSLoader.load delegates to load_source."""
    loader = DefaultVSLoader()
    path = tmp_path / "video.mkv"

    with (
        patch("frame_compare.vs.loader.load_source") as mock_load,
        patch.object(loader, "ensure_core") as mock_ensure,
    ):
        mock_core = MagicMock()
        mock_ensure.return_value = mock_core

        loader.load(path)

        mock_load.assert_called_once_with(path, mock_core)


def test_default_vs_loader_ensure_core_caches_per_instance() -> None:
    """Repeated calls reuse one instance's core, but loaders do not share state."""
    loader_a = DefaultVSLoader()
    loader_b = DefaultVSLoader()
    core_a = MagicMock(name="core_a")
    core_b = MagicMock(name="core_b")

    with patch(
        "frame_compare.vs.loader.ensure_vs_environment",
        side_effect=[core_a, core_b],
    ) as mock_ensure_env:
        assert loader_a.ensure_core() is core_a
        assert loader_a.ensure_core() is core_a
        assert loader_b.ensure_core() is core_b
        assert loader_b.ensure_core() is core_b

    assert mock_ensure_env.call_count == 2
