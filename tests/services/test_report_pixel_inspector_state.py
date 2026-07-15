"""Executable coordinate and sampling contracts for the report pixel inspector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pyright import node as pyright_node


@pytest.mark.unit
def test_pixel_inspector_harness_proves_mapping_sampling_and_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Path(__file__).with_name("pixel_inspector_harness.js")

    monkeypatch.setattr(pyright_node, "USE_NODEJS_WHEEL", True)
    monkeypatch.setattr(pyright_node, "USE_GLOBAL_NODE", False)
    monkeypatch.setattr(
        pyright_node,
        "_install_node_env",
        lambda: pytest.fail("pixel-inspector harness must use preinstalled nodejs wheel"),
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
        "equalDimensions": True,
        "mismatchedDimensions": True,
        "renderedBoxBounds": True,
        "anchors": ["slider-left", "slider-right", "single", "diff", "blink", "grid-cell"],
        "gestureThreshold": 6,
        "decodedPixelLensGeometry": True,
        "blinkForwardPlacement": True,
        "composedGestureThreshold": True,
        "contextTimerCancelled": True,
        "directRoiCancelPreservedPoint": True,
        "pagedGridDragRetainedAnchor": True,
        "nudgeBounds": True,
        "inactiveUiCleared": True,
        "samplerRecoveredAfterTaint": True,
        "unavailableSampling": True,
        "staleStateCleared": True,
    }
