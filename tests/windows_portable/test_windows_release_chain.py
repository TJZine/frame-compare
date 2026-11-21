from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest
from tools.windows_portable.portable_bundle import write_bundle


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class _Release:
    exe: str
    repo: Path
    input: Path
    sha: str
    requirements_sha: str
    private_key: str = field(repr=False)

    def run(
        self, script: str, *args: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                self.exe,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.repo / "tools/windows_portable" / script),
                *args,
            ],
            cwd=self.repo,
            env=os.environ | (env or {}),
            timeout=30,
            capture_output=True,
            text=True,
            check=False,
        )

    def stage(self, stage: str, output: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return self.run(
            "release_update.ps1",
            "-Stage",
            stage,
            "-ExpectedSha",
            self.sha,
            "-ReleaseTag",
            "v1.2.3-rc.1",
            "-InputDir",
            str(self.input),
            "-OutputDir",
            str(output),
            *args,
        )

    def verify(
        self, output: Path, *, require_authority: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return self.stage(
            "Verify",
            output,
            "-BundleDigest",
            _digest(self.input / "portable.zip"),
            "-UpdateDigest",
            _digest(self.input / "unsigned-update.zip"),
            "-RequirementsDigest",
            self.requirements_sha,
            "-RequirementsPath",
            str(self.input / "requirements.lock.txt"),
            *(("-RequirePortableAuthority",) if require_authority else ()),
        )


def _ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def _refused(result: subprocess.CompletedProcess[str], expected: str) -> None:
    assert result.returncode != 0
    # PowerShell's formatted error output wraps at the host width.
    assert expected in " ".join(result.stderr.replace("|", " ").split()), result.stderr


@pytest.fixture
def release_chain(repo_root: Path, tmp_path: Path) -> _Release:
    exe = shutil.which("pwsh")
    if exe is None:
        pytest.skip("PowerShell 7 unavailable for detached release chain")
    repo = tmp_path / "repo"
    source = repo / "src/frame_compare"
    source.mkdir(parents=True)
    (source / "__init__.py").write_bytes(b'__version__ = "1.2.3rc1"\n')
    (source / "empty.py").write_bytes(b"")
    (repo / "pyproject.toml").write_bytes(b'[project]\nversion = "1.2.3rc1"\n')
    owner = repo / "tools/windows_portable"
    owner.mkdir(parents=True)
    for filename in (
        "README.txt",
        "build_update.ps1",
        "install.cmd",
        "install.ps1",
        "portable_launchers.ps1",
        "portable_archive.py",
        "portable_bundle.py",
        "portable_runtime.py",
        "release_portable_authority.ps1",
        "release_update.ps1",
        "release_update_contract.ps1",
        "sign_verified_manifest.ps1",
        "uninstall.cmd",
        "uninstall.ps1",
        "update_manifest_bytes.ps1",
        "version_utils.ps1",
    ):
        shutil.copyfile(repo_root / "tools/windows_portable" / filename, owner / filename)
    shutil.copytree(repo_root / "tools/windows_portable/shim", owner / "shim")
    fingerprint = "a" * 64
    manifest_path = owner / "manifest.windows-x64.json"
    manifest_path.write_text(
        json.dumps({"bundle": {"runtime_fingerprints": {"full": fingerprint}}, "artifacts": []}),
        encoding="utf-8",
    )
    # Use an ephemeral keypair unrelated to the production key.
    keygen = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-Command",
            "$rsa = [Security.Cryptography.RSA]::Create(2048); "
            "try { $rsa.ToXmlString($false); $rsa.ToXmlString($true) } finally { $rsa.Dispose() }",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    public_key, private_key = keygen.stdout.splitlines()
    (owner / "update_public_key.xml").write_text(public_key, encoding="ascii")

    def git(*args: str) -> str:
        return subprocess.check_output(
            [
                "git",
                "-c",
                "core.hooksPath=.git/disabled-hooks",
                "-c",
                "core.autocrlf=false",
                "-c",
                "user.name=Release fixture",
                "-c",
                "user.email=release@example.invalid",
                *args,
            ],
            cwd=repo,
            timeout=10,
            text=True,
        ).strip()

    bundle = tmp_path / "frame-compare-portable-win-x64"
    shutil.copytree(source, bundle / "app/src/frame_compare")
    shutil.copytree(owner / "shim", bundle / "shim")
    shutil.copyfile(owner / "update_public_key.xml", bundle / "shim/update_public_key.xml")
    for filename in ("README.txt", "install.cmd", "install.ps1", "uninstall.cmd", "uninstall.ps1"):
        shutil.copyfile(owner / filename, bundle / filename)
    launch = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-Command",
            ". $env:PORTABLE_LAUNCHER_OWNER; Write-LauncherFiles $env:PORTABLE_FIXTURE",
        ],
        env=os.environ
        | {
            "PORTABLE_LAUNCHER_OWNER": str(owner / "portable_launchers.ps1"),
            "PORTABLE_FIXTURE": str(bundle),
        },
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _ok(launch)
    requirements = bundle / "requirements.lock.txt"
    requirements.write_bytes(b"package==1.0\n")
    requirements_sha = _digest(requirements)
    (bundle / "bundle_info.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "platform": "windows-x64",
                "bundle_kind": "full",
                "app_version": "1.2.3rc1",
                "requirements_lock_sha256": requirements_sha,
                "media_runtime_fingerprint": fingerprint,
                "media_runtime_fingerprints": {"full": fingerprint},
            }
        ),
        encoding="utf-8",
    )
    shutil.copyfile(manifest_path, bundle / "manifest.json")
    for filename in ("python/python.exe", "app/site-packages/fixture/native.pyd"):
        binary = bundle / filename
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"approved executable fixture\n")
    placeholder_sha = "0" * 40
    source_urls = bundle / "licenses/SOURCE_URLS.txt"
    source_urls.parent.mkdir()
    source_urls_template = (
        f"Frame Compare 1.2.3rc1 source ({placeholder_sha}): "
        f"https://github.com/TJZine/frame-compare/archive/{placeholder_sha}.tar.gz\n"
    )
    source_urls.write_bytes(source_urls_template.encode())
    source_urls_template_hash = _digest(source_urls)
    lock = repo / "uv.lock"
    lock.write_bytes(b"version = 1\n")
    directories = sorted(
        file.relative_to(bundle).as_posix() for file in bundle.rglob("*") if file.is_dir()
    )
    files = [
        {
            "path": file.relative_to(bundle).as_posix(),
            "bytes": file.stat().st_size,
            "sha256": _digest(file),
        }
        for file in sorted(bundle.rglob("*"))
        if file.is_file()
    ]
    inventory = {
        "schema_version": 2,
        "archive": {"files": files, "directories": directories},
        "manifest_artifacts": [],
        "licenses": [{"path": "licenses/SOURCE_URLS.txt", "sha256": source_urls_template_hash}],
        "bundle": {
            "commit_sha": placeholder_sha,
            "source_archive_url": f"https://github.com/TJZine/frame-compare/archive/{placeholder_sha}.tar.gz",
            "version": "1.2.3rc1",
            "requirements_lock_sha256": requirements_sha,
            "media_runtime_fingerprint": fingerprint,
            "media_runtime_fingerprints": {"full": fingerprint},
        },
    }
    inventory_template = json.dumps(inventory)
    # Keep the independent fixture tree outside the candidate input. Stub only
    # the expensive authenticated-input assembly in this PowerShell handoff test.
    (owner / "build_portable.ps1").write_text(
        r"""
param($OutDir, $CacheDir, $RequirementsPath, [switch]$AssemblyOnly, [switch]$RequireReleasePublicKey)
if (!$AssemblyOnly -or !$RequireReleasePublicKey) {
  throw "Expected the isolated authority mode."
}
$null = New-Item -ItemType Directory -Path $OutDir -Force
$source = Join-Path (Split-Path -Parent (Get-Location).Path) "frame-compare-portable-win-x64"
Get-ChildItem -LiteralPath $source -Force | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $OutDir -Recurse
}
""",
        encoding="utf-8",
    )
    git("init", "-q")
    git("config", "core.autocrlf", "false")
    git("add", ".")
    git("commit", "-qm", "Release fixture")
    sha = git("rev-parse", "HEAD")
    source_urls.write_bytes(source_urls_template.replace(placeholder_sha, sha).encode())
    (bundle / "bundle_inventory.json").write_text(
        inventory_template.replace(placeholder_sha, sha).replace(
            source_urls_template_hash, _digest(source_urls)
        ),
        encoding="utf-8",
    )
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    shutil.copyfile(requirements, inputs / "requirements.lock.txt")
    write_bundle(bundle, inputs / "portable.zip")
    release = _Release(exe, repo, inputs, sha, requirements_sha, private_key)
    _ok(
        release.run(
            "build_update.ps1",
            "-BundleDir",
            str(bundle),
            "-OutFile",
            str(inputs / "unsigned-update.zip"),
        )
    )
    return release


