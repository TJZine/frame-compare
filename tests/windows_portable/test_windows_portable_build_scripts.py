from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from frame_compare.vs import tonemap_runtime

from ._helpers import normalized_process_output as _normalized_process_output
from ._helpers import read_text_or_fail as _read_text_or_fail


def _bundle_runtime_function_block(build_script: str) -> str:
    start = build_script.index("function Assert-BundleRuntime")
    end = build_script.index("function Remove-PythonBytecodeCaches")
    return build_script[start:end]


def _runtime_proof_source(repo_root: Path) -> str:
    return _read_text_or_fail(repo_root / "tools/windows_portable/runtime_smoke.py")


def _generated_portable_launcher(repo_root: Path) -> str:
    launcher_source = _read_text_or_fail(
        repo_root / "tools/windows_portable/portable_launchers.ps1"
    )
    match = re.search(
        r"\$ps1 = @'\r?\n(?P<launcher>.*?)\r?\n'@\r?\n\r?\n  \$cmd = @'",
        launcher_source,
        flags=re.DOTALL,
    )
    assert match is not None, "generated portable launcher payload not found"
    return match.group("launcher")


def test_windows_portable_bundle_launcher_uses_cli_package_entry(repo_root: Path) -> None:
    launcher = _generated_portable_launcher(repo_root)
    assert "& $python -m frame_compare.cli.entry @args" in launcher
    assert "frame_compare.cli_entry" not in launcher


def test_windows_portable_generated_cmd_launchers_have_absolute_powershell_fallbacks(
    repo_root: Path,
) -> None:
    build_script = _read_text_or_fail(repo_root / "tools/windows_portable/portable_launchers.ps1")

    assert "%ProgramFiles%\\PowerShell\\7\\pwsh.exe" in build_script
    assert "%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" in build_script
    assert '"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File' in build_script
    launcher = build_script.split("$cmd = @'", 1)[1].split("'@", 1)[0]
    assert 'set "POWERSHELL_EXE="' in launcher


