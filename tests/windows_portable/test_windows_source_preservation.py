"""Windows filesystem transaction proof, without downloads or the host installation."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def pwsh() -> str:
    if os.name != "nt":
        pytest.skip("Windows filesystem semantics and PowerShell 7 required")
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell 7 not available")
    return executable


def _run(
    pwsh: str, command: str, root: Path, **environment: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [pwsh, "-NoProfile", "-Command", command],
        cwd=root,
        env=os.environ | {"LOCALAPPDATA": str(root / "appdata"), "NO_COLOR": "1"} | environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "scenario",
    [
        "occupied",
        "partial",
        "root",
        "repo",
        "ancestor",
        "cwd",
        "cache-parent",
        "cache-child",
        "manifest",
        "malformed",
        "missing",
        "destination",
        "destination-absolute",
        "destination-traversal",
        "destination-normalized-root",
        "manifest-version",
        "fingerprints",
        "reserved-failure",
    ],
)
def test_builder_preserves_existing_state(
    pwsh: str, tmp_path: Path, repo_root: Path, scenario: str
) -> None:
    owner = tmp_path / "repo/tools/windows_portable"
    owner.mkdir(parents=True)
    for name in (
        "build_portable.ps1",
        "version_utils.ps1",
        "path_safety.ps1",
        "manifest.schema.json",
    ):
        shutil.copyfile(repo_root / "tools/windows_portable" / name, owner / name)
        if name == "version_utils.ps1":
            (owner / "shim").mkdir(exist_ok=True)
            shutil.copyfile(
                repo_root / "tools/windows_portable/shim/frame-compare-version.ps1",
                owner / "shim/frame-compare-version.ps1",
            )
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text()
    )
    manifest_path = owner / "manifest.json"
    out = tmp_path / "repo/dist/new"
    cache = tmp_path / "cache"
    if scenario in {"occupied", "partial"}:
        out.mkdir(parents=True)
        (out / "sentinel").write_bytes(b"existing user data\x00")
    elif scenario == "root":
        out = Path(tmp_path.anchor)
    elif scenario == "repo":
        out = tmp_path / "repo"
    elif scenario == "ancestor":
        out = tmp_path
    elif scenario == "cwd":
        out = tmp_path / "working"
        out.mkdir()
    elif scenario == "cache-parent":
        cache = out / "cache"
    elif scenario == "cache-child":
        out = cache / "out"
    elif scenario == "manifest":
        out = owner / "out"
    elif scenario == "destination":
        manifest["artifacts"][0]["install"]["destination"] = "."
    elif scenario.startswith("destination-"):
        manifest["artifacts"][0]["install"]["destination"] = {
            "destination-absolute": str(tmp_path / "outside"),
            "destination-traversal": "../escape",
            "destination-normalized-root": "sub/..",
        }[scenario]
    elif scenario == "manifest-version":
        manifest["manifest_version"] = 1
    elif scenario == "fingerprints":
        del manifest["bundle"]["runtime_fingerprints"]
    manifest_path.write_text("{" if scenario == "malformed" else json.dumps(manifest))
    if scenario == "missing":
        manifest_path.unlink()
    # Execute the real Main with only the expensive download boundary failing.
    script = owner / "build_portable.ps1"
    source = script.read_text()
    source = (
        source.rsplit("Main", 1)[0]
        + '\nfunction Download-Artifact { throw "injected download failure" }\nMain\n'
    )
    script.write_text(source)
    before = _snapshot(tmp_path)
    result = _run(
        pwsh,
        "& $env:BUILD -ManifestPath $env:MANIFEST -OutDir $env:OUT -CacheDir $env:CACHE -RepoRoot $env:REPO",
        tmp_path,
        BUILD=str(script),
        MANIFEST=str(manifest_path),
        OUT=str(out),
        CACHE=str(cache),
        REPO=str(tmp_path / "repo"),
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert _snapshot(tmp_path) == before
    if scenario == "reserved-failure":
        assert "injected download failure" in result.stderr
        assert not out.exists()
    elif scenario in {"occupied", "partial"}:
        assert str(out) in result.stderr


@pytest.fixture
def source_fixture(tmp_path: Path, repo_root: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    owner = root / "tools/windows_portable"
    owner.mkdir(parents=True)
    for name in ("install-from-source.ps1", "path_safety.ps1"):
        shutil.copyfile(repo_root / "tools/windows_portable" / name, owner / name)
    shutil.copyfile(repo_root / "install.ps1", root / "install.ps1")
    (owner / "manifest.windows-x64.json").write_text("{}")
    previous = tmp_path / "previous"
    previous.mkdir()
    for name, payload in {
        "bundle_info.json": "{}",
        "runtime.dll": "runtime",
        "app/src/code.py": "code",
        "config/config.toml": "user config",
        "comparison_videos/x.mkv": "media",
        "generated/run/result": "result",
    }.items():
        path = previous / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload)
    pointer = tmp_path / "appdata/Programs/FrameCompare/state/config.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text(
        json.dumps(
            {"schema_version": 1, "install_type": "portable_bundle", "bundle_path": str(previous)}
        )
    )
    bin_dir = pointer.parent.parent / "bin"
    bin_dir.mkdir()
    for name in (
        "frame-compare.ps1",
        "frame-compare.cmd",
        "frame-compare-update.ps1",
        "frame-compare-version.ps1",
        "frame-compare-update.cmd",
        "update_public_key.xml",
    ):
        shim = previous / "shim" / name
        shim.parent.mkdir(exist_ok=True)
        shim.write_bytes(f"old {name}".encode())
        (bin_dir / name).write_bytes(shim.read_bytes())
    # Restoration must follow pointer repair AND data reversal. Reserializing the
    # pointer proves the source installer finally restores its exact byte snapshot.
    (previous / "install.ps1").write_text(r"""
