"""Executable layout and paging contracts for the report Grid owner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pyright import node as pyright_node


@pytest.mark.unit
def test_grid_view_harness_proves_layout_paging_and_mount_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Path(__file__).with_name("grid_view_harness.js")

    monkeypatch.setattr(pyright_node, "USE_NODEJS_WHEEL", True)
    monkeypatch.setattr(pyright_node, "USE_GLOBAL_NODE", False)
    monkeypatch.setattr(
        pyright_node,
        "_install_node_env",
        lambda: pytest.fail("grid-view harness must use preinstalled nodejs wheel"),
    )
    result = pyright_node.run(
        "node",
        str(harness),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

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
