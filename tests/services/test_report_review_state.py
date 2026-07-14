"""Executable contracts for report-local review state and transfer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pyright import node as pyright_node


@pytest.mark.unit
def test_review_state_harness_proves_schema_storage_and_atomic_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Path(__file__).with_name("review_state_harness.js")
    monkeypatch.setattr(pyright_node, "USE_NODEJS_WHEEL", True)
    monkeypatch.setattr(pyright_node, "USE_GLOBAL_NODE", False)
    monkeypatch.setattr(
        pyright_node,
        "_install_node_env",
        lambda: pytest.fail("review-state harness must use preinstalled nodejs wheel"),
    )
    result = pyright_node.run(
        "node",
        str(harness),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary == {
        "records": 2,
        "exactRoundTrip": True,
        "atomicRollback": True,
        "boundaryCases": True,
    }


@pytest.mark.unit
def test_review_controller_harness_proves_preview_races_render_and_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Path(__file__).with_name("review_controller_harness.js")
    monkeypatch.setattr(pyright_node, "USE_NODEJS_WHEEL", True)
    monkeypatch.setattr(pyright_node, "USE_GLOBAL_NODE", False)
    monkeypatch.setattr(
        pyright_node,
        "_install_node_env",
        lambda: pytest.fail("review controller harness must use preinstalled nodejs wheel"),
    )
    result = pyright_node.run(
        "node",
        str(harness),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "stalePreviewRefreshed": True,
        "replacementReadIsolated": True,
        "stableRender": True,
        "singleAnnouncements": True,
        "downloadLifecycle": True,
        "initialWarningsAnnouncedOnce": True,
    }
