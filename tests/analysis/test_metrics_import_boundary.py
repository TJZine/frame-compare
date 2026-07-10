"""Process-level tests for analysis import boundaries."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_metrics_imports_without_vapoursynth(repo_root: Path) -> None:
    script = """
import importlib.abc
import sys


class BlockVapourSynth(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "vapoursynth" or fullname.startswith("vapoursynth."):
            raise ModuleNotFoundError("vapoursynth blocked by import-boundary test")
        return None


sys.meta_path.insert(0, BlockVapourSynth())
import frame_compare.analysis.metrics
assert "vapoursynth" not in sys.modules
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
