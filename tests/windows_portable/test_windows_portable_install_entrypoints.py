from __future__ import annotations

from pathlib import Path

from ._helpers import first_significant_line as _first_significant_line
from ._helpers import read_text_or_fail as _read_text_or_fail


def test_first_significant_line_returns_empty_for_blank_or_comment_only() -> None:
    assert _first_significant_line("") == ""
    assert _first_significant_line("# comment\n# another") == ""
    assert _first_significant_line("\n\n\n") == ""


def test_install_from_source_param_block_is_first_statement(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    script_text = _read_text_or_fail(script_path)
    assert _first_significant_line(script_text).startswith("Param(")


def test_install_from_source_avoids_pscore_only_windows_variable(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    script_text = _read_text_or_fail(script_path)
    assert "$IsWindows" not in script_text


def test_root_install_cmd_exists_and_calls_install_ps1(repo_root: Path) -> None:
    path = repo_root / "install.cmd"
    assert path.exists()
    text = _read_text_or_fail(path).lower()
    assert "where pwsh" in text
    assert "powershell_exe" in text
    assert "%programfiles%\\powershell\\7\\pwsh.exe" in text
    assert "%systemroot%\\system32\\windowspowershell\\v1.0\\powershell.exe" in text
    assert "-noprofile" in text
    assert "-executionpolicy bypass" in text
    assert "-file" in text
    assert "install.ps1" in text


def test_root_install_ps1_exists_and_delegates_to_install_from_source(repo_root: Path) -> None:
    path = repo_root / "install.ps1"
    assert path.exists()
    text = _read_text_or_fail(path)
    assert _first_significant_line(text).startswith("Param(")
    normalized = text.replace("\\\\", "/").replace("\\", "/")
    assert "tools/windows_portable/install-from-source.ps1" in normalized


def test_install_from_source_mentions_uv_auto_install(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    text = _read_text_or_fail(script_path).lower()
    assert "winget" in text
    assert "pip" in text
    assert "uv" in text
    assert "docs: https://docs.astral.sh/uv/getting-started/installation/" in text
    assert "curl" not in text
    assert "invoke-expression" not in text


def test_install_from_source_uv_install_paths_and_recovery_guidance(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    text = _read_text_or_fail(script_path).lower()

    assert "winget install" in text
    assert "pip install --user uv" in text

    # Recovery block must be copy/paste friendly and include both commands.
    recovery_lines = {line.strip() for line in text.splitlines()}
    assert "winget install --id astral-sh.uv -e --source winget" in recovery_lines
    assert "py -m pip install --user uv" in recovery_lines


def test_install_from_source_refreshes_process_path_before_uv_lookup(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    text = _read_text_or_fail(script_path)

    assert text.index("Update-ProcessPathFromRegistry\nEnsure-UvOnPath") > text.index(
        "function Update-ProcessPathFromRegistry()"
    )


def test_install_from_source_invokes_bundle_install_ps1_directly(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    text = _read_text_or_fail(script_path)

    assert '$installScript = Join-Path $outDirFullPath "install.ps1"' in text
    assert "& $installScript" in text
    assert 'Assert-LastExitCode -Label "install.ps1"' in text
    assert '$installCmd = Join-Path $outDirFullPath "install.cmd"' not in text
    assert "& $installCmd" not in text


def test_windows_portable_installer_initializes_state_config_toml(repo_root: Path) -> None:
    installer_path = repo_root / "tools" / "windows_portable" / "install.ps1"
    installer = _read_text_or_fail(installer_path)
    assert '$portableConfigToml = Join-Path $stateDir "config.toml"' in installer
    assert (
        '$bundleConfigToml = Join-Path (Join-Path $bundleRoot "config") "config.toml"' in installer
    )
    assert (
        "Copy-Item -LiteralPath $bundleConfigToml -Destination $portableConfigToml -Force"
        in installer
    )
    assert "[paths]" in installer


def test_windows_portable_installer_copies_update_shims(repo_root: Path) -> None:
    installer_path = repo_root / "tools" / "windows_portable" / "install.ps1"
    installer = _read_text_or_fail(installer_path)
    assert "frame-compare-update.ps1" in installer
    assert "frame-compare-update.cmd" in installer
    assert "update_public_key.xml" in installer


def test_windows_portable_cmd_wrappers_have_absolute_powershell_fallbacks(
    repo_root: Path,
) -> None:
    cmd_paths = [
        repo_root / "install.cmd",
        repo_root / "tools" / "windows_portable" / "install-from-source.cmd",
        repo_root / "tools" / "windows_portable" / "install.cmd",
        repo_root / "tools" / "windows_portable" / "uninstall.cmd",
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.cmd",
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.cmd",
    ]

    for cmd_path in cmd_paths:
        text = _read_text_or_fail(cmd_path).lower()
        assert "powershell_exe" in text, cmd_path
        assert "%programfiles%\\powershell\\7\\pwsh.exe" in text, cmd_path
        assert "%systemroot%\\system32\\windowspowershell\\v1.0\\powershell.exe" in text, cmd_path
        assert '"%powershell_exe%" -noprofile -executionpolicy bypass -file' in text, cmd_path
