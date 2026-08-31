"""Tests for package-root import surface policy."""

import importlib
import sys

import pytest

NAMESPACE_ROOTS = (
    "frame_compare.analysis",
    "frame_compare.cli",
    "frame_compare.config",
    "frame_compare.orchestration.probing",
    "frame_compare.render",
    "frame_compare.render.batch",
    "frame_compare.render.backend",
    "frame_compare.services",
    "frame_compare.services.report",
    "frame_compare.utils",
    "frame_compare.vsview",
)

ORCHESTRATION_EXPORTS = (
    "CheckResult",
    "DoctorCheck",
    "DoctorReport",
    "RunDependencies",
    "RunRequest",
    "RunResult",
    "execute_run",
    "run_doctor",
)


def test_root_package_exports_only_version() -> None:
    frame_compare = importlib.import_module("frame_compare")

    assert frame_compare.__all__ == ["__version__"]
    assert isinstance(frame_compare.__version__, str)


@pytest.mark.parametrize("module_name", NAMESPACE_ROOTS)
def test_namespace_roots_do_not_export_facade_symbols(module_name: str) -> None:
    module = importlib.import_module(module_name)

    assert module.__all__ == []


def test_orchestration_curated_facade_export_set() -> None:
    orchestration = importlib.import_module("frame_compare.orchestration")

    assert orchestration.__all__ == ORCHESTRATION_EXPORTS


def test_orchestration_import_does_not_load_facade_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for module_name in list(sys.modules):
        if module_name.startswith("frame_compare.orchestration"):
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    importlib.import_module("frame_compare.orchestration")

    assert "frame_compare.orchestration" in sys.modules
    assert "frame_compare.orchestration.coordinator" not in sys.modules
    assert "frame_compare.orchestration.doctor" not in sys.modules
