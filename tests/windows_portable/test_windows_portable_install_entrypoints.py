from __future__ import annotations

from pathlib import Path

import pytest

from ._helpers import first_significant_line as _first_significant_line
from ._helpers import read_text_or_fail as _read_text_or_fail


@pytest.mark.parametrize(
    "entrypoint", ("install.ps1", "tools/windows_portable/install-from-source.ps1")
)
def test_windows_install_entrypoints_start_with_parameter_block(
    repo_root: Path, entrypoint: str
) -> None:
    assert _first_significant_line(_read_text_or_fail(repo_root / entrypoint)).startswith("Param(")


def test_windows_install_entrypoint_avoids_remote_script_execution(repo_root: Path) -> None:
    source = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    ).lower()

    assert "winget" in source
    assert "pip" in source
    assert "curl" not in source
    assert "invoke-expression" not in source


def test_root_install_delegates_to_fail_closed_source_install(repo_root: Path) -> None:
    root_install = _read_text_or_fail(repo_root / "install.ps1").replace("\\", "/")
    source_install = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    )

    assert "tools/windows_portable/install-from-source.ps1" in root_install
    assert "exit $LASTEXITCODE" in root_install
    assert "uv sync --group dev --frozen" in source_install
    assert "& $buildScript -ManifestPath $manifestFullPath" in source_install
    assert 'Assert-LastExitCode -Label "build_portable.ps1"' in source_install
    assert '$installScript = Join-Path $outDirFullPath "install.ps1"' in source_install
    assert "& $installScript" in source_install
    assert 'Assert-LastExitCode -Label "install.ps1"' in source_install


@pytest.mark.parametrize(
    ("wrapper", "script"),
    (
        ("install.cmd", "install.ps1"),
        (
            "tools/windows_portable/install-from-source.cmd",
            "install-from-source.ps1",
        ),
    ),
)
def test_windows_source_install_cmd_wrappers_forward_args_and_exit_code(
    repo_root: Path, wrapper: str, script: str
) -> None:
    source = _read_text_or_fail(repo_root / wrapper).lower()

    assert f'-file "%~dp0{script}" %*' in source
    assert "exit /b %errorlevel%" in source


def test_windows_cmd_launchers_have_absolute_powershell_fallbacks(repo_root: Path) -> None:
    for relative_path in (
        "install.cmd",
        "tools/windows_portable/install-from-source.cmd",
        "tools/windows_portable/install.cmd",
        "tools/windows_portable/uninstall.cmd",
        "tools/windows_portable/shim/frame-compare.cmd",
        "tools/windows_portable/shim/frame-compare-update.cmd",
    ):
        source = _read_text_or_fail(repo_root / relative_path).lower()
        assert "%programfiles%\\powershell\\7\\pwsh.exe" in source
        assert "%systemroot%\\system32\\windowspowershell\\v1.0\\powershell.exe" in source
