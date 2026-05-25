from __future__ import annotations

import re
from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


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
