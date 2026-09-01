from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import step_by_name as _step_by_name
from tests.workflows._helpers import bash_executable_or_skip as _bash_executable_or_skip
from tests.workflows._helpers import bash_path_or_skip as _bash_path_or_skip

_SCRIPT_TIMEOUT_SECONDS = 10.0


def test_windows_portable_workflow_delegates_extracted_bundle_verification(
    repo_root: Path,
) -> None:
    path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _load_workflow(path)

    assert set(workflow["jobs"]) == {"build"}
    assert "permissions" not in workflow
    assert "permissions" not in workflow["jobs"]["build"]
    verify_step = _step_by_name(workflow["jobs"]["build"], "Verify extracted portable bundle")
    assert "tools/windows_portable/verify_extracted_bundle.ps1" in verify_step["run"]
    assert "-ZipPath dist/frame-compare-portable-win-x64.zip" in verify_step["run"]
    assert "-ExtractRoot dist/zip_extract_check" in verify_step["run"]
    assert verify_step["env"] == {"EXPECTED_SHA": "${{ inputs.expected_sha }}"}
    assert '-ExpectedCommitSha "$env:EXPECTED_SHA"' in verify_step["run"]
    assert "WINDOWS_EXTRACTED_PROOF license_inventory=ok" in verify_step["run"]
    assert "WINDOWS_EXTRACTED_PROOF vsview_distributions=ok" in verify_step["run"]
    assert (
        "WINDOWS_EXTRACTED_PROOF qt_webengine_runtime=absent deployment=excluded"
        in verify_step["run"]
    )
    assert "WINDOWS_EXTRACTED_PROOF result=ok" in verify_step["run"]
    assert "inputs.expected_sha" not in verify_step["run"]
    assert "-CommandTimeoutSeconds 300" in verify_step["run"]


