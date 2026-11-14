"""Executable contracts for report-local review state and transfer."""

from pathlib import Path

import pytest

from .node_harness import assert_node_harness


@pytest.mark.unit
@pytest.mark.parametrize("filename", ["review_state_harness.js", "review_controller_harness.js"])
def test_review_harness_contract(filename: str) -> None:
    assert_node_harness(Path(__file__).with_name(filename), timeout=30)
