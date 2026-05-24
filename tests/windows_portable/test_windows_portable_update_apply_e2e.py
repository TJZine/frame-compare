from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from ._helpers import powershell_exe as _powershell_exe
from ._helpers import write_valid_config_json as _write_valid_config_json

_OLD_VERSION_CONTENT = '__version__ = "1.0.0"\n'
_NEW_VERSION_CONTENT = '__version__ = "1.0.1"\n'
_REQ_HASH = "3a0058b73f8a4872c3d0b27b99c017d9a8c087cf283d5f9923b0df35b44bfd82"


def _generate_rsa_keypair(*, exe: str) -> tuple[str, str]:
    key_gen_cmd = (
        "function B64([byte[]]$Bytes) { [Convert]::ToBase64String($Bytes) }; "
        "$rsa = [System.Security.Cryptography.RSA]::Create(); "
        "$rsa.KeySize = 2048; "
        "$private = $rsa.ExportParameters($true); "
        "$public = $rsa.ExportParameters($false); "
        "$privateXml = '<RSAKeyValue>' + "
        "'<Modulus>' + (B64 $private.Modulus) + '</Modulus>' + "
        "'<Exponent>' + (B64 $private.Exponent) + '</Exponent>' + "
        "'<P>' + (B64 $private.P) + '</P>' + "
        "'<Q>' + (B64 $private.Q) + '</Q>' + "
        "'<DP>' + (B64 $private.DP) + '</DP>' + "
        "'<DQ>' + (B64 $private.DQ) + '</DQ>' + "
        "'<InverseQ>' + (B64 $private.InverseQ) + '</InverseQ>' + "
        "'<D>' + (B64 $private.D) + '</D>' + "
        "'</RSAKeyValue>'; "
        "$publicXml = '<RSAKeyValue>' + "
        "'<Modulus>' + (B64 $public.Modulus) + '</Modulus>' + "
        "'<Exponent>' + (B64 $public.Exponent) + '</Exponent>' + "
        "'</RSAKeyValue>'; "
        "$rsa.Dispose(); "
        "Write-Output '---PRIVATE---'; "
        "Write-Output $privateXml; "
        "Write-Output '---PUBLIC---'; "
        "Write-Output $publicXml;"
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
    return private_key_xml, public_key_xml


def _setup_update_install(
    *,
    tmp_path: Path,
    repo_root: Path,
    public_key_xml: str,
) -> tuple[Path, Path, Path]:
    install_root = tmp_path / "install"
    shim_dir = install_root / "shim"
    state_dir = install_root / "state"
    bundle_dir = install_root / "bundle"
    shim_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    bundle_dir.mkdir(parents=True)
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    repo_update_script = (
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    )
    shim_update_ps1 = shim_dir / "frame-compare-update.ps1"
    shim_update_ps1.write_text(repo_update_script.read_text(encoding="utf-8"), encoding="utf-8")

    public_key_path = shim_dir / "update_public_key.xml"
    public_key_path.write_text(public_key_xml, encoding="utf-8")
    return bundle_dir, shim_update_ps1, state_dir


def _write_mock_bundle(*, bundle_dir: Path) -> Path:
    bundle_app_fc = bundle_dir / "app" / "src" / "frame_compare"
    bundle_app_fc.mkdir(parents=True)
    version_py = bundle_app_fc / "version.py"
    version_py.write_text(_OLD_VERSION_CONTENT, encoding="utf-8")

    python_dir = bundle_dir / "python"
    python_dir.mkdir(parents=True)
    python_exe = python_dir / "python.exe"
    if os.name == "nt":
        shutil.copy(sys.executable, python_exe)
    else:
        python_exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
        python_exe.chmod(0o755)

    bundle_info = bundle_dir / "bundle_info.json"
    bundle_info.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bundle_kind": "portable_bundle",
                "platform": "windows-x64",
                "requirements_lock_sha256": _REQ_HASH,
            }
        ),
        encoding="utf-8",
    )

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
    return version_py


def _build_update_zip(*, tmp_path: Path) -> Path:
    import hashlib

    update_staging = tmp_path / "update_staging"
    update_staging.mkdir()

    new_version_py_rel = "app/src/frame_compare/version.py"
    payload_version_py = update_staging / "payload" / new_version_py_rel
    payload_version_py.parent.mkdir(parents=True)
    payload_version_py.write_text(_NEW_VERSION_CONTENT, encoding="utf-8")

    file_sha256 = hashlib.sha256(payload_version_py.read_bytes()).hexdigest()
    manifest_data = {
        "schema_version": 1,
        "target_platform": "windows-x64",
        "to_app_version": "1.0.1",
        "from_app_version_min": "1.0.0",
        "from_app_version_max": "1.1.0",
        "payload_root": "payload",
        "signature_file": "update-manifest.sig",
        "expected_requirements_lock_sha256": _REQ_HASH,
        "files": [
            {
                "path": new_version_py_rel,
                "sha256": file_sha256,
            }
        ],
    }
    manifest_path = update_staging / "update-manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    update_zip_path = tmp_path / "update.zip"
    with zipfile.ZipFile(update_zip_path, mode="w") as archive:
        archive.write(manifest_path, arcname="update-manifest.json")
        archive.write(payload_version_py, arcname="payload/" + new_version_py_rel)
    return update_zip_path


def _sign_update_zip(
    *,
    exe: str,
    repo_root: Path,
    update_zip_path: Path,
    private_key_path: Path,
) -> dict[str, str]:
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
    return env


def _apply_update(
    *,
    exe: str,
    env: dict[str, str],
    bundle_dir: Path,
    shim_update_ps1: Path,
    update_zip_path: Path,
) -> subprocess.CompletedProcess[str]:
    env["PYTHONPATH"] = str(bundle_dir / "app" / "src")
    return subprocess.run(
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


def _assert_update_applied(*, bundle_dir: Path, version_py: Path) -> None:
    assert version_py.read_text(encoding="utf-8") == _NEW_VERSION_CONTENT

    backup_root = bundle_dir / "app" / ".update_backups"
    assert backup_root.is_dir()
    backups = list(backup_root.iterdir())
    assert len(backups) == 1
    backup_version_py = backups[0] / "frame_compare" / "version.py"
    assert backup_version_py.read_text(encoding="utf-8") == _OLD_VERSION_CONTENT


@pytest.mark.integration
def test_windows_portable_update_apply_e2e(tmp_path: Path, repo_root: Path) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    private_key_xml, public_key_xml = _generate_rsa_keypair(exe=exe)
    private_key_path = tmp_path / "private_key.xml"
    private_key_path.write_text(private_key_xml, encoding="utf-8")

    bundle_dir, shim_update_ps1, _state_dir = _setup_update_install(
        tmp_path=tmp_path,
        repo_root=repo_root,
        public_key_xml=public_key_xml,
    )
    version_py = _write_mock_bundle(bundle_dir=bundle_dir)
    update_zip_path = _build_update_zip(tmp_path=tmp_path)
    env = _sign_update_zip(
        exe=exe,
        repo_root=repo_root,
        update_zip_path=update_zip_path,
        private_key_path=private_key_path,
    )

    apply_proc = _apply_update(
        exe=exe,
        env=env,
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=update_zip_path,
    )
    assert apply_proc.returncode == 0, (
        f"stdout:\n{apply_proc.stdout}\n\nstderr:\n{apply_proc.stderr}"
    )

    _assert_update_applied(bundle_dir=bundle_dir, version_py=version_py)
