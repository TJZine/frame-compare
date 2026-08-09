from __future__ import annotations

from pathlib import Path

from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import step_by_name as _step_by_name


def test_windows_portable_workflow_delegates_extracted_bundle_verification(
    repo_root: Path,
) -> None:
    path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _load_workflow(path)
    source = path.read_text(encoding="utf-8")
    verifier_source = (
        repo_root / "tools" / "windows_portable" / "verify_extracted_bundle.ps1"
    ).read_text(encoding="utf-8")

    assert set(workflow["jobs"]) == {"build"}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["build"]["permissions"] == {"contents": "read"}
    verify_step = _step_by_name(workflow["jobs"]["build"], "Verify extracted portable bundle")
    assert "tools/windows_portable/verify_extracted_bundle.ps1" in verify_step["run"]
    assert "-ZipPath dist/frame-compare-portable-win-x64.zip" in verify_step["run"]
    assert "-ExtractRoot dist/zip_extract_check" in verify_step["run"]
    assert "-ExpectedCommitSha ${{ inputs.expected_sha }}" in verify_step["run"]
    for required_path in (
        "frame-compare-portable-win-x64/install.cmd",
        "frame-compare-portable-win-x64/install.ps1",
        "frame-compare-portable-win-x64/frame-compare.ps1",
        "frame-compare-portable-win-x64/frame-compare-update.ps1",
    ):
        assert required_path in verifier_source
    for selector in (
        "& $candidateLauncher --help",
        "& $candidateLauncher version",
        "& $candidateLauncher doctor --json",
        "& $installer",
        "& $installedShim version",
        "& $installedShim --help",
    ):
        assert selector in verifier_source
    assert "dist/frame-compare-portable-win-x64" in source
    assert (
        "dist/release-assets/frame-compare-update-win-x64-${{ inputs.release_tag }}.zip" in source
    )


def test_windows_portable_workflow_signing_and_uploads_fail_closed(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable-build.yml")
    build = workflow["jobs"]["build"]
    sign = _step_by_name(build, "Sign code-only update zip")
    verify = _step_by_name(build, "Verify code-only update zip layout")
    prepare = _step_by_name(build, "Prepare exact orchestrated release assets")
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
