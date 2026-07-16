"""Executable contracts for report-local review state and transfer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .node_harness import run_node_harness


@pytest.mark.unit
def test_review_state_harness_proves_schema_storage_and_atomic_import() -> None:
    harness = Path(__file__).with_name("review_state_harness.js")
    result = run_node_harness(harness, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary == {
        "records": 2,
        "exactRoundTrip": True,
        "atomicRollback": True,
        "boundaryCases": True,
    }


@pytest.mark.unit
def test_review_controller_harness_proves_preview_races_render_and_download() -> None:
    harness = Path(__file__).with_name("review_controller_harness.js")
    result = run_node_harness(harness, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "stalePreviewRefreshed": True,
        "replacementReadIsolated": True,
        "stableRender": True,
        "singleAnnouncements": True,
        "downloadLifecycle": True,
        "initialWarningsAnnouncedOnce": True,
    }
