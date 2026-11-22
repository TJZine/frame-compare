from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import step_by_name as _step_by_name


def _build_action(repo_root: Path) -> dict[str, Any]:
    return _load_workflow(repo_root / ".github/actions/windows-portable-build/action.yml")["runs"]


def test_windows_portable_workflow_installs_native_vsview_extra(repo_root: Path) -> None:
    install_step = _step_by_name(_build_action(repo_root), "Install dev dependencies (frozen)")

    assert (
        "uv sync --all-groups --extra vsview --frozen --no-build --no-install-package anitopy"
        in (install_step["run"])
    )
    assert "portable_runtime.py anitopy-wheel" in install_step["run"]
    assert (
        "uv --offline --no-config pip install --no-index --no-deps --no-build"
        in (install_step["run"])
    )


def test_windows_portable_workflow_requires_native_alignment_package_proof(
    repo_root: Path,
) -> None:
    build_step = _step_by_name(_build_action(repo_root), "Build portable bundle")
    for marker in (
        "project_entrypoint=ok source=app/src",
        "alignment_panel=ok state=inactive platform=offscreen",
        "alignment_metadata=ok outputs=Reference,Comparison_1",
        "alignment_result_roundtrip=ok",
        "alignment_result_validation=ok malformed=rejected",
    ):
        assert marker in build_step["run"]


def test_windows_workflow_scans_the_raw_producer_zip(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github/workflows/windows-portable.yml")
    assert set(workflow["on"]) == {"pull_request", "workflow_call"}
    assert workflow["on"]["pull_request"] == ""
    assert workflow["on"]["workflow_call"]["inputs"]["sha"]["required"] == "true"
    assert workflow["on"]["workflow_call"]["inputs"]["release_build"]["type"] == "boolean"
    assert workflow["permissions"] == {}
    assert (
        workflow["env"]["EXPECTED_SHA"]
        == "${{ inputs.sha || (github.event_name == 'pull_request' && github.sha) }}"
    )
    build, scanner = (workflow["jobs"][job] for job in ("build_test", "artifact_security"))
    assert build["runs-on"] == "windows-latest"
    assert scanner["runs-on"] == "ubuntu-24.04"
    assert scanner["needs"] == "build_test"
    for job in (build, scanner):
        assert job["permissions"] == {"contents": "read"}
        checkout = _step_by_name(job, "Checkout exact source")
        assert checkout["with"]["ref"] == "${{ env.EXPECTED_SHA }}"
        assert checkout["with"]["persist-credentials"] == "false"
        assert "git rev-parse HEAD" in _step_by_name(job, "Verify exact checkout")["run"]
    assert _step_by_name(build, "Build and exercise Windows portable inputs")["with"] == {
        "expected_sha": "${{ env.EXPECTED_SHA }}",
        "release_build": "${{ inputs.release_build }}",
    }

    upload = _step_by_name(_build_action(repo_root), "Upload raw portable ZIP")
    assert upload["with"] == {
        "name": "frame-compare-portable-win-x64.zip",
        "path": "dist/frame-compare-portable-win-x64.zip",
        "archive": "false",
        "if-no-files-found": "error",
    }
    outputs = workflow["on"]["workflow_call"]["outputs"]
    assert outputs["bundle_id"]["value"] == "${{ jobs.build_test.outputs.bundle_id }}"
    assert outputs["bundle_digest"]["value"] == "${{ jobs.build_test.outputs.bundle_digest }}"
    download = _step_by_name(scanner, "Download exact portable ZIP")
    assert download["with"]["skip-decompress"] == "true"
    assert download["with"]["digest-mismatch"] == "error"
    assert download["with"]["artifact-ids"] == "${{ needs.build_test.outputs.bundle_id }}"
    stage = _step_by_name(scanner, "Verify producer digest and safely stage the portable tree")
    assert stage["env"]["BUNDLE_DIGEST"] == "${{ needs.build_test.outputs.bundle_digest }}"
    assert stage["env"]["BUNDLE_ID"] == download["with"]["artifact-ids"]
    for argument in (
        '--expected-digest "$BUNDLE_DIGEST"',
        '--expected-sha "$EXPECTED_SHA"',
        '--expected-artifact-id "$BUNDLE_ID"',
    ):
        assert argument in stage["run"]
    pins = _step_by_name(scanner, "Install checksum-pinned scanners")["run"]
    assert "syft_1.57.1_linux_amd64.tar.gz" in pins
    assert "grype_0.121.3_linux_amd64.tar.gz" in pins
    assert pins.count("sha256sum --check") == 2
    policy = _step_by_name(scanner, "Generate SBOMs and unsuppressed advisory evidence")
    assert policy["env"]["GRYPE_DB_MAX_ALLOWED_BUILT_AGE"] == "120h"
    for field in (
        "GRYPE_DB_REQUIRE_UPDATE_CHECK",
        "GRYPE_DB_VALIDATE_AGE",
        "GRYPE_DB_VALIDATE_BY_HASH_ON_START",
    ):
        assert policy["env"][field] == "true"
    assert "artifact_security.py policy" in policy["run"]
    assert "cyclonedx-json=" in policy["run"]
    assert (
        _step_by_name(scanner, "Retain final-artifact security evidence")["with"]["retention-days"]
        == "90"
    )


def test_windows_workflow_runs_lifecycle_after_packing_and_before_upload(repo_root: Path) -> None:
    action = _build_action(repo_root)
    names = [step["name"] for step in action["steps"]]
    assert names.index("Full test suite") < names.index("Package zip")
    assert (
        names.index("Package zip")
        < names.index("Test packed ZIP succession")
        < names.index("Upload raw portable ZIP")
    )
    assert (
        " --ignore=tests/windows_portable/test_windows_portable_zip_succession.py"
        in (_step_by_name(action, "Full test suite")["run"])
    )
    succession = _step_by_name(action, "Test packed ZIP succession")["run"]
    assert "FRAME_COMPARE_TEST_PORTABLE_ZIP" in succession
    assert "pytest -q -rs -s" in succession
    assert "[int]$suite.tests -ne 8 -or [int]$suite.skipped -ne 0" in succession
    assert "$($suite.tests) passed, $($suite.skipped) skipped" in succession
    smoke = _step_by_name(action, "Smoke: absolute candidate launcher")["run"]
    assert '$versionOutput[0] -cne "frame-compare $expectedVersion"' in smoke
    assert "& $launcher doctor --json" in smoke
    assert "-ReleaseBuild" in _step_by_name(action, "Build portable bundle")["run"]


def test_windows_build_requires_current_manifest_from_exact_checkout_before_setup(
    repo_root: Path,
) -> None:
    action = _build_action(repo_root)
    gate = _step_by_name(action, "Require current portable manifest")
    assert action["steps"][0] == gate
    assert "if" not in gate
    assert gate["env"] == {"EXPECTED_SHA": "${{ inputs.expected_sha }}"}
    assert (
        'git show "${env:EXPECTED_SHA}:tools/windows_portable/manifest.windows-x64.json"'
        in gate["run"]
    )
    assert "$version -ne 3" in gate["run"]
    assert "Hosted Windows portable builds require manifest version 3." in gate["run"]
