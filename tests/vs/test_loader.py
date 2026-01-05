"""Tests for VapourSynth loader."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from frame_compare.vs.loader import DefaultVSLoader


def test_default_vs_loader_load_calls_load_source(tmp_path: Path) -> None:
    """Verify DefaultVSLoader.load delegates to load_source."""
    loader = DefaultVSLoader()
    path = tmp_path / "video.mkv"

    with (
        patch("frame_compare.vs.source.load_source") as mock_load,
        patch.object(loader, "ensure_core") as mock_ensure,
    ):
        mock_core = MagicMock()
        mock_ensure.return_value = mock_core

        loader.load(path)

        mock_load.assert_called_once_with(path, mock_core)
