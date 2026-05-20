from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _powershell_exe() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _run_shim(
    *,
    exe: str,
    shim_path: Path,
    env: dict[str, str],
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(shim_path), *args],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _write_valid_config_json(
    *, state_dir: Path, bundle_dir: Path, schema_version: object = 1
) -> None:
    (state_dir / "config.json").write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "install_type": "portable_bundle",
                "bundle_path": str(bundle_dir),
            }
        ),
        encoding="utf-8",
    )


def _setup_install_layout(*, tmp_path: Path, repo_root: Path) -> tuple[Path, Path, Path, Path]:
    repo_shim = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    install_root = tmp_path / "install"
    shim_dir = install_root / "shim"
    state_dir = install_root / "state"
    bundle_dir = install_root / "bundle"
    shim_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    bundle_dir.mkdir(parents=True)

    shim_path = shim_dir / "frame-compare.ps1"
    shim_path.write_text(repo_shim.read_text(encoding="utf-8"), encoding="utf-8")
    return install_root, shim_path, state_dir, bundle_dir


@pytest.mark.integration
def test_windows_portable_shim_preset_apply_injection_e2e(tmp_path: Path, repo_root: Path) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )

    state_config_toml = state_dir / "config.toml"
    state_config_toml.write_text('[paths]\ninput_dir = "inputs"\n', encoding="utf-8")

    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    args_file = tmp_path / "args.txt"
    cwd_file = tmp_path / "cwd.txt"
    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                "$argsFile = $env:FC_TEST_ARGS_FILE",
                "$cwdFile = $env:FC_TEST_CWD_FILE",
                "if ($null -eq $argsFile -or $null -eq $cwdFile) { exit 2 }",
                'Set-Content -LiteralPath $argsFile -Value ($args -join "|") -Encoding UTF8',
                "Set-Content -LiteralPath $cwdFile -Value (Get-Location).Path -Encoding UTF8",
                '$configIndex = [Array]::IndexOf($args, "--config")',
                "if ($configIndex -lt 0) { exit 3 }",
                "if (($configIndex + 1) -ge $args.Count) { exit 4 }",
                "$cfg = [string]$args[$configIndex + 1]",
                "if (!(Test-Path -LiteralPath $cfg)) { exit 5 }",
                '$boostIndex = [Array]::IndexOf($args, "boost")',
                "if ($boostIndex -lt 0) { exit 6 }",
                "if ($configIndex -gt $boostIndex) { exit 7 }",
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    # Verify Get-ConfigInjectionIndex directly (dot-sourcing should not execute the shim).
    cmd = (
        f". '{shim_path}'; "
        "$idx = Get-ConfigInjectionIndex -ArgsValues @('preset','apply','boost'); "
        "Write-Output $idx"
    )
    proc = subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == "2"

    # Execute shim end-to-end and assert injected args reach bundle launcher.
    env = os.environ.copy()
    env["FC_TEST_ARGS_FILE"] = str(args_file)
    env["FC_TEST_CWD_FILE"] = str(cwd_file)
    proc2 = _run_shim(exe=exe, shim_path=shim_path, env=env, args=["preset", "apply", "boost"])
    assert proc2.returncode == 0, f"stdout:\n{proc2.stdout}\n\nstderr:\n{proc2.stderr}"

    forwarded = args_file.read_text(encoding="utf-8-sig").rstrip("\r\n")
    parts = forwarded.split("|")
    assert parts[:2] == ["preset", "apply"]
    assert parts[2:4] == ["--config", str(state_config_toml)]
    assert parts[4] == "boost"

    recorded_cwd = cwd_file.read_text(encoding="utf-8-sig").strip()
    assert Path(recorded_cwd).resolve() == bundle_dir.resolve()