def test_windows_portable_workflow_installs_native_vsview_extra(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable-build.yml")
    install_step = _step_by_name(workflow["jobs"]["build"], "Install dev dependencies (frozen)")

    assert install_step["run"] == "uv sync --all-groups --extra vsview --frozen"


def test_windows_portable_workflow_requires_native_alignment_package_proof(
    repo_root: Path,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable-build.yml")
    build_step = _step_by_name(workflow["jobs"]["build"], "Build portable bundle")
    for marker in (
        "project_entrypoint=ok source=app/src",
        "alignment_panel=ok state=inactive platform=offscreen",
        "alignment_metadata=ok outputs=Reference,Comparison_1",
        "alignment_result_roundtrip=ok",
        "alignment_result_validation=ok malformed=rejected",
    ):
        assert marker in build_step["run"]


def test_windows_portable_manual_verify_binds_exact_sha_to_selected_ref(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _load_workflow(workflow_path)
    validate = workflow["jobs"]["validate_manual"]
    verify = workflow["jobs"]["verify_manual"]
    step = validate["steps"][0]

    assert validate["permissions"] == {}
    assert "secrets" not in validate
    assert validate["outputs"] == {"expected_sha": "${{ steps.validate.outputs.expected_sha }}"}
    assert step["env"] == {
        "DISPATCH_REF_NAME": "${{ github.ref_name }}",
        "DISPATCH_REF_PROTECTED": "${{ github.ref_protected }}",
        "DISPATCH_REF_TYPE": "${{ github.ref_type }}",
        "DISPATCH_SHA": "${{ github.sha }}",
        "EXPECTED_SHA": "${{ inputs.expected_sha || github.sha }}",
    }
    assert verify["needs"] == "validate_manual"
    assert verify["with"]["expected_sha"] == ("${{ needs.validate_manual.outputs.expected_sha }}")
    assert verify["with"]["environment_name"] == (
        "${{ inputs.channel == 'stable' && 'production' || 'release-candidate' }}"
    )
    assert "secrets" not in verify


@pytest.mark.parametrize(
    ("expected_sha", "dispatch_sha", "ref_type", "ref_name", "protected", "succeeds"),
    [
        ("a" * 40, "a" * 40, "branch", "main", "true", True),
        ("b" * 40, "b" * 40, "tag", "v0.5.0", "true", True),
        ("c" * 40, "c" * 40, "tag", "v0.6.0-rc.1", "true", True),
        ("A" * 40, "A" * 40, "branch", "main", "true", False),
        ("a" * 40, "b" * 40, "branch", "main", "true", False),
        ("a" * 40, "a" * 40, "branch", "topic", "false", False),
        ("a" * 40, "a" * 40, "tag", "v0.5.0", "false", False),
        ("a" * 40, "a" * 40, "tag", "not-a-release", "true", False),
        ("a" * 40, "a" * 40, "pull_request", "1/merge", "false", False),
    ],
)
def test_windows_portable_manual_sha_validation_fails_closed(
    repo_root: Path,
    tmp_path: Path,
    expected_sha: str,
    dispatch_sha: str,
    ref_type: str,
    ref_name: str,
    protected: str,
    succeeds: bool,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable.yml")
    script = workflow["jobs"]["validate_manual"]["steps"][0]["run"]
    output = tmp_path / "github-output"
    bash = _bash_executable_or_skip()

    completed = subprocess.run(
        [bash, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=_SCRIPT_TIMEOUT_SECONDS,
        env=os.environ
        | {
            "DISPATCH_REF_NAME": ref_name,
            "DISPATCH_REF_PROTECTED": protected,
            "DISPATCH_REF_TYPE": ref_type,
            "DISPATCH_SHA": dispatch_sha,
            "EXPECTED_SHA": expected_sha,
            "GITHUB_OUTPUT": _bash_path_or_skip(bash, output),
        },
    )

    assert (completed.returncode == 0) is succeeds, completed.stderr
    assert output.exists() is succeeds
    if succeeds:
        assert output.read_text(encoding="utf-8") == f"expected_sha={expected_sha}\n"


def test_windows_portable_workflow_signing_and_uploads_fail_closed(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable-build.yml")
    build = workflow["jobs"]["build"]
    sign = _step_by_name(build, "Sign code-only update zip")
    verify = _step_by_name(build, "Verify code-only update zip layout")
    prepare = _step_by_name(build, "Prepare exact orchestrated release assets")
    attest = _step_by_name(build, "Attest release ZIP provenance")
    upload = _step_by_name(build, "Upload exact orchestrated release assets")

    assert set(workflow["on"]["workflow_call"]["inputs"]) == {
        "expected_sha",
        "release_tag",
        "require_signing",
        "environment_name",
        "prepare_release_assets",
    }
    assert "secrets" not in workflow["on"]["workflow_call"]
    assert build["environment"] == {"name": "${{ inputs.environment_name }}"}
    assert sign["if"] == "env.REQUIRE_SIGNING == 'true'"
    assert sign["env"]["WINDOWS_UPDATE_SIGNING_KEY_XML"] == (
        "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}"
    )
    assert "is required" in sign["run"]
    assert verify["env"]["REQUIRE_SIGNED_UPDATE"] == "${{ env.REQUIRE_SIGNING }}"
    assert "update-manifest.sig" in verify["run"]
    assert prepare["if"] == "inputs.prepare_release_assets"
    assert "Expected exactly one signed update zip" in prepare["run"]
    assert attest["if"] == "inputs.prepare_release_assets"
    assert attest["uses"] == "actions/attest@a1948c3f048ba23858d222213b7c278aabede763"
    assert attest["with"]["subject-path"] == (
        "dist/release-assets/frame-compare-portable-win-x64-${{ inputs.release_tag }}.zip\n"
        "dist/release-assets/frame-compare-update-win-x64-${{ inputs.release_tag }}.zip\n"
    )
    assert upload["if"] == "inputs.prepare_release_assets"
    assert upload["with"]["if-no-files-found"] == "error"


def test_windows_portable_release_checksum_paths_are_individual_powershell_values(
    repo_root: Path,
) -> None:
    source = (repo_root / ".github" / "workflows" / "windows-portable-build.yml").read_text(
        encoding="utf-8"
    )

    assert (
        "(Join-Path -Path $assetDir -ChildPath "
        '"frame-compare-portable-win-x64-$($env:RELEASE_TAG).zip.sha256")'
    ) in source
    assert (
        "(Join-Path -Path $assetDir -ChildPath "
        '"frame-compare-update-win-x64-$($env:RELEASE_TAG).zip.sha256")'
    ) in source
