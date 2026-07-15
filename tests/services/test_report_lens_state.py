"""Executable geometry, behavior, and persistence contracts for the report lens."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pyright import node as pyright_node


@pytest.mark.unit
def test_lens_harness_proves_mapping_behavior_comparison_and_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Path(__file__).with_name("lens_harness.js")

    monkeypatch.setattr(pyright_node, "USE_NODEJS_WHEEL", True)
    monkeypatch.setattr(pyright_node, "USE_GLOBAL_NODE", False)
    monkeypatch.setattr(
        pyright_node,
        "_install_node_env",
        lambda: pytest.fail("lens harness must use preinstalled nodejs wheel"),
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
        "defaultsNormalized": True,
        "strictOptionsNormalized": True,
        "mappingAndClamping": True,
        "splitGeometry": True,
        "boundedPopover": True,
        "longIdentityCaptions": True,
        "diffCompositionAndAlignment": True,
        "staleContextReseeds": True,
        "immediateActivation": True,
        "stablePaletteAndFixedWindow": True,
        "fixedTouchSampling": True,
        "lostPointerCaptureRecovers": True,
        "touchDragReleasesWithoutSampling": True,
        "touchLayoutRefreshStable": True,
        "focusedDisableRestoresToggle": True,
        "programmaticDisablePreservesFocus": True,
        "cloneFailuresAreSourceMatched": True,
        "detachedLoadersAreIsolated": True,
        "detachedLoaderHandlersCleaned": True,
        "cloneSourceChangeRetries": True,
        "staleCloneCallbacksIgnored": True,
        "comparisonFallback": True,
        "unavailableComparisonClears": True,
        "comparisonSingleOnly": True,
        "clearTransientRetainsEnabled": True,
        "enabledAcrossContextChange": True,
        "reportPersistenceExcludesPointer": True,
        "storageFailureIsSessionOnly": True,
    }
