"""Executable viewer-state contract tests for the static report viewer."""

from __future__ import annotations

from pathlib import Path

import pytest

from .node_harness import assert_node_harness


@pytest.mark.unit
def test_viewer_state_harness_exercises_pair_scoped_alignment() -> None:
    assert_node_harness(Path(__file__).with_name("viewer_state_harness.js"))
