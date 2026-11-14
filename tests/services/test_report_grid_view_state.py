"""Executable layout and paging contracts for the report Grid owner."""

from __future__ import annotations

from pathlib import Path

import pytest

from .node_harness import assert_node_harness


@pytest.mark.unit
def test_grid_view_harness_proves_layout_paging_and_mount_limits() -> None:
    assert_node_harness(Path(__file__).with_name("grid_view_harness.js"))
