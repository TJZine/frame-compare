"""Focused contracts for the report Inspector and formatting owners."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from frame_compare.services.report.viewer import get_js

from .node_harness import run_node_harness


@pytest.mark.unit
def test_inspector_harness_owns_formatting_and_inspector_policy() -> None:
    result = run_node_harness(Path(__file__).with_name("inspector_harness.js"))

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == {
        "pureFormattingOwner": True,
        "focusedInspectorOwner": True,
        "safeSlowpicsBoundary": True,
    }


@pytest.mark.unit
def test_viewer_assets_have_one_inspector_owner_and_deterministic_order() -> None:
    assets = Path(__file__).parents[2] / "src" / "frame_compare" / "services" / "report" / "assets"
    viewer_format = (assets / "viewer_format.js").read_text(encoding="utf-8")
    inspector = (assets / "inspector.js").read_text(encoding="utf-8")
    viewer = (assets / "viewer.js").read_text(encoding="utf-8")

    assert "document" not in viewer_format
    assert "localStorage" not in viewer_format
    assert "renderSlowpics()" in inspector
    assert "const slowpicsUrl" not in viewer
    assert "rv-inspector-clip-heading" in inspector
    assert "rv-inspector-clip-heading" not in viewer

    assembled = get_js()
    assert assembled.index("const ViewerFormat") < assembled.index("const Inspector")
    assert assembled.index("const Inspector") < assembled.index("const ReportViewer")
