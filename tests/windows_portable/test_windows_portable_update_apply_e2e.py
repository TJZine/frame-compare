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

from ._helpers import snapshot_bytes as _snapshot_bytes
from ._helpers import write_valid_config_json as _write_valid_config_json

_OLD_VERSION_CONTENT = '__version__ = "1.0.0"\n'
_NEW_VERSION_CONTENT = '__version__ = "1.0.1"\n'
_REQ_HASH = "3a0058b73f8a4872c3d0b27b99c017d9a8c087cf283d5f9923b0df35b44bfd82"
_RUNTIME_HASH = "a17abda6b032c5568e557f881c018d2220230c832c612b75c7461e03d0eb4ba8"
_POWERSHELL_KEYGEN_TIMEOUT_SECONDS = 30.0
_POWERSHELL_SIGN_TIMEOUT_SECONDS = 30.0
_POWERSHELL_APPLY_TIMEOUT_SECONDS = 30.0


@pytest.fixture(params=["powershell", "pwsh"])
def update_exe(request: pytest.FixtureRequest) -> str:
    if os.name != "nt":
        pytest.skip("Windows PowerShell 5.1/7 updater E2E required")
    executable = shutil.which(request.param)
    if executable is None:
        pytest.skip(f"{request.param} unavailable")
    return executable


