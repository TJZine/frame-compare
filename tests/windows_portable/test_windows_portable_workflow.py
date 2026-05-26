from __future__ import annotations

import re
from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def _assert_release_asset_name_hardening(workflow: str) -> None:
    assert re.search(
        r"- name: Resolve release asset names[\s\S]*?env:\s*\n\s+RELEASE_TAG:\s+\$\{\{\s*github\.event\.release\.tag_name\s*\}\}"
        r"[\s\S]*?asset_tag=\"\$\{RELEASE_TAG//\\//-\}\"",
        workflow,
    )
    assert re.search(
        r"- name: Prepare versioned release asset[\s\S]*?env:\s*\n\s+ASSET_TAG:\s+\$\{\{\s*steps\.release_names\.outputs\.asset_tag\s*\}\}"
        r"[\s\S]*?frame-compare-portable-win-x64-\$\{ASSET_TAG\}\.zip",
        workflow,
    )
    assert re.search(
        r"- name: Prepare versioned signed update asset[\s\S]*?env:\s*\n\s+ASSET_TAG:\s+\$\{\{\s*steps\.release_names\.outputs\.asset_tag\s*\}\}"
        r"[\s\S]*?frame-compare-update-win-x64-\$\{ASSET_TAG\}\.zip",
        workflow,
    )
    assert 'tag="${{ github.event.release.tag_name }}"' not in workflow
    assert 'asset_tag="${{ steps.release_names.outputs.asset_tag }}"' not in workflow


def test_windows_portable_workflow_does_not_flatten_zip_contents(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    wf = _read_text_or_fail(wf_path)
    assert not re.search(r"Compress-Archive\s+-Path\s+['\"]?\$bundle/\*['\"]?", wf)


def test_windows_portable_workflow_zips_bundle_folder(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    wf = _read_text_or_fail(wf_path)
    assert re.search(r"Compress-Archive\s+-Path\s+\$bundle\b\s+-DestinationPath\s+\$zip\b", wf)


def test_windows_portable_workflow_verifies_zip_required_entries(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
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


def test_windows_portable_workflow_enables_release_public_key_gate_only_for_release_events(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)
    release_gate = re.search(
        r'if\s*\(\s*"\$\{\{\s*github\.event_name\s*\}\}"\s*-eq\s*"release"\s*-or\s*'
        r'"\$\{\{\s*github\.event_name\s*\}\}"\s*-eq\s*"workflow_dispatch"\s*\)'
        r"\s*\{[\s\S]*?\$buildArgs\s*\+=\s*\"-RequireReleasePublicKey\"",
        workflow,
    )
    assert release_gate is not None
    assert not re.search(
        r"github\.event_name[^\n]+pull_request[^\n]+RequireReleasePublicKey", workflow
    )


def test_windows_portable_workflow_verifies_workspace_directories(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
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
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Setup Python 3.13.13" in workflow
    assert "app/site-packages/vapoursynth/plugins" in workflow
    assert "vs/extra-plugins" in workflow
    assert "lsmas/manifest.vs" in workflow
    assert "tools/windows_portable/build_portable.ps1" in workflow
    assert "Smoke: VS clip + tonemap does not raise" not in workflow
    assert "WINDOWS_WORKFLOW_PROOF" not in workflow


def test_windows_portable_workflow_validates_update_public_key_on_release(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)
    assert "Validate update public key" in workflow
    assert "tools/windows_portable/update_public_key.xml" in workflow.replace("\\", "/")
    assert re.search(
        r"if:\s*github\.event_name\s*==\s*'release'\s*\|\|\s*"
        r"github\.event_name\s*==\s*'workflow_dispatch'",
        workflow,
    )


def test_windows_portable_workflow_uploads_versioned_release_assets(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Resolve release asset names" in workflow
    assert "Prepare versioned release asset" in workflow
    _assert_release_asset_name_hardening(workflow)
    assert "steps.release_names.outputs.asset_tag" in workflow
    assert 'hash="$(sha256sum "$zip" | cut -d \' \' -f 1)"' in workflow
    assert 'printf \'%s  %s\\n\' "$hash" "$(basename "$zip")" > "$zip.sha256"' in workflow
    assert (
        "dist/release-assets/frame-compare-portable-win-x64-${{ "
        "steps.release_names.outputs.asset_tag }}.zip"
    ) in workflow
    assert (
        "dist/release-assets/frame-compare-portable-win-x64-${{ "
        "steps.release_names.outputs.asset_tag }}.zip.sha256"
    ) in workflow


def test_windows_portable_workflow_smokes_extracted_install_shim(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
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
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
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


def test_windows_portable_workflow_signs_update_only_for_release_like_events(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Pull requests prove update zip creation without requiring signing secrets." in workflow
    assert (
        "Release/manual runs sign only when the private key XML secret is configured." in workflow
    )
    assert "id: sign_update" in workflow
    assert (
        "if: github.event_name == 'release' || github.event_name == 'workflow_dispatch'" in workflow
    )
    assert (
        "WINDOWS_UPDATE_SIGNING_KEY_XML: ${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}" in workflow
    )
    assert "::notice::Skipping signed update zip; WINDOWS_UPDATE_SIGNING_KEY_XML secret" in workflow
    assert "$env:SIGNING_KEY_XML_PATH = $keyPath" in workflow
    assert "tools/windows_portable/sign_update.ps1" in workflow
    assert "-UpdateZip $env:UPDATE_ZIP" in workflow
    assert "signed=false" in workflow
    assert "signed=true" in workflow
    assert "pull_request" not in re.search(
        r"- name: Sign code-only update zip[\s\S]*?(?=\n      - name:)",
        workflow,
    ).group(0)


def test_windows_portable_workflow_verifies_and_uploads_update_artifact(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Hash code-only update zip" in workflow
    assert "Verify code-only update zip layout" in workflow
    assert "update-manifest.json" in workflow
    assert "payload/app/src/frame_compare/" in workflow
    assert 'target_platform -ne "windows-x64"' in workflow
    assert 'payload_root -ne "payload"' in workflow
    assert 'signature_file -ne "update-manifest.sig"' in workflow
    assert "Signed update zip is missing update-manifest.sig." in workflow
    assert "Upload code-only update artifact" in workflow
    assert "name: frame-compare-update-win-x64" in workflow
    assert "dist/frame-compare-update-win-x64-*.zip" in workflow
    assert "dist/frame-compare-update-win-x64-*.zip.sha256" in workflow


def test_windows_portable_workflow_uploads_signed_update_release_asset_conditionally(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "update_signed: ${{ steps.sign_update.outputs.signed }}" in workflow
    assert "Download signed update artifact" in workflow
    assert "Prepare versioned signed update asset" in workflow
    assert "Upload signed update release asset" in workflow
    assert workflow.count("if: needs.build.outputs.update_signed == 'true'") == 3
    assert "mapfile -t update_zips" in workflow
    assert "Expected exactly one signed update zip artifact, found ${#update_zips[@]}." in workflow
    assert "frame-compare-update-win-x64-${ASSET_TAG}.zip" in workflow
    assert (
        "dist/release-assets/frame-compare-update-win-x64-${{ "
        "steps.release_names.outputs.asset_tag }}.zip"
    ) in workflow
    assert (
        "dist/release-assets/frame-compare-update-win-x64-${{ "
        "steps.release_names.outputs.asset_tag }}.zip.sha256"
    ) in workflow
