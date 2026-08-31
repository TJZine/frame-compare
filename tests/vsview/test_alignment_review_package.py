from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path


def test_vsview_entry_point_registers_exactly_one_alignment_panel() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["entry-points"]["vsview"] == {
        "frame-compare-alignment-review": "frame_compare.vsview.alignment_review_panel"
    }


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
