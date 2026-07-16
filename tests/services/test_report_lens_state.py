"""Executable geometry, behavior, and persistence contracts for the report lens."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .node_harness import run_node_harness


@pytest.mark.unit
def test_lens_harness_proves_mapping_behavior_comparison_and_storage() -> None:
    harness = Path(__file__).with_name("lens_harness.js")
    result = run_node_harness(harness)

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
        "clearTransientRestoresVisibleFocus": True,
        "clearTransientClosesPopover": True,
        "clearTransientPreservesExternalFocus": True,
        "clearTransientPreservesPaletteFocus": True,
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