@pytest.mark.integration
def test_windows_portable_shim_missing_config_json_returns_10(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, _state_dir, _bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 10, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
def test_windows_portable_shim_invalid_config_json_returns_11(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, _bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    (state_dir / "config.json").write_text("{not-json", encoding="utf-8")
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 11, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
def test_windows_portable_shim_non_numeric_schema_version_returns_15(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version="abc")
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 15, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
@pytest.mark.parametrize("schema_version", [0, 2])
def test_windows_portable_shim_unsupported_numeric_schema_version_returns_15(
    tmp_path: Path, repo_root: Path, schema_version: int
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(
        state_dir=state_dir, bundle_dir=bundle_dir, schema_version=schema_version
    )
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 15, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
def test_windows_portable_shim_missing_bundle_launcher_returns_14(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 14, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
def test_windows_portable_shim_missing_state_config_toml_skips_injection(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    args_file = tmp_path / "args.txt"
    cwd_file = tmp_path / "cwd.txt"
    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                "$argsFile = $env:FC_TEST_ARGS_FILE",
                "$cwdFile = $env:FC_TEST_CWD_FILE",
                "if ($null -eq $argsFile -or $null -eq $cwdFile) { exit 2 }",
                'Set-Content -LiteralPath $argsFile -Value ($args -join "|") -Encoding UTF8',
                "Set-Content -LiteralPath $cwdFile -Value (Get-Location).Path -Encoding UTF8",
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["FC_TEST_ARGS_FILE"] = str(args_file)
    env["FC_TEST_CWD_FILE"] = str(cwd_file)
    proc = _run_shim(exe=exe, shim_path=shim_path, env=env, args=["preset", "apply", "boost"])
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"

    forwarded = args_file.read_text(encoding="utf-8-sig").rstrip("\r\n")
    parts = forwarded.split("|")
    assert len(parts) == 3
    assert parts[:3] == ["preset", "apply", "boost"]
    assert "--config" not in parts


@pytest.mark.integration
def test_windows_portable_update_apply_e2e(tmp_path: Path, repo_root: Path) -> None:
    import hashlib
    import sys
    import zipfile

    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    # 1. Generate RSA keypair using PowerShell to ensure .NET compatibility
    key_gen_cmd = (
        "$rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider; "
        "Write-Output '---PRIVATE---'; "
        "Write-Output $rsa.ToXmlString($true); "
        "Write-Output '---PUBLIC---'; "
        "Write-Output $rsa.ToXmlString($false);"
    )
    proc = subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", key_gen_cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = proc.stdout
    assert "---PRIVATE---" in stdout and "---PUBLIC---" in stdout
    private_key_xml = stdout.split("---PRIVATE---")[1].split("---PUBLIC---")[0].strip()
    public_key_xml = stdout.split("---PUBLIC---")[1].strip()

    private_key_path = tmp_path / "private_key.xml"
    private_key_path.write_text(private_key_xml, encoding="utf-8")

    # 2. Setup the install layout directories
    install_root = tmp_path / "install"
    shim_dir = install_root / "shim"
    state_dir = install_root / "state"
    bundle_dir = install_root / "bundle"
    shim_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    bundle_dir.mkdir(parents=True)

    # 3. Write public key and copy updater script
    repo_update_script = (
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    )
    shim_update_ps1 = shim_dir / "frame-compare-update.ps1"
    shim_update_ps1.write_text(repo_update_script.read_text(encoding="utf-8"), encoding="utf-8")

    public_key_path = shim_dir / "update_public_key.xml"
    public_key_path.write_text(public_key_xml, encoding="utf-8")

    # 4. Setup mock bundle files (initial state: version 1.0.0)
    bundle_app_fc = bundle_dir / "app" / "src" / "frame_compare"
    bundle_app_fc.mkdir(parents=True)
    version_py = bundle_app_fc / "version.py"
    version_py.write_text('__version__ = "1.0.0"\n', encoding="utf-8")

    # Mock python.exe structure
    python_dir = bundle_dir / "python"
    python_dir.mkdir(parents=True)
    python_exe = python_dir / "python.exe"
    if os.name == "nt":
        shutil.copy(sys.executable, python_exe)
    else:
        python_exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
        python_exe.chmod(0o755)

    # Mock requirements footprint
    req_hash = "3a0058b73f8a4872c3d0b27b99c017d9a8c087cf283d5f9923b0df35b44bfd82"
    bundle_info = bundle_dir / "bundle_info.json"
    bundle_info.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bundle_kind": "portable_bundle",
                "platform": "windows-x64",
                "requirements_lock_sha256": req_hash,
            }
        ),
        encoding="utf-8",
    )

    # Write mock launcher frame-compare.ps1 which prints version
    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                "param([string]$cmd)",
                'if ($cmd -eq "version") {',
                '  $versionFile = Join-Path $PSScriptRoot "app/src/frame_compare/version.py"',
                "  if (Test-Path -LiteralPath $versionFile) {",
                "    $content = Get-Content -LiteralPath $versionFile -Raw",
                '    if ($content -match \'__version__\\s*=\\s*"([^"]+)"\') {',
                "      Write-Output $Matches[1]",
                "      exit 0",
                "    }",
                "  }",
                '  Write-Output "unknown"',
                "  exit 1",
                "}",
            ]
        ),
        encoding="utf-8",
    )

    # 5. Build update zip in temporary staging directory
    update_staging = tmp_path / "update_staging"
    update_staging.mkdir()

    new_version_content = '__version__ = "1.0.1"\n'
    new_version_py_rel = "app/src/frame_compare/version.py"
    payload_version_py = update_staging / "payload" / new_version_py_rel
    payload_version_py.parent.mkdir(parents=True)
    payload_version_py.write_text(new_version_content, encoding="utf-8")

    # Compute hash of the updated file
    sha256_hasher = hashlib.sha256()
    sha256_hasher.update(new_version_content.encode("utf-8"))
    file_sha256 = sha256_hasher.hexdigest()

    manifest_data = {
        "schema_version": 1,
        "target_platform": "windows-x64",
        "to_app_version": "1.0.1",
        "from_app_version_min": "1.0.0",
        "from_app_version_max": "1.1.0",
        "payload_root": "payload",
        "signature_file": "update-manifest.sig",
        "expected_requirements_lock_sha256": req_hash,
        "files": [
            {
                "path": new_version_py_rel,
                "sha256": file_sha256,
            }
        ],
    }
    manifest_path = update_staging / "update-manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # Create the zip archive
    update_zip_path = tmp_path / "update.zip"
    with zipfile.ZipFile(update_zip_path, mode="w") as archive:
        archive.write(manifest_path, arcname="update-manifest.json")
        archive.write(payload_version_py, arcname="payload/" + new_version_py_rel)

    # 6. Sign the update zip using the official sign_update.ps1 script
    env = os.environ.copy()
    env["SIGNING_KEY_XML_PATH"] = str(private_key_path)
    sign_script = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    sign_proc = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(sign_script),
            str(update_zip_path),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Signed:" in sign_proc.stdout

    # 7. Execute frame-compare-update.ps1 apply update.zip
    # Pass PYTHONPATH to ensure python.exe can locate frame_compare (required for versions check)
    env["PYTHONPATH"] = str(bundle_dir / "app" / "src")
    apply_proc = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(shim_update_ps1),
            "apply",
            str(update_zip_path),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert apply_proc.returncode == 0, (
        f"stdout:\n{apply_proc.stdout}\n\nstderr:\n{apply_proc.stderr}"
    )

    # 8. Assertions:
    # Check that version.py was updated to 1.0.1
    assert version_py.read_text(encoding="utf-8") == new_version_content

    # Check that a backup was successfully created
    backup_root = bundle_dir / "app" / ".update_backups"
    assert backup_root.is_dir()
    backups = list(backup_root.iterdir())
    assert len(backups) == 1
    backup_version_py = backups[0] / "frame_compare" / "version.py"
    assert backup_version_py.read_text(encoding="utf-8") == '__version__ = "1.0.0"\n'