$pointer = Join-Path $env:LOCALAPPDATA 'Programs/FrameCompare/state/config.json'
$active = Get-Content -LiteralPath $pointer -Raw | ConvertFrom-Json
if ($active.bundle_path -ne $PSScriptRoot) { throw 'shim restoration before pointer repair' }
foreach ($data in @('config/config.toml', 'comparison_videos/x.mkv', 'generated/run/result')) {
  if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot $data))) { throw 'shim restoration before data reversal' }
}
$bin = Join-Path $env:LOCALAPPDATA 'Programs/FrameCompare/bin'
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'shim') | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $bin -Force }
$active | ConvertTo-Json | Set-Content -LiteralPath $pointer
Add-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'activation-events') -Value 'previous-shims-restored'
$global:LASTEXITCODE = 0
""")
    (owner / "build_portable.ps1").write_text(r"""
param($ManifestPath, $OutDir, $CacheDir, $RepoRoot)
if ($env:FAILURE -eq 'build') { throw 'injected build failure' }
if (Test-Path -LiteralPath $OutDir) { throw "occupied: $OutDir" }
New-Item -ItemType Directory -Path $OutDir | Out-Null
foreach ($name in @('config', 'comparison_videos')) { New-Item -ItemType Directory -Path (Join-Path $OutDir $name) | Out-Null }
if ($env:FAILURE -eq 'occupied-target') { Set-Content -LiteralPath (Join-Path $OutDir 'config/unexpected') -Value 'preserve new data' }
Set-Content -LiteralPath (Join-Path $OutDir 'bundle_info.json') -Value '{}'
Set-Content -LiteralPath (Join-Path $OutDir 'install.ps1') -Value @'
$bin = Join-Path $env:LOCALAPPDATA 'Programs/FrameCompare/bin'
New-Item -ItemType Directory -Path $bin -Force | Out-Null
foreach ($name in @('frame-compare.ps1', 'frame-compare.cmd', 'frame-compare-update.ps1', 'frame-compare-version.ps1', 'frame-compare-update.cmd', 'update_public_key.xml')) {
  Set-Content -LiteralPath (Join-Path $bin $name) -Value "new $name"
}
Add-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'activation-events') -Value 'new-shims-written'
if ($env:FAILURE -eq 'before-pointer') { throw 'activation before pointer' }
$pointer = Join-Path $env:LOCALAPPDATA 'Programs/FrameCompare/state/config.json'
@{schema_version=1; install_type='portable_bundle'; bundle_path=$PSScriptRoot} | ConvertTo-Json | Set-Content -LiteralPath $pointer
Add-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'activation-events') -Value 'new-pointer-written'
if ($env:FAILURE -eq 'locked-pointer') {
  $global:lockedPointer = [IO.File]::Open($pointer, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
  throw 'activation locked pointer'
}
if ($env:FAILURE -eq 'after-pointer') { throw 'activation after pointer' }
$global:LASTEXITCODE = 0
'@
$global:LASTEXITCODE = 0
""")
    return owner / "install-from-source.ps1", previous, pointer


@pytest.mark.parametrize("policy", ["Move", "Leave"])
def test_source_install_moves_only_documented_data(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path], policy: str
) -> None:
    script, previous, pointer = source_fixture
    before = _snapshot(previous)
    result = _run(
        pwsh,
        "function uv {}; & $env:INSTALL -SkipSync -UserData $env:POLICY",
        tmp_path,
        INSTALL=str(script.parents[2] / "install.ps1"),
        POLICY=policy,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    new = Path(json.loads(pointer.read_text())["bundle_path"])
    assert new != previous
    assert new.name.startswith("frame-compare-portable-win-x64-") and new.name.endswith("Z")
    for relative, payload in before.items():
        is_data = relative.split("/")[0] in {"config", "comparison_videos", "generated"}
        assert (new if is_data and policy == "Move" else previous).joinpath(
            relative
        ).read_bytes() == payload
    if policy == "Move":
        assert not (previous / "config").exists()
    else:
        assert _snapshot(previous) == before
        assert "older AppData state config" in result.stdout + result.stderr


@pytest.mark.parametrize(
    "failure",
    ["build", "before-pointer", "after-pointer", "rename", "cross-volume", "occupied-target"],
)
def test_source_install_failure_restores_data_and_pointer(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path], failure: str
) -> None:
    script, previous, pointer = source_fixture
    before = _snapshot(previous)
    pointer_before = pointer.read_bytes()
    bin_before = _snapshot(pointer.parent.parent / "bin")
    if failure in {"rename", "cross-volume"}:
        # Inject the filesystem failure at the actual rename, after config moved.
        failing_folder = "config" if failure == "cross-volume" else "comparison_videos"
        injected_error = (
            "throw [ComponentModel.Win32Exception]::new(17, 'injected cross-volume failure')"
            if failure == "cross-volume"
            else "throw 'injected rename failure'"
        )
        source = script.read_text().replace(
            "[IO.Directory]::Move($folder.Source, $folder.Target)",
            f"if ($folder.Name -eq '{failing_folder}') {{ {injected_error} }}; [IO.Directory]::Move($folder.Source, $folder.Target)",
        )
        script.write_text(source)
    result = _run(
        pwsh,
        "function uv {}; & $env:INSTALL -SkipSync",
        tmp_path,
        INSTALL=str(script),
        FAILURE=failure,
    )
    assert result.returncode != 0
    expected_boundary = {
        "build": "injected build failure",
        "before-pointer": "activation before pointer",
        "after-pointer": "activation after pointer",
        "rename": "injected rename failure",
        "cross-volume": "injected cross-volume failure",
        "occupied-target": "New user folder is occupied",
    }[failure]
    assert expected_boundary in result.stdout + result.stderr
    assert _snapshot(previous) == before
    assert pointer.read_bytes() == pointer_before
    assert _snapshot(pointer.parent.parent / "bin") == bin_before
    candidates = list((script.parents[2] / "dist").glob("*"))
    assert len(candidates) == (0 if failure == "build" else 1)
    if failure in {"before-pointer", "after-pointer"}:
        events = (tmp_path / "appdata/activation-events").read_text().splitlines()
        assert events == (
            ["new-shims-written"]
            + (["new-pointer-written"] if failure == "after-pointer" else [])
            + ["previous-shims-restored"]
        )
    for new in candidates:
        if failure == "occupied-target":
            assert (new / "config/unexpected").read_text().strip() == "preserve new data"
        else:
            assert not list((new / "config").iterdir())
        assert not list((new / "comparison_videos").iterdir())
        assert not (new / "generated").exists()


@pytest.mark.parametrize(
    "pointer_kind",
    [
        "missing",
        "malformed",
        "stale",
        "no-info",
        "self",
        "nested-child",
        "nested-parent",
        "empty-data",
    ],
)
def test_source_install_pointer_edges(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path], pointer_kind: str
) -> None:
    script, previous, pointer = source_fixture
    out = script.parents[2] / "dist/explicit"
    if pointer_kind == "missing":
        pointer.unlink()
    elif pointer_kind == "malformed":
        pointer.write_text("{")
    elif pointer_kind == "stale":
        pointer.write_text(json.dumps({"bundle_path": str(tmp_path / "absent")}))
    elif pointer_kind == "no-info":
        (previous / "bundle_info.json").unlink()
    elif pointer_kind == "self":
        out = previous
    elif pointer_kind == "nested-child":
        out = previous / "new"
    elif pointer_kind == "nested-parent":
        out = tmp_path
    elif pointer_kind == "empty-data":
        for name in ("config", "comparison_videos", "generated"):
            shutil.rmtree(previous / name)
            (previous / name).mkdir()
    before = _snapshot(previous)
    result = _run(
        pwsh,
        "function uv {}; & $env:INSTALL -SkipSync -OutDir $env:OUT",
        tmp_path,
        INSTALL=str(script),
        OUT=str(out),
    )
    if pointer_kind in {"nested-child", "nested-parent", "self"}:
        assert result.returncode != 0
        if pointer_kind != "self":
            assert "must not nest" in result.stderr
        # A self pointer is absent for migration, but occupied output still refuses.
        assert _snapshot(previous) == before
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert Path(json.loads(pointer.read_text())["bundle_path"]) == out
        assert _snapshot(previous) == before
        if pointer_kind == "empty-data":
            assert (previous / "config").is_dir()


def test_source_install_repeat_uses_fresh_default(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path]
) -> None:
    script, previous, pointer = source_fixture
    first = _run(pwsh, "function uv {}; & $env:INSTALL -SkipSync", tmp_path, INSTALL=str(script))
    assert first.returncode == 0, first.stdout + first.stderr
    first_bundle = Path(json.loads(pointer.read_text())["bundle_path"])
    # UTC default names have second precision; move the real clock past that name.
    second = _run(
        pwsh,
        "Start-Sleep -Milliseconds 1100; function uv {}; & $env:INSTALL -SkipSync",
        tmp_path,
        INSTALL=str(script),
    )
    assert second.returncode == 0, second.stdout + second.stderr
    second_bundle = Path(json.loads(pointer.read_text())["bundle_path"])
    assert first_bundle != second_bundle
    assert first_bundle.is_dir() and previous.is_dir()
    assert (second_bundle / "config/config.toml").read_text() == "user config"


def test_builder_uses_committed_version_and_empty_workspace(
    pwsh: str, tmp_path: Path, repo_root: Path
) -> None:
    """Observe Main's assembled metadata/layout with native/download work stubbed."""
    if shutil.which("git") is None or shutil.which("tar") is None:
        pytest.skip("git and tar required for committed-source fixture")
    root = tmp_path / "repo"
    owner = root / "tools/windows_portable"
    owner.mkdir(parents=True)
    for name in (
        "build_portable.ps1",
        "version_utils.ps1",
        "path_safety.ps1",
        "manifest.schema.json",
        "manifest.windows-x64.json",
    ):
        shutil.copyfile(repo_root / "tools/windows_portable" / name, owner / name)
        if name == "version_utils.ps1":
            (owner / "shim").mkdir(exist_ok=True)
            shutil.copyfile(
                repo_root / "tools/windows_portable/shim/frame-compare-version.ps1",
                owner / "shim/frame-compare-version.ps1",
            )
    init = root / "src/frame_compare/__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text('__version__ = "1.2.3"\n')
    for arguments in (
        ["init"],
        ["add", "src"],
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
    ):
        subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)
    init.write_text('__version__ = "9.9.9"\n')
    script = owner / "build_portable.ps1"
    source = script.read_text().rsplit("Main", 1)[0]
    source += r"""
function Download-Artifact { return 'unused' }
function Install-Artifact {}
function Install-PythonDeps { param($BundleRoot) Set-Content -LiteralPath (Join-Path $BundleRoot 'requirements.lock.txt') -Value 'fixture dependencies' }
function Install-PythonWheelArtifacts {}
function Remove-UnusedQtWebEngineRuntime {}
function Configure-EmbeddedPython {}
function Assert-BundleRuntime {}
function Remove-PythonBytecodeCaches {}
function Write-LauncherFiles {}
function Copy-InstallerFiles {}
function Copy-Licenses {}
function Assert-RequiredPySideLicenseMetadata {}
function Write-BundleInventory {}
Main
"""
    script.write_text(source)
    out = root / "dist/new"
    result = _run(
        pwsh,
        "& $env:BUILD -OutDir $env:OUT -CacheDir $env:CACHE -RepoRoot $env:REPO",
        tmp_path,
        BUILD=str(script),
        OUT=str(out),
        CACHE=str(tmp_path / "cache"),
        REPO=str(root),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((out / "bundle_info.json").read_text())["app_version"] == "1.2.3"
    for name in ("config", "comparison_videos"):
        assert (out / name).is_dir()
        assert not list((out / name).iterdir())
    assert not (out / "screenshots").exists()


def test_source_install_reversal_failure_retains_and_reports_locations(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path]
) -> None:
    script, previous, pointer = source_fixture
    pointer_before = pointer.read_bytes()
    script.write_text(
        script.read_text().replace(
            "[IO.Directory]::Move($folder.Target, $folder.Source)",
            "throw 'injected reversal failure'",
        )
    )
    result = _run(
        pwsh,
        "function uv {}; & $env:INSTALL -SkipSync",
        tmp_path,
        INSTALL=str(script),
        FAILURE="after-pointer",
    )
    assert result.returncode != 0
    assert pointer.read_bytes() == pointer_before
    new = next((script.parents[2] / "dist").iterdir())
    for name in ("config", "comparison_videos", "generated"):
        assert (new / name).is_dir()
        assert not (previous / name).exists()
        assert str(new / name) in result.stdout + result.stderr
        assert str(previous / name) in result.stdout + result.stderr
    assert "Recovery stopped" in result.stdout + result.stderr
    assert "Recovery failed" in result.stderr


