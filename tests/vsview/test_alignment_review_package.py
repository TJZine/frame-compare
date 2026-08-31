from __future__ import annotations

import importlib.metadata
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


def test_vsview_entry_point_metadata_names_exactly_one_alignment_panel() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["entry-points"]["vsview"] == {
        "frame-compare-alignment-review": "frame_compare.vsview.alignment_review_panel"
    }


def test_vsview_entry_point_registers_panel_through_pluggy() -> None:
    pytest.importorskip("vsview")
    import pluggy
    from vsview.app.plugins import specs

    entry_points = tuple(
        entry_point
        for entry_point in importlib.metadata.entry_points(group="vsview")
        if entry_point.name == "frame-compare-alignment-review"
    )
    assert len(entry_points) == 1

    manager = pluggy.PluginManager("vsview")
    manager.add_hookspecs(specs)
    manager.register(entry_points[0].load(), name=entry_points[0].name)

    from frame_compare.vsview.alignment_review_panel import AlignmentReviewPanel

    assert manager.hook.vsview_register_toolpanel() == [AlignmentReviewPanel]


def test_vsview_package_import_stays_lazy() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import frame_compare.vsview; "
            "assert 'vsview' not in sys.modules; assert 'PySide6' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
