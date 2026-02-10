from pathlib import Path


def _first_significant_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return stripped
    return ""


def test_install_from_source_param_block_is_first_statement() -> None:
    script_path = Path("tools/windows_portable/install-from-source.ps1")
    script_text = script_path.read_text(encoding="utf-8")
    assert _first_significant_line(script_text).startswith("Param(")


def test_install_from_source_avoids_pscore_only_windows_variable() -> None:
    script_path = Path("tools/windows_portable/install-from-source.ps1")
    script_text = script_path.read_text(encoding="utf-8")
    assert "$IsWindows" not in script_text


def test_root_install_cmd_exists_and_calls_install_ps1() -> None:
    path = Path("install.cmd")
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    assert "powershell" in text
    assert "-noprofile" in text
    assert "-executionpolicy bypass" in text
    assert "-file" in text
    assert "install.ps1" in text


def test_root_install_ps1_exists_and_delegates_to_install_from_source() -> None:
    path = Path("install.ps1")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert _first_significant_line(text).startswith("Param(")
    normalized = text.replace("\\\\", "/").replace("\\", "/")
    assert "tools/windows_portable/install-from-source.ps1" in normalized


def test_install_from_source_mentions_uv_auto_install() -> None:
    script_path = Path("tools/windows_portable/install-from-source.ps1")
    text = script_path.read_text(encoding="utf-8").lower()
    assert "winget" in text
    assert "pip" in text
    assert "uv" in text
    assert "docs: https://docs.astral.sh/uv/getting-started/installation/" in text
    assert "curl" not in text
    assert "invoke-expression" not in text


def test_install_from_source_uv_install_order_is_deterministic() -> None:
    script_path = Path("tools/windows_portable/install-from-source.ps1")
    text = script_path.read_text(encoding="utf-8").lower()

    # The plan requires winget first, then pip as fallback.
    winget_idx = text.index("winget install")
    pip_idx = text.index("pip install --user uv")
    assert winget_idx < pip_idx

    # Recovery block must be copy/paste friendly and include both commands.
    assert "winget install --id astral-sh.uv -e --source winget" in text
    assert "py -m pip install --user uv" in text


def test_windows_portable_workflow_does_not_flatten_zip_contents() -> None:
    wf = Path(".github/workflows/windows-portable.yml").read_text(encoding="utf-8")
    assert 'Compress-Archive -Path "$bundle/*"' not in wf


def test_windows_portable_workflow_zips_bundle_folder() -> None:
    wf = Path(".github/workflows/windows-portable.yml").read_text(encoding="utf-8")
    assert "Compress-Archive -Path $bundle -DestinationPath $zip" in wf


def test_windows_portable_workflow_verifies_zip_required_entries() -> None:
    wf = Path(".github/workflows/windows-portable.yml").read_text(encoding="utf-8")
    required = [
        "frame-compare-portable-win-x64/install.cmd",
        "frame-compare-portable-win-x64/install.ps1",
        "frame-compare-portable-win-x64/frame-compare.ps1",
        "frame-compare-portable-win-x64/shim/frame-compare.cmd",
    ]
    for entry in required:
        assert entry in wf