@pytest.mark.parametrize("failure", ["", "after-pointer"])
def test_source_install_refreshes_pointer_after_build(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path], failure: str
) -> None:
    script, previous, pointer = source_fixture
    activated_during_build = tmp_path / "activated-during-build"
    shutil.copytree(previous, activated_during_build)
    for name in ("config", "comparison_videos", "generated"):
        shutil.rmtree(activated_during_build / name)
    for shim in (activated_during_build / "shim").iterdir():
        shim.write_bytes(b"boundary bundle " + shim.name.encode())
    boundary_bytes = json.dumps(
        {
            "schema_version": 1,
            "install_type": "portable_bundle",
            "bundle_path": str(activated_during_build),
        },
        indent=4,
    ).encode()
    snapshot = tmp_path / "boundary-pointer.json"
    snapshot.write_bytes(boundary_bytes)
    builder = script.parent / "build_portable.ps1"
    builder.write_text(
        builder.read_text()
        + r"""
foreach ($name in @('config', 'comparison_videos', 'generated')) {
  [IO.Directory]::Move((Join-Path $env:ORIGINAL $name), (Join-Path $env:BOUNDARY_BUNDLE $name))
}
$statePointer = Join-Path $env:LOCALAPPDATA 'Programs/FrameCompare/state/config.json'
[IO.File]::WriteAllBytes($statePointer, [IO.File]::ReadAllBytes($env:BOUNDARY_POINTER))
Get-ChildItem -LiteralPath (Join-Path $env:BOUNDARY_BUNDLE 'shim') | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $env:LOCALAPPDATA 'Programs/FrameCompare/bin') -Force
}
Write-Host 'build-boundary activation completed'
"""
    )
    result = _run(
        pwsh,
        "function uv {}; & $env:INSTALL -SkipSync",
        tmp_path,
        INSTALL=str(script),
        FAILURE=failure,
        ORIGINAL=str(previous),
        BOUNDARY_BUNDLE=str(activated_during_build),
        BOUNDARY_POINTER=str(snapshot),
    )
    assert "build-boundary activation completed" in result.stdout
    candidates = list((script.parents[2] / "dist").iterdir())
    assert len(candidates) == 1
    candidate = candidates[0]
    if failure:
        assert result.returncode != 0
        assert "activation after pointer" in result.stdout + result.stderr
        assert pointer.read_bytes() == boundary_bytes
        destination = activated_during_build
        assert _snapshot(pointer.parent.parent / "bin") == _snapshot(
            activated_during_build / "shim"
        )
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert Path(json.loads(pointer.read_text())["bundle_path"]) == candidate
        destination = candidate
    for relative, payload in {
        "config/config.toml": "user config",
        "comparison_videos/x.mkv": "media",
        "generated/run/result": "result",
    }.items():
        assert (destination / relative).read_text() == payload
        assert not (previous / relative).exists()
    assert (previous / "runtime.dll").read_text() == "runtime"


