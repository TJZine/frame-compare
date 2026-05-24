from __future__ import annotations

import re
from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_workflow_does_not_flatten_zip_contents(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    wf = _read_text_or_fail(wf_path)
    assert 'Compress-Archive -Path "$bundle/*"' not in wf


def test_windows_portable_workflow_zips_bundle_folder(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    wf = _read_text_or_fail(wf_path)
    assert "Compress-Archive -Path $bundle -DestinationPath $zip" in wf


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
    assert '$buildArgs += "-RequireReleasePublicKey"' in workflow
    assert (
        'if ("${{ github.event_name }}" -eq "release" -or '
        '"${{ github.event_name }}" -eq "workflow_dispatch")'
    ) in workflow
    assert not re.search(
        r"github\.event_name[^\n]+pull_request[^\n]+RequireReleasePublicKey", workflow
    )


def test_windows_portable_workflow_verifies_workspace_directories(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)
    assert '$bundleConfigDir = Join-Path $bundle "config"' in workflow
    assert '$bundleInputDir = Join-Path $bundle "comparison_videos"' in workflow
    assert "Test-Path -LiteralPath $bundleConfigDir -PathType Container" in workflow
    assert "Test-Path -LiteralPath $bundleInputDir -PathType Container" in workflow
    assert 'throw "Missing default workspace directory in bundle:' in workflow


def test_windows_portable_workflow_validates_update_public_key_on_release(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)
    assert "Validate update public key" in workflow
    assert "tools/windows_portable/update_public_key.xml" in workflow.replace("\\", "/")
    assert (
        "if: github.event_name == 'release' || github.event_name == 'workflow_dispatch'" in workflow
    )
