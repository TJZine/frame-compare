"""Executable layout and paging contracts for the report Grid owner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .node_harness import run_node_harness


@pytest.mark.unit
def test_grid_view_harness_proves_layout_paging_and_mount_limits() -> None:
    harness = Path(__file__).with_name("grid_view_harness.js")
    result = run_node_harness(harness)

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == {
        "layouts": ["two", "three-wide", "three-wrap", "four", "mobile"],
        "desktopPageLimit": 4,
        "desktopPages": [[0, 1, 2, 3], [4, 5]],
        "mobilePageLimit": 1,
        "payloadOrderPreserved": True,
        "realOwnerLifecycle": True,
        "staleEventsIgnored": True,
        "retryState": True,
        "allFailedRecoverable": True,
        "normalizedMixedAspectViewport": True,
        "focusRetainedAcrossRenderAndReflow": True,
        "referenceAndActiveCues": True,
    }