@pytest.mark.parametrize("pointer_kind", ["drive-relative", "root-relative"])
def test_source_install_rejects_nonqualified_pointer_paths(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path], pointer_kind: str
) -> None:
    script, previous, pointer = source_fixture
    # Both spellings resolve to the real populated bundle in this process context.
    # They remain malformed persisted pointers and must never authorize migration.
    path = str(previous)
    malformed = (
        previous.drive + previous.name
        if pointer_kind == "drive-relative"
        else path[len(previous.drive) :]
    )
    pointer.write_text(
        json.dumps(
            {"schema_version": 1, "install_type": "portable_bundle", "bundle_path": malformed}
        )
    )
    before = _snapshot(previous)
    result = _run(pwsh, "function uv {}; & $env:INSTALL -SkipSync", tmp_path, INSTALL=str(script))
    assert result.returncode == 0, result.stdout + result.stderr
    assert _snapshot(previous) == before
    candidate = Path(json.loads(pointer.read_text())["bundle_path"])
    assert candidate != previous
    assert not list((candidate / "config").iterdir())


def test_source_install_locked_pointer_still_reports_every_recovery_location(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path]
) -> None:
    script, previous, pointer = source_fixture
    result = _run(
        pwsh,
        "function uv {}; & $env:INSTALL -SkipSync",
        tmp_path,
        INSTALL=str(script),
        FAILURE="locked-pointer",
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "activation locked pointer" in output
    assert "Recovery failed" in output and "Pointer contents unavailable" in output
    assert str(pointer) in output
    candidates = list((script.parents[2] / "dist").iterdir())
    assert len(candidates) == 1
    candidate = candidates[0]
    assert Path(json.loads(pointer.read_text())["bundle_path"]) == candidate
    for name in ("config", "comparison_videos", "generated"):
        assert str(previous / name) in output and str(candidate / name) in output
        assert (candidate / name).is_dir() and not (previous / name).exists()


def test_source_install_owns_activation_until_recovery_or_commit(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path]
) -> None:
    import time

    script, previous, pointer = source_fixture
    pointer_before = pointer.read_bytes()
    marker = pointer.parent / "source-migration.pending.json"
    script.write_text(
        script.read_text().replace(
            'Write-Host "Installing shim from built bundle..."',
            r'''if ($env:HOLD_ACTIVATION -eq '1') {
  Set-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'activation-held') -Value 'ready'
  $deadline = [DateTime]::UtcNow.AddSeconds(15)
  while (!(Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'activation-release'))) {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'activation hold timed out' }
    Start-Sleep -Milliseconds 50
  }
}
Write-Host "Installing shim from built bundle..."''',
        )
    )
    first_out = script.parents[2] / "dist/first"
    second_out = script.parents[2] / "dist/second"
    environment = os.environ | {
        "LOCALAPPDATA": str(tmp_path / "appdata"),
        "INSTALL": str(script),
        "OUT": str(first_out),
        "HOLD_ACTIVATION": "1",
    }
    first = subprocess.Popen(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            "function uv {}; & $env:INSTALL -SkipSync -OutDir $env:OUT",
        ],
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready = tmp_path / "appdata/activation-held"
        deadline = time.monotonic() + 10
        while not ready.exists() and first.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "first installer did not reach the held post-migration boundary"
        assert marker.exists()
        marker_payload = json.loads(marker.read_text())
        assert marker_payload["previous_bundle"] == str(previous)
        assert marker_payload["candidate_bundle"] == str(first_out)
        assert marker_payload["pointer_bytes_base64"] == base64.b64encode(pointer_before).decode()
        assert {
            (folder["name"], Path(folder["source"]), Path(folder["target"]))
            for folder in marker_payload["folders"]
        } == {
            (name, previous / name, first_out / name)
            for name in ("config", "comparison_videos", "generated")
        }
        second = _run(
            pwsh,
            "function uv {}; & $env:INSTALL -SkipSync -OutDir $env:OUT",
            tmp_path,
            INSTALL=str(script),
            OUT=str(second_out),
            HOLD_ACTIVATION="",
        )
        assert second.returncode != 0
        assert "Cannot own source-install activation lock" in second.stdout + second.stderr
        assert Path(json.loads(pointer.read_text())["bundle_path"]) == previous
        assert (first_out / "config/config.toml").read_text() == "user config"
        assert not second_out.exists()
        first.kill()
        stdout, stderr = first.communicate(timeout=10)
        assert first.returncode != 0, stdout + stderr
        assert marker.exists()
        for name in ("config", "comparison_videos", "generated"):
            assert not (previous / name).exists()
            assert (first_out / name).exists()

        retry = _run(
            pwsh,
            "function uv {}; & $env:INSTALL -SkipSync -OutDir $env:OUT",
            tmp_path,
            INSTALL=str(script),
            OUT=str(second_out),
            HOLD_ACTIVATION="",
        )
        assert retry.returncode != 0
        output = retry.stdout + retry.stderr
        assert "pending source migration" in output
        assert "migration was not committed" in output
        assert "Move back manually" in output
        assert str(previous) in output and str(first_out) in output
        for name in ("config", "comparison_videos", "generated"):
            assert str(previous / name) in output and str(first_out / name) in output
        assert not second_out.exists()
        assert pointer.read_bytes() == pointer_before
        assert marker.exists()

        # This is the manual repair the refused retry instructs the user to perform.
        for name in ("config", "comparison_videos", "generated"):
            if (first_out / name).exists():
                (first_out / name).rename(previous / name)
        marker.unlink()

        # An occupied leftover lock file is reusable after its owning handle closes.
        third = _run(
            pwsh,
            "function uv {}; & $env:INSTALL -SkipSync -OutDir $env:OUT",
            tmp_path,
            INSTALL=str(script),
            OUT=str(script.parents[2] / "dist/third"),
            HOLD_ACTIVATION="",
            FAILURE="",
        )
        assert third.returncode == 0, third.stdout + third.stderr
    finally:
        if first.poll() is None:
            first.kill()
        first.communicate(timeout=5)


