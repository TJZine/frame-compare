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
    assert json.loads(result.stdout.strip().splitlines()[-1]) == {
        "canonicalStateShared": True,
        "zoomBounds": True,
        "pointerAnchor": True,
        "panClampAndGridConversion": True,
        "fitAndReset": True,
        "directionalAlignment": True,
        "revealAndRefresh": True,
        "storageDelegated": True,
    }


@pytest.mark.unit
def test_viewer_assets_have_deterministic_owner_assembly_order() -> None:
    assembled = get_js()
    assert assembled.index("const Viewport") < assembled.index("const ReportViewer")
