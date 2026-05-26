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
    assert "if %errorlevel% equ 0" in text
    assert "pwsh" in text
    assert "powershell" in text
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


def test_install_from_source_uv_install_order_is_deterministic(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    text = _read_text_or_fail(script_path).lower()

    # The plan requires winget first, then pip as fallback.
    winget_idx = text.index("winget install")
    pip_idx = text.index("pip install --user uv")
    assert winget_idx < pip_idx

    # Recovery block must be copy/paste friendly and include both commands.
    assert "winget install --id astral-sh.uv -e --source winget" in text
    assert "py -m pip install --user uv" in text


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
