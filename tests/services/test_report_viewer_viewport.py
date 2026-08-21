"""Focused contracts for the report viewport owner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from frame_compare.services.report.viewer import get_js

from .node_harness import run_node_harness


@pytest.mark.unit
def test_viewport_harness_owns_coordinate_and_alignment_policy() -> None:
    result = run_node_harness(Path(__file__).with_name("viewport_harness.js"))

    assert result.returncode == 0, result.stdout + result.stderr
    assert all(json.loads(result.stdout.strip().splitlines()[-1]).values())


@pytest.mark.unit
def test_viewer_assets_have_one_viewport_owner_and_deterministic_order() -> None:
    assets = Path(__file__).parents[2] / "src/frame_compare/services/report/assets"
    viewport = (assets / "viewport.js").read_text(encoding="utf-8")
    viewer = (assets / "viewer.js").read_text(encoding="utf-8")

    assert "clampZoom(level)" in viewport
    assert "clampZoom(level)" not in viewer
    assert "pairAlignmentKey(leftIdx, rightIdx)" in viewport
    assert "pairAlignmentKey(leftIdx, rightIdx)" not in viewer
    assert "localStorage" not in viewport

    assembled = get_js()
    assert assembled.index("const Viewport") < assembled.index("const ReportViewer")