def test_windows_release_rejects_portable_zip_with_noncanonical_bytes(
    release_chain: _Release, tmp_path: Path
) -> None:
    _ok(release_chain.verify(tmp_path / "unsigned", require_authority=False))
    with ZipFile(release_chain.input / "portable.zip", "a") as candidate:
        candidate.comment = b"a" * 40
    output = tmp_path / "blocked"
    _refused(release_chain.verify(output), "differs from the independently rebuilt canonical bytes")
    assert not (output / "verification.json").exists()
    assert not (output / "verified-portable.zip").exists()


@pytest.mark.parametrize(
    ("member", "rehash"),
    [
        ("install.ps1", True),
        ("frame-compare.cmd", True),
        ("shim/frame-compare-update.ps1", True),
        ("shim/update_public_key.xml", True),
        ("python/python.exe", False),
        ("python/python.exe", True),
        ("app/site-packages/fixture/native.pyd", False),
        ("app/site-packages/fixture/native.pyd", True),
    ],
)
def test_windows_portable_rejects_substituted_executable_bytes(
    release_chain: _Release, tmp_path: Path, member: str, rehash: bool
) -> None:
    bundle_path = release_chain.input / "portable.zip"
    prefix = "frame-compare-portable-win-x64/"
    with ZipFile(bundle_path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    replaced = b"x" + entries[prefix + member][1:]
    entries[prefix + member] = replaced
    if rehash:
        inventory_path = prefix + "bundle_inventory.json"
        inventory = json.loads(entries[inventory_path])
        record = next(file for file in inventory["archive"]["files"] if file["path"] == member)
        record["sha256"] = hashlib.sha256(replaced).hexdigest()
        entries[inventory_path] = json.dumps(inventory).encode()
    with ZipFile(bundle_path, "w", ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    output = tmp_path / "rejected"
    _refused(release_chain.verify(output), "Portable member")
    assert not (output / "verification.json").exists()


@pytest.mark.parametrize(
    ("attack", "expected"),
    [
        ("extra-file", "Unexpected portable member"),
        ("missing-file", "omits independently derived files or directories"),
        ("colliding-file", "Case-colliding portable member"),
        ("reparse", "Unsafe or duplicate portable ZIP member"),
        ("inventory", "Unexpected portable member or wrong size"),
    ],
)
def test_windows_portable_rejects_incomplete_or_unsafe_archive_layout(
    release_chain: _Release, tmp_path: Path, attack: str, expected: str
) -> None:
    bundle_path = release_chain.input / "portable.zip"
    prefix = "frame-compare-portable-win-x64/"
    with ZipFile(bundle_path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    if attack == "extra-file":
        entries[prefix + "python/extra.dll"] = b"extra"
    elif attack == "missing-file":
        del entries[prefix + "python/python.exe"]
    elif attack == "colliding-file":
        entries[prefix + "python/Python.exe"] = b"collision"
    elif attack == "inventory":
        inventory_path = prefix + "bundle_inventory.json"
        inventory = json.loads(entries[inventory_path])
        inventory["source_build_install_scripts"] = ["forged"]
        entries[inventory_path] = json.dumps(inventory).encode()
    with ZipFile(bundle_path, "w", ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            if attack == "reparse" and name.endswith("/python.exe"):
                entry = ZipInfo(name)
                entry.external_attr = 0x400
                archive.writestr(entry, data)
            else:
                archive.writestr(name, data)
    _refused(release_chain.verify(tmp_path / "rejected"), expected)


def test_windows_detached_release_chain_and_digest_binding(
    release_chain: _Release, tmp_path: Path
) -> None:
    release = release_chain
    with ZipFile(release.input / "unsigned-update.zip", "a") as unsigned:
        unsigned.comment = b"untrusted producer metadata"
    verified = tmp_path / "verified"
    _ok(release.verify(verified))
    for name in (
        "manifest.json",
        "verification.json",
        "verified-portable.zip",
        "verified-update.zip",
    ):
        shutil.copyfile(verified / name, release.input / name)
    manifest = release.input / "manifest.json"
    receipt = release.input / "verification.json"
    receipt_data = json.loads(receipt.read_bytes())
    assert receipt_data["portable_reproduced"] is True
    receipt_data.update(portable_artifact_id="123", unsigned_update_artifact_id="456")
    receipt.write_text(json.dumps(receipt_data | {"portable_reproduced": False}), encoding="utf-8")
    _refused(
        release.stage(
            "PrepareSigning",
            tmp_path / "unreproduced",
            "-ManifestDigest",
            _digest(manifest),
            "-VerificationDigest",
            _digest(receipt),
        ),
        "Verification receipt does not bind this release and manifest",
    )
    receipt.write_text(json.dumps(receipt_data), encoding="utf-8")
    binding = ("-ManifestDigest", _digest(manifest), "-VerificationDigest", _digest(receipt))
    package_binding = (*binding, "-VerifiedBundleId", "123", "-VerifiedUpdateId", "456")
    approved = tmp_path / "approved"
    _ok(release.stage("PrepareSigning", approved, *binding))
    assert (approved / "manifest.json").read_bytes() == manifest.read_bytes()

    wrong_receipt = receipt.read_bytes()
    receipt.write_bytes(wrong_receipt + b" ")
    _refused(
        release.stage("PrepareSigning", tmp_path / "wrong-receipt", *binding),
        "Release input digest mismatch",
    )
    receipt.write_bytes(wrong_receipt)

    signature = release.input / "detached-signature.json"
    signing_args = (
        "-ManifestPath",
        str(approved / "manifest.json"),
        *binding,
        "-OutFile",
        str(signature),
    )
    _refused(
        release.run(
            "sign_verified_manifest.ps1",
            *signing_args,
            env={"WINDOWS_UPDATE_SIGNING_KEY_XML": "environment-only"},
        ),
        "The protected environment signing key is required",
    )
    assert not signature.exists()
    _ok(
        release.run(
            "sign_verified_manifest.ps1",
            *signing_args,
            env={"WINDOWS_UPDATE_SIGNING_KEY_XML": release.private_key},
        )
    )
    assets = tmp_path / "dist" / "release-assets"
    _ok(release.stage("Package", assets, *package_binding, "-SignatureDigest", _digest(signature)))
    portable = "frame-compare-portable-win-x64-v1.2.3-rc.1.zip"
    update = "frame-compare-update-win-x64-v1.2.3-rc.1.zip"
    assert {item.name for item in assets.iterdir()} == {
        portable,
        update,
        f"{portable}.sha256",
        f"{update}.sha256",
    }
    assert (assets / portable).read_bytes() == (
        release.input / "verified-portable.zip"
    ).read_bytes()
    _refused(
        release.stage(
            "Package",
            tmp_path / "bad-artifact-id",
            *binding,
            "-VerifiedBundleId",
            "124",
            "-VerifiedUpdateId",
            "456",
            "-SignatureDigest",
            _digest(signature),
        ),
        "Release input artifact IDs do not match",
    )
    for name in (portable, update):
        assert (assets / f"{name}.sha256").read_text(encoding="ascii").strip() == (
            f"{_digest(assets / name)}  {name}"
        )
    signed = json.loads(signature.read_text(encoding="utf-8"))
    with ZipFile(assets / update) as archive:
        assert archive.comment == b""
        assert archive.read("update-manifest.json") == manifest.read_bytes()
        assert archive.read("update-manifest.sig") == signed["signature"].encode("ascii")
        assert set(archive.namelist()) == {
            "update-manifest.json",
            "update-manifest.sig",
            "payload/app/src/frame_compare/__init__.py",
            "payload/app/src/frame_compare/empty.py",
        }
    original_signature = signed["signature"]
    signed["signature"] = ("A" if original_signature[0] != "A" else "B") + original_signature[1:]
    signature.write_text(json.dumps(signed), encoding="utf-8")
    _refused(
        release.stage(
            "Package",
            tmp_path / "bad-signature",
            *package_binding,
            "-SignatureDigest",
            _digest(signature),
        ),
        "Detached signature does not verify",
    )
    signed["signature"] = original_signature
    signed["verification_sha256"] = "0" * 64
    signature.write_text(json.dumps(signed), encoding="utf-8")
    _refused(
        release.stage(
            "Package",
            tmp_path / "bad-binding",
            *package_binding,
            "-SignatureDigest",
            _digest(signature),
        ),
        "Detached signature receipt does not bind",
    )


@pytest.mark.parametrize(
    ("attack", "expected"),
    [
        ("../escape.py", "must not contain traversal"),
        ("/absolute.py", "must be relative"),
        ("C:/drive.py", "must not contain a drive letter"),
        ("payload/stream.py:ads", "Unsafe ZIP entry path or type"),
        ("payload/CON.py", "Unsafe ZIP entry path or type"),
        ("payload/app/src/frame_compare/EMPTY.py", "duplicate entry name"),
        ("payload/app/src/frame_compare/empty.py", "duplicate entry name"),
        ("payload/app/src/frame_compare/extra.py", "Unexpected update ZIP entry"),
        ("payload/app/src/frame_compare/empty.py/child.py", "Unexpected update ZIP entry"),
        ("update-manifest.sig", "preexisting signature"),
        ("symlink", "Unsafe ZIP entry path or type"),
        ("reparse", "Unsafe ZIP entry path or type"),
        ("wrong-source", "ZIP source digest mismatch"),
        ("missing-source", "Update archive is missing required entries"),
        ("wrong-version", "Update manifest differs"),
        ("wrong-fingerprint", "Update manifest differs"),
        ("wrong-requirements", "Update manifest differs"),
        ("malformed-manifest", "Update manifest differs"),
        ("overlong-manifest", "update-manifest.json exceeds"),
        ("compression-bomb", "maximum compression ratio"),
        ("entry-count", "Update archive entry count"),
    ],
)
def test_windows_unsigned_verification_rejects_tampering(
    release_chain: _Release, tmp_path: Path, attack: str, expected: str
) -> None:
    update = release_chain.input / "unsigned-update.zip"
    with ZipFile(update) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    manifest = "update-manifest.json"
    source = "payload/app/src/frame_compare/__init__.py"
    if attack == "wrong-source":
        entries[source] = entries[source].replace(b"1.2.3", b"1.2.4")
    elif attack == "missing-source":
        del entries[source]
    elif attack == "wrong-version":
        entries[manifest] = entries[manifest].replace(b"1.2.3", b"1.2.4")
    elif attack == "wrong-fingerprint":
        entries[manifest] = entries[manifest].replace(b"a" * 64, b"b" * 64)
    elif attack == "wrong-requirements":
        entries[manifest] = entries[manifest].replace(
            release_chain.requirements_sha.encode("ascii"), b"0" * 64
        )
    elif attack == "malformed-manifest":
        entries[manifest] = b'{"schema_version":'
    elif attack == "overlong-manifest":
        entries[manifest] = b" " * (4 * 1024 * 1024 + 1)
    with ZipFile(update, "w", ZIP_STORED) as archive:
        for name, data in entries.items():
            if name == source and attack in {"symlink", "reparse"}:
                info = ZipInfo(name)
                info.external_attr = (stat.S_IFLNK << 16) if attack == "symlink" else 0x400
                archive.writestr(info, data)
            else:
                archive.writestr(name, data)
        if "/" in attack or attack == "update-manifest.sig":
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Duplicate name:")
                archive.writestr(attack, b"rogue")
        elif attack == "compression-bomb":
            archive.writestr("bomb", b" " * (1024 * 1024), compress_type=ZIP_DEFLATED)
        elif attack == "entry-count":
            for index in range(4096):
                archive.writestr(f"rogue/{index}", b"")
    output = tmp_path / "rejected"
    _refused(release_chain.verify(output), expected)
    assert not (output / "verification.json").exists()
