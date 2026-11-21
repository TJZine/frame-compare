"""Focused contracts for the report viewport owner."""

from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.services.report.viewer import get_js

from .node_harness import assert_node_harness


@pytest.mark.unit
def test_viewport_harness_owns_coordinate_and_alignment_policy() -> None:
    assert_node_harness(Path(__file__).with_name("viewport_harness.js"))


@pytest.mark.unit
def test_viewer_assets_have_deterministic_owner_assembly_order() -> None:
    assembled = get_js()
    assert assembled.index("const Viewport") < assembled.index("const ReportViewer")
