"""Executable viewer-state contract tests for the static report viewer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pyright import node as pyright_node


@pytest.mark.unit
def test_viewer_state_harness_exercises_pair_scoped_alignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Path(__file__).with_name("viewer_state_harness.js")

    monkeypatch.setattr(pyright_node, "USE_NODEJS_WHEEL", True)
    monkeypatch.setattr(pyright_node, "USE_GLOBAL_NODE", False)
    monkeypatch.setattr(
        pyright_node,
        "_install_node_env",
        lambda: pytest.fail("viewer-state harness must use preinstalled nodejs wheel"),
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
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    assert summary == {
        "restoreFourClip": {
            "clipCount": 4,
            "leftClipIdx": 0,
            "rightClipIdx": 1,
            "activeClipIdx": 3,
            "restoredPairKeys": ["0:1", "1:0"],
            "currentAlignment": [5, -2],
        },
        "pairSwitchFourClip": {
            "finalPair": "3:0",
            "finalAlignment": [-21, 3],
            "persistedPairKeys": ["0:1", "0:2", "0:3", "2:0", "3:0"],
            "persistedAlignments": {
                "0:1": [4, 5],
                "0:2": [-1, 8],
                "0:3": [21, -3],
                "2:0": [12, 13],
                "3:0": [-21, 3],
            },
        },
        "directionalFourClip": {
            "swappedPair": "0:1",
            "swappedAlignment": [6, 7],
            "reversePairAlignment": [-6, -7],
        },
    }
