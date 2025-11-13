from __future__ import annotations

import frame_compare as fc

EXPECTED_EXPORTS = (
    "run_cli",
    "main",
    "RunRequest",
    "RunResult",
    "CLIAppError",
    "ScreenshotError",
    "resolve_tmdb_workflow",
    "TMDBLookupResult",
    "render_collection_name",
    "prepare_preflight",
    "resolve_workspace_root",
    "PreflightResult",
    "collect_path_diagnostics",
    "collect_doctor_checks",
    "emit_doctor_results",
    "DoctorCheck",
    "vs_core",
)


def test_public_surface_matches_curated_exports() -> None:
    assert hasattr(fc, "__all__")
    assert tuple(fc.__all__) == EXPECTED_EXPORTS


def test_curated_exports_are_available_without_privates() -> None:
    for name in EXPECTED_EXPORTS:
        assert hasattr(fc, name), f"{name} missing from module globals"
    assert all(not name.startswith("_") for name in fc.__all__)


def test_importing_core_types_and_vs_alias() -> None:
    from frame_compare import RunRequest, RunResult, vs_core

    assert RunRequest is fc.RunRequest
    assert RunResult is fc.RunResult
    assert hasattr(vs_core, "VerificationResult")
