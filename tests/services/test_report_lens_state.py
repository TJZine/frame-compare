"""Executable geometry, behavior, and persistence contracts for the report lens."""

from __future__ import annotations

from pathlib import Path

import pytest

from .node_harness import assert_node_harness


@pytest.mark.unit
def test_lens_harness_proves_mapping_behavior_comparison_and_storage() -> None:
    assert_node_harness(Path(__file__).with_name("lens_harness.js"))