def _generate_rsa_keypair(
    *,
    exe: str,
    repo_root: Path,
    tmp_path: Path,
) -> tuple[Path, str]:
    # Key generation is a PS7.3+ build tool; the updater itself is exercised with
    # the selected legacy/modern interpreter, independently of signing tooling.
    keygen_exe = shutil.which("pwsh")
    if keygen_exe is None:
        pytest.skip("PowerShell 7.3+ key-generation tool required for signed updater fixtures")
    private_key_path = tmp_path / "private_key.xml"
    public_key_path = tmp_path / "public_key.xml"
    keygen_script = repo_root / "tools" / "windows_portable" / "generate_update_keypair.ps1"
    proc = subprocess.run(
        [
            keygen_exe,
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
    shutil.copyfile(
        repo_update_script.with_name("frame-compare-version.ps1"),
        shim_dir / "frame-compare-version.ps1",
    )

    public_key_path = shim_dir / "update_public_key.xml"
    public_key_path.write_text(public_key_xml, encoding="utf-8")
    return bundle_dir, shim_update_ps1, state_dir


def _write_mock_bundle(*, bundle_dir: Path) -> Path:
    bundle_app_fc = bundle_dir / "app" / "src" / "frame_compare"
    bundle_app_fc.mkdir(parents=True)
    version_py = bundle_app_fc / "version.py"
    version_py.write_bytes(_OLD_VERSION_CONTENT.encode("utf-8"))

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
                "schema_version": 3,
                "bundle_kind": "full",
                "app_version": "1.0.0",
                "requirements_lock_sha256": _REQ_HASH,
                "manifest_version": 2,
                "platform": "windows-x64",
                "media_runtime_fingerprint": _RUNTIME_HASH,
                "media_runtime_fingerprints": {
                    "analysis": "739628f62807a9267454596340da845715d6002e8e9db49b04a948ee1a1fde1d",
                    "probe": "c65f5a36b64e5e2b00890fdb84650b7d6ef3f36fe0f5633cad710142d80fb10e",
                    "alignment": "04a8dfb581214e976bfa011132006c819169f1ce3ca00176711801df84941464",
                    "index": "097c1b9d605b9a303c4f0cffaca993e30280c1b2f55ededa677595492800c234",
                    "full": _RUNTIME_HASH,
                },
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


def _build_update_zip(
    *,
    tmp_path: Path,
    runtime_fingerprint: str = _RUNTIME_HASH,
    requirements_fingerprint: str = _REQ_HASH,
    archive_name: str = "update.zip",
    payload_content: str = _NEW_VERSION_CONTENT,
    target_version: str = "1.0.1",
    minimum: str = "1.0.0",
    maximum: str | None = "1.1.0",
) -> Path:
    update_staging = tmp_path / f"{Path(archive_name).stem}_staging"
    update_staging.mkdir()

    new_version_py_rel = "app/src/frame_compare/version.py"
    payload_version_py = update_staging / "payload" / new_version_py_rel
    payload_version_py.parent.mkdir(parents=True)
    payload_version_py.write_text(payload_content, encoding="utf-8")

    file_sha256 = hashlib.sha256(payload_version_py.read_bytes()).hexdigest()
    manifest_data = {
        "schema_version": 2,
        "target_platform": "windows-x64",
        "to_app_version": target_version,
        "from_app_version_min": minimum,
        "from_app_version_max": maximum,
        "expected_requirements_lock_sha256": requirements_fingerprint,
        "expected_media_runtime_fingerprint": runtime_fingerprint,
        "signature_algorithm": "rsa-sha256-pkcs1",
        "signature_file": "update-manifest.sig",
        "payload_root": "payload",
        "files": [
            {
                "path": new_version_py_rel,
                "sha256": file_sha256,
                "bytes": payload_version_py.stat().st_size,
            }
        ],
    }
    manifest_path = update_staging / "update-manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    update_zip_path = tmp_path / archive_name
    with zipfile.ZipFile(
        update_zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
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
    record = json.loads((backups[0] / "backup.json").read_text(encoding="utf-8"))
    assert record == {
        "schema_version": 1,
        "app_version": "1.0.0",
        "files": [
            {
                "path": "version.py",
                "sha256": hashlib.sha256(_OLD_VERSION_CONTENT.encode()).hexdigest(),
                "bytes": len(_OLD_VERSION_CONTENT.encode()),
            }
        ],
    }
    assert not (backups[0] / "frame_compare/backup.json").exists()
    assert not (backups[0] / "frame_compare/compatibility.json").exists()
    assert backup_version_py.read_text(encoding="utf-8") == _OLD_VERSION_CONTENT
    assert json.loads((backups[0] / "compatibility.json").read_text(encoding="utf-8-sig")) == {
        "media_runtime_fingerprint": _RUNTIME_HASH,
        "requirements_lock_sha256": _REQ_HASH,
    }


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
def test_windows_portable_update_apply_e2e(
    tmp_path: Path, repo_root: Path, update_exe: str
) -> None:
    exe = update_exe

    private_key_path, public_key_xml = _generate_rsa_keypair(
        exe=exe,
        repo_root=repo_root,
        tmp_path=tmp_path,
    )

    bundle_dir, shim_update_ps1, state_dir = _setup_update_install(
        tmp_path=tmp_path,
        repo_root=repo_root,
        public_key_xml=public_key_xml,
    )
    external_generated_root = tmp_path / "external-generated-root"
    sentinel_run = external_generated_root / "Movie (2026)"
    (sentinel_run / "screenshots").mkdir(parents=True)
    (external_generated_root / "cache" / "analysis").mkdir(parents=True)
    (sentinel_run / "report.html").write_bytes(b"<html>update-sentinel</html>\x00")
    (sentinel_run / "screenshots" / "frame.png").write_bytes(b"PNG-UPDATE-SENTINEL\x00")
    (external_generated_root / "cache" / "analysis" / "clip.compframes").write_bytes(
        b"CACHE-UPDATE-SENTINEL\x00"
    )
    external_snapshot = _snapshot_bytes(external_generated_root)
    authored_generated = str(external_generated_root).replace("\\", "/")
    (state_dir / "config.toml").write_text(
        f'[paths]\ngenerated_dir = "{authored_generated}"\n', encoding="utf-8"
    )
    version_py = _write_mock_bundle(bundle_dir=bundle_dir)
    update_zip_path = _build_update_zip(tmp_path=tmp_path)

    unsigned_rejection = _apply_update(
        exe=exe,
        env=os.environ.copy(),
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=update_zip_path,
    )
    assert unsigned_rejection.returncode != 0
    assert "Canonical update-manifest.sig not found" in unsigned_rejection.stderr
    assert version_py.read_text(encoding="utf-8") == _OLD_VERSION_CONTENT
    assert not (bundle_dir / "app" / ".update_backups").exists()

    env = _sign_update_zip(
        exe=exe,
        repo_root=repo_root,
        update_zip_path=update_zip_path,
        private_key_path=private_key_path,
        expected_public_key_path=shim_update_ps1.parent / "update_public_key.xml",
    )

    installed_tree = bundle_dir / "app" / "src" / "frame_compare"
    original_snapshot = _snapshot_tree(installed_tree)

    bundle_launcher = bundle_dir / "frame-compare.ps1"
    original_launcher = bundle_launcher.read_text(encoding="utf-8")
    python_exe = bundle_dir / "python" / "python.exe"
    disabled_python_exe = python_exe.with_suffix(".disabled")
    bundle_launcher.write_text("exit 1\n", encoding="utf-8")
    python_exe.rename(disabled_python_exe)
    try:
        missing_version_rejection = _apply_update(
            exe=exe,
            env=env,
            bundle_dir=bundle_dir,
            shim_update_ps1=shim_update_ps1,
            update_zip_path=update_zip_path,
        )
    finally:
        disabled_python_exe.rename(python_exe)
        bundle_launcher.write_text(original_launcher, encoding="utf-8")
    assert missing_version_rejection.returncode != 0
    assert "Installed app version could not be determined" in missing_version_rejection.stderr
    assert _snapshot_tree(installed_tree) == original_snapshot
    assert not (bundle_dir / "app" / ".update_backups").exists()

    high_compression_zip = _build_update_zip(
        tmp_path=tmp_path,
        archive_name="high-compression.zip",
        payload_content=_NEW_VERSION_CONTENT + ("#" + ("A" * (1024 * 1024))),
    )
    _sign_update_zip(
        exe=exe,
        repo_root=repo_root,
        update_zip_path=high_compression_zip,
        private_key_path=private_key_path,
        expected_public_key_path=shim_update_ps1.parent / "update_public_key.xml",
    )
    high_compression_rejection = _apply_update(
        exe=exe,
        env=env,
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=high_compression_zip,
    )
    assert high_compression_rejection.returncode != 0
    assert "maximum compression ratio" in high_compression_rejection.stderr
    assert _snapshot_tree(installed_tree) == original_snapshot
    assert not (bundle_dir / "app" / ".update_backups").exists()

    runtime_mismatch_zip = _build_update_zip(
        tmp_path=tmp_path,
        runtime_fingerprint="f" * 64,
        archive_name="runtime-mismatch.zip",
    )
    _sign_update_zip(
        exe=exe,
        repo_root=repo_root,
        update_zip_path=runtime_mismatch_zip,
        private_key_path=private_key_path,
        expected_public_key_path=shim_update_ps1.parent / "update_public_key.xml",
    )
    runtime_rejection = _apply_update(
        exe=exe,
        env=env,
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=runtime_mismatch_zip,
    )
    assert runtime_rejection.returncode != 0
    runtime_output = runtime_rejection.stdout + runtime_rejection.stderr
    assert "Media runtime fingerprint mismatch" in runtime_output
    assert "complete portable bundle" in runtime_output
    assert _snapshot_tree(installed_tree) == original_snapshot
    assert not (bundle_dir / "app" / ".update_backups").exists()
    assert _snapshot_bytes(external_generated_root) == external_snapshot

    dependency_mismatch_zip = _build_update_zip(
        tmp_path=tmp_path,
        requirements_fingerprint="e" * 64,
        archive_name="dependency-mismatch.zip",
    )
    _sign_update_zip(
        exe=exe,
        repo_root=repo_root,
        update_zip_path=dependency_mismatch_zip,
        private_key_path=private_key_path,
        expected_public_key_path=shim_update_ps1.parent / "update_public_key.xml",
    )
    dependency_rejection = _apply_update(
        exe=exe,
        env=env,
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=dependency_mismatch_zip,
    )
    assert dependency_rejection.returncode != 0
    dependency_output = dependency_rejection.stdout + dependency_rejection.stderr
    assert "Dependency fingerprint mismatch; code-only update refused" in dependency_output
    assert "complete Windows portable bundle" in dependency_output
    assert _snapshot_tree(installed_tree) == original_snapshot
    assert not (bundle_dir / "app" / ".update_backups").exists()
    assert _snapshot_bytes(external_generated_root) == external_snapshot

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
    assert _snapshot_bytes(external_generated_root) == external_snapshot

    payload_tampered_zip = tmp_path / "payload-tampered.zip"
    _rewrite_zip_entry(
        source_zip=update_zip_path,
        target_zip=payload_tampered_zip,
        entry_name="payload/app/src/frame_compare/version.py",
        transform=lambda content: content.replace(b"1.0.1", b"9.9.9", 1),
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
    assert _snapshot_bytes(external_generated_root) == external_snapshot

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
    assert _snapshot_bytes(external_generated_root) == external_snapshot
    rollback = _run_update_command(
        exe=exe,
        env=env,
        shim_update_ps1=shim_update_ps1,
        args=["rollback", backup_id],
    )
    assert rollback.returncode == 0, f"stdout:\n{rollback.stdout}\n\nstderr:\n{rollback.stderr}"
    assert _snapshot_tree(installed_tree) == original_snapshot
    assert _snapshot_bytes(external_generated_root) == external_snapshot


@pytest.mark.integration
def test_windows_portable_update_refuses_pre_native_panel_bundle(
    tmp_path: Path, repo_root: Path, update_exe: str
) -> None:
    exe = update_exe

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
    bundle_info_path = bundle_dir / "bundle_info.json"
    bundle_info = json.loads(bundle_info_path.read_text(encoding="utf-8"))
    bundle_info["schema_version"] = 2
    bundle_info_path.write_text(json.dumps(bundle_info), encoding="utf-8")

    update_zip_path = _build_update_zip(tmp_path=tmp_path)
    env = _sign_update_zip(
        exe=exe,
        repo_root=repo_root,
        update_zip_path=update_zip_path,
        private_key_path=private_key_path,
        expected_public_key_path=shim_update_ps1.parent / "update_public_key.xml",
    )
    original_content = version_py.read_bytes()

    result = _apply_update(
        exe=exe,
        env=env,
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=update_zip_path,
    )

    assert result.returncode != 0
    normalized_output = (result.stdout + result.stderr).lower().replace("_", " ").replace("-", " ")
    assert "native vsview alignment panel capability" in normalized_output
    assert "bundle info schema version 3 required" in normalized_output
    assert "complete portable reinstall is required" in normalized_output
    assert version_py.read_bytes() == original_content
    assert not (bundle_dir / "app" / ".update_backups").exists()


@pytest.mark.integration
@pytest.mark.parametrize("invalid_value", [None, "not-a-sha256", "A" * 64])
def test_windows_portable_update_refuses_invalid_installed_runtime_identity(
    tmp_path: Path, repo_root: Path, invalid_value: str | None, update_exe: str
) -> None:
    exe = update_exe

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
    bundle_info_path = bundle_dir / "bundle_info.json"
    bundle_info = json.loads(bundle_info_path.read_text(encoding="utf-8"))
    if invalid_value is None:
        del bundle_info["media_runtime_fingerprint"]
    else:
        bundle_info["media_runtime_fingerprint"] = invalid_value
    bundle_info_path.write_text(json.dumps(bundle_info), encoding="utf-8")

    update_zip_path = _build_update_zip(tmp_path=tmp_path)
    env = _sign_update_zip(
        exe=exe,
        repo_root=repo_root,
        update_zip_path=update_zip_path,
        private_key_path=private_key_path,
        expected_public_key_path=shim_update_ps1.parent / "update_public_key.xml",
    )
    original_content = version_py.read_bytes()

    result = _apply_update(
        exe=exe,
        env=env,
        bundle_dir=bundle_dir,
        shim_update_ps1=shim_update_ps1,
        update_zip_path=update_zip_path,
    )

    assert result.returncode != 0
    normalized_output = (result.stdout + result.stderr).lower().replace("_", " ").replace("-", " ")
    assert "media runtime fingerprint" in normalized_output
    assert version_py.read_bytes() == original_content
    assert not (bundle_dir / "app" / ".update_backups").exists()


@pytest.mark.integration
@pytest.mark.parametrize(
    "identity", ["matching", "missing", "runtime", "requirements", "malformed"]
)
def test_windows_rollback_checks_backup_identity_without_mutating_on_refusal(
    tmp_path: Path, repo_root: Path, identity: str, update_exe: str
) -> None:
    exe = update_exe
    bundle_dir, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml=""
    )
    version_py = _write_mock_bundle(bundle_dir=bundle_dir)
    backup_id = "20261008000000"
    backup_parent = bundle_dir / "app" / ".update_backups" / backup_id
    backup_code = backup_parent / "frame_compare"
    backup_code.mkdir(parents=True)
    (backup_code / "version.py").write_text(_NEW_VERSION_CONTENT, encoding="utf-8")
    compatibility = {
        "media_runtime_fingerprint": _RUNTIME_HASH,
        "requirements_lock_sha256": _REQ_HASH,
    }
    if identity in ("runtime", "requirements"):
        key = "media_runtime_fingerprint" if identity == "runtime" else "requirements_lock_sha256"
        compatibility[key] = "f" * 64
    if identity != "missing":
        (backup_parent / "compatibility.json").write_text(
            "invalid json" if identity == "malformed" else json.dumps(compatibility),
            encoding="utf-8",
        )
    backup_file = backup_code / "version.py"
    (backup_parent / "backup.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "app_version": "1.0.1",
                "files": [
                    {
                        "path": "version.py",
                        "sha256": hashlib.sha256(backup_file.read_bytes()).hexdigest(),
                        "bytes": backup_file.stat().st_size,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    before = _snapshot_bytes(bundle_dir)
    listing = _run_update_command(
        exe=exe, env=os.environ.copy(), shim_update_ps1=updater, args=["list-backups"]
    )
    assert listing.returncode == 0, listing.stderr
    assert backup_id in listing.stdout
    assert ("unavailable:" in listing.stdout) == (identity != "matching")
    assert _snapshot_bytes(bundle_dir) == before

    rollback = _run_update_command(
        exe=exe, env=os.environ.copy(), shim_update_ps1=updater, args=["rollback", backup_id]
    )
    if identity == "matching":
        assert rollback.returncode == 0, rollback.stderr
        assert version_py.read_text(encoding="utf-8") == _NEW_VERSION_CONTENT
    else:
        assert rollback.returncode != 0
        assert "Rollback refused" in rollback.stdout + rollback.stderr
        assert _snapshot_bytes(bundle_dir) == before


def _complete_backup(bundle: Path, backup_id: str, version: str = "1.0.0") -> Path:
    parent = bundle / "app/.update_backups" / backup_id
    code = parent / "frame_compare"
    code.mkdir(parents=True)
    (code / "version.py").write_bytes(f'__version__ = "{version}"\n'.encode())
    (parent / "compatibility.json").write_text(
        json.dumps(
            {
                "requirements_lock_sha256": _REQ_HASH,
                "media_runtime_fingerprint": _RUNTIME_HASH,
            }
        ),
        encoding="utf-8",
    )
    payload = (code / "version.py").read_bytes()
    (parent / "backup.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "app_version": version,
                "files": [
                    {
                        "path": "version.py",
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return parent


def _run_updater_functions(
    exe: str, updater: Path, bundle: Path, body: str, **extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            exe,
            "-NoProfile",
            "-Command",
            "$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest; . $env:UPDATER; "
            + "try { "
            + body
            + " } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }",
        ],
        env=os.environ | {"UPDATER": str(updater), "BUNDLE": str(bundle)} | extra,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    ("installed", "target", "minimum", "maximum", "allowed"),
    [
        ("1.0.0rc1", "1.0.0rc2", "1.0.0", None, True),
        ("1.0.0rc2", "1.0.0", "1.0.0", None, True),
        ("1.0.0", "1.0.0rc2", "1.0.0", None, True),
        ("1.0.1", "1.0.0rc2", "1.0.0", None, True),
        ("1.0.0", "1.1.0rc1", "1.1.0", None, False),
        ("1.0.0rc2", "1.0.0rc3", "1.0.0rc1", "1.0.0rc2", True),
        ("invalid", "1.0.1", "1.0.0", None, False),
        ("1.0.0", "invalid", "1.0.0", None, False),
        ("1.0.0", "1.0.1", "invalid", None, False),
        ("1.0.0", "1.0.1", "1.0.0", "invalid", False),
        ("1.0.0", "1.0.1", "1.0.0", "", False),
    ],
)
def test_signed_update_version_admission(
    tmp_path: Path,
    repo_root: Path,
    update_exe: str,
    installed: str,
    target: str,
    minimum: str,
    maximum: str | None,
    allowed: bool,
) -> None:
    private, public = _generate_rsa_keypair(exe=update_exe, repo_root=repo_root, tmp_path=tmp_path)
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml=public
    )
    version_file = _write_mock_bundle(bundle_dir=bundle)
    version_file.write_text(f'__version__ = "{installed}"\n', encoding="utf-8")
    # A malformed reported installed version must not be rescued by an unrelated
    # host Python import in this generated bundle fixture.
    if installed == "invalid":
        (bundle / "python/python.exe").unlink()
    (bundle / "app/.update_lock").touch()
    before = _snapshot_bytes(bundle)
    archive = _build_update_zip(
        tmp_path=tmp_path,
        payload_content=f'__version__ = "{target}"\n',
        target_version=target,
        minimum=minimum,
        maximum=maximum,
    )
    env = _sign_update_zip(
        exe=update_exe,
        repo_root=repo_root,
        update_zip_path=archive,
        private_key_path=private,
        expected_public_key_path=updater.parent / "update_public_key.xml",
    )
    result = _apply_update(
        exe=update_exe, env=env, bundle_dir=bundle, shim_update_ps1=updater, update_zip_path=archive
    )
    if allowed:
        assert result.returncode == 0, result.stdout + result.stderr
        assert version_file.read_text(encoding="utf-8") == f'__version__ = "{target}"\n'
        backup = next((bundle / "app/.update_backups").iterdir())
        assert (
            json.loads((backup / "backup.json").read_text(encoding="utf-8"))["app_version"]
            == installed
        )
    else:
        assert result.returncode != 0
        assert any(
            marker in result.stdout + result.stderr
            for marker in ("Malformed", "outside supported range", "could not be determined")
        )
        assert _snapshot_bytes(bundle) == before
        assert not (bundle / "app/.update_backups").exists()


@pytest.mark.parametrize(("expected", "reported"), [("0.8.0", "0.8.0rc1"), ("1.0.1", "1.0.10")])
def test_signed_update_exact_smoke_mismatch_recovers(
    tmp_path: Path, repo_root: Path, update_exe: str, expected: str, reported: str
) -> None:
    private, public = _generate_rsa_keypair(exe=update_exe, repo_root=repo_root, tmp_path=tmp_path)
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml=public
    )
    version = _write_mock_bundle(bundle_dir=bundle)
    minimum = ".".join(expected.split(".")[:2]) + ".0"
    version.write_text(f'__version__ = "{minimum}"\n', encoding="utf-8")
    before = _snapshot_bytes(version.parent)
    archive = _build_update_zip(
        tmp_path=tmp_path,
        payload_content=f'__version__ = "{reported}"\n',
        target_version=expected,
        minimum=minimum,
        maximum=None,
    )
    env = _sign_update_zip(
        exe=update_exe,
        repo_root=repo_root,
        update_zip_path=archive,
        private_key_path=private,
        expected_public_key_path=updater.parent / "update_public_key.xml",
    )
    result = _apply_update(
        exe=update_exe, env=env, bundle_dir=bundle, shim_update_ps1=updater, update_zip_path=archive
    )
    assert result.returncode != 0
    assert f"expected version '{expected}', got '{reported}'" in result.stdout + result.stderr
    assert _snapshot_bytes(version.parent) == before
    failed = list(version.parent.parent.glob("frame_compare.failed-*"))
    assert len(failed) == 1
    assert (failed[0] / "version.py").read_text(encoding="utf-8") == f'__version__ = "{reported}"\n'
    assert not (bundle / "app/.frame_compare_replacement.json").exists()


@pytest.mark.parametrize("operation", ["apply", "rollback"])
@pytest.mark.parametrize(
    "state", ["staging", "promoting-before", "promoting-first", "promoting-both", "committed"]
)
def test_update_commands_repair_interrupted_journals(
    tmp_path: Path, repo_root: Path, update_exe: str, operation: str, state: str
) -> None:
    private, public = _generate_rsa_keypair(exe=update_exe, repo_root=repo_root, tmp_path=tmp_path)
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml=public
    )
    version = _write_mock_bundle(bundle_dir=bundle)
    before = _snapshot_bytes(version.parent)
    backup = _complete_backup(bundle, "20260101000000")
    target = version.parent
    new = target.with_name("frame_compare.new")
    old = target.with_name("frame_compare.old")
    if state in {"staging", "promoting-before", "promoting-first", "promoting-both"}:
        new.mkdir()
        (new / "version.py").write_text('__version__ = "2.2.2"\n', encoding="utf-8")
    if state in {"promoting-first", "promoting-both"}:
        target.rename(old)
    if state == "promoting-both":
        new.rename(target)
        for name in ("frame_compare.failed-20000101", "frame_compare.failed-20000102"):
            stale = target.parent / name
            stale.mkdir()
            (stale / "diagnostic").write_bytes(b"older failure")
    if state == "committed":
        old.mkdir()
        (old / "prior").write_bytes(b"previous committed tree")
    journal = bundle / "app/.frame_compare_replacement.json"
    journal.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operation": operation,
                "state": "promoting" if state.startswith("promoting") else state,
                "started_at": "2026-10-15T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    journal.with_suffix(".json.tmp").write_bytes(b"partial atomic journal write")
    # A real terminated owner leaves a fresh lock file beside the journal. The
    # next command must recover immediately, without an age threshold or removal.
    abandoned = _run_updater_functions(
        update_exe,
        updater,
        bundle,
        "$held = Acquire-UpdateLock $env:BUNDLE; [Environment]::Exit(17)",
    )
    assert abandoned.returncode == 17, abandoned.stdout + abandoned.stderr
    lock_path = bundle / "app/.update_lock"
    assert lock_path.is_file()
    if operation == "apply":
        archive = _build_update_zip(tmp_path=tmp_path)
        env = _sign_update_zip(
            exe=update_exe,
            repo_root=repo_root,
            update_zip_path=archive,
            private_key_path=private,
            expected_public_key_path=updater.parent / "update_public_key.xml",
        )
        result = _apply_update(
            exe=update_exe,
            env=env,
            bundle_dir=bundle,
            shim_update_ps1=updater,
            update_zip_path=archive,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert version.read_text(encoding="utf-8") == _NEW_VERSION_CONTENT
    else:
        result = _run_update_command(
            exe=update_exe,
            env=os.environ.copy(),
            shim_update_ps1=updater,
            args=["rollback", backup.name],
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert _snapshot_bytes(target) == before
    assert not journal.exists() and not journal.with_suffix(".json.tmp").exists()
    assert not new.exists() and not old.exists()
    assert lock_path.is_file()
    if state == "promoting-both":
        failed = list(target.parent.glob("frame_compare.failed-*"))
        assert (
            len(failed) == 1
            and (failed[0] / "version.py").read_text(encoding="utf-8") == '__version__ = "2.2.2"\n'
        )


@pytest.mark.parametrize("operation", ["apply", "rollback"])
@pytest.mark.parametrize("state", ["orphan-new", "orphan-old", "invalid-journal", "missing-both"])
def test_update_commands_refuse_unknown_replacement_state(
    tmp_path: Path, repo_root: Path, update_exe: str, operation: str, state: str
) -> None:
    private, public = _generate_rsa_keypair(exe=update_exe, repo_root=repo_root, tmp_path=tmp_path)
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml=public
    )
    version = _write_mock_bundle(bundle_dir=bundle)
    backup = _complete_backup(bundle, "20260101000000")
    if state.startswith("orphan"):
        path = version.parent.with_name("frame_compare." + state.split("-")[1])
        path.mkdir()
        (path / "sentinel").write_bytes(b"retain unknown tree")
    else:
        journal = {
            "schema_version": 1,
            "operation": operation,
            "state": "unknown" if state == "invalid-journal" else "promoting",
            "started_at": "2026-10-15T00:00:00Z",
        }
        (bundle / "app/.frame_compare_replacement.json").write_text(
            json.dumps(journal), encoding="utf-8"
        )
        if state == "missing-both":
            shutil.rmtree(version.parent)
    (bundle / "app/.update_lock").touch()
    before = _snapshot_bytes(bundle)
    if operation == "apply":
        archive = _build_update_zip(tmp_path=tmp_path)
        env = _sign_update_zip(
            exe=update_exe,
            repo_root=repo_root,
            update_zip_path=archive,
            private_key_path=private,
            expected_public_key_path=updater.parent / "update_public_key.xml",
        )
        result = _apply_update(
            exe=update_exe,
            env=env,
            bundle_dir=bundle,
            shim_update_ps1=updater,
            update_zip_path=archive,
        )
    else:
        result = _run_update_command(
            exe=update_exe,
            env=os.environ.copy(),
            shim_update_ps1=updater,
            args=["rollback", backup.name],
        )
    assert result.returncode != 0
    assert "Replacement recovery refused/failed" in result.stdout + result.stderr
    assert "frame_compare.old" in result.stdout + result.stderr
    assert "frame_compare.new" in result.stdout + result.stderr
    assert _snapshot_bytes(bundle) == before


@pytest.mark.parametrize("operation", ["apply", "rollback"])
@pytest.mark.parametrize(
    "failure",
    [
        "copy",
        "inventory",
        "size",
        "path-set",
        "wrong-path",
        "rename",
        "smoke",
        "launcher",
        "recovery",
    ],
)
def test_source_replacement_failure_keeps_current_or_recoverable_tree(
    tmp_path: Path, repo_root: Path, update_exe: str, operation: str, failure: str
) -> None:
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml="unused"
    )
    version = _write_mock_bundle(bundle_dir=bundle)
    before = _snapshot_bytes(version.parent)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    payload = _NEW_VERSION_CONTENT.encode()
    (candidate / "version.py").write_bytes(payload)
    inventory = [
        {"path": "version.py", "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    ]
    if failure == "inventory":
        inventory[0]["sha256"] = "0" * 64
    elif failure == "size":
        inventory[0]["bytes"] = len(payload) + 1
    elif failure == "path-set":
        (candidate / "unexpected.py").write_bytes(payload)
    elif failure == "wrong-path":
        (candidate / "version.py").rename(candidate / "other.py")
    elif failure == "launcher":
        (bundle / "frame-compare.ps1").write_text("exit 1\n", encoding="utf-8")
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    injection = {
        "copy": r"function Copy-DirectoryContents { param($SourceDir,$DestinationDir) Ensure-Directory $DestinationDir; Set-Content (Join-Path $DestinationDir 'partial') partial; throw 'injected stage copy failure' }; ",
        "inventory": "",
        "size": "",
        "path-set": "",
        "wrong-path": "",
        "launcher": "",
        "rename": r"function Invoke-WithRetry { param($Action,$Label) if ($Label -eq 'Rename .new into place') { throw 'injected promote failure' }; & $Action }; ",
        "smoke": r"function Invoke-SmokeCheck { throw 'injected smoke failure' }; ",
        "recovery": r"function Invoke-WithRetry { param($Action,$Label) if ($Label -eq 'Rename .new into place') { throw 'injected promote failure' }; if ($Label -eq 'Restore previous source tree') { throw 'injected recovery rename failure' }; & $Action }; ",
    }[failure]
    result = _run_updater_functions(
        update_exe,
        updater,
        bundle,
        injection
        + r"""
$inventoryData = Get-Content -LiteralPath $env:INVENTORY -Raw | ConvertFrom-Json
$inventory = @($inventoryData)
$held = $null
try {
  $held = Acquire-UpdateLock $env:BUNDLE
  Repair-InterruptedReplacement $env:BUNDLE
  Invoke-SourceTreeReplacement -BundlePath $env:BUNDLE -TargetDir (Join-Path $env:BUNDLE 'app/src/frame_compare') -CandidateDir $env:CANDIDATE -ExpectedInventory $inventory -ExpectedVersion '1.0.1' -Operation $env:OPERATION
} finally { Release-UpdateLock $held }
""",
        INVENTORY=str(inventory_path),
        CANDIDATE=str(candidate),
        OPERATION=operation,
    )
    assert result.returncode != 0
    expected = {
        "copy": "injected stage copy failure",
        "inventory": "Source inventory hash/size mismatch",
        "size": "Source inventory hash/size mismatch",
        "path-set": "Source inventory path-set mismatch",
        "wrong-path": "Unexpected source inventory path",
        "launcher": "Smoke check failed: frame-compare version exited with code 1",
        "rename": "injected promote failure",
        "smoke": "injected smoke failure",
        "recovery": "injected recovery rename failure",
    }[failure]
    assert expected in result.stdout + result.stderr
    journal = bundle / "app/.frame_compare_replacement.json"
    old = version.parent.with_name("frame_compare.old")
    new = version.parent.with_name("frame_compare.new")
    if failure == "recovery":
        assert not version.parent.exists() and _snapshot_bytes(old) == before
        assert new.exists() and journal.exists()
        assert "Retained paths:" in result.stdout + result.stderr
        repaired = _run_updater_functions(
            update_exe,
            updater,
            bundle,
            "$held = Acquire-UpdateLock $env:BUNDLE; try { Repair-InterruptedReplacement $env:BUNDLE } finally { Release-UpdateLock $held }",
        )
        assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    assert _snapshot_bytes(version.parent) == before
    assert not old.exists() and not new.exists() and not journal.exists()


@pytest.mark.parametrize(
    "mutation", ["missing", "malformed", "truncated", "bad-version", "unreadable"]
)
def test_incomplete_backups_are_unavailable_before_lock(
    tmp_path: Path, repo_root: Path, update_exe: str, mutation: str
) -> None:
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml="unused"
    )
    version = _write_mock_bundle(bundle_dir=bundle)
    backup = _complete_backup(bundle, "20260101000000", "1.0.1")
    record = backup / "backup.json"
    if mutation == "missing":
        record.unlink()
    elif mutation == "malformed":
        record.write_text("{", encoding="utf-8")
    elif mutation == "truncated":
        (backup / "frame_compare/version.py").write_bytes(b"truncated")
    elif mutation == "bad-version":
        parsed = json.loads(record.read_text(encoding="utf-8"))
        parsed["app_version"] = "1.0.0rc0"
        record.write_text(json.dumps(parsed), encoding="utf-8")
    before = _snapshot_bytes(bundle)
    result = _run_updater_functions(
        update_exe,
        updater,
        bundle,
        r"""
$held = $null
try {
  if ($env:MUTATION -eq 'unreadable') {
    $held = [IO.File]::Open((Join-Path $env:BACKUP 'frame_compare/version.py'), [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
  }
  Invoke-ListBackups $env:BUNDLE | Out-Null
  try { Invoke-Rollback $env:BUNDLE '20260101000000'; throw 'rollback unexpectedly succeeded' }
  catch {
    if ($_.Exception.Message -notlike 'Rollback refused:*') { throw }
    Write-Host $_.Exception.Message
  }
  if (Test-Path -LiteralPath (Join-Path $env:BUNDLE 'app/.update_lock')) { throw 'preflight created a lock' }
} finally { if ($null -ne $held) { $held.Dispose() } }
""",
        MUTATION=mutation,
        BACKUP=str(backup),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unavailable:" in result.stdout and "Rollback refused:" in result.stdout
    assert "completeness" in result.stdout
    assert _snapshot_bytes(bundle) == before
    assert version.read_text(encoding="utf-8") == _OLD_VERSION_CONTENT


@pytest.mark.parametrize("failure", ["collision", "copy", "verify"])
def test_backup_creation_refuses_collision_and_removes_partial_copy(
    tmp_path: Path, repo_root: Path, update_exe: str, failure: str
) -> None:
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml="unused"
    )
    version = _write_mock_bundle(bundle_dir=bundle)
    backup = bundle / "app/.update_backups/20260101000000"
    if failure == "collision":
        backup.mkdir(parents=True)
        (backup / "sentinel").write_bytes(b"occupied backup must survive")
    (bundle / "app/.update_lock").touch()
    before = _snapshot_bytes(bundle)
    injection = ""
    if failure == "copy":
        injection = r"""
function Copy-Item {
  param($LiteralPath,$Destination,[switch]$Recurse,[switch]$Force,$ErrorAction)
  [IO.Directory]::CreateDirectory($Destination) | Out-Null
  [IO.File]::WriteAllText((Join-Path $Destination 'partial'), 'partial copied data')
  throw 'injected backup copy failure'
}
"""
    if failure == "verify":
        injection = r"""
function Copy-Item {
  param($LiteralPath,$Destination,[switch]$Recurse,[switch]$Force,$ErrorAction)
  Microsoft.PowerShell.Management\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Recurse -Force -ErrorAction Stop
  [IO.File]::WriteAllText((Join-Path $Destination 'version.py'), 'truncated copy')
}
"""
    result = _run_updater_functions(
        update_exe,
        updater,
        bundle,
        injection
        + r"""
$lockInfo = $null
try {
  $lockInfo = Acquire-UpdateLock $env:BUNDLE
  $compatibility = Get-InstalledBundleCompatibilityContract $env:BUNDLE
  New-CompleteBackup -BundlePath $env:BUNDLE -TargetDir (Join-Path $env:BUNDLE 'app/src/frame_compare') -Compatibility $compatibility -Version '1.0.0' -BackupId '20260101000000'
} finally { Release-UpdateLock $lockInfo }
""",
    )
    assert result.returncode != 0
    expected = {
        "collision": "Backup id already exists",
        "copy": "injected backup copy failure",
        "verify": "Source inventory hash/size mismatch",
    }[failure]
    assert expected in result.stdout + result.stderr
    assert _snapshot_bytes(bundle) == before
    assert version.read_text(encoding="utf-8") == _OLD_VERSION_CONTENT
    assert backup.exists() == (failure == "collision")


def test_backup_retention_counts_only_complete_compatible_backups(
    tmp_path: Path, repo_root: Path, update_exe: str
) -> None:
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml="unused"
    )
    _write_mock_bundle(bundle_dir=bundle)
    complete = [_complete_backup(bundle, f"2026010{index}000000") for index in range(1, 8)]
    incomplete = _complete_backup(bundle, "20260201000000")
    (incomplete / "backup.json").unlink()
    invalid_identity = _complete_backup(bundle, "20260202000000")
    (invalid_identity / "compatibility.json").write_text("{", encoding="utf-8")
    result = _run_update_command(
        exe=update_exe, env=os.environ.copy(), shim_update_ps1=updater, args=["purge-backups"]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(path.name for path in (bundle / "app/.update_backups").iterdir()) == [
        path.name for path in complete[2:]
    ]
    assert (bundle / "app/.update_lock").is_file()


def test_backup_purge_respects_update_lock_owner(
    tmp_path: Path, repo_root: Path, update_exe: str
) -> None:
    bundle, updater, _ = _setup_update_install(
        tmp_path=tmp_path, repo_root=repo_root, public_key_xml="unused"
    )
    _write_mock_bundle(bundle_dir=bundle)
    _complete_backup(bundle, "20260101000000")
    (bundle / "app/.update_lock").touch()
    before = _snapshot_bytes(bundle)
    result = _run_updater_functions(
        update_exe,
        updater,
        bundle,
        r"""
$held = Acquire-UpdateLock $env:BUNDLE
try {
  try { Invoke-FrameCompareUpdate -ArgsValues @('purge-backups','--keep','0'); throw 'purge unexpectedly ran' }
  catch {
    if ($_.Exception.Message -notlike 'Another update appears to be running*') { throw }
    Write-Host 'purge refused while owner held lock'
  }
  if (!$held['stream'].CanWrite) { throw 'contender closed owner stream' }
} finally { Release-UpdateLock $held }
""",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "purge refused while owner held lock" in result.stdout
    assert _snapshot_bytes(bundle) == before
