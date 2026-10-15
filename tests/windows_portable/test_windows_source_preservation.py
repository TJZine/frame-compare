"""Windows filesystem transaction proof, without downloads or the host installation."""

from __future__ import annotations

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
    # Old activation restores shims; the caller restores the exact original pointer bytes.
    (previous / "install.ps1").write_text("$global:LASTEXITCODE = 0")
    (owner / "build_portable.ps1").write_text(r"""
param($ManifestPath, $OutDir, $CacheDir, $RepoRoot)
if ($env:FAILURE -eq 'build') { throw 'injected build failure' }
if (Test-Path -LiteralPath $OutDir) { throw "occupied: $OutDir" }
New-Item -ItemType Directory -Path $OutDir | Out-Null
foreach ($name in @('config', 'comparison_videos')) { New-Item -ItemType Directory -Path (Join-Path $OutDir $name) | Out-Null }
if ($env:FAILURE -eq 'occupied-target') { Set-Content -LiteralPath (Join-Path $OutDir 'config/unexpected') -Value 'preserve new data' }
Set-Content -LiteralPath (Join-Path $OutDir 'bundle_info.json') -Value '{}'
Set-Content -LiteralPath (Join-Path $OutDir 'install.ps1') -Value @'
if ($env:FAILURE -eq 'before-pointer') { throw 'activation before pointer' }
$pointer = Join-Path $env:LOCALAPPDATA 'Programs/FrameCompare/state/config.json'
@{schema_version=1; install_type='portable_bundle'; bundle_path=$PSScriptRoot} | ConvertTo-Json | Set-Content -LiteralPath $pointer
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
    assert _snapshot(previous) == before
    assert pointer.read_bytes() == pointer_before
    for new in (script.parents[2] / "dist").glob("*"):
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