@pytest.mark.parametrize("boundary", ["after-commit", "before-first-move", "conflicting-target"])
def test_source_install_refusal_reports_interrupted_migration_state(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path], boundary: str
) -> None:
    import time

    script, previous, pointer = source_fixture
    pointer_before = pointer.read_bytes()
    marker = pointer.parent / "source-migration.pending.json"
    first_out = script.parents[2] / "dist/first"
    second_out = script.parents[2] / "dist/second"
    anchor = (
        "    $succeeded = $true"
        if boundary == "after-commit"
        else "          try { [IO.Directory]::Move($folder.Source, $folder.Target) }"
    )
    hold = r"""
if ($env:HOLD_ACTIVATION -eq '1' -and !$script:migrationHeld) {
  $script:migrationHeld = $true
  Set-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'activation-held') -Value 'ready'
  $deadline = [DateTime]::UtcNow.AddSeconds(15)
  while (!(Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'activation-release'))) {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'migration hold timed out' }
    Start-Sleep -Milliseconds 50
  }
}
"""
    source = script.read_text()
    assert source.count(anchor) == 1
    replacement = anchor + hold if boundary == "after-commit" else hold + anchor
    script.write_text(
        source.replace(
            '$ErrorActionPreference = "Stop"',
            '$ErrorActionPreference = "Stop"\n$script:migrationHeld = $false',
            1,
        ).replace(anchor, replacement, 1)
    )
    environment = os.environ | {
        "LOCALAPPDATA": str(tmp_path / "appdata"),
        "INSTALL": str(script),
        "OUT": str(first_out),
        "HOLD_ACTIVATION": "1",
        "FAILURE": "",
        "NO_COLOR": "1",
    }
    first = subprocess.Popen(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            "function uv {}; & $env:INSTALL -SkipSync -OutDir $env:OUT",
        ],
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    sentinels = {
        "config/config.toml": "user config",
        "comparison_videos/x.mkv": "media",
        "generated/run/result": "result",
    }
    try:
        ready = tmp_path / "appdata/activation-held"
        deadline = time.monotonic() + 10
        while not ready.exists() and first.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), f"installer did not reach {boundary}"
        assert marker.exists()
        if boundary == "conflicting-target":
            target = first_out / "config"
            target.mkdir(exist_ok=True)
            (target / "conflicting-user-data").write_text("keep both copies")
        first.kill()
        stdout, stderr = first.communicate(timeout=10)
        assert first.returncode != 0, stdout + stderr
        if boundary == "after-commit":
            assert Path(json.loads(pointer.read_text())["bundle_path"]) == first_out
            data_root = first_out
            for name in ("config", "comparison_videos", "generated"):
                assert not (previous / name).exists()
        else:
            assert pointer.read_bytes() == pointer_before
            data_root = previous
            # The real builder's still-empty placeholder is an unmoved folder.
            assert (first_out / "comparison_videos").is_dir()
            assert not list((first_out / "comparison_videos").iterdir())
        for relative, payload in sentinels.items():
            assert (data_root / relative).read_text() == payload
        before = _snapshot(tmp_path)

        retry = _run(
            pwsh,
            "function uv {}; & $env:INSTALL -SkipSync -OutDir $env:OUT",
            tmp_path,
            INSTALL=str(script),
            OUT=str(second_out),
            HOLD_ACTIVATION="",
            FAILURE="",
        )

        assert retry.returncode != 0
        output = (retry.stdout + retry.stderr).lower()
        assert "pending source migration" in output
        assert "move back" not in output
        assert str(marker).lower() in output
        if boundary == "after-commit":
            assert "migration completed" in output
            assert str(first_out).lower() in output
            assert "safe to delete" in output
        elif boundary == "before-first-move":
            assert "not committed" in output
            assert "no folder moved" in output
            assert "already in place" in output
            assert "safe to delete" in output
        else:
            assert "migration state conflict" in output
            assert "current pointer value" in output
            assert "do not move anything" in output
            assert "safe to delete" not in output
            for name in ("config", "comparison_videos", "generated"):
                assert str(previous / name).lower() in output
                assert str(first_out / name).lower() in output
        assert not second_out.exists()
        assert marker.exists()
        assert _snapshot(tmp_path) == before
    finally:
        if first.poll() is None:
            first.kill()
        first.communicate(timeout=5)


