from __future__ import annotations

from pathlib import Path

from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import step_by_name as _step_by_name


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
    assert "WINDOWS_EXTRACTED_PROOF result=ok" in verify_step["run"]
    assert "inputs.expected_sha" not in verify_step["run"]
    assert "-CommandTimeoutSeconds 300" in verify_step["run"]


def test_windows_portable_workflow_signing_and_uploads_fail_closed(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable-build.yml")
    build = workflow["jobs"]["build"]
    sign = _step_by_name(build, "Sign code-only update zip")
    verify = _step_by_name(build, "Verify code-only update zip layout")
    prepare = _step_by_name(build, "Prepare exact orchestrated release assets")
    attest = _step_by_name(build, "Attest release ZIP provenance")
    upload = _step_by_name(build, "Upload exact orchestrated release assets")

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
