from __future__ import annotations

import json
import re
from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_bundle_launcher_sets_cwd_to_bundle_root(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "Push-Location $bundleRoot" in build_script
    assert "Pop-Location" in build_script


def test_windows_portable_bundle_launcher_uses_cli_package_entry(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "& $python -m frame_compare.cli.entry @args" in build_script
    assert "frame_compare.cli_entry" not in build_script


def test_windows_portable_build_creates_default_workspace_directories(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert '$bundleConfigDir = Join-Path $OutDir "config"' in build_script
    assert '$bundleInputDir = Join-Path $OutDir "comparison_videos"' in build_script
    assert "Ensure-Directory -Path $bundleConfigDir" in build_script
    assert "Ensure-Directory -Path $bundleInputDir" in build_script


def test_windows_portable_build_download_errors_name_manifest_remediation(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "Failed to download artifact '$id' from $url" in build_script
    assert "update $ManifestPath with a reachable URL and matching sha256" in build_script


def test_windows_portable_ffmpeg_manifest_uses_reachable_pinned_asset_shape(
    repo_root: Path,
) -> None:
    manifest_path = repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json"
    manifest = json.loads(_read_text_or_fail(manifest_path))
    ffmpeg = next(
        artifact for artifact in manifest["artifacts"] if artifact["id"].startswith("ffmpeg-")
    )

    assert "autobuild-2026-02-04-14-23" not in ffmpeg["url"]
    assert "/releases/download/autobuild-" in ffmpeg["url"]
    assert ffmpeg["url"].endswith(".zip")
    assert len(ffmpeg["sha256"]) == 64
    assert ffmpeg["install"]["strip_prefix"].rstrip("/") in ffmpeg["url"]
    assert ffmpeg["license"]["spdx"] == "LGPL-2.1-or-later"


def test_windows_portable_manifest_tracks_r76_runtime_artifacts(repo_root: Path) -> None:
    manifest_path = repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json"
    manifest = json.loads(_read_text_or_fail(manifest_path))
    artifacts = {artifact["id"]: artifact for artifact in manifest["artifacts"]}

    assert manifest["bundle"]["vs_ref"] == "R76"
    assert manifest["bundle"]["python_version"].startswith("3.13.")
    assert "3.14" not in manifest["bundle"]["python_version"]

    python = artifacts["python-embed-amd64"]
    assert python["version"].startswith("3.13.")
    assert python["url"].endswith(f"python-{python['version']}-embed-amd64.zip")

    vapoursynth = artifacts["vapoursynth-portable-r76"]
    assert vapoursynth["version"] == "R76"
    assert vapoursynth["url"].endswith("/R76/VapourSynth64-Portable-R76.zip")

    lsmas = artifacts["vs-plugin-lsmas-1282"]
    assert lsmas["version"] == "1282.0.0.0"
    assert lsmas["install"]["destination"] == "vs/extra-plugins/lsmas/libvslsmashsource.dll"
    assert lsmas["install"]["manifest"] == "libvslsmashsource"

    placebo = artifacts["vs-plugin-vs-placebo-2.0.2-win-amd64-wheel"]
    assert placebo["version"] == "2.0.2"
    assert placebo["install"]["type"] == "python_wheel"
    assert placebo["url"].endswith("-win_amd64.whl")


def test_windows_portable_build_uses_r74_plus_plugin_layout(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    assert "VAPOURSYNTH_EXTRA_PLUGIN_PATH" in build_script
    assert "Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue" in build_script
    assert '$sitePackages = Join-Path $BundleRoot "app\\\\site-packages"' in build_script
    assert '$vsPackage = Join-Path $sitePackages "vapoursynth"' in build_script
    assert '$vsPluginDir = Join-Path $vsPackage "plugins"' in build_script
    assert (
        '$vsDllPackage = Join-Path $sitePackages "vapoursynth\\\\libvapoursynth.dll"'
        in build_script
    )
    assert "expected R76 package layout" in build_script
    assert 'Join-Path $sitePackages "vapoursynth.dll"' not in build_script
    assert 'Join-Path $sitePackages "Lib\\\\site-packages\\\\vapoursynth.dll"' not in build_script
    assert "manifest.vs" in build_script
    assert "Install-PythonWheelArtifacts" in build_script
    assert "Expand-ArchiveFile" in build_script
    assert "7z extract" in build_script
    assert "tar extract" in build_script
    assert "VAPOURSYNTH_PLUGIN_PATH =" not in build_script
    assert "Consolidate-VapourSynthPlugins" not in build_script


def test_windows_portable_build_runtime_validation_proves_vs_plugins(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    for expected in (
        "Invoke-BundleRuntimeProof",
        "phase=$Phase start",
        "version_major == 76",
        "core.lsmas.LWLibavSource",
        "core.placebo.Tonemap",
        "apply_tonemap",
        "get_frame(0)",
        "import vspreview",
        "import PyQt6",
        "WINDOWS_BUNDLE_PROOF",
        "ffmpeg tiny media generation",
    ):
        assert expected in build_script

    for phase in (
        "package_imports",
        "vapoursynth_environment",
        "lwlibavsource_frame",
        "placebo_tonemap_api",
        "apply_tonemap_frame",
        "placebo_tonemap_frame",
        "vspreview_pyqt6_import",
    ):
        assert phase in build_script

    assert (
        "bundle runtime validation phase '$Phase' failed with exit code $exitCode" in build_script
    )
    assert 'Phase "vspreview_pyqt6_import" -MediaPath $mediaPath -Required $false' in build_script
    assert 'Phase "lwlibavsource_frame" -MediaPath $mediaPath -Required $true' in build_script
    assert 'Phase "placebo_tonemap_api" -MediaPath $mediaPath -Required $true' in build_script
    assert 'Phase "apply_tonemap_frame" -MediaPath $mediaPath -Required $true' in build_script
    assert 'Phase "placebo_tonemap_frame" -MediaPath $mediaPath -Required $false' in build_script
    assert "placebo_tonemap_api=ok" in build_script
    assert "apply_tonemap=ok frame=rendered fallback_aware=true" in build_script
    assert "libplacebo_runtime_usable=" in build_script


def test_pyproject_defines_vspreview_optional_dependency(repo_root: Path) -> None:
    pyproject_path = repo_root / "pyproject.toml"
    pyproject = _read_text_or_fail(pyproject_path)
    assert "[project.optional-dependencies]" in pyproject
    assert re.search(r"vspreview\s*=\s*\[", pyproject)
    assert re.search(r'"vspreview([^"]*)"', pyproject)


def test_windows_portable_build_exports_vspreview_extra(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "--extra vspreview" in build_script
    assert "requirements.lock.txt" in build_script


def test_windows_portable_build_installs_manifest_wheels_dependency_closed(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    assert 'Get-RequiredStringProperty -Object $artifact -Name "sha256"' in build_script
    assert "Assert-Sha256 -FilePath $wheelPath -ExpectedHex $sha256" in build_script
    assert re.search(
        r"uv pip install --reinstall --strict --no-deps --target \$sitePackages \$wheelPath",
        build_script,
    )
    assert "uv pip install --no-deps --only-binary :all: --target $sitePackages $vsWheel" in (
        build_script
    )


def test_windows_portable_build_has_release_public_key_gate(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "[switch]$RequireReleasePublicKey" in build_script
    assert "function Assert-ReleasePublicKey()" in build_script
    assert 'Join-Path $PSScriptRoot "validate_update_public_key.ps1"' in build_script
    assert 'Join-Path $PSScriptRoot "update_public_key.xml"' in build_script
    assert "& $validator -PublicKeyPath $publicKey" in build_script
    assert re.search(
        r"function Main\(\) \{\s*if \(\$RequireReleasePublicKey\) \{\s*Assert-ReleasePublicKey",
        build_script,
    )


def test_windows_portable_build_runtime_validation_checks_qt_stack(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "import vspreview" in build_script
    assert "import PyQt6" in build_script
    assert "pyqt6_import=ok" in build_script
    assert "vspreview_pyqt6=ok" in build_script
    assert 'Phase "vspreview_pyqt6_import" -MediaPath $mediaPath -Required $false' in build_script


def test_windows_portable_build_writes_bundle_info_file(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "bundle_info.json" in build_script
    assert "requirements_lock_sha256" in build_script
    assert "bundle_kind" in build_script
    assert "platform" in build_script


def test_windows_portable_build_portable_updater_launcher_fails_closed_without_exit_code(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "& $updater @args" in build_script
    assert "if ($null -eq $LASTEXITCODE) {" in build_script
    assert "exit 1" in build_script
    assert "if ($?)" not in build_script


def test_windows_portable_build_copies_dist_info_licenses_when_present(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert (
        re.search(r"dist-info\\\\licenses", build_script) or "dist-info\\licenses" in build_script
    )