def test_source_install_pipeline_stop_reverses_data_and_removes_marker(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path]
) -> None:
    script, previous, pointer = source_fixture
    before = _snapshot(previous)
    pointer_before = pointer.read_bytes()
    script.write_text(
        script.read_text().replace(
            'Write-Host "Installing shim from built bundle..."',
            "throw [System.Management.Automation.PipelineStoppedException]::new()",
        )
    )
    result = _run(
        pwsh,
        "function uv {}; & $env:INSTALL -SkipSync",
        tmp_path,
        INSTALL=str(script),
    )
    assert result.returncode != 0
    assert _snapshot(previous) == before
    assert pointer.read_bytes() == pointer_before
    assert not (pointer.parent / "source-migration.pending.json").exists()
    candidate = next((script.parents[2] / "dist").iterdir())
    for name in ("config", "comparison_videos"):
        assert (previous / name).exists()
        assert (candidate / name).is_dir()
        assert not list((candidate / name).iterdir())
    assert not (candidate / "generated").exists()


def _junction(pwsh: str, root: Path, alias: Path, target: Path) -> None:
    alias.parent.mkdir(parents=True, exist_ok=True)
    result = _run(
        pwsh,
        "New-Item -ItemType Junction -Path $env:ALIAS -Target $env:TARGET | Out-Null",
        root,
        ALIAS=str(alias),
        TARGET=str(target),
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "alias_role",
    ["output-cache", "output-repo", "output-manifest", "output-cwd", "cache", "manifest"],
)
def test_builder_refuses_junction_ancestry_before_mutation(
    pwsh: str, tmp_path: Path, repo_root: Path, alias_role: str
) -> None:
    root = tmp_path / "repo"
    owner = root / "tools/windows_portable"
    owner.mkdir(parents=True)
    for name in (
        "build_portable.ps1",
        "version_utils.ps1",
        "path_safety.ps1",
        "manifest.windows-x64.json",
    ):
        shutil.copyfile(repo_root / "tools/windows_portable" / name, owner / name)
        if name == "version_utils.ps1":
            (owner / "shim").mkdir(exist_ok=True)
            shutil.copyfile(
                repo_root / "tools/windows_portable/shim/frame-compare-version.ps1",
                owner / "shim/frame-compare-version.ps1",
            )
    cache = tmp_path / "cache"
    cache.mkdir()
    sentinel = cache / "sentinel"
    sentinel.write_bytes(b"cache contents")
    out = root / "dist/new"
    alias = root / "dist/linked"
    manifest = owner / "manifest.windows-x64.json"
    if alias_role.startswith("output-"):
        target = {
            "output-cache": cache,
            "output-repo": root,
            "output-manifest": owner,
            "output-cwd": tmp_path,
        }[alias_role]
        _junction(pwsh, tmp_path, alias, target)
        out = alias / "new"
    elif alias_role == "cache":
        _junction(pwsh, tmp_path, alias, cache)
        cache = alias
    else:
        _junction(pwsh, tmp_path, alias, owner)
        manifest = alias / "manifest.windows-x64.json"
    result = _run(
        pwsh,
        "& $env:BUILD -ManifestPath $env:MANIFEST -OutDir $env:OUT -CacheDir $env:CACHE -RepoRoot $env:REPO",
        tmp_path,
        BUILD=str(owner / "build_portable.ps1"),
        MANIFEST=str(manifest),
        OUT=str(out),
        CACHE=str(cache),
        REPO=str(root),
    )
    assert result.returncode != 0
    assert "reparse-point ancestor" in result.stdout + result.stderr
    assert not out.exists()
    assert sentinel.read_bytes() == b"cache contents"


