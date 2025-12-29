"""Tests for VapourSynth loader."""

from pathlib import Path

import pytest

from frame_compare.errors import SourceLoadError
from frame_compare.vs.loader import DefaultVSLoader


def test_default_vs_loader_load_raises_source_load_error(tmp_path: Path) -> None:
    """Verify DefaultVSLoader.load raises SourceLoadError."""
    loader = DefaultVSLoader()
    with pytest.raises(SourceLoadError) as exc:
        loader.load(tmp_path / "video.mkv")
    assert exc.value.code == "FC-4015"
