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
    assert '$installScript = Join-Path $outDirFullPath "install.ps1"' in source_install
    assert "& $installScript" in source_install
    assert 'Assert-LastExitCode -Label "build_portable.ps1"' in source_install
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
        "tools/windows_portable/install.cmd",
        "tools/windows_portable/uninstall.cmd",
        "tools/windows_portable/shim/frame-compare.cmd",
        "tools/windows_portable/shim/frame-compare-update.cmd",
    ):
        source = _read_text_or_fail(repo_root / relative_path).lower()
        assert "%programfiles%\\powershell\\7\\pwsh.exe" in source
        assert "%systemroot%\\system32\\windowspowershell\\v1.0\\powershell.exe" in source


@pytest.mark.parametrize(
    "entrypoint", ("install.ps1", "tools/windows_portable/install-from-source.ps1")
)
def test_source_install_requires_ps7_before_bootstrap(repo_root: Path, entrypoint: str) -> None:
    source = _read_text_or_fail(repo_root / entrypoint)
    guard = source.index("$PSVersionTable.PSVersion.Major -lt 7")
    assert "PowerShell 7 or newer is required to build Frame Compare from source." in source
    boundary = (
        source.index("Update-ProcessPathFromRegistry\nEnsure-UvOnPath")
        if "install-from-source.ps1" in entrypoint
        else source.index("& (Join-Path $PSScriptRoot")
    )
    assert guard < boundary


@pytest.mark.parametrize(
    "wrapper", ("install.cmd", "tools/windows_portable/install-from-source.cmd")
)
def test_source_cmd_requires_ps7_without_legacy_fallback(repo_root: Path, wrapper: str) -> None:
    source = _read_text_or_fail(repo_root / wrapper).lower()
    assert "powershell 7 or newer is required to build frame compare from source." in source
    assert "windowspowershell" not in source
    assert source.index("exit /b 9009") < source.index("-noprofile")


@pytest.mark.integration
def test_root_source_cmd_refuses_without_pwsh_before_invoking_installer(
    tmp_path: Path, repo_root: Path
) -> None:
    import os
    import shutil
    import subprocess

    if os.name != "nt":
        pytest.skip("Windows CMD process semantics required")
    wrapper = tmp_path / "install.cmd"
    wrapper.write_bytes((repo_root / "install.cmd").read_bytes())
    marker = tmp_path / "invoked.txt"
    (tmp_path / "install.ps1").write_text(
        f"Set-Content -LiteralPath '{marker}' -Value invoked; exit 0",
        encoding="utf-8",
    )
    env = os.environ.copy()
    # Keep real command discovery, without exposing host executables or its working directory.
    shutil.copyfile(Path(env["SYSTEMROOT"]) / "System32/where.exe", tmp_path / "where.exe")
    env["PATH"] = str(tmp_path)
    env["PROGRAMFILES"] = str(tmp_path / "no-powershell")
    proc = subprocess.run(
        [env["COMSPEC"], "/d", "/c", str(wrapper), "-SkipSync"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode != 0
    assert "PowerShell 7 or newer is required" in proc.stdout + proc.stderr
    assert not marker.exists()


@pytest.mark.integration
@pytest.mark.parametrize("interpreter", ["powershell", "pwsh"])
def test_root_source_installer_prerequisite_at_process_boundary(
    tmp_path: Path, repo_root: Path, interpreter: str
) -> None:
    import os
    import shutil
    import subprocess

    if os.name != "nt":
        pytest.skip("Windows source installer process semantics required")
    exe = shutil.which(interpreter)
    if exe is None:
        pytest.skip(f"{interpreter} not available")
    copied_repo = tmp_path / "repo"
    owner = copied_repo / "tools/windows_portable"
    owner.mkdir(parents=True)
    for relative in ("install.ps1", "tools/windows_portable/install-from-source.ps1"):
        (copied_repo / relative).write_bytes((repo_root / relative).read_bytes())
    (owner / "manifest.windows-x64.json").write_text("{}", encoding="utf-8")
    # Keep the production installer path; stub only its expensive build/bootstrap boundaries.
    (owner / "build_portable.ps1").write_text(
        """
param($ManifestPath, $OutDir, $CacheDir, $RepoRoot)
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
Set-Content -LiteralPath (Join-Path $OutDir "install.ps1") -Value '$global:LASTEXITCODE = 0'
$global:LASTEXITCODE = 0
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"function uv {{ throw 'uv must not run with SkipSync' }}; & '{copied_repo / 'install.ps1'}' -SkipSync",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if interpreter == "powershell":
        assert proc.returncode != 0
        assert "PowerShell 7 or newer is required" in proc.stdout + proc.stderr
        assert not (copied_repo / "dist").exists()
        assert not (copied_repo / ".portable_cache").exists()
    else:
        assert proc.returncode == 0, proc.stderr
        assert "Source install complete." in proc.stdout
        assert (copied_repo / "dist/frame-compare-portable-win-x64/install.ps1").exists()
