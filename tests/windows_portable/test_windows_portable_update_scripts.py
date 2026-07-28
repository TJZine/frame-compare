from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from ._helpers import powershell_exe as _powershell_exe
from ._helpers import read_text_or_fail as _read_text_or_fail

_KEYGEN_TIMEOUT_SECONDS = 60.0


def _extract_powershell_function(script: str, name: str) -> str:
    match = re.search(rf"\bfunction\s+{re.escape(name)}\b", script)
    assert match is not None, f"Function not found: {name}"

    open_brace = script.find("{", match.end())
    assert open_brace >= 0, f"Function has no opening brace: {name}"

    depth = 0
    for index in range(open_brace, len(script)):
        char = script[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[match.start() : index + 1]
    raise AssertionError(f"Function has no matching closing brace: {name}")


def test_windows_portable_update_artifacts_exist(repo_root: Path) -> None:
    paths = [
        repo_root / "tools" / "windows_portable" / "update_manifest.schema.json",
        repo_root / "tools" / "windows_portable" / "bundle_info.schema.json",
        repo_root / "tools" / "windows_portable" / "update_public_key.xml",
        repo_root / "tools" / "windows_portable" / "build_update.ps1",
        repo_root / "tools" / "windows_portable" / "generate_update_keypair.ps1",
        repo_root / "tools" / "windows_portable" / "sign_update.ps1",
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1",
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.cmd",
    ]
    for path in paths:
        assert path.exists(), f"Required file not found: {path}"


def _run_keygen(
    *,
    exe: str,
    script: Path,
    public_path: Path,
    private_path: Path,
    replace_placeholder: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = [
        exe,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-PublicKeyPath",
        str(public_path),
        "-PrivateKeyPath",
        str(private_path),
        "-KeyId",
        "frame-compare-update-test-01",
        "-KeySize",
        "2048",
    ]
    if replace_placeholder:
        args.append("-ReplacePlaceholderPublicKey")
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=_KEYGEN_TIMEOUT_SECONDS,
    )


def _copy_keygen_owner(*, repo_root: Path, tmp_path: Path) -> tuple[Path, Path, Path]:
    copied_repo = tmp_path / "copied-repo"
    owner_dir = copied_repo / "tools" / "windows_portable"
    owner_dir.mkdir(parents=True)
    script = owner_dir / "generate_update_keypair.ps1"
    placeholder = owner_dir / "update_public_key.xml"
    shutil.copy2(
        repo_root / "tools" / "windows_portable" / "generate_update_keypair.ps1",
        script,
    )
    placeholder.write_text(
        "\n".join(
            [
                "<!--",
                "  key_id: REPLACE_WITH_RELEASE_KEY_ID",
                "  generated_at: REPLACE_WITH_UTC_DATE",
                "-->",
                "<RSAKeyValue>",
                "  <Modulus>AQAB</Modulus>",
                "  <Exponent>AQAB</Exponent>",
                "</RSAKeyValue>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return copied_repo, script, placeholder


@pytest.mark.integration
def test_windows_update_keygen_creates_redacted_compatible_keypair(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    public_path = tmp_path / "public.xml"
    private_path = tmp_path / "private.xml"
    script = repo_root / "tools" / "windows_portable" / "generate_update_keypair.ps1"
    proc = _run_keygen(
        exe=exe,
        script=script,
        public_path=public_path,
        private_path=private_path,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"

    public_text = public_path.read_text(encoding="utf-8")
    private_text = private_path.read_text(encoding="utf-8")
    assert "key_id: frame-compare-update-test-01" in public_text
    assert "generated_at:" in public_text
    assert public_text.count("<Modulus>") == 1
    assert public_text.count("<Exponent>") == 1
    for private_field in ("P", "Q", "DP", "DQ", "InverseQ", "D"):
        assert f"<{private_field}>" not in public_text
        assert f"<{private_field}>" in private_text

    combined_output = proc.stdout + proc.stderr
    assert private_text.strip() not in combined_output
    assert "<RSAKeyValue>" not in combined_output
    assert "<P>" not in combined_output
    assert "Public key fingerprint (SHA256 over XML):" in proc.stdout

    validator = repo_root / "tools" / "windows_portable" / "validate_update_public_key.ps1"
    validation = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(validator),
            "-PublicKeyPath",
            str(public_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    assert validation.returncode == 0, validation.stderr


@pytest.mark.integration
def test_windows_update_keygen_refuses_existing_outputs(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    script = repo_root / "tools" / "windows_portable" / "generate_update_keypair.ps1"
    public_path = tmp_path / "public.xml"
    private_path = tmp_path / "private.xml"
    private_path.write_text("sentinel", encoding="utf-8")
    private_refusal = _run_keygen(
        exe=exe,
        script=script,
        public_path=public_path,
        private_path=private_path,
    )
    assert private_refusal.returncode != 0
    assert "already exists" in private_refusal.stderr
    assert private_path.read_text(encoding="utf-8") == "sentinel"
    assert not public_path.exists()

    private_path.unlink()
    public_path.write_text("real-public-sentinel", encoding="utf-8")
    public_refusal = _run_keygen(
        exe=exe,
        script=script,
        public_path=public_path,
        private_path=private_path,
        replace_placeholder=True,
    )
    assert public_refusal.returncode != 0
    assert "known repository placeholder" in public_refusal.stderr
    assert public_path.read_text(encoding="utf-8") == "real-public-sentinel"
    assert not private_path.exists()


@pytest.mark.integration
def test_windows_update_keygen_rejects_repository_private_path(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    copied_repo, script, placeholder = _copy_keygen_owner(
        repo_root=repo_root,
        tmp_path=tmp_path,
    )
    private_path = copied_repo / "private.xml"
    before = placeholder.read_bytes()
    proc = _run_keygen(
        exe=exe,
        script=script,
        public_path=placeholder,
        private_path=private_path,
        replace_placeholder=True,
    )
    assert proc.returncode != 0
    assert "outside the repository" in proc.stderr
    assert placeholder.read_bytes() == before
    assert not private_path.exists()


@pytest.mark.integration
def test_windows_update_keygen_replaces_only_placeholder_once(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _copied_repo, script, placeholder = _copy_keygen_owner(
        repo_root=repo_root,
        tmp_path=tmp_path,
    )
    private_path = tmp_path / "private.xml"
    first = _run_keygen(
        exe=exe,
        script=script,
        public_path=placeholder,
        private_path=private_path,
        replace_placeholder=True,
    )
    assert first.returncode == 0, f"stdout:\n{first.stdout}\n\nstderr:\n{first.stderr}"
    public_after_first = placeholder.read_bytes()

    second_private = tmp_path / "private-2.xml"
    second = _run_keygen(
        exe=exe,
        script=script,
        public_path=placeholder,
        private_path=second_private,
        replace_placeholder=True,
    )
    assert second.returncode != 0
    assert "known repository placeholder" in second.stderr
    assert placeholder.read_bytes() == public_after_first
    assert not second_private.exists()


def test_windows_portable_update_manifest_schema_disallows_empty_from_app_version_max(
    repo_root: Path,
) -> None:
    schema_path = repo_root / "tools" / "windows_portable" / "update_manifest.schema.json"
    schema = json.loads(_read_text_or_fail(schema_path))
    assert schema.get("properties") is not None
    props = schema.get("properties", {})
    assert props.get("from_app_version_max") is not None
    max_schema = props.get("from_app_version_max", {})
    assert max_schema.get("oneOf") is not None
    branches = max_schema.get("oneOf", [])
    assert any(branch.get("type") == "null" for branch in branches)
    assert any(
        branch.get("type") == "string" and branch.get("minLength") == 1 for branch in branches
    )


def test_windows_portable_updater_compares_app_versions_as_versions(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    assert "function Test-StringInRange" in updater
    assert "System.Version" in updater


def test_windows_portable_updater_handles_stale_update_locks(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    assert "function Acquire-UpdateLock" in updater
    assert "LastWriteTimeUtc" in updater
    assert "FromHours" in updater or "FromMinutes" in updater


def test_windows_portable_updater_uses_native_path_helpers_for_pwsh_e2e(
    repo_root: Path,
) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    assert "function Join-PathParts" in updater
    assert "function Convert-RelativePathToNative" in updater
    assert 'Join-Path $BundlePath "app\\\\src\\\\frame_compare"' not in updater
    assert 'Join-Path $BundlePath "python\\\\python.exe"' not in updater
    assert 'Join-Path $BundlePath "app\\\\.update_lock"' not in updater


def test_windows_portable_updater_validates_rollback_backup_id_format_and_containment(
    repo_root: Path,
) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    body = _extract_powershell_function(updater, "Invoke-Rollback")
    assert r"^\d{14}$" in body
    assert "Get-SafeChildPath" in body
    assert "backup id" in body.lower()


def test_windows_portable_updater_always_clears_rsa_in_signature_verification(
    repo_root: Path,
) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    signature_fn = _extract_powershell_function(updater, "Verify-ManifestSignature")
    assert re.search(r"\bfinally\b", signature_fn)
    assert re.search(r"\$rsa\.Clear\(\)", signature_fn)


def test_windows_portable_build_update_validates_normalized_from_app_version_min(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_update.ps1"
    build_script = _read_text_or_fail(build_path)
    fn = _extract_powershell_function(build_script, "Get-FromVersionMin")
    assert re.search(r"\bthrow\b", fn)
    assert re.search(r"\[regex\]::Match\(", fn)


def test_windows_portable_build_update_add_file_to_zip_opens_entry_before_source(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_update.ps1"
    build_script = _read_text_or_fail(build_path)
    function_text = _extract_powershell_function(build_script, "Add-FileToZip")
    entry_open_idx = function_text.find("$entry.Open()")
    source_open_idx = function_text.find("OpenRead($SourceFile)")
    assert entry_open_idx >= 0
    assert source_open_idx >= 0
    assert entry_open_idx < source_open_idx


def test_windows_portable_build_update_manifest_entries_use_mutable_list(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_update.ps1"
    build_script = _read_text_or_fail(build_path)
    fn = _extract_powershell_function(build_script, "New-ManifestFiles")
    assert "System.Collections.Generic.List[object]" in fn
    assert re.search(r"\$entries\.Add\(", fn)


def test_windows_portable_build_update_hashes_staged_payload_files(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_update.ps1"
    build_script = _read_text_or_fail(build_path)
    fn = _extract_powershell_function(build_script, "New-ManifestFiles")
    assert re.search(
        r"Copy-Item\s+-LiteralPath\s+\$sourceFile\.FullName\s+-Destination\s+\$destFile",
        fn,
    )
    assert re.search(r"Get-FileHash\s+-LiteralPath\s+\$destFile\s+-Algorithm\s+SHA256", fn)


@pytest.mark.integration
def test_windows_portable_build_update_preserves_relative_paths_and_excludes_caches(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    fake_repo = tmp_path / "repo"
    package = fake_repo / "src" / "frame_compare"
    render = package / "render"
    cache = render / "__pycache__"
    cache.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "1.2.3"\n', encoding="utf-8")
    (render / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (cache / "module.cpython-313.pyc").write_bytes(b"cache")

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "bundle_info.json").write_text(
        json.dumps({"requirements_lock_sha256": "a" * 64}),
        encoding="utf-8",
    )
    update_zip = tmp_path / "update.zip"
    build_script = repo_root / "tools" / "windows_portable" / "build_update.ps1"
    result = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(build_script),
            "-BundleDir",
            str(bundle),
            "-RepoRoot",
            str(fake_repo),
            "-OutFile",
            str(update_zip),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"

    with zipfile.ZipFile(update_zip) as archive:
        names = sorted(archive.namelist())
        manifest = json.loads(archive.read("update-manifest.json"))
    assert names == [
        "payload/app/src/frame_compare/__init__.py",
        "payload/app/src/frame_compare/render/module.py",
        "update-manifest.json",
    ]
    assert [entry["path"] for entry in manifest["files"]] == [
        "app/src/frame_compare/__init__.py",
        "app/src/frame_compare/render/module.py",
    ]


def test_windows_portable_sign_update_avoids_private_key_path_cli_argument(repo_root: Path) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    assert "PrivateKeyXml" not in sign_script
    assert "SIGNING_KEY_XML_PATH" in sign_script
    assert "Read-Host" in sign_script
    assert "UserInteractive" in sign_script
    assert "IsInputRedirected" in sign_script


def test_windows_portable_update_signing_uses_cross_platform_rsa_import(
    repo_root: Path,
) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    updater = _read_text_or_fail(updater_path)

    for script in (sign_script, updater):
        assert "function New-RsaFromXml" in script
        assert "[System.Security.Cryptography.RSA]::Create()" in script
        assert "$rsa.ImportParameters($parameters)" in script
        assert "System.Security.Cryptography.RSACryptoServiceProvider" in script


def test_windows_portable_sign_update_fingerprints_public_key_only(repo_root: Path) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    assert "function Get-PublicRsaXml" in sign_script
    assert "$publicKeyText = Get-PublicRsaXml -KeyXmlText $privateKeyText" in sign_script
    assert "P>[" not in sign_script


def test_windows_portable_updater_restores_original_on_rename_failure(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    assert "Rename current frame_compare to .old" in updater
    assert "Rename .new into place" in updater
    assert "Restore .old after rename failure" in updater or "Rename failed; restoring" in updater


def test_windows_portable_updater_warns_when_installed_version_missing(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    assert "Get-BundleAppVersion" in updater
    assert "Write-Warning" in updater
    assert "skipping version range check" in updater.lower()


def test_windows_portable_updater_prefers_bundle_launcher_for_installed_version(
    repo_root: Path,
) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    assert "function Get-VersionFromCommandOutput" in updater
    assert '$bundleLauncher = Join-Path $BundlePath "frame-compare.ps1"' in updater
    assert "& $bundleLauncher version 2>&1" in updater
    assert "Get-VersionFromCommandOutput -OutputLines $launcherResult" in updater


def test_windows_portable_updater_finally_does_not_mask_exception(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    invoke_apply = _extract_powershell_function(updater, "Invoke-ApplyUpdate")
    assert "finally" in invoke_apply
    assert re.search(r"try\s*\{\s*Release-UpdateLock", invoke_apply)
    assert "Write-Warning" in invoke_apply


def test_windows_portable_updater_isolates_rename_recovery_cleanup_steps(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    body = _extract_powershell_function(updater, "Invoke-ApplyUpdate")
    assert "Rename failed; restoring original installation." in body
    assert "Cleanup step failed" in body
    assert re.search(
        r"try\s*\{\s*if \(Test-Path -LiteralPath \$targetDir\)\s*\{[\s\S]*?Remove partial target after rename failure",
        body,
        flags=re.DOTALL,
    )
    assert re.search(
        r"try\s*\{\s*if \(Test-Path -LiteralPath \$newDir\)\s*\{[\s\S]*?Remove \.new after rename failure",
        body,
        flags=re.DOTALL,
    )
    assert re.search(
        r"if \(Test-Path -LiteralPath \$oldDir\)\s*\{\s*try\s*\{[\s\S]*?Restore \.old after rename failure",
        body,
        flags=re.DOTALL,
    )
    assert re.search(
        r"try\s*\{[\s\S]*?Restore-FromBackup\s+-BackupDir\s+\$backupDir\s+-TargetDir\s+\$targetDir",
        body,
        flags=re.DOTALL,
    )


def test_windows_portable_updater_extract_zip_entry_disposes_streams_safely(
    repo_root: Path,
) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    body = _extract_powershell_function(updater, "Invoke-ApplyUpdate")
    assert "$stream = $entry.Open()" in body
    assert "$out = $null" in body
    assert re.search(r"try\s*\{\s*\$out = \[System\.IO\.File\]::Open\(", body, flags=re.DOTALL)
    assert re.search(r"if \(\$null -ne \$out\)\s*\{\s*\$out\.Dispose\(\)", body, flags=re.DOTALL)
    assert re.search(
        r"if \(\$null -ne \$stream\)\s*\{\s*\$stream\.Dispose\(\)", body, flags=re.DOTALL
    )


def test_windows_portable_sign_update_write_string_entry_disposes_writer(
    repo_root: Path,
) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    fn = _extract_powershell_function(sign_script, "Write-StringEntry")
    assert "finally" in fn
    assert re.search(r"\$writer\.Dispose\(\)", fn)
    assert not re.search(r"\$stream\.Dispose\(\)", fn)


def test_windows_portable_sign_update_disposes_rsa_in_finally(repo_root: Path) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    assert re.search(
        r"finally\s*\{[\s\S]*?if\s*\(\$null -ne \$rsa\)\s*\{[\s\S]*?\$rsa\.Clear\(\)[\s\S]*?\$rsa\.Dispose\(\)",
        sign_script,
        flags=re.DOTALL,
    )


def test_windows_portable_update_signature_uses_explicit_pkcs1_sha256(
    repo_root: Path,
) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    updater = _read_text_or_fail(updater_path)

    assert "function Sign-ManifestBytes" in sign_script
    assert "[System.Security.Cryptography.HashAlgorithmName]::SHA256" in sign_script
    assert "[System.Security.Cryptography.RSASignaturePadding]::Pkcs1" in sign_script
    assert "function Test-ManifestSignature" in updater
    assert "[System.Security.Cryptography.HashAlgorithmName]::SHA256" in updater
    assert "[System.Security.Cryptography.RSASignaturePadding]::Pkcs1" in updater


def test_windows_portable_sign_update_preserves_console_detection_error_context(
    repo_root: Path,
) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    assert "input cannot be read interactively" in sign_script
    assert "$_.Exception.Message" in sign_script
