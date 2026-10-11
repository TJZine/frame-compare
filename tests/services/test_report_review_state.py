"""Executable contracts for report-local review state and transfer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .node_harness import run_node_harness


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        pytest.param(
            "review_state_harness.js",
            {
                "records": 2,
                "exactRoundTrip": True,
                "atomicRollback": True,
                "boundaryCases": True,
            },
            id="review_state_harness.js",
        ),
        pytest.param(
            "review_controller_harness.js",
            {
                "stalePreviewRefreshed": True,
                "replacementReadIsolated": True,
                "stableRender": True,
                "singleAnnouncements": True,
                "downloadLifecycle": True,
                "initialWarningsAnnouncedOnce": True,
            },
            id="review_controller_harness.js",
        ),
    ],
)
def test_review_harness_contract(filename: str, expected: dict[str, int | bool]) -> None:
    result = run_node_harness(Path(__file__).with_name(filename), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == expected
