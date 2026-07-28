from __future__ import annotations

import re
from pathlib import Path

from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import step_by_name as _step_by_name

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_workflow_does_not_flatten_zip_contents(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    wf = _read_text_or_fail(wf_path)
    assert not re.search(r"Compress-Archive\s+-Path\s+['\"]?\$bundle/\*['\"]?", wf)


def test_windows_portable_workflow_zips_bundle_folder(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    wf = _read_text_or_fail(wf_path)
    assert re.search(r"Compress-Archive\s+-Path\s+\$bundle\b\s+-DestinationPath\s+\$zip\b", wf)


def test_windows_portable_workflow_verifies_zip_required_entries(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    wf = _read_text_or_fail(wf_path)
    required = [
        "frame-compare-portable-win-x64/install.cmd",
        "frame-compare-portable-win-x64/install.ps1",
        "frame-compare-portable-win-x64/frame-compare.ps1",
        "frame-compare-portable-win-x64/frame-compare-update.cmd",
        "frame-compare-portable-win-x64/shim/frame-compare.cmd",
        "frame-compare-portable-win-x64/shim/frame-compare-update.cmd",
        "frame-compare-portable-win-x64/frame-compare-update.ps1",
        "frame-compare-portable-win-x64/shim/frame-compare-update.ps1",
    ]
    for entry in required:
        assert entry in wf


def test_windows_portable_workflow_enables_public_key_gate_only_when_signing_required(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)
    release_gate = re.search(
        r'if\s*\(\$env:REQUIRE_SIGNING\s*-eq\s*"true"\)'
        r"\s*\{[\s\S]*?\$buildArgs\s*\+=\s*\"-RequireReleasePublicKey\"",
        workflow,
    )
    assert release_gate is not None
    assert "REQUIRE_SIGNING: ${{ inputs.require_signing }}" in workflow
    assert "require_signing:" in workflow


def test_windows_portable_workflow_verifies_workspace_directories(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)
    assert re.search(r'\$bundleConfigDir\s*=\s*Join-Path\s+\$bundle\s+"config"', workflow)
    assert re.search(
        r'\$bundleInputDir\s*=\s*Join-Path\s+\$bundle\s+"comparison_videos"',
        workflow,
    )
    assert re.search(
        r"Test-Path\s+-LiteralPath\s+\$bundleConfigDir\s+-PathType\s+Container",
        workflow,
    )
    assert re.search(
        r"Test-Path\s+-LiteralPath\s+\$bundleInputDir\s+-PathType\s+Container",
        workflow,
    )
    assert 'throw "Missing default workspace directory in bundle:' in workflow


def test_windows_portable_workflow_proves_r76_plugin_layout_and_runtime(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Setup Python 3.13.13" in workflow
    assert "app/site-packages/vapoursynth/plugins" in workflow
    assert "vs/extra-plugins" in workflow
    assert "lsmas/manifest.vs" in workflow
    assert "tools/windows_portable/build_portable.ps1" in workflow
    assert "Smoke: VS clip + tonemap does not raise" not in workflow
    assert "WINDOWS_WORKFLOW_PROOF" not in workflow


def test_windows_portable_workflow_validates_update_public_key_when_signing(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)
    assert "Validate update public key" in workflow
    assert "tools/windows_portable/update_public_key.xml" in workflow.replace("\\", "/")
    assert re.search(r"if:\s*env\.REQUIRE_SIGNING\s*==\s*'true'", workflow)


def test_windows_portable_workflow_prepares_exact_versioned_release_assets(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Prepare exact orchestrated release assets" in workflow
    assert "Verify exact orchestrated release asset set" in workflow
    assert "Upload exact orchestrated release assets" in workflow
    assert "inputs.prepare_release_assets" in workflow
    assert "^v\\d+\\.\\d+\\.\\d+(?:-rc\\.\\d+)?$" in workflow
    assert (
        "dist/release-assets/frame-compare-portable-win-x64-${{ "
        "inputs.release_tag }}.zip"
    ) in workflow
    assert (
        "dist/release-assets/frame-compare-portable-win-x64-${{ "
        "inputs.release_tag }}.zip.sha256"
    ) in workflow
    assert "Orchestrated release assets do not match the exact mandatory set." in workflow
    assert "Checksum mismatch for $assetPath" in workflow


def test_windows_portable_workflow_smokes_extracted_install_shim(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Smoke: extracted install shim" in workflow
    assert "dist/zip_extract_check/frame-compare-portable-win-x64" in workflow
    assert '& "$bundle/install.cmd"' in workflow
    assert "Programs/FrameCompare/bin/frame-compare.cmd" in workflow
    assert "& $shim version" in workflow
    assert 'versionOutput -notmatch "^frame-compare \\d+\\.\\d+\\.\\d+"' in workflow
    assert "& $shim --help" in workflow


def test_windows_portable_workflow_builds_code_only_update_after_bundle(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert workflow.index("Smoke: extracted install shim") < workflow.index(
        "Build code-only update zip"
    )
    assert workflow.index("Build code-only update zip") < workflow.index("Upload bundle artifact")
    assert "tools/windows_portable/build_update.ps1" in workflow
    assert "$PSNativeCommandUseErrorActionPreference = $true" in workflow
    assert '$bundle = "dist/frame-compare-portable-win-x64"' in workflow
    assert "frame-compare-update-win-x64-$version.zip" in workflow
    assert "-BundleDir $bundle" in workflow
    assert "-OutFile $updateZip" in workflow
    assert "UPDATE_ZIP=$updateZip" in workflow


def test_windows_portable_workflow_requires_signing_for_release_like_events(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    source = _read_text_or_fail(workflow_path)
    workflow = _load_workflow(workflow_path)
    sign_update_step = _step_by_name(workflow["jobs"]["build"], "Sign code-only update zip")
    sign_update_run = sign_update_step["run"]

    assert "Pull requests prove unsigned update zip creation without signing secrets." in source
    assert "Reusable release and manual runs require a signed update and fail closed" in source
    assert sign_update_step["if"] == "env.REQUIRE_SIGNING == 'true'"
    assert sign_update_step["env"]["WINDOWS_UPDATE_SIGNING_KEY_XML"] == (
        "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}"
    )
    assert (
        "WINDOWS_UPDATE_SIGNING_KEY_XML is required for reusable release and manual runs."
        in sign_update_run
    )
    assert "$env:SIGNING_KEY_XML_PATH = $keyPath" in sign_update_run
    assert "tools/windows_portable/sign_update.ps1" in sign_update_run
    assert "-UpdateZip $env:UPDATE_ZIP" in sign_update_run
    assert "pull_request" not in sign_update_step["if"]
    assert "exit 0" not in sign_update_run
    assert "signed=false" not in sign_update_run
    assert "signed=true" not in sign_update_run
    assert "update_signed" not in source


def test_windows_portable_workflow_verifies_and_uploads_update_artifact(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Hash code-only update zip" in workflow
    assert "Verify code-only update zip layout" in workflow
    assert "update-manifest.json" in workflow
    assert "payload/app/src/frame_compare/" in workflow
    assert 'target_platform -ne "windows-x64"' in workflow
    assert 'payload_root -ne "payload"' in workflow
    assert 'signature_file -ne "update-manifest.sig"' in workflow
    assert (
        "REQUIRE_SIGNED_UPDATE: ${{ env.REQUIRE_SIGNING }}"
    ) in workflow
    assert "Signed update zip is missing update-manifest.sig." in workflow
    assert "Upload code-only update artifact" in workflow
    assert "name: frame-compare-update-win-x64" in workflow
    assert "dist/frame-compare-update-win-x64-*.zip" in workflow
    assert "dist/frame-compare-update-win-x64-*.zip.sha256" in workflow


def test_windows_portable_workflow_requires_signed_update_release_assets(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _load_workflow(workflow_path)
    build = workflow["jobs"]["build"]
    upload_bundle = _step_by_name(build, "Upload bundle artifact")
    upload_update = _step_by_name(build, "Upload code-only update artifact")
    prepare = _step_by_name(build, "Prepare exact orchestrated release assets")
    verify_assets = _step_by_name(build, "Verify exact orchestrated release asset set")
    upload = _step_by_name(build, "Upload exact orchestrated release assets")

    assert set(workflow["jobs"]) == {"build"}
    assert prepare["if"] == "inputs.prepare_release_assets"
    assert verify_assets["if"] == "inputs.prepare_release_assets"
    assert upload["if"] == "inputs.prepare_release_assets"
    assert upload_bundle["with"]["if-no-files-found"] == "error"
    assert upload_update["with"]["if-no-files-found"] == "error"
    assert "Expected exactly one signed update zip" in prepare["run"]
    assert "frame-compare-update-win-x64-$($env:RELEASE_TAG).zip" in prepare["run"]
    assert "exact mandatory set" in verify_assets["run"]
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["name"] == "frame-compare-release-assets"
    assert (
        "dist/release-assets/frame-compare-update-win-x64-${{ "
        "inputs.release_tag }}.zip"
    ) in upload["with"]["path"]
    assert (
        "dist/release-assets/frame-compare-update-win-x64-${{ "
        "inputs.release_tag }}.zip.sha256"
    ) in upload["with"]["path"]
