"""Smoke tests for orchestration module imports.

Verifies that the orchestration package and submodules are importable
without errors or side effects.
"""

import importlib


def test_orchestration_modules_importable() -> None:
    """Verify all orchestration modules import without errors.

    This test ensures the orchestration package scaffold is correctly
    structured and all submodules can be imported.
    """
    # Top-level package
    orchestration = importlib.import_module("frame_compare.orchestration")
    assert orchestration is not None

    # Submodules
    preflight = importlib.import_module("frame_compare.orchestration.preflight")
    assert preflight is not None

    doctor = importlib.import_module("frame_compare.orchestration.doctor")
    assert doctor is not None

    progress = importlib.import_module("frame_compare.orchestration.progress")
    assert progress is not None

    phases = importlib.import_module("frame_compare.orchestration.phases")
    assert phases is not None
