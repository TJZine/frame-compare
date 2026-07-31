from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from ._helpers import powershell_exe as _powershell_exe
from ._helpers import write_valid_config_json as _write_valid_config_json

_OLD_VERSION_CONTENT = '__version__ = "1.0.0"\n'
_NEW_VERSION_CONTENT = '__version__ = "1.0.1"\n'
_REQ_HASH = "3a0058b73f8a4872c3d0b27b99c017d9a8c087cf283d5f9923b0df35b44bfd82"
_POWERSHELL_KEYGEN_TIMEOUT_SECONDS = 30.0
_POWERSHELL_SIGN_TIMEOUT_SECONDS = 30.0
_POWERSHELL_APPLY_TIMEOUT_SECONDS = 30.0


def _generate_rsa_keypair(
    *,
    exe: str,
    repo_root: Path,
    tmp_path: Path,
) -> tuple[Path, str]:
    private_key_path = tmp_path / "private_key.xml"
    public_key_path = tmp_path / "public_key.xml"
    keygen_script = (
        repo_root / "tools" / "windows_portable" / "generate_update_keypair.ps1"
    )
    proc = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(keygen_script),
            "-PublicKeyPath",
            str(public_key_path),
            "-PrivateKeyPath",
            str(private_key_path),
            "-KeyId",
            "frame-compare-update-e2e-test",
            "-KeySize",
            "2048",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=_POWERSHELL_KEYGEN_TIMEOUT_SECONDS,
    )
    assert "<RSAKeyValue>" not in proc.stdout + proc.stderr
    return private_key_path, public_key_path.read_text(encoding="utf-8")


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
    expected_public_key_path: Path,
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
            "-ExpectedPublicKeyPath",
            str(expected_public_key_path),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=_POWERSHELL_SIGN_TIMEOUT_SECONDS,
    )
    assert "Signed:" in sign_proc.stdout
    env.pop("SIGNING_KEY_XML_PATH")
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
        timeout=_POWERSHELL_APPLY_TIMEOUT_SECONDS,
    )


def _assert_update_applied(*, bundle_dir: Path, version_py: Path) -> None:
    assert version_py.read_text(encoding="utf-8") == _NEW_VERSION_CONTENT

    backup_root = bundle_dir / "app" / ".update_backups"
    assert backup_root.is_dir()
    backups = list(backup_root.iterdir())
    assert len(backups) == 1
    backup_version_py = backups[0] / "frame_compare" / "version.py"
    assert backup_version_py.read_text(encoding="utf-8") == _OLD_VERSION_CONTENT


def _snapshot_tree(path: Path) -> dict[str, str]:
    return {
        file.relative_to(path).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(path.rglob("*"))
        if file.is_file()
    }


def _rewrite_zip_entry(
    *,
    source_zip: Path,
    target_zip: Path,
    entry_name: str,
    transform: Callable[[bytes], bytes],
) -> None:
    with zipfile.ZipFile(source_zip, mode="r") as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]
    with zipfile.ZipFile(target_zip, mode="w") as target:
        for info, content in entries:
            if info.filename == entry_name:
                content = transform(content)
            target.writestr(info, content)


def _run_update_command(
    *,
    exe: str,
    env: dict[str, str],
    shim_update_ps1: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(shim_update_ps1),
            *args,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=_POWERSHELL_APPLY_TIMEOUT_SECONDS,
    )


@pytest.mark.integration
def test_windows_portable_update_apply_e2e(tmp_path: Path, repo_root: Path) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    private_key_path, public_key_xml = _generate_rsa_keypair(
        exe=exe,
        repo_root=repo_root,
        tmp_path=tmp_path,
    )

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
        expected_public_key_path=shim_update_ps1.parent / "update_public_key.xml",
    )

    installed_tree = bundle_dir / "app" / "src" / "frame_compare"
    original_snapshot = _snapshot_tree(installed_tree)

    manifest_tampered_zip = tmp_path / "manifest-tampered.zip"
    _rewrite_zip_entry(
        source_zip=update_zip_path,
        target_zip=manifest_tampered_zip,
        entry_name="update-manifest.json",
        transform=lambda content: content + b"\n",
    )
    manifest_rejection = _apply_update(
        exe=exe,
        env=env,
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=manifest_tampered_zip,
    )
    assert manifest_rejection.returncode != 0
    assert "Signature missing or invalid" in manifest_rejection.stderr
    assert _snapshot_tree(installed_tree) == original_snapshot
    assert not (bundle_dir / "app" / ".update_backups").exists()

    payload_tampered_zip = tmp_path / "payload-tampered.zip"
    _rewrite_zip_entry(
        source_zip=update_zip_path,
        target_zip=payload_tampered_zip,
        entry_name="payload/app/src/frame_compare/version.py",
        transform=lambda content: content + b"# tampered\n",
    )
    payload_rejection = _apply_update(
        exe=exe,
        env=env,
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=payload_tampered_zip,
    )
    assert payload_rejection.returncode != 0
    assert "Payload hash mismatch" in payload_rejection.stderr
    assert _snapshot_tree(installed_tree) == original_snapshot
    assert not (bundle_dir / "app" / ".update_backups").exists()

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
    backup_root = bundle_dir / "app" / ".update_backups"
    backup_id = next(backup_root.iterdir()).name
    rollback = _run_update_command(
        exe=exe,
        env=env,
        shim_update_ps1=shim_update_ps1,
        args=["rollback", backup_id],
    )
    assert rollback.returncode == 0, (
        f"stdout:\n{rollback.stdout}\n\nstderr:\n{rollback.stderr}"
    )
    assert _snapshot_tree(installed_tree) == original_snapshot
