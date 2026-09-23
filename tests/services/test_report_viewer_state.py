"""Executable viewer-state contract tests for the static report viewer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .node_harness import run_node_harness


@pytest.mark.unit
def test_viewer_state_harness_exercises_pair_scoped_alignment() -> None:
    harness = Path(__file__).with_name("viewer_state_harness.js")
    result = run_node_harness(harness)

    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout.strip().splitlines()[-1])

    assert (
        summary["viewerStorageKey"]
        == "frame-compare:report-viewer:report_viewer_state_contract:viewport"
    )
    assert summary["clipDisplayProfiles"] == {
        "requiredPayloadProfiles": True,
        "stableInspectorRoles": True,
    }

    restored = summary["restoreFourClip"]
    assert restored["clipCount"] == 4
    assert restored["leftClipIdx"] != restored["rightClipIdx"]
    assert restored["activeClipIdx"] == 3
    assert set(restored["restoredPairKeys"]) == {"0:1", "1:0"}
    assert restored["currentAlignment"] == [5, -2]

    pair_switch = summary["pairSwitchFourClip"]
    assert pair_switch["finalPair"] == "3:0"
    assert pair_switch["finalAlignment"] == [-21, 3]
    assert pair_switch["persistedAlignments"]["3:0"] == [-21, 3]
    assert set(pair_switch["persistedPairKeys"]) >= {"0:1", "0:2", "0:3", "2:0", "3:0"}

    assert summary["alignmentStatus"]["neutral"] == summary["alignmentStatus"]["reset"]
    assert summary["filmstripState"] == {
        "collapsed": False,
        "size": "compact",
        "collapsedClassRemoved": True,
    }
    assert summary["invalidFilmstripStateFallback"] == {
        "collapsed": False,
        "size": "normal",
        "stringBlinkIntervalFallback": 700,
    }

    inspector_state = summary["inspectorBlinkKeyboardState"]
    assert inspector_state["inspectorOpen"] is False
    assert inspector_state["inspectorTab"] == "clips"
    assert inspector_state["lensExcludedFromViewport"] is True
    assert inspector_state["rovingTabWrapped"] is True
    assert inspector_state["blinkPausedPersisted"] is False
    assert inspector_state["closedInspectorInert"] is True
    assert inspector_state["closedInspectorTabIndex"] == "-1"
    assert inspector_state["restoredKeyboardFocusToOrigin"] is True
    assert inspector_state["clearedKeyboardFocusRestoreTarget"] is True

    assert summary["escapeOrder"] == {
        "popoverHandlerPreventedGlobalShortcut": True,
        "alignmentClosedBeforeInspector": True,
        "legacyInfoModalWins": True,
        "inspectorStillOpenAfterAlignmentEscape": True,
    }
    assert summary["modalKeyboardAccessibility"] == {
        "helpFocusTrappedAndRestored": True,
        "infoFocusTrappedAndRestored": True,
    }
    assert summary["inspectorFrameSources"] == [
        "Clip 1 Shown left | 10 / 100 | B · DV RPU",
        "Clip 2 Shown right | 10 / 100 | B",
    ]
    assert summary["inspectorClipMetadata"] == {
        "heading": "Reference · shown left",
        "badge": "SDR",
        "standardName": "Clip 1",
        "fileName": "clip-1.mkv",
        "rows": [
            ["Picture", "1920×1080 · full frame"],
            ["Length", "100 frames · 0:00:04"],
            ["Size", "17.00 GiB"],
            ["Signal", "SDR · BT.709 / BT.709 / BT.2020c · Limited"],
        ],
    }
    assert summary["inspectorFrameIdentity"] == {
        "identity": "10 · Selected",
        "position": "1 / 2 in All",
        "defaultDetailHidden": True,
    }

    single_mode = summary["singleModeAlignment"]
    assert single_mode["mode"] == "overlay"
    assert single_mode["alignedComparisonActive"] is True
    assert single_mode["baseClipUnshifted"] is True
    assert single_mode["emptyStateClearsAlignment"] is True
    assert single_mode["emptyStateClearsLensTransient"] is True

    assert summary["blinkControls"]["reducedMotionPaused"] is True
    assert summary["blinkControls"]["intervalAfterSteps"] == 700
    assert summary["keyboardGuard"] == {
        "button": True,
        "textarea": True,
        "contentEditable": True,
        "nestedInButton": True,
        "plain": False,
    }
    assert summary["radioGroupKeyboard"] == {
        "wrapsAndSelects": True,
        "rovingTabStop": True,
        "preventsNativeScroll": True,
        "stopsGlobalShortcut": True,
    }
    assert summary["frameKeyboard"] == {
        "selectedNextFrame": True,
        "preventsNativeScroll": True,
    }
    assert summary["filmstripKeyboard"] == {
        "selectedNextFrame": True,
        "focusedSelection": True,
        "preventsNativeScroll": True,
        "stopsGlobalShortcut": True,
    }
    assert summary["directionalFourClip"]["swappedAlignment"] == [6, 7]
    assert summary["directionalFourClip"]["reversePairAlignment"] == [-6, -7]
    assert summary["paletteOrientationState"] == {
        "restoredOrientation": "vertical",
        "savedOrientation": "vertical",
    }
    assert summary["activeFilterBadge"]["badgeHiddenByDefault"] is True
    assert summary["activeFilterBadge"]["badgeClearedToHidden"] is True
    assert summary["sourceOverlayLabels"] == {
        "single": "Title.2160p.WEB-DL.Service-GROUP · 3840×2160 · HDR · 17.00 GiB",
        "slider": "Title.2160p.WEB-DL.Service-GROUP · 3840×2160 · HDR · 17.00 GiB",
        "diff": "Title.2160p.WEB-DL.Service-GROUP · 3840×2160 · HDR · 17.00 GiB",
    }
    assert summary["blinkLabels"] == {
        "labels": {
            "left": "Clip 1 · 1920×1080 · SDR · 17.00 GiB",
            "right": "Clip 2 · 1920×1080 · SDR · 17.00 GiB",
        },
        "activeLabelMoved": False,
        "activeStateMoved": True,
    }
    assert summary["lensPanIndependence"] == {
        "panAppliedWithoutInspectorGestureGate": True,
        "panMovedRecorded": True,
        "touchLensTapDidNotCycle": True,
    }
    assert summary["lensLayoutRefresh"] == {
        "touchPanPreservedSample": True,
        "pinchZoomPreservedSample": True,
        "alignmentPreservedSample": True,
        "contextSyncNotUsed": True,
    }
    assert summary["deferredTouchOwnership"] == {
        "sliderRetainsRevealDrag": True,
        "allPanModesRetainPanDrag": True,
        "viewerChromeRecognized": True,
        "chromeWheelAndDoubleClickIsolated": True,
    }
    assert summary["gridModeBoundary"] == {
        "publicPayloadRejected": True,
        "internalStoredModeRestored": True,
    }
    assert summary["lazyReviewController"] == {
        "opensOnFirstVisibleUse": True,
        "createsOnce": True,
    }
    assert summary["restoredWidthFitNoVisibleRadio"] == {
        "fitModeRestored": True,
        "zoomUsedWidthMath": True,
        "noRadioChecked": True,
        "exactlyOneKeyboardReachable": True,
    }
    assert summary["gridShortcut"] == {
        "lowerSelectsGrid": True,
        "upperSelectsGrid": True,
    }
    assert summary["proximityStateMachine"] == {
        "thresholds": True,
        "hysteresis": True,
        "overrides": True,
    }
    assert summary["paletteProximityWiring"] == {
        "startsNear": True,
        "loadOverride": True,
        "farWhenDistant": True,
        "hysteresisHoldsFar": True,
        "nearWhenClose": True,
        "dragOverride": True,
        "alignPopoverOverride": True,
        "lensPopoverOverride": True,
        "pointerLeaveSetsFar": True,
        "coarseStaysNear": True,
        "coarseLeaveStaysNear": True,
        "mediaInitFine": True,
        "mediaChangeGates": True,
        "loadHoldsNear": True,
        "loadExpiryRecomputes": True,
        "rafDefers": True,
        "leaveCancelsQueuedFrame": True,
        "rafFlushApplies": True,
        "nanHoldsFar": True,
        "reinitCancelsQueuedFrame": True,
    }