@pytest.mark.parametrize("alias_role", ["new-output", "previous-pointer"])
def test_source_install_refuses_junction_aliases_into_previous_bundle(
    pwsh: str, tmp_path: Path, source_fixture: tuple[Path, Path, Path], alias_role: str
) -> None:
    script, previous, pointer = source_fixture
    alias = script.parents[2] / "dist/linked"
    out = script.parents[2] / "dist/new"
    if alias_role == "new-output":
        _junction(pwsh, tmp_path, alias, previous / "generated")
        out = alias / "new"
    else:
        _junction(pwsh, tmp_path, alias, previous)
        pointer.write_text(
            json.dumps(
                {"schema_version": 1, "install_type": "portable_bundle", "bundle_path": str(alias)}
            )
        )
    before = _snapshot(previous)
    pointer_before = pointer.read_bytes()
    result = _run(
        pwsh,
        "function uv {}; & $env:INSTALL -SkipSync -OutDir $env:OUT",
        tmp_path,
        INSTALL=str(script),
        OUT=str(out),
        FAILURE="",
    )
    assert result.returncode != 0
    assert "reparse-point ancestor" in result.stdout + result.stderr
    assert not out.exists()
    assert _snapshot(previous) == before and pointer.read_bytes() == pointer_before


@pytest.mark.parametrize("interpreter", ["pwsh", "powershell"])
@pytest.mark.parametrize("ownership", ["refuse", "borrow", "own"])
def test_bundle_activation_coordinates_with_source_install_lock(
    tmp_path: Path, repo_root: Path, interpreter: str, ownership: str
) -> None:
    if os.name != "nt":
        pytest.skip("Windows bundle activation semantics required")
    executable = shutil.which(interpreter)
    if executable is None:
        pytest.skip(f"{interpreter} not available")
    bundle = tmp_path / "bundlé"
    (bundle / "shim").mkdir(parents=True)
    (bundle / "frame-compare.ps1").write_text("# launcher")
    names = (
        "frame-compare.ps1",
        "frame-compare.cmd",
        "frame-compare-update.ps1",
        "frame-compare-version.ps1",
        "frame-compare-update.cmd",
        "update_public_key.xml",
    )
    for name in names:
        (bundle / "shim" / name).write_bytes(f"candidate {name}".encode())
    installer = bundle / "install.ps1"
    source = (repo_root / "tools/windows_portable/install.ps1").read_text()
    # Stop after real shim/pointer writes, before any user PATH registry operation.
    installer.write_text(
        source.replace(
            "$portableConfigToml = Join-Path",
            "throw 'activation boundary reached'\n  $portableConfigToml = Join-Path",
        )
    )
    state = tmp_path / "appdata/Programs/FrameCompare/state"
    state.mkdir(parents=True)
    pointer = state / "config.json"
    pointer.write_text('{"old":true}')
    bin_dir = state.parent / "bin"
    bin_dir.mkdir()
    for name in names:
        (bin_dir / name).write_bytes(b"old shim")
    before = _snapshot(bin_dir)
    result = _run(
        executable,
        r"""
$held = $null
if ($env:OWNERSHIP -ne 'own') {
  $held = [IO.File]::Open($env:LOCK, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
}
try {
  try {
    if ($env:OWNERSHIP -eq 'borrow') { & $env:INSTALL -ActivationLock $held }
    else { & $env:INSTALL }
    throw 'installer unexpectedly completed'
  } catch { Write-Host $_.Exception.Message }
  if ($null -eq $held) {
    $probe = [IO.File]::Open($env:LOCK, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $probe.Dispose()
    Write-Host 'owned-lock-released'
  } else {
  if (!$held.CanWrite) { throw 'installer closed caller-owned activation lock' }
  $probe = $null
  try { $probe = [IO.File]::Open($env:LOCK, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None) }
  catch [IO.IOException] { Write-Host 'borrowed-lock-retained' }
  if ($null -ne $probe) { $probe.Dispose(); throw 'activation lock was released early' }
  }
} finally { if ($null -ne $held) { $held.Dispose() } }
""",
        tmp_path,
        INSTALL=str(installer),
        LOCK=str(state / "source-install.lock"),
        OWNERSHIP=ownership,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "owned-lock-released" if ownership == "own" else "borrowed-lock-retained"
    ) in result.stdout
    if ownership != "refuse":
        assert not pointer.read_bytes().startswith(b"\xef\xbb\xbf")
        assert "activation boundary reached" in result.stdout
        assert Path(json.loads(pointer.read_text(encoding="utf-8-sig"))["bundle_path"]) == bundle
        assert _snapshot(bin_dir) == _snapshot(bundle / "shim")
    else:
        assert "Cannot own source-install activation lock" in result.stdout
        assert _snapshot(bin_dir) == before and pointer.read_text() == '{"old":true}'