@pytest.mark.skipif(os.name != "nt", reason="Windows CMD required")
def test_windows_portable_generated_cmd_launchers_select_script_and_propagate_exit(
    repo_root: Path, tmp_path: Path
) -> None:
    pwsh = shutil.which("pwsh.exe")
    if pwsh is None:
        pytest.skip("PowerShell 7 is required to generate portable launchers")
    bundle = tmp_path / "Media & Tools"
    bundle.mkdir()
    owner = repo_root / "tools/windows_portable/portable_launchers.ps1"
    system_root = Path(os.environ["SYSTEMROOT"])
    env = os.environ | {"LAUNCHER_SOURCE": str(owner), "BUNDLE": str(bundle)}
    subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            ". $env:LAUNCHER_SOURCE; Write-LauncherFiles -BundleRoot $env:BUNDLE",
        ],
        env=env,
        check=True,
        capture_output=True,
        timeout=30,
    )
    (bundle / "frame-compare.ps1").write_text(
        'Write-Output "frame-compare $($args[0]) $($PSVersionTable.PSEdition)"\nexit 23\n',
        encoding="ascii",
    )
    # Supply the same pwsh on PATH for the CMD's first discovery branch.
    env = env | {
        "PATH": os.pathsep.join((str(Path(pwsh).parent), str(system_root / "System32"))),
        "PATHEXT": ".EXE",
    }
    result = subprocess.run(
        [str(system_root / "System32/cmd.exe"), "/d", "/c", "frame-compare.cmd", "test-argument"],
        cwd=bundle,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 23, _normalized_process_output(result)
    assert result.stdout.strip() == "frame-compare test-argument Core"


def test_windows_portable_build_resolves_relative_paths_from_provider_location(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot, $currentLocation)" in build_script
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is required for the portable build regression")

    provider_root = tmp_path / "provider-root"
    process_root = tmp_path / "process-root"
    provider_root.mkdir()
    process_root.mkdir()
    environment = os.environ | {
        "FRAME_COMPARE_TEST_BUILD_SCRIPT": str(build_path),
        "FRAME_COMPARE_TEST_PROVIDER_ROOT": str(provider_root),
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    command = """
Set-Location -LiteralPath $env:FRAME_COMPARE_TEST_PROVIDER_ROOT
& $env:FRAME_COMPARE_TEST_BUILD_SCRIPT `
  -ManifestPath manifest.json `
  -OutDir relative-out `
  -CacheDir relative-cache `
  -RepoRoot relative-repo
"""

    result = subprocess.run(
        [pwsh, "-NoProfile", "-Command", command],
        cwd=process_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    output = _normalized_process_output(result)
    assert result.returncode != 0
    assert str(provider_root / "manifest.json") in output
    assert not (provider_root / "relative-out").exists()
    assert not (provider_root / "relative-cache").exists()
    assert not (process_root / "relative-out").exists()
    assert not (process_root / "relative-cache").exists()

    occupied = provider_root / "relative-out"
    occupied.mkdir()
    (occupied / "sentinel").write_bytes(b"preserve me")
    environment["FRAME_COMPARE_TEST_MANIFEST"] = str(
        repo_root / "tools/windows_portable/manifest.windows-x64.json"
    )
    result = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-Command",
            command.replace(
                "-ManifestPath manifest.json", "-ManifestPath $env:FRAME_COMPARE_TEST_MANIFEST"
            ),
        ],
        cwd=process_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = _normalized_process_output(result)
    assert result.returncode != 0
    assert str(occupied) in output
    assert str(provider_root / "relative-cache") in output
    assert (occupied / "sentinel").read_bytes() == b"preserve me"
    assert not (provider_root / "relative-cache").exists()


def test_windows_portable_installed_default_config_uses_generated_root_only(
    repo_root: Path,
) -> None:
    install_script = _read_text_or_fail(
        repo_root / "tools/windows_portable/portable_activation.ps1"
    )
    default_block_start = install_script.index('$defaultPortableConfigToml = @"')
    default_block_end = install_script.index('"@', default_block_start)
    default_config = install_script[default_block_start:default_block_end]

    assert 'generated_dir = "generated"' in default_config
    assert "screenshots_dir" not in default_config
    assert "use_run_folders" not in default_config
    assert "output_dir" not in default_config


def test_windows_portable_uninstall_does_not_manage_bundle_data(repo_root: Path) -> None:
    uninstall = _read_text_or_fail(repo_root / "tools/windows_portable/uninstall.ps1")
    assert "$installedFiles = $shimPaths + $pointerPaths" in uninstall
    assert '"config.json", "config.json.tmp"' in uninstall
    for name in ("config.toml", "comparison_videos", "generated", "-Recurse"):
        assert name not in uninstall


def test_windows_portable_ffmpeg_manifest_has_pinned_zip_asset_shape(
    repo_root: Path,
) -> None:
    manifest_path = repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json"
    manifest = json.loads(_read_text_or_fail(manifest_path))
    ffmpeg = next(
        artifact for artifact in manifest["artifacts"] if artifact["id"].startswith("ffmpeg-")
    )

    assert "autobuild-2026-05-25-14-02" not in ffmpeg["url"]
    assert "/releases/download/autobuild-" in ffmpeg["url"]
    assert ffmpeg["url"].endswith(".zip")
    assert len(ffmpeg["sha256"]) == 64
    assert ffmpeg["install"]["strip_prefix"].rstrip("/") in ffmpeg["url"]
    assert ffmpeg["license"]["spdx"] == "LGPL-2.1-or-later"


def test_windows_portable_manifest_tracks_coordinated_media_runtime_artifacts(
    repo_root: Path,
) -> None:
    manifest_path = repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json"
    manifest = json.loads(_read_text_or_fail(manifest_path))
    artifacts = {artifact["id"]: artifact for artifact in manifest["artifacts"]}

    assert manifest["manifest_version"] == 3
    assert manifest["bundle"]["vs_ref"] == "R82"
    assert manifest["bundle"]["ffmpeg_policy"] == "lgpl-only"
    assert set(manifest["bundle"]["runtime_fingerprints"]) == {
        "analysis",
        "probe",
        "alignment",
        "index",
        "full",
    }
    assert all(
        re.fullmatch(r"[a-f0-9]{64}", fingerprint)
        for fingerprint in manifest["bundle"]["runtime_fingerprints"].values()
    )

    expected_python_version = "3.15.2"
    assert manifest["bundle"]["python_version"] == expected_python_version
    python = artifacts["python-embed-amd64"]
    assert python["version"] == expected_python_version
    assert python["source_ref"] == expected_python_version
    assert python["release_date"] == "2026-10-25"
    assert python["url"] == (
        "https://www.python.org/ftp/python/3.15.2/python-3.15.2-embed-amd64.zip"
    )
    assert python["bytes"] == 13740486
    assert python["sha256"] == ("d012f3aa29cf07436dae8aea1fec0fd195c2612a0b059b1f915ae0afb9ad1f62")
    assert python["source_url"] == "https://www.python.org/ftp/python/3.15.2/Python-3.15.2.tgz"
    assert python["source_bytes"] == 35882840
    assert python["source_sha256"] == (
        "f74e1db0eabd651cd01e4e2a00201bd41866abe74869ab716f9bf33cbbaa0943"
    )

    vapoursynth = artifacts["vapoursynth-portable-r82"]
    assert vapoursynth["version"] == "R82"
    assert vapoursynth["url"].endswith("/R82/VapourSynth64-Portable-R82.zip")
    assert vapoursynth["source_ref"] == "R82"
    assert vapoursynth["source_commit"] == "e0fadcc1c8977e99b11ce2e478996a867a939874"
    assert vapoursynth["bytes"] == 31801679
    assert vapoursynth["sha256"] == (
        "f97ea50c4c9f778eeac4bc4e3e43f86fb3b71787371d06e584e0c47f396874ca"
    )
    assert vapoursynth["source_bytes"] == 1140334
    assert vapoursynth["source_sha256"] == (
        "d908d2c7a9278918658db0f2e3e46ac11c78cfb365d265616c41e648bc561900"
    )

    lsmas = artifacts["vs-plugin-lsmas-1310.0.0.0-win-amd64-wheel"]
    assert lsmas["version"] == "1310.0.0.0"
    assert lsmas["install"] == {"type": "python_wheel"}
    assert lsmas["url"].endswith("vapoursynth_lsmas-1310.0.0.0-py3-none-win_amd64.whl")
    assert lsmas["bytes"] == 11530241
    assert lsmas["sha256"] == ("8197e2c901ff7b9ac651a66819986bfd993767a0b656a8d11c8f5b53829d2f6b")
    assert lsmas["source_bytes"] == 19063403
    assert lsmas["source_sha256"] == (
        "d529128e2d13763cbb56c21f0fd534191380530de6042907cbdae366b23ba2e5"
    )
    assert lsmas["source_commit"] == "7e65185d3f08ba4ad191e9a5cbba3e2c6fd3bb67"

    placebo = artifacts["vs-plugin-vs-placebo-2.0.5-win-amd64-wheel"]
    assert placebo["version"] == "2.0.5"
    assert placebo["install"]["type"] == "python_wheel"
    assert placebo["url"].endswith("-win_amd64.whl")

    ffmpeg = artifacts["ffmpeg-btbn-win64-lgpl-8.1-2026-10-31"]
    assert ffmpeg["version"].startswith("n8.1.3-27-g8dca1586f4")
    assert ffmpeg["license"]["spdx"] == "LGPL-2.1-or-later"
    assert not any(artifact_id.startswith("ffms2") for artifact_id in artifacts)

    sources = {source["name"]: source for source in manifest["corresponding_sources"]}
    lsmash = sources["L-SMASH"]
    assert lsmash["source_commit"] == "d186eb95388710a7a91f6fd353169b457ebbb9db"
    assert lsmash["bytes"] == 503436
    assert lsmash["sha256"] == ("a58cf7fb8314d8422257b9f0a4cabe117aa2fb8a8488b4e9a31f4b6d05c8e00c")

    for artifact in (python, vapoursynth, lsmas, placebo, ffmpeg):
        assert artifact["bytes"] > 0
        assert re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"])
        assert artifact["source_bytes"] > 0
        assert re.fullmatch(r"[a-f0-9]{64}", artifact["source_sha256"])


def test_windows_portable_build_uses_r74_plus_plugin_layout(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    assert "$env:VAPOURSYNTH_EXTRA_PLUGIN_PATH =" not in build_script
    assert "Remove-Item Env:VAPOURSYNTH_EXTRA_PLUGIN_PATH" in build_script
    assert "Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue" in build_script
    assert '$sitePackages = Join-Path $BundleRoot "app\\\\site-packages"' in build_script
    assert '$vsPackage = Join-Path $sitePackages "vapoursynth"' in build_script
    assert '(Join-Path $vsPackage "plugins")' in build_script
    assert 'Join-Path $sitePackages "vapoursynth.dll"' not in build_script
    assert 'Join-Path $sitePackages "Lib\\\\site-packages\\\\vapoursynth.dll"' not in build_script
    assert "VAPOURSYNTH_PLUGIN_PATH =" not in build_script
    assert 'Join-Path $sitePackages "PySide6"' not in build_script
    assert 'Get-ChildItem -LiteralPath $sitePackages -Filter "*.dll" -File -Recurse' not in (
        build_script
    )
    assert (
        '$env:FRAME_COMPARE_FFMPEG_EXECUTABLE = "$BundleRoot\\ffmpeg\\bin\\ffmpeg.exe"'
        in build_script
    )
    runtime_function = build_script[
        build_script.index("function Set-BundleRuntimeEnvironment") : build_script.index(
            "function Get-ProcessEnvironmentValue"
        )
    ]
    assert "ffmpeg\\\\bin" not in runtime_function.split("$pathEntries = @(", 1)[1]


def test_windows_portable_manifest_pins_exact_vsview_windows_graph(repo_root: Path) -> None:
    manifest = json.loads(
        _read_text_or_fail(repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json")
    )
    artifacts = {artifact["id"]: artifact for artifact in manifest["artifacts"]}
    expected = {
        "vsview-0.14.0-wheel": ("0.14.0", 2377037),
        "cyclopts-5.4.2-wheel": ("5.4.2", 300704),
        "pyside6-6.12.0-win-amd64-wheel": ("6.12.0", 578958),
        "pyside6-addons-6.12.0-win-amd64-wheel": ("6.12.0", 40522402),
        "pyside6-essentials-6.12.0-win-amd64-wheel": ("6.12.0", 82153795),
        "shiboken6-6.12.0-win-amd64-wheel": ("6.12.0", 1265476),
        "pyside6-pdf-6.12.0.140-win-amd64-wheel": ("6.12.0.140", 2983516),
        "pyside6-webengine-6.12.0.140-win-amd64-wheel": ("6.12.0.140", 131697708),
        "vapoursynth-bestsource-23-win-amd64-wheel": ("23", 16086999),
        "vspackrgb-2.0.0-win-amd64-wheel": ("2.0.0", 122797),
    }
    for artifact_id, (version, byte_count) in expected.items():
        artifact = artifacts[artifact_id]
        assert artifact["version"] == version
        assert artifact["bytes"] == byte_count
        assert artifact["install"] == {"type": "python_wheel"}
        assert re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"])
        assert artifact["source_bytes"] > 0
        assert re.fullmatch(r"[a-f0-9]{64}", artifact["source_sha256"])

    assert artifacts["pyside6-addons-6.12.0-win-amd64-wheel"]["license"]["files"]
    sources = {source["name"]: source for source in manifest["corresponding_sources"]}
    assert sources["Qt"]["version"] == "6.12.0"
    assert sources["Qt for Python"]["sha256"] == (
        "099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751"
    )
    pdf_source = sources["Qt PDF (Qt WebEngine source tree)"]
    assert pdf_source["version"] == "6.140.0"
    assert pdf_source["selection_kind"] == "commit"
    assert pdf_source["source_commit"] == "d505fc23640d2bd6345e6483eb73daf4e19f5829"
    assert pdf_source["sha256"] == (
        "141e9b230e5ec9ee65a7357ca4b87d702e4badc515289eeade1047a788bb96e7"
    )
    assert pdf_source["bytes"] == 584649116


def test_windows_qt_ffmpeg_pins_binary_source_recipe_and_build_registry(repo_root: Path) -> None:
    manifest = json.loads(
        _read_text_or_fail(repo_root / "tools/windows_portable/manifest.windows-x64.json")
    )
    (qt_ffmpeg,) = (
        artifact
        for artifact in manifest["artifacts"]
        if artifact["install"]["type"] == "qt_multimedia_ffmpeg"
    )
    assert qt_ffmpeg["id"] == "qt-multimedia-ffmpeg-9.1-win-x64"
    assert qt_ffmpeg["install"] == {"type": "qt_multimedia_ffmpeg"}
    assert qt_ffmpeg["version"] == "9.1"
    assert qt_ffmpeg["url"] == (
        "https://github.com/System233/ffmpeg-msvc-prebuilt/releases/download/"
        "ffmpeg-9.1/ffmpeg-9.1_x64-windows-shared-lgpl.zip"
    )
    assert qt_ffmpeg["bytes"] == 45526634
    assert qt_ffmpeg["sha256"] == "af02e8cc60d57fa3f668c579e65edf6586eb16c0f6c687532f9324cfd07f07d2"
    assert qt_ffmpeg["source_ref"] == "n9.1"
    assert qt_ffmpeg["source_commit"] == "74e4393595cf2b5857f0da925c4e0dd74ea306e5"
    assert qt_ffmpeg["source_url"] == "https://ffmpeg.org/releases/ffmpeg-9.1.tar.xz"
    assert qt_ffmpeg["source_bytes"] == 12557532
    assert qt_ffmpeg["source_sha256"] == (
        "1a4d394ae63d190a526cd052eb4415c156b5c5e2df37efab41a7de0b8fde2433"
    )
    assert qt_ffmpeg["build_source_commit"] == "7bd67a2dfc716f34e53849434e46a8c57c71884b"
    assert qt_ffmpeg["build_source_url"] == (
        "https://codeload.github.com/System233/ffmpeg-msvc-prebuilt/tar.gz/"
        "7bd67a2dfc716f34e53849434e46a8c57c71884b"
    )
    assert qt_ffmpeg["build_source_bytes"] == 230937
    assert qt_ffmpeg["build_source_sha256"] == (
        "816571843f901030625d30d1d52e1cffe374d2e76ade4bd8791e9cfa91265fe9"
    )
    assert qt_ffmpeg["license"]["spdx"] == "LGPL-3.0-or-later"
    (notice,) = qt_ffmpeg["license"]["files"]
    assert notice["path"] == "licenses/common/LGPL-3.0.txt"
    assert notice["sha256"] == "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768"

    registry = next(
        source
        for source in manifest["corresponding_sources"]
        if source["name"] == "vcpkg ports for the Qt Multimedia FFmpeg build"
    )
    assert registry["source_ref"] == "2026.06.01"
    assert registry["source_commit"] == "f3e10653cc27d62a37a3763cd84b38bca07c6075"
    assert registry["source_url"] == (
        "https://codeload.github.com/microsoft/vcpkg/tar.gz/f3e10653cc27d62a37a3763cd84b38bca07c6075"
    )
    assert registry["bytes"] == 5263899
    assert registry["sha256"] == "86f72c4ff5c853eb7f749e26bc7b8edf2bffaa5b959753d2685e96f9653b0fd5"


def test_windows_portable_vsview_artifacts_match_uv_lock(repo_root: Path) -> None:
    manifest = json.loads(
        _read_text_or_fail(repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json")
    )
    lock = tomllib.loads(_read_text_or_fail(repo_root / "uv.lock"))
    packages = {package["name"]: package for package in lock["package"]}
    artifact_ids = {
        "vsview": "vsview-0.14.0-wheel",
        "cyclopts": "cyclopts-5.4.2-wheel",
        "pyside6": "pyside6-6.12.0-win-amd64-wheel",
        "pyside6-addons": "pyside6-addons-6.12.0-win-amd64-wheel",
        "pyside6-essentials": "pyside6-essentials-6.12.0-win-amd64-wheel",
        "shiboken6": "shiboken6-6.12.0-win-amd64-wheel",
        "pyside6-pdf": "pyside6-pdf-6.12.0.140-win-amd64-wheel",
        "pyside6-webengine": "pyside6-webengine-6.12.0.140-win-amd64-wheel",
        "vapoursynth-bestsource": "vapoursynth-bestsource-23-win-amd64-wheel",
        "vspackrgb": "vspackrgb-2.0.0-win-amd64-wheel",
    }
    artifacts = {artifact["id"]: artifact for artifact in manifest["artifacts"]}
    for package_name, artifact_id in artifact_ids.items():
        package = packages[package_name]
        candidates = [
            wheel
            for wheel in package["wheels"]
            if (
                "win_amd64" in wheel["url"]
                and (package_name != "vspackrgb" or "cp312-abi3" in wheel["url"])
            )
            or package_name in {"vsview", "cyclopts"}
        ]
        assert len(candidates) == 1
        wheel = candidates[0]
        artifact = artifacts[artifact_id]
        assert artifact["url"] == wheel["url"]
        assert artifact["sha256"] == wheel["hash"].removeprefix("sha256:")
        assert artifact["bytes"] == wheel["size"]


@pytest.mark.parametrize(
    ("exit_code", "stderr", "error", "expected"),
    [
        (3221225477, b"\x1b[31mVK_ERROR_INCOMPATIBLE_DRIVER\x1b[0m", None, "unavailable"),
        (3221225477, b"Failed creating instance", None, "unavailable"),
        (1, b"VK_ERROR_INCOMPATIBLE_DRIVER", None, "probe failed"),
        (3221225477, b"unexpected access violation", None, "probe failed"),
        (1, b"filter error", None, "probe failed"),
        (None, b"", subprocess.TimeoutExpired("probe", 5), "probe failed"),
        (0, b"", None, "render failed"),
    ],
    ids=[
        "incompatible-driver",
        "instance-failure",
        "wrong-exit-code",
        "unexpected-crash",
        "filter-error",
        "timeout",
        "render-error",
    ],
)
def test_windows_portable_direct_placebo_smoke_respects_runtime_probe(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exit_code: int | None,
    stderr: bytes,
    error: subprocess.TimeoutExpired | None,
    expected: str,
) -> None:
    def run_probe(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if error is not None:
            raise error
        assert exit_code is not None
        return subprocess.CompletedProcess([], exit_code, b"", stderr)

    def fail_render(_frame: int) -> None:
        raise RuntimeError("render failed")

    def blank_clip(**_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(std=SimpleNamespace(SetFrameProps=lambda **_: object()))

    def tonemap(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(get_frame=fail_render)

    monkeypatch.setattr(tonemap_runtime, "run_subprocess", run_probe)
    monkeypatch.setitem(
        sys.modules,
        "vapoursynth",
        SimpleNamespace(
            core=SimpleNamespace(
                std=SimpleNamespace(BlankClip=blank_clip), placebo=SimpleNamespace(Tonemap=tonemap)
            ),
            RGB48=0,
        ),
    )
    smoke = repo_root / "tools/windows_portable/runtime_smoke.py"
    monkeypatch.setattr(sys, "argv", [str(smoke), "placebo_tonemap_frame", "fixture.mp4"])
    skip_receipt = "placebo_direct_frame=skipped reason=vulkan_runtime_unavailable"
    if expected == "unavailable":
        runpy.run_path(str(smoke))
        assert skip_receipt in capsys.readouterr().out
    else:
        with pytest.raises((AssertionError, RuntimeError), match=expected):
            runpy.run_path(str(smoke))
        assert skip_receipt not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("phase", "expected_proof"),
    (
        ("package_imports", "prove_package_imports"),
        ("runtime_contract", "prove_runtime_contract"),
        ("vapoursynth_environment", "prove_vapoursynth_environment"),
        ("lwlibavsource_frame", "prove_lwlibavsource"),
        ("vapoursynth_screenshot", "prove_vapoursynth_screenshot"),
        ("placebo_tonemap_api", "prove_placebo_tonemap_api"),
        ("apply_tonemap_frame", "prove_apply_tonemap_frame"),
        ("placebo_tonemap_frame", "prove_placebo_tonemap_frame"),
        ("vsview_runtime", "prove_vsview_runtime"),
        ("unknown", None),
    ),
)
def test_windows_portable_python_phase_dispatch_is_fail_closed(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    expected_proof: str | None,
) -> None:
    # Execute the real CLI dispatcher, replacing only platform proof bodies.
    tree = ast.parse(_runtime_proof_source(repo_root))
    namespace = {}
    calls = []

    def failing_proof(*args):
        calls.append(args)
        raise RuntimeError("native proof failed")

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            namespace[node.name] = failing_proof
    dispatcher = ast.Module(
        body=[node for node in tree.body if not isinstance(node, ast.FunctionDef)],
        type_ignores=[],
    )
    monkeypatch.setattr(sys, "argv", ["runtime-smoke.py", phase, "fixture.mp4"])
    if expected_proof is None:
        with pytest.raises(AssertionError, match="unknown runtime proof phase"):
            exec(compile(dispatcher, "runtime_smoke.py", "exec"), namespace)
        assert calls == []
    else:
        # Only the selected phase may run; its error must escape to PowerShell.
        for name in tuple(namespace):
            if name != expected_proof:
                del namespace[name]
        with pytest.raises(RuntimeError, match="native proof failed"):
            exec(compile(dispatcher, "runtime_smoke.py", "exec"), namespace)
        assert len(calls) == 1
        expected_args = (
            (Path("fixture.mp4"),)
            if phase in {"lwlibavsource_frame", "vapoursynth_screenshot", "vsview_runtime"}
            else ()
        )
        assert calls[0] == expected_args


def test_windows_portable_copies_python_proof_under_owned_cleanup(repo_root: Path) -> None:
    build_script = _read_text_or_fail(repo_root / "tools/windows_portable/build_portable.ps1")
    runtime = _bundle_runtime_function_block(build_script)
    copy = "Copy-Item -LiteralPath $smokeSource -Destination $smokePath -Force"
    assert '$smokeSource = Join-Path $PSScriptRoot "runtime_smoke.py"' in runtime
    assert runtime.index("try {") < runtime.index(copy) < runtime.index("Invoke-BundleRuntimeProof")
    assert runtime.index("} finally {") < runtime.index(
        "Remove-Item -Force -LiteralPath $smokePath"
    )
    assert "$smokeScript" not in runtime
    # Parsing the Python source provides the syntax gate even on hosts without Windows.
    compile(_runtime_proof_source(repo_root), "runtime_smoke.py", "exec")


def test_windows_portable_workflow_surfaces_direct_placebo_result(repo_root: Path) -> None:
    workflow = _read_text_or_fail(repo_root / ".github/actions/windows-portable-build/action.yml")

    assert "WINDOWS_BUNDLE_PROOF placebo_direct_frame=ok " in workflow
    assert (
        "WINDOWS_BUNDLE_PROOF placebo_direct_frame=skipped reason=vulkan_runtime_unavailable"
    ) in workflow
    assert "direct placebo frame proof remains required in Phase 2" in workflow


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell required")
@pytest.mark.parametrize(
    ("variant", "accepted", "warns"),
    [
        ("both-ok", True, False),
        ("post-qt-skip", True, True),
        ("missing", False, False),
        ("prefixed", False, False),
        ("suffixed", False, False),
        ("wrong-reason", False, False),
        ("duplicate", False, False),
    ],
)
def test_windows_portable_workflow_admits_exact_direct_placebo_receipts(
    repo_root: Path, variant: str, accepted: bool, warns: bool
) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is required")
    action = _read_text_or_fail(repo_root / ".github/actions/windows-portable-build/action.yml")
    block = action[
        action.index("        $directReceipts = @(") : action.index(
            "    - name: Verify bundle workspace directories"
        )
    ]
    prefix = "WINDOWS_BUNDLE_PROOF placebo_direct_frame="
    standalone = prefix + "ok format=RGB48 bits=16 context=standalone"
    post_qt_ok = prefix + "ok format=RGB48 bits=16 context=post_qt"
    post_qt_skip = prefix + "skipped reason=vulkan_runtime_unavailable context=post_qt"
    post_qt = {
        "both-ok": post_qt_ok,
        "post-qt-skip": post_qt_skip,
        "missing": "",
        "prefixed": f"unrelated {post_qt_skip}",
        "suffixed": f"{post_qt_skip} unrelated",
        "wrong-reason": post_qt_skip.replace("vulkan_runtime_unavailable", "probe_failed"),
        "duplicate": f"{standalone}\n{post_qt_ok}",
    }[variant]
    result = subprocess.run(
        [pwsh, "-NoProfile", "-Command", "$proof = $env:WB_RECEIPTS\n" + block],
        env=os.environ | {"WB_RECEIPTS": f"{standalone}\r\n{post_qt}\r\n"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert (result.returncode == 0) is accepted, _normalized_process_output(result)
    assert ("remains required in Phase 2" in result.stdout) is warns


def test_windows_portable_build_runtime_validation_proves_vs_plugins(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    proof_source = _runtime_proof_source(repo_root)

    for expected in (
        "Invoke-BundleRuntimeProof",
        "phase=$Phase start",
        "ffmpeg tiny media generation",
        "bundle runtime validation phase '$Phase' failed with exit code $exitCode",
    ):
        assert expected in build_script

    for expected in (
        "version_major == 82",
        "api_minor == 3",
        "LWLibavSource",
        "LibavSMASHSource",
        "core.placebo.Tonemap",
        "apply_tonemap",
        "get_frame(0)",
        "import vsview.app.main",
        "import vsview.cli",
        "import vspackrgb.rust",
        "from PySide6.QtWidgets import QApplication",
        "WINDOWS_BUNDLE_PROOF",
        "runtime_contract=ok",
        'prove_embedded_python(bundle_root, manifest["bundle"]["python_version"])',
        "FFMS2 must remain excluded",
        "standalone FFmpeg directory leaked onto PATH",
    ):
        assert expected in proof_source

    phases = re.findall(
        r"Invoke-BundleRuntimeProof -Python \$python -SmokePath \$smokePath "
        r'-Phase "([^"]+)" -MediaPath \$mediaPath -Required \$true',
        _bundle_runtime_function_block(build_script),
    )
    assert phases == [
        "package_imports",
        "runtime_contract",
        "vapoursynth_environment",
        "lwlibavsource_frame",
        "vapoursynth_screenshot",
        "placebo_tonemap_api",
        "apply_tonemap_frame",
        "placebo_tonemap_frame",
        "vsview_runtime",
    ]
    assert "placebo_tonemap_api=ok" in proof_source
    assert "apply_tonemap=ok " in proof_source
    assert "unexpectedly reduced output below 10-bit" in proof_source
    assert "libplacebo_runtime_usable=" in proof_source


@pytest.mark.integration
@pytest.mark.parametrize("owner", ["launcher", "runtime-validation"])
@pytest.mark.parametrize("initial_value", [None, "", "outer-value"], ids=["absent", "empty", "set"])
def test_windows_portable_restores_environment_and_location_after_failure(
    repo_root: Path,
    tmp_path: Path,
    owner: str,
    initial_value: str | None,
) -> None:
    if os.name != "nt":
        pytest.skip("Windows process environment semantics required")
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is required for the portable restoration regression")
    build_path = repo_root / "tools/windows_portable/build_portable.ps1"
    bundle = tmp_path / "bundle"
    (bundle / "python").mkdir(parents=True)
    # Both entry points require Python to exist before entering their owned
    # environment scope; failure must happen after that admission.
    (bundle / "python/python.exe").touch()
    launcher = bundle / "frame-compare.ps1"
    launcher.write_text(_generated_portable_launcher(repo_root), encoding="utf-8")
    (bundle / "bundle_info.json").write_text(
        '{"media_runtime_fingerprint":"fixture-fingerprint"}', encoding="utf-8"
    )
    if owner == "runtime-validation":
        # Missing FFmpeg fails after runtime environment setup and Push-Location.
        expected_error = "Bundled FFmpeg executable not found"
    else:
        # The invalid executable fails after environment setup and Push-Location.
        expected_error = None
    names = [
        "PATH",
        "PYTHONUTF8",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONPATH",
        "VAPOURSYNTH_EXTRA_PLUGIN_PATH",
        "VAPOURSYNTH_PLUGIN_PATH",
        "FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT",
        "FRAME_COMPARE_RUNTIME_KIND",
        "FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED",
        "FRAME_COMPARE_FFMPEG_EXECUTABLE",
        "FRAME_COMPARE_FFPROBE_EXECUTABLE",
    ]
    inputs = tmp_path / "inputs.json"
    inputs.write_text(
        json.dumps(
            {
                "build": str(build_path),
                "bundle": str(bundle),
                "launcher": str(launcher),
                "owner": owner,
                "names": names,
                "value": initial_value,
            }
        ),
        encoding="utf-8",
    )
    proof_script = tmp_path / "restore-after-failure.ps1"
    proof_script.write_text(
        r"""param([string]$InputsPath)
$ErrorActionPreference = "Stop"
$inputs = Get-Content -LiteralPath $InputsPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($inputs.owner -eq "runtime-validation") {
  $tokens = $null
  $errors = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $inputs.build, [ref]$tokens, [ref]$errors
  )
  if ($errors.Count -ne 0) { throw "Build script failed to parse" }
  # Load real function definitions without running the builder. Private helper
  # names and local-variable spelling have no role in the observed contract.
  foreach ($definition in $ast.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst]
  }, $false)) {
    Invoke-Expression $definition.Extent.Text
  }
}
$before = [ordered]@{}
foreach ($name in $inputs.names) {
  [Environment]::SetEnvironmentVariable($name, $inputs.value, "Process")
  $before[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
$location = (Get-Location).Path
$failure = $null
try {
  if ($inputs.owner -eq "runtime-validation") {
    Assert-BundleRuntime -BundleRoot $inputs.bundle
  } else {
    & $inputs.launcher version
  }
} catch {
  $failure = $_.Exception.Message
}
$after = [ordered]@{}
foreach ($name in $inputs.names) {
  $after[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
[ordered]@{
  before = $before
  after = $after
  location_before = $location
  location_after = (Get-Location).Path
  failure = $failure
} | ConvertTo-Json -Depth 4 -Compress
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(proof_script),
            str(inputs),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout)
    assert observed["failure"]
    if expected_error is not None:
        assert expected_error in observed["failure"]
    assert set(observed["before"]) == set(names)
    assert observed["after"] == observed["before"]
    assert observed["location_after"] == observed["location_before"]


def test_windows_portable_build_projects_dependencies_in_isolated_host_python(
    repo_root: Path,
) -> None:
    build_script = _read_text_or_fail(repo_root / "tools/windows_portable/build_portable.ps1")
    assert '& $HostPython -B -I -S (Join-Path $PSScriptRoot "portable_runtime.py")' in build_script
    assert "uv pip install" not in build_script
    assert "uv build" not in build_script
    runtime = _read_text_or_fail(repo_root / "tools/windows_portable/portable_runtime.py")
    assert 'root / "requirements.lock.txt"' in runtime


def test_windows_portable_release_build_requires_clean_exact_source(repo_root: Path) -> None:
    build = _read_text_or_fail(repo_root / "tools/windows_portable/build_portable.ps1")
    assert "[switch]$ReleaseBuild" in build
    assert "if (!$hasExpectedCommitSha -or $ReleaseBuild)" in build
    assert "git -C $RepoRoot rev-parse HEAD" in build
    assert re.search(
        r"if \(\$ReleaseBuild\) \{\s*if \(\$commitSha -cne \$headSha\)",
        build,
    )
    assert "git -C $RepoRoot status --porcelain=v1 --untracked-files=all" in build
    assert "Portable release builds require a clean, exact source checkout." in build
    assert "if ($ReleaseBuild -and $manifestVersion -ne 3)" in build
    assert "Portable release builds require manifest version 3." in build
    assert build.count("Assert-BuildManifest -Manifest $manifest") == 2
    assert 'if ($ReleaseBuild) {\n    $arguments += "--require-clean-repo"' in build


def test_windows_portable_build_surfaces_dirty_app_source_before_archiving(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    function_start = build_script.index("function Copy-RepoApp")
    function_end = build_script.index("function Initialize-PortableRuntime")
    copy_repo_app = build_script[function_start:function_end]

    status_command = (
        "git -C $RepoRoot status --porcelain=v1 --untracked-files=all -- src/frame_compare"
    )
    archive_command = '"portable_bundle.py") install-project'
    assert status_command in copy_repo_app
    assert "if ($ReleaseBuild)" in copy_repo_app
    assert "throw $dirtySourceMessage" in copy_repo_app
    assert "Write-Warning $dirtySourceMessage" in copy_repo_app
    assert copy_repo_app.index(status_command) < copy_repo_app.index(archive_command)
    assert 'Assert-LastExitCode -CommandLabel "inspect Frame Compare source worktree"' in (
        copy_repo_app
    )


def test_windows_portable_build_runtime_validation_checks_vsview_stack(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    proof_source = _runtime_proof_source(repo_root)
    assert "import vsview.app.main" in proof_source
    assert "import vsview.cli" in proof_source
    assert "import vspackrgb.rust" in proof_source
    assert "from PySide6.QtWidgets import QApplication" in proof_source
    assert '"testsrc2=size=64x64:rate=1:duration=3"' in build_script
    fixture_generation = re.search(
        r'-f lavfi -i "testsrc2=size=64x64:rate=1:duration=(?P<duration>\d+)" '
        r"-frames:v (?P<frames>\d+) -pix_fmt yuv420p -y \$mediaPath",
        build_script,
    )
    assert fixture_generation is not None
    lwlibavsource_proof = proof_source[
        proof_source.index("def prove_lwlibavsource") : proof_source.index("def build_placebo_clip")
    ]
    frame_count_assertion = re.search(
        r"assert_true\(source\.num_frames == (?P<count>\d+),", lwlibavsource_proof
    )
    assert frame_count_assertion is not None
    assert fixture_generation.group("duration") == fixture_generation.group("frames")
    assert fixture_generation.group("frames") == frame_count_assertion.group("count") == "3"
    combined_proof = proof_source[
        proof_source.index("def prove_vsview_runtime") : proof_source.index("phase = sys.argv[1]")
    ]
    for required_proof in (
        "preload_vapoursynth_runtime()",
        "app.exec()",
        "prove_qt_ffmpeg_runtime(media_path)",
        "prove_qt_webengine_excluded()",
        "prove_vsview_distribution_contract()",
        "prove_runtime_contract()",
        "prove_vapoursynth_environment()",
        "prove_bestsource_frame(media_path)",
        "prove_lwlibavsource(media_path)",
        "prove_generated_vsview_session(media_path)",
        "prove_placebo_tonemap_api()",
        "prove_apply_tonemap_frame()",
        'prove_placebo_tonemap_frame(context="post_qt")',
    ):
        assert required_proof in combined_proof
    assert "vsview_runtime_preload=ok" in combined_proof
    assert "pyside6_event_loop=ok" in combined_proof
    assert combined_proof.index('os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"') < combined_proof.index(
        "import vsview.app.main"
    )
    assert "qt_ffmpeg_runtime=ok backend=ffmpeg decoded_frame=64x64 dlls=5" in proof_source
    assert (
        "if manifest_version == 3:\n        prove_qt_ffmpeg_runtime(media_path)" in combined_proof
    )
    assert "qt_ffmpeg_runtime=ok lineage=9.0.1" in combined_proof
    assert "sink.videoFrameChanged.connect(receive_frame)" in proof_source
    assert "player.errorOccurred.connect(receive_error)" in proof_source
    assert "kernel32.K32EnumProcessModules" in proof_source
    assert "prove_qt_ffmpeg_loaded_from(bundle_root" in proof_source
    assert "qt_pdf_runtime=ok deployment=retained" in combined_proof
    assert "qt_webengine_runtime=absent deployment=excluded" in proof_source
    assert "vsview_runtime=ok" in combined_proof
    assert 'Phase "vsview_runtime" -MediaPath $mediaPath -Required $true' in build_script
    assert combined_proof.index("preload_vapoursynth_runtime()") < combined_proof.index(
        "from PySide6.QtCore import QTimer"
    )
    assert combined_proof.index("from PySide6.QtCore import QTimer") < combined_proof.index(
        "import vsview.app.main"
    )


def test_windows_portable_python_vsview_proof_covers_viewer_first_whole_set(
    repo_root: Path,
) -> None:
    build_script = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    )
    proof_source = _runtime_proof_source(repo_root)
    proof = proof_source[
        proof_source.index("def prove_generated_vsview_session") : proof_source.index(
            "def prove_vsview_runtime"
        )
    ]

    assert '$comparisonOneMediaPath = Join-Path $BundleRoot "runtime-smoke-comparison-1.mp4"' in (
        build_script
    )
    assert '$comparisonTwoMediaPath = Join-Path $BundleRoot "runtime-smoke-comparison-2.mp4"' in (
        build_script
    )
    assert "Copy-Item -LiteralPath $mediaPath -Destination $comparisonOneMediaPath" in build_script
    assert "Copy-Item -LiteralPath $mediaPath -Destination $comparisonTwoMediaPath" in build_script
    assert 'names == ["Reference", "Comparison 1", "Comparison 2"]' in proof
    assert "sorted(vs.get_outputs()) == [0, 1, 2]" in proof
    assert "len({media_path, comparison_one_media_path, comparison_two_media_path}) == 3" in proof
    assert "comparisons=[comparison_one_media_path, comparison_two_media_path]" in proof
    assert "comparisons=[media_path" not in proof
    assert 'comparison_one_media_path.stem: {"_Matrix": 2, "_Range": 2}' in proof
    assert 'comparison_two_media_path.stem: {"_Matrix": 2, "_Range": 2}' in proof
    tree = ast.parse(proof_source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "prove_generated_vsview_session"
    )
    callback_methods = {
        "on_workspace_loaded",
        "on_current_voutput_changed",
        "click",
    }
    observed_callbacks = []
    for node in ast.walk(function):
        for statements in (getattr(node, "body", None), getattr(node, "orelse", None)):
            if not isinstance(statements, list):
                continue
            for index, statement in enumerate(statements):
                if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                    continue
                callback = statement.value.func
                if isinstance(callback, ast.Attribute) and callback.attr in callback_methods:
                    observed_callbacks.append(callback.attr)
                    following = statements[index + 1]
                    assert isinstance(following, ast.Expr) and isinstance(following.value, ast.Call)
                    assert ast.unparse(following.value.func) == "app.processEvents"
    assert observed_callbacks.count("on_workspace_loaded") == 2
    assert observed_callbacks.count("on_current_voutput_changed") == 1
    assert observed_callbacks.count("click") == 2
    clicks = {
        ast.unparse(node.func.value)
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "click"
    }
    assert clicks == {"active_panel.use_positions_button", "keep_panel.keep_button"}
    assert "anchor_buttons" not in proof
    assert "select_buttons" not in proof
    assert "active_panel.frame_inputs[output_index].setText(str(frame))" in proof
    assert "[decision.action for decision in observed_result.decisions]" in proof
    assert '["confirmed", "confirmed"]' in proof
    assert '["keep_current", "keep_current"]' in proof
    assert '"0/3 frames ready"' in proof
    assert r'"3/3 frames ready"' in proof
    assert '"alignment_positions=ok"' in proof
    assert '"alignment_keep_current=ok"' in proof
    assert '"alignment_metadata=ok outputs=Reference,Comparison_1,Comparison_2 "' in proof
    assert '"alignment_result_roundtrip=ok"' in proof
    assert '"alignment_result_validation=ok malformed=rejected"' in proof


def test_windows_portable_build_launches_real_vsview_offscreen_and_cleans_up(
    repo_root: Path,
) -> None:
    build_script = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    )
    launch_proof = build_script[
        build_script.index("function Invoke-VSViewOffscreenLaunchProof") : build_script.index(
            "function Assert-BundleRuntime"
        )
    ]

    assert '"frame_compare.vsview.launcher"' in launch_proof
    assert '"-vv"' in launch_proof
    assert '"--verbose"' not in launch_proof
    assert '"--no-settings"' in launch_proof
    assert '$env:QT_QPA_PLATFORM = "offscreen"' in launch_proof
    assert '$env:NO_COLOR = "1"' in launch_proof
    assert "VAPOURSYNTH_EXTRA_PLUGIN_PATH" not in launch_proof
    assert "$process.WaitForExit(20000)" in launch_proof
    assert "Stop-Process -Id $process.Id -Force" in launch_proof
    assert "$process.WaitForExit(10000)" in launch_proof
    assert "VSView offscreen proof left its process running." in launch_proof
    assert "$normalizedCombined.Contains($marker)" in launch_proof
    for marker in (
        "VSView is open",
        "Script execution completed",
        "Switching to video output",
        "Frame 0 rendered",
    ):
        assert marker in launch_proof
    assert '$_ -match "(?i)\\bERROR\\b"' in launch_proof
    assert "vsview_gui_launch=ok platform=offscreen timeout=expected cleanup=ok" in launch_proof

    proof_source = _runtime_proof_source(repo_root)
    assert 'media_path.stem: {"_Matrix": 2, "_Range": 2}' in proof_source
    assert 'comparison_one_media_path.stem: {"_Matrix": 2, "_Range": 2}' in proof_source
    assert 'comparison_two_media_path.stem: {"_Matrix": 2, "_Range": 2}' in proof_source
    assert "Color metadata incomplete; using standard display defaults (BT.709)" in proof_source
    assert '$normalizedCombined = ($combined -replace "\\s+", " ").Trim()' in launch_proof


def test_windows_portable_workflow_requires_combined_vsview_proof(
    repo_root: Path,
) -> None:
    workflow = _read_text_or_fail(repo_root / ".github/actions/windows-portable-build/action.yml")

    required_phases = workflow[
        workflow.index("foreach ($phase in @(") : workflow.index("$directReceipts = @(")
    ]
    assert '"vsview_runtime"' in required_phases
    assert "WINDOWS_BUNDLE_PROOF vsview_runtime=ok" in required_phases
    assert "vsview_gui_launch=ok platform=offscreen timeout=expected cleanup=ok" in required_phases
    assert "Required combined VSView runtime proof marker missing." in required_phases


def test_windows_portable_generated_launcher_sanitizes_malformed_bundle_info(
    repo_root: Path,
) -> None:
    launcher = _generated_portable_launcher(repo_root)

    assert "ConvertFrom-Json -ErrorAction Stop" in launcher
    assert "$bundleInfo -isnot [PSCustomObject]" in launcher
    assert "bundle_info.json is invalid" in launcher
    assert "Rebuild or reinstall the complete portable bundle." in launcher
    assert "$_.Exception.Message" not in launcher


def test_windows_portable_generated_launcher_rejects_malformed_bundle_info_in_process(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    pwsh = shutil.which("pwsh")
    if os.name != "nt" or pwsh is None:
        pytest.skip("Windows with PowerShell is required for the generated launcher regression")

    bundle = tmp_path / "portable-bundle"
    (bundle / "python").mkdir(parents=True)
    (bundle / "python" / "python.exe").write_bytes(b"")
    malformed_marker = "PRIVATE-MALFORMED-METADATA"
    (bundle / "bundle_info.json").write_text(
        f'{{"marker":"{malformed_marker}"',
        encoding="utf-8",
    )
    launcher_path = bundle / "frame-compare.ps1"
    launcher_path.write_text(_generated_portable_launcher(repo_root), encoding="utf-8")

    result = subprocess.run(
        [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(launcher_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=os.environ | {"NO_COLOR": "1", "TERM": "dumb"},
    )

    output = _normalized_process_output(result)
    assert result.returncode != 0
    assert "bundle_info.json is invalid" in output
    assert "Rebuild or reinstall the complete portable bundle." in output
    assert malformed_marker not in output


def test_physical_windows_validation_fetches_and_checks_out_exact_pr_head(
    repo_root: Path,
) -> None:
    physical_checklist = _read_text_or_fail(
        repo_root / "docs" / "media-runtime-windows-validation.md"
    )

    assert "bundle_info.schema_version` is 3" in physical_checklist
    assert "refs/pull/$PrNumber/head" in physical_checklist
    assert "refs/remotes/origin/pr/$PrNumber/head" in physical_checklist
    assert 'git fetch --no-tags origin "+${PrHeadRef}:${LocalPrHeadRef}"' in physical_checklist
    assert "git switch --detach $ExpectedPrHeadSha" in physical_checklist
    assert "(git rev-parse --verify HEAD).Trim()" in physical_checklist
    assert "git pull --ff-only" not in physical_checklist
    assert "git ls-remote origin refs/heads/" not in physical_checklist
    assert "Checked-out pull-request branch" not in physical_checklist


def test_windows_portable_build_uses_vendored_manifest_license_files(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "Assert-Sha256 -FilePath $resolvedPath -ExpectedHex $expectedSha256" in build_script
    assert "Invoke-WebRequest -Uri $licenseUrl" not in build_script
    assert (
        "Copy-ManifestLicenseFiles -LicensesDir $licensesDir -ArtifactId $id -Spdx $spdx"
        in build_script
    )


def test_windows_portable_manifest_schema_models_current_install_shapes(repo_root: Path) -> None:
    schema_path = repo_root / "tools" / "windows_portable" / "manifest.schema.json"
    schema = json.loads(_read_text_or_fail(schema_path))
    artifact_def = schema["$defs"]["artifact"]
    install_def = schema["$defs"]["install"]
    assert "install" in artifact_def["required"]
    assert artifact_def["properties"]["bundled_dependencies"]["items"] == {
        "$ref": "#/$defs/bundled_dependency"
    }
    paired_required_fields = {frozenset(rule["then"]["required"]) for rule in artifact_def["allOf"]}
    assert paired_required_fields == {
        frozenset({"source_sha256", "source_bytes"}),
        frozenset({"build_source_sha256", "build_source_bytes"}),
    }
    assert "oneOf" in install_def

    variants = {variant["properties"]["type"]["const"]: variant for variant in install_def["oneOf"]}
    assert schema["properties"]["manifest_version"] == {"type": "integer", "enum": [2, 3]}
    assert schema["if"]["properties"]["manifest_version"] == {"const": 3}
    assert schema["then"]["properties"]["artifacts"] == {
        "contains": {"$ref": "#/$defs/qt_ffmpeg_overlay"},
        "minContains": 1,
        "maxContains": 1,
    }
    assert schema["else"]["properties"]["artifacts"] == {
        "contains": {"$ref": "#/$defs/qt_ffmpeg_overlay"},
        "minContains": 0,
        "maxContains": 0,
    }
    info_schema = json.loads(_read_text_or_fail(schema_path.with_name("bundle_info.schema.json")))
    assert info_schema["properties"]["manifest_version"] == {"type": "integer", "enum": [2, 3]}
    assert set(variants) == {"extract", "python_wheel", "qt_multimedia_ffmpeg"}
    assert variants["extract"]["required"] == ["type", "destination"]
    assert variants["python_wheel"]["required"] == ["type"]
    assert "destination" not in variants["python_wheel"]["properties"]
    assert set(variants["qt_multimedia_ffmpeg"]["properties"]) == {"type"}
    assert variants["qt_multimedia_ffmpeg"]["additionalProperties"] is False


def test_windows_portable_manifest_vendored_license_files_exist_and_match_hashes(
    repo_root: Path,
) -> None:
    manifest_path = repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json"
    manifest = json.loads(_read_text_or_fail(manifest_path))
    active_gitattributes_lines = {
        line.strip()
        for line in _read_text_or_fail(repo_root / ".gitattributes").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "tools/windows_portable/licenses/**/*.txt text eol=lf" in active_gitattributes_lines

    licensed_artifacts = [
        artifact for artifact in manifest["artifacts"] if "files" in artifact["license"]
    ]
    assert licensed_artifacts

    for artifact in licensed_artifacts:
        license_info = artifact["license"]
        assert license_info["url"].startswith("https://")
        for license_file in license_info["files"]:
            relative_path = Path(license_file["path"])
            vendored_path = manifest_path.parent / relative_path
            assert vendored_path.is_file(), f"Missing vendored license file: {vendored_path}"
            license_bytes = vendored_path.read_bytes()
            assert b"\r\n" not in license_bytes
            actual_hash = hashlib.sha256(license_bytes).hexdigest()
            assert actual_hash == license_file["sha256"]
            assert license_file["source_url"].startswith("https://")


def _write_packaged_runtime_contract(*, bundle: Path, fingerprints: dict[str, str]) -> None:
    contract_root = bundle / "app" / "src" / "frame_compare" / "vs"
    contract_root.mkdir(parents=True, exist_ok=True)
    (contract_root.parent / "__init__.py").write_text("", encoding="utf-8")
    (contract_root / "__init__.py").write_text("", encoding="utf-8")
    (contract_root / "runtime_contract.py").write_text(
        (
            f"MEDIA_RUNTIME_SCOPES = {tuple(fingerprints)!r}\n"
            f"_FINGERPRINTS = {fingerprints!r}\n"
            "def media_runtime_fingerprint(scope, *, profile=None):\n"
            "    if profile != 'windows-x64':\n"
            "        raise ValueError(profile)\n"
            "    return _FINGERPRINTS[scope]\n"
        ),
        encoding="utf-8",
    )


def _write_fake_inventory_bundle(*, tmp_path: Path, repo_root: Path) -> Path:
    bundle = tmp_path / "bundle"
    site_packages = bundle / "app" / "site-packages"
    licenses = bundle / "licenses"
    shim = bundle / "shim"
    site_packages.mkdir(parents=True)
    licenses.mkdir()
    shim.mkdir()

    distributions = {
        "jetpytools": ("3.2.0", "MIT"),
        "PySide6": ("6.12.0", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
        "PySide6-Addons": ("6.12.0", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
        "PySide6-Essentials": ("6.12.0", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
        "PySide6-Pdf": ("6.12.0.140", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
        "PySide6-WebEngine": ("6.12.0.140", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
        "shiboken6": ("6.12.0", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
        "VapourSynth": ("82", "LGPL-2.1-or-later"),
        "vapoursynth-bestsource": ("23", "MIT"),
        "vapoursynth-lsmas": ("1310.0.0.0", "ISC AND LGPL-2.1-or-later"),
        "vs-placebo": ("2.0.5", "LGPL-2.1-only"),
        "vspackrgb": ("2.0.0", "MIT"),
        "VSView": ("0.14.0", "EUPL-1.2"),
        "cyclopts": ("5.4.2", "Apache-2.0"),
        "vsjetengine": ("2.0.0", "EUPL-1.2"),
    }
    for index, (name, (version, license_expression)) in enumerate(distributions.items()):
        dist_info = site_packages / f"package_{index}-{version}.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            "\n".join(
                [
                    "Metadata-Version: 2.4",
                    f"Name: {name}",
                    f"Version: {version}",
                    f"License-Expression: {license_expression}",
                    "Project-URL: Source Code, https://example.invalid/source",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    (licenses / "frame-compare-LICENSE.txt").write_text("GPL test fixture\n", encoding="utf-8")
    manifest = json.loads(
        (repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json").read_text(
            encoding="utf-8"
        )
    )
    for artifact in manifest["artifacts"]:
        license_info = artifact["license"]
        files = license_info.get("files", [])
        for notice in files:
            source = repo_root / "tools/windows_portable" / notice["path"]
            prefix = f"{artifact['id']}-{license_info['spdx']}"
            suffix = source.suffix if len(files) == 1 else f"--{source.name}"
            shutil.copyfile(source, licenses / f"{prefix}{suffix}")
    runtime_fingerprints = manifest["bundle"]["runtime_fingerprints"]
    _write_packaged_runtime_contract(bundle=bundle, fingerprints=runtime_fingerprints)
    bundled_font_dir = bundle / "app" / "src" / "frame_compare" / "assets" / "fonts"
    bundled_font_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        repo_root / "src" / "frame_compare" / "assets" / "fonts" / "Inter-OFL.txt",
        bundled_font_dir / "Inter-OFL.txt",
    )
    (bundle / "bundle_info.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "bundle_kind": "full",
                "app_version": "0.1.0",
                "requirements_lock_sha256": "a" * 64,
                "manifest_version": manifest["manifest_version"],
                "platform": "windows-x64",
                "media_runtime_fingerprint": runtime_fingerprints["full"],
                "media_runtime_fingerprints": runtime_fingerprints,
            }
        ),
        encoding="utf-8",
    )
    return bundle


def _inventory_source_paths(repo_root: Path) -> tuple[str, ...]:
    tree = ast.parse(
        _read_text_or_fail(repo_root / "tools/windows_portable/write_bundle_inventory.py")
    )
    return next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "SOURCE_SCRIPTS"
            for target in node.targets
        )
    )


@pytest.fixture
def inventory_source_repo(repo_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Give inventory checks committed source provenance independent of the worktree."""
    source_repo = tmp_path_factory.mktemp("portable-inventory-source")
    source_paths = _inventory_source_paths(repo_root)
    for relative_path in source_paths:
        destination = source_repo / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo_root / relative_path, destination)
    subprocess.run(
        ["git", "-C", str(source_repo), "init", "--quiet"],
        check=True,
        capture_output=True,
        timeout=30,
    )
    _commit_inventory_fixture(source_repo, "source fixture")
    return source_repo


def _commit_inventory_fixture(repo: Path, message: str) -> str:
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True, timeout=30
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Portable test",
            "-c",
            "user.email=portable@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            message,
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return _source_commit(repo)


def _source_commit(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, timeout=10
    ).strip()


def _run_bundle_inventory(
    *,
    bundle: Path,
    repo_root: Path,
    source_repo: Path,
    manifest: Path | None = None,
    commit_sha: str | None = None,
    require_clean_repo: bool = False,
) -> subprocess.CompletedProcess[str]:
    if commit_sha is None:
        commit_sha = _source_commit(source_repo)
    return subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools" / "windows_portable" / "write_bundle_inventory.py"),
            "--bundle-root",
            str(bundle),
            "--manifest",
            str(manifest or repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json"),
            "--repo-root",
            str(source_repo),
            "--commit-sha",
            commit_sha,
            "--output",
            str(bundle / "bundle_inventory.json"),
            *(["--require-clean-repo"] if require_clean_repo else []),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )


def test_windows_portable_bundle_inventory_is_sorted_exact_and_path_safe(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    result = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=inventory_source_repo,
        require_clean_repo=True,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"

    inventory_text = (bundle / "bundle_inventory.json").read_text(encoding="utf-8")
    inventory = json.loads(inventory_text)
    assert str(tmp_path) not in inventory_text
    assert inventory["bundle"]["frame_compare_license"] == "GPL-3.0-only"
    assert re.fullmatch(r"[a-f0-9]{40}", inventory["bundle"]["commit_sha"])
    assert inventory["bundle"]["commit_sha"] in inventory["bundle"]["source_archive_url"]
    assert inventory["bundle"]["requirements_lock_sha256"] == "a" * 64
    assert inventory["schema_version"] == 2
    assert re.fullmatch(r"[a-f0-9]{64}", inventory["bundle"]["media_runtime_fingerprint"])

    distribution_names = [
        distribution["name"] for distribution in inventory["python_distributions"]
    ]
    assert distribution_names == sorted(distribution_names, key=str.lower)
    assert {
        "jetpytools",
        "pyside6",
        "pyside6-addons",
        "pyside6-essentials",
        "pyside6-pdf",
        "pyside6-webengine",
        "shiboken6",
        "vapoursynth",
        "vapoursynth-bestsource",
        "vapoursynth-lsmas",
        "vs-placebo",
        "vspackrgb",
        "vsview",
        "cyclopts",
        "vsjetengine",
    } <= {name.lower() for name in distribution_names}
    assert all(
        distribution["source_url"].endswith(f"/{distribution['version']}/")
        for distribution in inventory["python_distributions"]
    )

    artifact_ids = [artifact["id"] for artifact in inventory["manifest_artifacts"]]
    assert artifact_ids == sorted(artifact_ids)
    assert all(artifact["source_url"] for artifact in inventory["manifest_artifacts"])
    assert all(artifact["binary_bytes"] > 0 for artifact in inventory["manifest_artifacts"])
    assert any(
        source["name"] == "Qt"
        and source["version"] == "6.12.0"
        and "/6.12/6.12.0/" in source["source_url"]
        for source in inventory["corresponding_sources"]
    )
    assert all(
        re.fullmatch(r"[a-f0-9]{64}", source["sha256"]) and source["bytes"] > 0
        for source in inventory["corresponding_sources"]
    )
    assert "tools/windows_portable/runtime_smoke.py" in inventory["source_build_install_scripts"]
    assert inventory["source_build_install_scripts"] == sorted(_inventory_source_paths(repo_root))

    license_paths = [license_entry["path"] for license_entry in inventory["licenses"]]
    assert license_paths == sorted(license_paths)
    assert "licenses/frame-compare-LICENSE.txt" in license_paths
    assert "licenses/Inter-OFL.txt" in license_paths
    assert "licenses/qt-multimedia-ffmpeg-9.1-win-x64-LGPL-3.0-or-later.txt" in license_paths
    qt_ffmpeg = next(
        artifact
        for artifact in inventory["manifest_artifacts"]
        if artifact["id"] == "qt-multimedia-ffmpeg-9.1-win-x64"
    )
    assert qt_ffmpeg["source_commit"] == "74e4393595cf2b5857f0da925c4e0dd74ea306e5"
    assert qt_ffmpeg["build_source_commit"] == "7bd67a2dfc716f34e53849434e46a8c57c71884b"
    assert any(
        source["name"] == "vcpkg ports for the Qt Multimedia FFmpeg build"
        and source["source_commit"] == "f3e10653cc27d62a37a3763cd84b38bca07c6075"
        for source in inventory["corresponding_sources"]
    )
    source_urls = (bundle / "licenses" / "SOURCE_URLS.txt").read_text(encoding="utf-8")
    assert inventory["bundle"]["commit_sha"] in source_urls
    assert "live worktree" not in source_urls
    assert "qt-everywhere-src-6.12.0.tar.xz" in source_urls
    assert "Inter 4.1: https://github.com/rsms/inter/releases/tag/v4.1" in source_urls
    assert qt_ffmpeg["source_url"] in source_urls and qt_ffmpeg["build_source_url"] in source_urls
    assert (
        "codeload.github.com/microsoft/vcpkg/tar.gz/f3e10653cc27d62a37a3763cd84b38bca07c6075"
        in source_urls
    )
    notices = (bundle / "licenses" / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    assert "Inter 4.1 (OFL-1.1)" in notices
    assert f"{qt_ffmpeg['name']} 9.1 (LGPL-3.0-or-later)" in notices

    installer = inventory_source_repo / "tools/windows_portable/install.ps1"
    installer.write_bytes(installer.read_bytes() + b"\n# Local tooling edit\n")
    dirty = _run_bundle_inventory(
        bundle=bundle, repo_root=repo_root, source_repo=inventory_source_repo
    )
    assert dirty.returncode == 0, _normalized_process_output(dirty)
    assert "the live worktree" in (bundle / "licenses/SOURCE_URLS.txt").read_text(encoding="utf-8")
    strict = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=inventory_source_repo,
        require_clean_repo=True,
    )
    assert strict.returncode != 0
    assert "requires a clean, exact source checkout" in strict.stderr


@pytest.mark.parametrize(
    ("tampered", "expected_error"),
    [(False, "Missing manifest notice"), (True, "Manifest notice SHA-256 mismatch")],
    ids=["missing", "tampered"],
)
def test_windows_portable_inventory_requires_each_manifest_notice(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
    tampered: bool,
    expected_error: str,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    # Omit one member of a multi-file notice set while keeping the others.
    notice = next((bundle / "licenses").glob("vs-plugin-lsmas-*--VapourSynth-LICENSE.txt"))
    if tampered:
        notice.write_bytes(b"wrong license content")
    else:
        notice.unlink()

    result = _run_bundle_inventory(
        bundle=bundle, repo_root=repo_root, source_repo=inventory_source_repo
    )

    assert result.returncode != 0
    assert f"{expected_error}: licenses/{notice.name}" in result.stderr
    assert not (bundle / "bundle_inventory.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell build semantics required")
@pytest.mark.parametrize("mode", ["committed-default", "explicit-custom", "historical-v2"])
def test_windows_portable_builder_uses_one_manifest_for_notices_and_inventory(
    tmp_path: Path, repo_root: Path, inventory_source_repo: Path, mode: str
) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is required")
    custom = mode == "explicit-custom"
    historical = mode == "historical-v2"
    source = inventory_source_repo
    owner = source / "tools/windows_portable"
    original = repo_root / "tools/windows_portable"
    shutil.copytree(original / "licenses", owner / "licenses")

    manifest_path = owner / "manifest.windows-x64.json"
    manifest = json.loads(manifest_path.read_bytes())
    activation = owner / "portable_activation.ps1"
    activation_bytes = (original / activation.name).read_bytes()
    if historical:
        manifest["manifest_version"] = 2
        manifest["artifacts"] = [
            item
            for item in manifest["artifacts"]
            if item["install"]["type"] != "qt_multimedia_ffmpeg"
        ]
        manifest_path.write_bytes(json.dumps(manifest).encode())
        activation.unlink()
    committed_manifest = manifest_path.read_bytes()
    artifact = next(
        item for item in manifest["artifacts"] if len(item["license"].get("files", [])) == 1
    )
    pin = artifact["license"]["files"][0]
    notice = owner / pin["path"]
    committed_notice = notice.read_bytes()
    destination = f"{artifact['id']}-{artifact['license']['spdx']}{notice.suffix}"

    seed = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    shutil.rmtree(seed / "licenses")
    (seed / "requirements.lock.txt").write_text("fixture requirements", encoding="utf-8")
    app_source = source / "src/frame_compare"
    app_source.parent.mkdir()
    shutil.move(seed / "app/src/frame_compare", app_source)
    (seed / "app/src").rmdir()
    (app_source / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    (source / "pyproject.toml").write_text(
        """
[project]
name = "frame-compare"
version = "0.1.0"
requires-python = ">=3.13"
[project.scripts]
frame-compare = "frame_compare.cli.entry:console_main"
[project.entry-points.vsview]
frame-compare-alignment-review = "frame_compare.vsview.alignment_review_panel"
""",
        encoding="utf-8",
    )
    shutil.copyfile(repo_root / "LICENSE", source / "LICENSE")
    shutil.copyfile(original / "README.txt", owner / "README.txt")
    script = owner / "build_portable.ps1"
    script.write_text(
        script.read_text(encoding="utf-8").rsplit("\nMain", 1)[0]
        + r"""
function uv { $global:LASTEXITCODE = 0; return $env:FIXTURE_PYTHON }
function Initialize-PortableRuntime {
  param($BundleRoot, $CommitSha, $SelectedManifestPath)
  Get-ChildItem -LiteralPath $env:FIXTURE_LAYOUT | Copy-Item -Destination $BundleRoot -Recurse
  Copy-Item -LiteralPath $SelectedManifestPath -Destination (Join-Path $BundleRoot "manifest.json")
}
function Assert-RequiredPySideLicenseMetadata {}
function Assert-BundleRuntime {}
Main
""",
        encoding="utf-8",
    )

    subprocess.run(
        ["git", "-C", str(source), "config", "core.autocrlf", "false"],
        check=True,
        capture_output=True,
        timeout=30,
    )
    selected = _commit_inventory_fixture(source, "selected manifest and notices")
    newer_notice = b"changed live notice\r\n"
    # Give this artifact its own notice so other pins for the common file still agree.
    pin["path"] = f"licenses/fixture-notice{notice.suffix}"
    (owner / pin["path"]).write_bytes(newer_notice)
    pin["sha256"] = hashlib.sha256(newer_notice).hexdigest()
    manifest["bundle"]["runtime_fingerprints"]["full"] = "b" * 64
    newer_manifest = json.dumps(manifest).encode()
    manifest_path.write_bytes(newer_manifest)
    if historical:
        activation.write_bytes(activation_bytes)
        (app_source / "__init__.py").write_text('__version__ = "0.2.0"\n', encoding="utf-8")
    assert _commit_inventory_fixture(source, "newer manifest and notices") != selected
    installer = owner / "install.ps1"
    edited_installer = installer.read_bytes() + b"\r\n# Uncommitted installer fixture edit\r\n"
    if historical:
        installer.write_bytes(edited_installer)

    command = [
        pwsh,
        "-NoProfile",
        "-File",
        str(script),
        "-ExpectedCommitSha",
        selected,
        "-RepoRoot",
        str(source),
        "-CacheDir",
        str(tmp_path / "cache"),
        "-OutDir",
        str(tmp_path / "out"),
    ]
    expected_manifest = committed_manifest
    expected_notice = committed_notice
    env = os.environ | {"FIXTURE_PYTHON": sys.executable, "FIXTURE_LAYOUT": str(seed)}
    if custom:
        manifest["manifest_version"] = 2
        manifest["artifacts"] = [
            item
            for item in manifest["artifacts"]
            if item["install"]["type"] != "qt_multimedia_ffmpeg"
        ]
        custom_dir = tmp_path / "custom-manifest"
        shutil.copytree(owner / "licenses", custom_dir / "licenses")
        expected_notice = b"custom manifest notice\n"
        (custom_dir / pin["path"]).write_bytes(expected_notice)
        pin["sha256"] = hashlib.sha256(expected_notice).hexdigest()
        manifest["bundle"]["runtime_fingerprints"]["full"] = "c" * 64
        expected_manifest = json.dumps(manifest).encode()
        custom_path = custom_dir / "custom.json"
        custom_path.write_bytes(expected_manifest)
        command.extend(("-ManifestPath", str(custom_path)))
        release = subprocess.run(
            [*command, "-ReleaseBuild"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert release.returncode != 0
        assert "Portable release builds require manifest version 3." in _normalized_process_output(
            release
        )
        assert not (tmp_path / "out").exists()
        assert not (tmp_path / "cache").exists()
    if historical:
        activation.unlink()
        missing = subprocess.run(
            command, env=env, check=False, capture_output=True, text=True, timeout=90
        )
        assert missing.returncode != 0
        missing_output = _normalized_process_output(missing)
        assert "Installer file not found" in missing_output and activation.name in missing_output
        assert not (tmp_path / "out").exists()
        activation.write_bytes(activation_bytes)
    result = subprocess.run(
        command,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode == 0, _normalized_process_output(result)
    out = tmp_path / "out"
    assert (out / "manifest.json").read_bytes() == expected_manifest
    bundle_info = json.loads((out / "bundle_info.json").read_bytes())
    assert bundle_info["manifest_version"] == (2 if custom or historical else 3)
    assert bundle_info["app_version"] == "0.1.0"
    assert (out / "licenses" / destination).read_bytes() == expected_notice
    inventory = json.loads((out / "bundle_inventory.json").read_text(encoding="utf-8"))
    assert inventory["bundle"]["commit_sha"] == selected
    assert (
        inventory["bundle"]["media_runtime_fingerprints"]
        == json.loads(expected_manifest)["bundle"]["runtime_fingerprints"]
    )
    assert {
        "path": f"licenses/{destination}",
        "sha256": hashlib.sha256(expected_notice).hexdigest(),
    } in inventory["licenses"]

    if historical:
        source_url = f"https://github.com/TJZine/frame-compare/archive/{selected}.tar.gz"
        assert inventory["bundle"]["source_archive_url"] == source_url
        assert inventory["source_build_install_scripts"] == sorted(
            set(_inventory_source_paths(repo_root))
            - {"tools/windows_portable/portable_activation.ps1"}
        )
        source_urls = (out / "licenses/SOURCE_URLS.txt").read_text(encoding="utf-8")
        assert source_url in source_urls
        assert "The SHA identifies the application source." in source_urls
        assert "the live worktree" in source_urls
        assert "archive.files entries in bundle_inventory.json hash the" in source_urls
        assert str(source) not in source_urls
        archive_files = {entry["path"]: entry for entry in inventory["archive"]["files"]}
        for name, shipped_bytes in (
            (activation.name, activation_bytes),
            (installer.name, edited_installer),
        ):
            assert (out / name).read_bytes() == shipped_bytes
            assert archive_files[name]["sha256"] == hashlib.sha256(shipped_bytes).hexdigest()


def test_windows_portable_inventory_uses_dotfile_notice_extension(
    tmp_path: Path, repo_root: Path, inventory_source_repo: Path
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    artifact = next(
        item for item in manifest["artifacts"] if len(item["license"].get("files", [])) == 1
    )
    artifact["license"]["files"][0]["path"] = "licenses/.LICENSE"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    notice = next((bundle / "licenses").glob(f"{artifact['id']}-{artifact['license']['spdx']}.*"))
    dotfile_destination = notice.with_suffix(".LICENSE")
    notice.rename(dotfile_destination)

    result = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=inventory_source_repo,
        manifest=manifest_path,
    )
    assert result.returncode == 0, _normalized_process_output(result)
    inventory_path = bundle / "bundle_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert {
        "path": f"licenses/{dotfile_destination.name}",
        "sha256": artifact["license"]["files"][0]["sha256"],
    } in inventory["licenses"]

    inventory_path.unlink()
    dotfile_destination.rename(dotfile_destination.with_suffix(""))
    result = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=inventory_source_repo,
        manifest=manifest_path,
    )
    assert result.returncode != 0
    assert f"Missing manifest notice: licenses/{dotfile_destination.name}" in result.stderr
    assert not inventory_path.exists()


@pytest.mark.parametrize("historical_entry", ["missing", "symlink", "tree"])
def test_windows_portable_inventory_records_the_captured_commit(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
    historical_entry: str,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    source = inventory_source_repo
    helper_path = "tools/windows_portable/portable_activation.ps1"
    helper = source / helper_path
    helper_bytes = helper.read_bytes()
    helper.unlink()
    if historical_entry == "symlink":
        # Model the checkout of a Git symlink without requiring OS symlink privileges.
        subprocess.run(
            ["git", "-C", str(source), "config", "core.symlinks", "false"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        helper.write_text("install.ps1", encoding="utf-8")
        target = subprocess.check_output(
            ["git", "-C", str(source), "hash-object", "-w", helper_path],
            text=True,
            timeout=10,
        ).strip()
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "update-index",
                "--cacheinfo",
                f"120000,{target},{helper_path}",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    elif historical_entry == "tree":
        helper.mkdir()
        (helper / "nested.ps1").write_bytes(helper_bytes)
    captured = _commit_inventory_fixture(source, "historical scripts")

    for require_clean in (False, True):
        strict = _run_bundle_inventory(
            bundle=bundle,
            repo_root=repo_root,
            source_repo=source,
            require_clean_repo=require_clean,
        )
        assert strict.returncode != 0
        assert (
            f"source commit lacks required regular build/install scripts: {helper_path}"
            in strict.stderr
        )

    if historical_entry == "tree":
        shutil.rmtree(helper)
    helper.write_bytes(helper_bytes)
    if historical_entry == "symlink":
        subprocess.run(
            ["git", "-C", str(source), "update-index", "--force-remove", helper_path],
            check=True,
            capture_output=True,
            timeout=30,
        )
    assert _commit_inventory_fixture(source, "current scripts") != captured
    strict = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=source,
        commit_sha=captured,
        require_clean_repo=True,
    )
    assert strict.returncode != 0
    assert "requires a clean, exact source checkout" in strict.stderr

    result = _run_bundle_inventory(
        bundle=bundle, repo_root=repo_root, source_repo=source, commit_sha=captured
    )
    assert result.returncode == 0, _normalized_process_output(result)
    inventory = json.loads((bundle / "bundle_inventory.json").read_text(encoding="utf-8"))
    assert inventory["bundle"]["commit_sha"] == captured
    assert inventory["bundle"]["source_archive_url"].endswith(f"/{captured}.tar.gz")
    assert inventory["source_build_install_scripts"] == sorted(
        set(_inventory_source_paths(repo_root)) - {helper_path}
    )
    source_urls = (bundle / "licenses/SOURCE_URLS.txt").read_text(encoding="utf-8")
    assert captured in source_urls
    assert "the live worktree" in source_urls

    if historical_entry == "missing":
        (bundle / "bundle_inventory.json").unlink()
        unreadable = _run_bundle_inventory(
            bundle=bundle, repo_root=repo_root, source_repo=source, commit_sha="0" * 40
        )
        assert unreadable.returncode != 0
        assert "ls-tree" in unreadable.stderr
        assert not (bundle / "bundle_inventory.json").exists()


def test_windows_portable_requirements_export_uses_the_captured_commit(
    tmp_path: Path, repo_root: Path
) -> None:
    if shutil.which("uv") is None:
        pytest.skip("uv is required to export the committed dependency lock")
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "uv.lock"):
        (source / name).write_bytes(
            subprocess.check_output(
                ["git", "-C", str(repo_root), "show", f"HEAD:{name}"], timeout=15
            )
        )
    for args in (
        ("init", "--quiet"),
        ("add", "pyproject.toml", "uv.lock"),
        (
            "-c",
            "user.name=Portable test",
            "-c",
            "user.email=portable@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "locked inputs",
        ),
    ):
        subprocess.run(
            ["git", "-C", str(source), *args], check=True, capture_output=True, timeout=30
        )
    captured = _source_commit(source)
    output = tmp_path / "requirements.lock.txt"
    subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--no-emit-package",
            "vapoursynth-lsmas",
            "--extra",
            "vsview",
            "--format",
            "requirements.txt",
            "--output-file",
            str(output),
        ],
        cwd=source,
        env=os.environ | {"UV_OFFLINE": "1", "UV_NO_CONFIG": "1"},
        check=True,
        capture_output=True,
        timeout=45,
    )
    expected = output.read_bytes()
    output.unlink()
    # Exporting from the live checkout would now fail to parse the lock.
    (source / "uv.lock").write_text("corrupt live lock", encoding="utf-8")

    owner = repo_root / "tools/windows_portable/portable_runtime.py"
    subprocess.run(
        [
            sys.executable,
            "-B",
            "-I",
            "-S",
            "-c",
            (
                "import runpy, sys; from pathlib import Path; "
                "export = runpy.run_path(sys.argv[1])['export']; "
                "export(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))"
            ),
            str(owner),
            str(source),
            captured,
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )

    assert b"vsview==0.14.0" in expected
    assert output.read_bytes() == expected


def test_windows_portable_inventory_requires_committed_python_proof(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    proof_path = "tools/windows_portable/runtime_smoke.py"
    for args in (
        ("rm", "--quiet", proof_path),
        (
            "-c",
            "user.name=Portable test",
            "-c",
            "user.email=portable@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "missing proof fixture",
        ),
    ):
        subprocess.run(
            ["git", "-C", str(inventory_source_repo), *args],
            check=True,
            capture_output=True,
            timeout=30,
        )
    result = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=inventory_source_repo,
    )
    assert result.returncode != 0
    assert proof_path in result.stderr
    assert not (bundle / "bundle_inventory.json").exists()


@pytest.mark.parametrize("field", ["bytes", "source_bytes", "build_source_bytes"])
def test_windows_portable_bundle_inventory_rejects_negative_artifact_sizes(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
    field: str,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    manifest["artifacts"][0][field] = -1
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=inventory_source_repo,
        manifest=manifest_path,
    )

    assert result.returncode != 0
    assert "must be non-negative" in result.stderr


@pytest.mark.parametrize(
    "field_path",
    [
        ("requirements_lock_sha256",),
        ("media_runtime_fingerprint",),
        ("media_runtime_fingerprints", "analysis"),
    ],
)
def test_windows_portable_bundle_inventory_rejects_malformed_fingerprints(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
    field_path: tuple[str, ...],
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    bundle_info_path = bundle / "bundle_info.json"
    bundle_info = json.loads(bundle_info_path.read_text(encoding="utf-8"))
    target = bundle_info
    for segment in field_path[:-1]:
        target = target[segment]
    target[field_path[-1]] = "NOT-A-SHA256"
    bundle_info_path.write_text(json.dumps(bundle_info), encoding="utf-8")

    result = _run_bundle_inventory(
        bundle=bundle, repo_root=repo_root, source_repo=inventory_source_repo
    )

    assert result.returncode != 0
    assert "must be a lowercase SHA-256 digest" in result.stderr


def test_windows_portable_bundle_inventory_never_imports_packaged_runtime_contract(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    packaged_fingerprints = {
        scope: str(index) * 64
        for index, scope in enumerate(("analysis", "probe", "alignment", "index", "full"), start=1)
    }
    contract = bundle / "app/src/frame_compare/vs/runtime_contract.py"
    contract.write_text("raise RuntimeError('packaged runtime must never execute')\n")

    bundle_info_path = bundle / "bundle_info.json"
    bundle_info = json.loads(bundle_info_path.read_text(encoding="utf-8"))
    bundle_info["media_runtime_fingerprint"] = packaged_fingerprints["full"]
    bundle_info["media_runtime_fingerprints"] = packaged_fingerprints
    bundle_info_path.write_text(json.dumps(bundle_info), encoding="utf-8")

    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    manifest["bundle"]["runtime_fingerprints"] = packaged_fingerprints
    manifest_path = tmp_path / "packaged-contract-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=inventory_source_repo,
        manifest=manifest_path,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    inventory = json.loads((bundle / "bundle_inventory.json").read_text(encoding="utf-8"))
    assert inventory["bundle"]["media_runtime_fingerprints"] == packaged_fingerprints


@pytest.mark.parametrize(
    "relative_path",
    [
        "runtime-smoke.mp4.lwi",
        "runtime-smoke.mp4.frame-compare-lsw1310-deadbeefcafe.lwi",
        "app/src/frame_compare/__pycache__/module.pyc",
        "config/local.toml",
        "comparison_videos/input.mkv",
        ".env",
        "app/.env",
        "config.toml",
        "app/config.toml",
        "report.html",
        "app/report.html",
        "private_key.xml",
    ],
)
def test_windows_portable_bundle_inventory_rejects_prohibited_local_and_generated_files(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
    relative_path: str,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    residue = bundle / relative_path
    residue.parent.mkdir(parents=True, exist_ok=True)
    residue.write_text("generated index", encoding="utf-8")
    result = _run_bundle_inventory(
        bundle=bundle, repo_root=repo_root, source_repo=inventory_source_repo
    )
    assert result.returncode != 0
    assert "prohibited local/generated files found in bundle" in result.stderr


def test_windows_portable_manifest_records_exact_source_locations(repo_root: Path) -> None:
    manifest_path = repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json"
    manifest = json.loads(_read_text_or_fail(manifest_path))
    schema = json.loads(
        _read_text_or_fail(repo_root / "tools" / "windows_portable" / "manifest.schema.json")
    )
    assert {"sha256", "bytes"} <= set(schema["$defs"]["corresponding_source"]["required"])
    assert manifest["corresponding_sources"]
    assert all(
        re.fullmatch(r"[a-f0-9]{64}", source["sha256"]) and source["bytes"] > 0
        for source in manifest["corresponding_sources"]
    )
    for artifact in manifest["artifacts"]:
        assert artifact["source_url"].startswith("https://")
        assert artifact["version"].split()[0].lower().replace("r", "") in (
            artifact["source_url"].lower() + artifact["url"].lower()
        )

    qt_source = next(
        source for source in manifest["corresponding_sources"] if source["name"] == "Qt"
    )
    assert qt_source["version"] == "6.12.0"
    assert "/6.12/6.12.0/" in qt_source["source_url"]
    assert qt_source["sha256"] == (
        "98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165"
    )
    assert qt_source["bytes"] == 443394020


@pytest.mark.parametrize("field", ["sha256", "bytes"])
def test_windows_portable_bundle_inventory_rejects_missing_corresponding_source_integrity(
    tmp_path: Path,
    repo_root: Path,
    inventory_source_repo: Path,
    field: str,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    manifest["corresponding_sources"][0].pop(field)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        source_repo=inventory_source_repo,
        manifest=manifest_path,
    )

    assert result.returncode != 0
    assert f"source[0].{field}" in result.stderr


def test_windows_portable_builder_writes_inventory_and_cleans_runtime_index(
    repo_root: Path,
) -> None:
    build_script = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    )
    assert "write_bundle_inventory.py" in build_script
    assert "bundle_inventory.json" in build_script
    assert "--require-clean-repo" in build_script
    assert "$legacyMediaIndexPath" not in build_script
    assert "runtime-smoke*.mp4.frame-compare-*.lwi" not in build_script
    assert '"pyside6_addons-*.dist-info"' in build_script
    assert '"pyside6_essentials-*.dist-info"' in build_script
    assert '"pyside6_pdf-*.dist-info"' in build_script
    assert '"pyside6_webengine-*.dist-info"' in build_script
    assert "License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only" in build_script
    assert "$lgplNotices.Count -lt 6" in build_script
    assert "Copy-Item -Recurse -Force -LiteralPath $pkgSrc" not in build_script
    assert 'Filter "__pycache__"' in build_script
    assert '$env:PYTHONDONTWRITEBYTECODE = "1"' in build_script
    assert "& $HostPython -B -I -S @arguments" in build_script
