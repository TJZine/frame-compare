from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ._helpers import read_text_or_fail as _read_text_or_fail


def _bundle_runtime_function_block(build_script: str) -> str:
    start = build_script.index("function Assert-BundleRuntime")
    end = build_script.index("function Copy-PythonDistLicenses")
    return build_script[start:end]


def test_windows_portable_bundle_launcher_sets_cwd_to_bundle_root(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "Push-Location $bundleRoot" in build_script
    assert "Pop-Location" in build_script


def test_windows_portable_bundle_launcher_restores_process_environment(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    assert "function Get-FrameCompareLauncherEnvironmentValue" in build_script
    assert "function Restore-FrameCompareLauncherEnvironmentValue" in build_script
    assert '$originalPath = Get-FrameCompareLauncherEnvironmentValue -Name "PATH"' in build_script
    assert (
        '$originalPythonUtf8 = Get-FrameCompareLauncherEnvironmentValue -Name "PYTHONUTF8"'
        in build_script
    )
    assert '$originalPythonPath = Get-FrameCompareLauncherEnvironmentValue -Name "PYTHONPATH"' in (
        build_script
    )
    assert (
        "$originalVsExtraPluginPath = Get-FrameCompareLauncherEnvironmentValue -Name "
        '"VAPOURSYNTH_EXTRA_PLUGIN_PATH"'
    ) in build_script
    assert (
        "$originalVsPluginPath = Get-FrameCompareLauncherEnvironmentValue -Name "
        '"VAPOURSYNTH_PLUGIN_PATH"'
    ) in build_script
    assert (
        'Restore-FrameCompareLauncherEnvironmentValue -Name "PATH" -Value $originalPath'
        in build_script
    )
    assert (
        'Restore-FrameCompareLauncherEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH" '
        "-Value $originalVsPluginPath"
    ) in build_script


def test_windows_portable_bundle_launcher_uses_cli_package_entry(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "& $python -m frame_compare.cli.entry @args" in build_script
    assert "frame_compare.cli_entry" not in build_script


def test_windows_portable_generated_cmd_launchers_have_absolute_powershell_fallbacks(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    assert 'set "POWERSHELL_EXE="' in build_script
    assert "%ProgramFiles%\\PowerShell\\7\\pwsh.exe" in build_script
    assert "%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" in build_script
    assert '"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File' in build_script


def test_windows_portable_build_resolves_relative_paths_from_provider_location(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
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

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert str(provider_root / "manifest.json") in output
    assert (provider_root / "relative-out").is_dir()
    assert (provider_root / "relative-cache").is_dir()
    assert not (process_root / "relative-out").exists()
    assert not (process_root / "relative-cache").exists()
    build_script = _read_text_or_fail(build_path)
    assert "$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot, $currentLocation)" in build_script


def test_windows_portable_build_creates_default_workspace_directories(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert '$bundleConfigDir = Join-Path $OutDir "config"' in build_script
    assert '$bundleInputDir = Join-Path $OutDir "comparison_videos"' in build_script
    assert "Ensure-Directory -Path $bundleConfigDir" in build_script
    assert "Ensure-Directory -Path $bundleInputDir" in build_script
    assert 'Join-Path $OutDir "screenshots"' not in build_script


def test_windows_portable_installed_default_config_uses_generated_root_only(
    repo_root: Path,
) -> None:
    install_script = _read_text_or_fail(repo_root / "tools" / "windows_portable" / "install.ps1")
    default_block_start = install_script.index('$defaultPortableConfigToml = @"')
    default_block_end = install_script.index('"@', default_block_start)
    default_config = install_script[default_block_start:default_block_end]

    assert 'generated_dir = "generated"' in default_config
    assert "screenshots_dir" not in default_config
    assert "use_run_folders" not in default_config
    assert "output_dir" not in default_config


def test_windows_portable_lifecycle_does_not_manage_generated_data(repo_root: Path) -> None:
    portable_root = repo_root / "tools" / "windows_portable"
    lifecycle_sources = "\n".join(
        (
            (portable_root / "uninstall.ps1").read_text(encoding="utf-8"),
            (portable_root / "shim" / "frame-compare-update.ps1").read_text(encoding="utf-8"),
        )
    )

    # These scripts may preserve/configure the authored value, but they must not
    # create, copy, move, back up, or delete generated output as install state.
    assert "screenshots_dir" not in lifecycle_sources
    assert "use_run_folders" not in lifecycle_sources
    assert "output_dir" not in lifecycle_sources
    assert ".update_backups" in lifecycle_sources


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

    assert manifest["manifest_version"] == 2
    assert manifest["bundle"]["vs_ref"] == "R78"
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

    expected_python_version = "3.13.14"
    assert manifest["bundle"]["python_version"] == expected_python_version
    python = artifacts["python-embed-amd64"]
    assert python["version"] == expected_python_version

    vapoursynth = artifacts["vapoursynth-portable-r78"]
    assert vapoursynth["version"] == "R78"
    assert vapoursynth["url"].endswith("/R78/VapourSynth64-Portable-R78.zip")
    assert vapoursynth["source_ref"] == "R78"
    assert vapoursynth["source_commit"] == "c2f5751a412347f306eb7f6a5985dd9a719f3896"

    lsmas = artifacts["vs-plugin-lsmas-1296.0.0.1-win-amd64-wheel"]
    assert lsmas["version"] == "1296.0.0.1"
    assert lsmas["install"]["type"] == "copy_file"
    assert lsmas["install"]["source_path"] == "vapoursynth/plugins/LSMASHSource.dll"
    assert lsmas["url"].endswith("vapoursynth_lsmas-1296.0.0.1-py3-none-win_amd64.whl")
    assert lsmas["install"]["destination"] == "vs/extra-plugins/lsmas/libvslsmashsource.dll"
    assert lsmas["install"]["manifest"] == "libvslsmashsource"

    placebo = artifacts["vs-plugin-vs-placebo-2.0.4-win-amd64-wheel"]
    assert placebo["version"] == "2.0.4"
    assert placebo["install"]["type"] == "python_wheel"
    assert placebo["url"].endswith("-win_amd64.whl")

    ffmpeg = artifacts["ffmpeg-btbn-win64-lgpl-8.1-2026-07-31"]
    assert ffmpeg["version"].startswith("n8.1.2-34-g9b6c8969e0")
    assert ffmpeg["license"]["spdx"] == "LGPL-2.1-or-later"
    assert not any(artifact_id.startswith("ffms2") for artifact_id in artifacts)

    for artifact in (vapoursynth, lsmas, placebo, ffmpeg):
        assert artifact["bytes"] > 0
        assert re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"])
        assert artifact["source_bytes"] > 0
        assert re.fullmatch(r"[a-f0-9]{64}", artifact["source_sha256"])


def test_windows_portable_build_uses_r74_plus_plugin_layout(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    assert "VAPOURSYNTH_EXTRA_PLUGIN_PATH" in build_script
    assert "Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue" in build_script
    assert '$sitePackages = Join-Path $BundleRoot "app\\\\site-packages"' in build_script
    assert '$vsPackage = Join-Path $sitePackages "vapoursynth"' in build_script
    assert '(Join-Path $vsPackage "plugins")' in build_script
    assert (
        '$vsDllPackage = Join-Path $sitePackages "vapoursynth\\\\libvapoursynth.dll"'
        in build_script
    )
    assert "expected R78 package layout" in build_script
    assert 'Join-Path $sitePackages "vapoursynth.dll"' not in build_script
    assert 'Join-Path $sitePackages "Lib\\\\site-packages\\\\vapoursynth.dll"' not in build_script
    assert "manifest.vs" in build_script
    assert "Install-PythonWheelArtifacts" in build_script
    assert "Expand-ArchiveFile" in build_script
    assert "7z extract" in build_script
    assert "tar extract" in build_script
    assert "VAPOURSYNTH_PLUGIN_PATH =" not in build_script
    assert "Consolidate-VapourSynthPlugins" not in build_script
    assert "PyQt6\\Qt6\\bin" not in build_script
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


def test_windows_portable_direct_placebo_smoke_respects_runtime_probe(
    repo_root: Path,
) -> None:
    build_script = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    )

    direct_smoke = build_script[
        build_script.index("def prove_placebo_tonemap_frame()") : build_script.index(
            "def prove_apply_tonemap_frame()"
        )
    ]
    assert "probe_libplacebo_runtime" in direct_smoke
    assert "placebo_direct_frame=skipped reason=vulkan_runtime_unavailable" in direct_smoke
    assert "direct_out.get_frame(0)" in direct_smoke


def test_windows_portable_workflow_surfaces_direct_placebo_result(repo_root: Path) -> None:
    workflow = _read_text_or_fail(
        repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    )

    assert "WINDOWS_BUNDLE_PROOF placebo_direct_frame=ok " in workflow
    assert (
        "WINDOWS_BUNDLE_PROOF placebo_direct_frame=skipped reason=vulkan_runtime_unavailable"
    ) in workflow
    assert "direct placebo frame proof remains required in Phase 2" in workflow


def test_windows_portable_build_runtime_validation_proves_vs_plugins(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    for expected in (
        "Invoke-BundleRuntimeProof",
        "phase=$Phase start",
        "version_major == 78",
        "LWLibavSource",
        "LibavSMASHSource",
        "core.placebo.Tonemap",
        "apply_tonemap",
        "get_frame(0)",
        "import vspreview",
        "import PyQt6",
        "WINDOWS_BUNDLE_PROOF",
        "ffmpeg tiny media generation",
        "runtime_contract=ok",
        "FFMS2 must remain excluded",
        "standalone FFmpeg directory leaked onto PATH",
    ):
        assert expected in build_script

    for phase in (
        "package_imports",
        "runtime_contract",
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
    assert 'Phase "placebo_tonemap_frame" -MediaPath $mediaPath -Required $true' in build_script
    assert "placebo_tonemap_api=ok" in build_script
    assert "apply_tonemap=ok " in build_script
    assert "unexpectedly reduced output below 10-bit" in build_script
    assert "libplacebo_runtime_usable=" in build_script


def test_windows_portable_build_runtime_validation_restores_process_environment(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    runtime_validation = _bundle_runtime_function_block(build_script)

    assert "function Get-ProcessEnvironmentValue" in build_script
    assert "function Restore-ProcessEnvironmentValue" in build_script
    assert '$originalPath = Get-ProcessEnvironmentValue -Name "PATH"' in build_script
    assert '$originalPythonUtf8 = Get-ProcessEnvironmentValue -Name "PYTHONUTF8"' in build_script
    assert '$originalPythonPath = Get-ProcessEnvironmentValue -Name "PYTHONPATH"' in build_script
    assert (
        "$originalVsExtraPluginPath = Get-ProcessEnvironmentValue -Name "
        '"VAPOURSYNTH_EXTRA_PLUGIN_PATH"'
    ) in build_script
    assert (
        '$originalVsPluginPath = Get-ProcessEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH"'
        in build_script
    )
    assert 'Restore-ProcessEnvironmentValue -Name "PATH" -Value $originalPath' in build_script
    assert (
        'Restore-ProcessEnvironmentValue -Name "VAPOURSYNTH_PLUGIN_PATH" '
        "-Value $originalVsPluginPath"
    ) in build_script
    for name in (
        "FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT",
        "FRAME_COMPARE_RUNTIME_KIND",
        "FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED",
        "FRAME_COMPARE_FFMPEG_EXECUTABLE",
        "FRAME_COMPARE_FFPROBE_EXECUTABLE",
    ):
        assert f'Get-ProcessEnvironmentValue -Name "{name}"' in runtime_validation
        assert f'Restore-ProcessEnvironmentValue -Name "{name}"' in runtime_validation
    assert runtime_validation.count("Set-BundleRuntimeEnvironment -BundleRoot $BundleRoot") == 1
    assert runtime_validation.index("try {") < runtime_validation.index(
        "Set-BundleRuntimeEnvironment -BundleRoot $BundleRoot"
    )
    assert runtime_validation.index("Set-BundleRuntimeEnvironment -BundleRoot $BundleRoot") < (
        runtime_validation.index("} finally {")
    )


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


def test_windows_portable_build_surfaces_dirty_app_source_before_archiving(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    function_start = build_script.index("function Copy-RepoApp")
    function_end = build_script.index("function Configure-EmbeddedPython")
    copy_repo_app = build_script[function_start:function_end]

    status_command = (
        "git -C $RepoRoot status --porcelain=v1 --untracked-files=all -- src/frame_compare"
    )
    archive_command = "git -C $RepoRoot archive"
    assert status_command in copy_repo_app
    assert 'Assert-LastExitCode -CommandLabel "inspect Frame Compare source worktree"' in (
        copy_repo_app
    )
    assert "if ($RequireReleasePublicKey)" in copy_repo_app
    assert "throw $dirtySourceMessage" in copy_repo_app
    assert "Write-Warning $dirtySourceMessage" in copy_repo_app
    assert copy_repo_app.index(status_command) < copy_repo_app.index(archive_command)


def test_windows_portable_build_reads_version_from_archived_app_source(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)

    assert 'Get-AppVersionFromSource -RepoRootPath (Join-Path $OutDir "app")' in build_script
    assert "Get-AppVersionFromSource -RepoRootPath $RepoRoot" not in build_script


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
    assert "schema_version = 2" in build_script
    assert "manifest_version = $manifestVersion" in build_script
    assert "media_runtime_fingerprint" in build_script
    assert "media_runtime_fingerprints" in build_script


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


def test_windows_portable_build_uses_vendored_manifest_license_files(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "function Resolve-ManifestRelativePath" in build_script
    assert "function Copy-ManifestLicenseFiles" in build_script
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
    paired_required_fields = {frozenset(rule["then"]["required"]) for rule in artifact_def["allOf"]}
    assert paired_required_fields == {
        frozenset({"source_sha256", "source_bytes"}),
        frozenset({"build_source_sha256", "build_source_bytes"}),
    }
    assert "oneOf" in install_def

    variants = {variant["properties"]["type"]["const"]: variant for variant in install_def["oneOf"]}
    assert set(variants) == {"extract", "copy_file", "python_wheel"}
    assert variants["extract"]["required"] == ["type", "destination"]
    assert variants["copy_file"]["required"] == ["type", "destination", "source_path"]
    assert "manifest" in variants["copy_file"]["properties"]
    assert variants["python_wheel"]["required"] == ["type"]
    assert "destination" not in variants["python_wheel"]["properties"]


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
        "PyQt6": ("6.10.2", "GPL-3.0-only"),
        "PyQt6-Qt6": ("6.10.2", "LGPL-3.0-only"),
        "PyQt6-sip": ("13.10.3", "BSD-2-Clause"),
        "VapourSynth": ("78", "LGPL-2.1-or-later"),
        "vs-placebo": ("2.0.4", "LGPL-2.1-only"),
        "VSPreview": ("0.20.1", "Apache-2.0"),
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
    shutil.copy2(
        repo_root / "tools" / "windows_portable" / "update_public_key.xml",
        shim / "update_public_key.xml",
    )
    manifest = json.loads(
        (repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json").read_text(
            encoding="utf-8"
        )
    )
    runtime_fingerprints = manifest["bundle"]["runtime_fingerprints"]
    _write_packaged_runtime_contract(bundle=bundle, fingerprints=runtime_fingerprints)
    (bundle / "bundle_info.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "bundle_kind": "full",
                "app_version": "0.1.0",
                "requirements_lock_sha256": "a" * 64,
                "manifest_version": 2,
                "platform": "windows-x64",
                "media_runtime_fingerprint": runtime_fingerprints["full"],
                "media_runtime_fingerprints": runtime_fingerprints,
            }
        ),
        encoding="utf-8",
    )
    return bundle


def _run_bundle_inventory(
    *,
    bundle: Path,
    repo_root: Path,
    manifest: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools" / "windows_portable" / "write_bundle_inventory.py"),
            "--bundle-root",
            str(bundle),
            "--manifest",
            str(manifest or repo_root / "tools" / "windows_portable" / "manifest.windows-x64.json"),
            "--repo-root",
            str(repo_root),
            "--output",
            str(bundle / "bundle_inventory.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )


def test_windows_portable_bundle_inventory_is_sorted_exact_and_path_safe(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    result = _run_bundle_inventory(bundle=bundle, repo_root=repo_root)
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
        "pyqt6",
        "pyqt6-qt6",
        "pyqt6-sip",
        "vapoursynth",
        "vs-placebo",
        "vspreview",
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
        and source["version"] == "6.10.2"
        and "/6.10/6.10.2/" in source["source_url"]
        for source in inventory["corresponding_sources"]
    )
    assert all(
        re.fullmatch(r"[a-f0-9]{64}", source["sha256"]) and source["bytes"] > 0
        for source in inventory["corresponding_sources"]
    )
    assert inventory["source_build_install_scripts"] == sorted(
        inventory["source_build_install_scripts"]
    )

    license_paths = [license_entry["path"] for license_entry in inventory["licenses"]]
    assert license_paths == sorted(license_paths)
    assert "licenses/frame-compare-LICENSE.txt" in license_paths
    source_urls = (bundle / "licenses" / "SOURCE_URLS.txt").read_text(encoding="utf-8")
    assert inventory["bundle"]["commit_sha"] in source_urls
    assert "qt-everywhere-src-6.10.2.tar.xz" in source_urls
    assert (bundle / "licenses" / "THIRD_PARTY_NOTICES.txt").is_file()


@pytest.mark.parametrize("field", ["bytes", "source_bytes", "build_source_bytes"])
def test_windows_portable_bundle_inventory_rejects_negative_artifact_sizes(
    tmp_path: Path,
    repo_root: Path,
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

    result = _run_bundle_inventory(bundle=bundle, repo_root=repo_root)

    assert result.returncode != 0
    assert "must be a lowercase SHA-256 digest" in result.stderr


def test_windows_portable_bundle_inventory_rejects_matching_stale_runtime_fingerprints(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    stale_fingerprints = dict.fromkeys(
        ("analysis", "probe", "alignment", "index", "full"), "0" * 64
    )
    bundle_info_path = bundle / "bundle_info.json"
    bundle_info = json.loads(bundle_info_path.read_text(encoding="utf-8"))
    bundle_info["media_runtime_fingerprint"] = stale_fingerprints["full"]
    bundle_info["media_runtime_fingerprints"] = stale_fingerprints
    bundle_info_path.write_text(json.dumps(bundle_info), encoding="utf-8")

    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    manifest["bundle"]["runtime_fingerprints"] = stale_fingerprints
    manifest_path = tmp_path / "stale-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_bundle_inventory(bundle=bundle, repo_root=repo_root, manifest=manifest_path)

    assert result.returncode != 0
    assert "do not match the canonical windows-x64 contract" in result.stderr


def test_windows_portable_bundle_inventory_uses_packaged_runtime_contract(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    packaged_fingerprints = {
        scope: str(index) * 64
        for index, scope in enumerate(("analysis", "probe", "alignment", "index", "full"), start=1)
    }
    _write_packaged_runtime_contract(bundle=bundle, fingerprints=packaged_fingerprints)

    bundle_info_path = bundle / "bundle_info.json"
    bundle_info = json.loads(bundle_info_path.read_text(encoding="utf-8"))
    bundle_info["media_runtime_fingerprint"] = packaged_fingerprints["full"]
    bundle_info["media_runtime_fingerprints"] = packaged_fingerprints
    bundle_info_path.write_text(json.dumps(bundle_info), encoding="utf-8")

    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    assert manifest["bundle"]["runtime_fingerprints"] != packaged_fingerprints
    manifest["bundle"]["runtime_fingerprints"] = packaged_fingerprints
    manifest_path = tmp_path / "packaged-contract-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_bundle_inventory(
        bundle=bundle,
        repo_root=repo_root,
        manifest=manifest_path,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    inventory = json.loads((bundle / "bundle_inventory.json").read_text(encoding="utf-8"))
    assert inventory["bundle"]["media_runtime_fingerprints"] == packaged_fingerprints


@pytest.mark.parametrize(
    "relative_path",
    [
        "runtime-smoke.mp4.lwi",
        "runtime-smoke.mp4.frame-compare-lsw1296-deadbeefcafe.lwi",
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
    relative_path: str,
) -> None:
    bundle = _write_fake_inventory_bundle(tmp_path=tmp_path, repo_root=repo_root)
    residue = bundle / relative_path
    residue.parent.mkdir(parents=True, exist_ok=True)
    residue.write_text("generated index", encoding="utf-8")
    result = _run_bundle_inventory(bundle=bundle, repo_root=repo_root)
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
    assert qt_source["version"] == "6.10.2"
    assert "/6.10/6.10.2/" in qt_source["source_url"]
    assert qt_source["sha256"] == (
        "c3df0f0e421130cc52ed81cb712358804471ce9bd2a41d97828f9f5b1bf7fed2"
    )
    assert qt_source["bytes"] == 1315359412


@pytest.mark.parametrize("field", ["sha256", "bytes"])
def test_windows_portable_bundle_inventory_rejects_missing_corresponding_source_integrity(
    tmp_path: Path,
    repo_root: Path,
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
    assert "function Write-BundleInventory" in build_script
    assert "write_bundle_inventory.py" in build_script
    assert "bundle_inventory.json" in build_script
    assert "--require-clean-repo" in build_script
    assert "Remove-Item -Force -LiteralPath $legacyMediaIndexPath" in build_script
    assert (
        "Get-ChildItem -LiteralPath $BundleRoot -Filter "
        '"runtime-smoke.mp4.frame-compare-*.lwi"' in build_script
    )
    assert "function Copy-RequiredQtLicenseDirectories" in build_script
    assert 'Join-Path $licenseOwners[0].FullName "LICENSE"' in build_script
    assert 'Join-Path $licenseOwners[0].FullName "licenses\\\\LICENSE"' in build_script
    assert "$licenseCandidates.Count -ne 1" in build_script
    assert "git -C $RepoRoot archive" in build_script
    assert "HEAD src/frame_compare" in build_script
    assert "Copy-Item -Recurse -Force -LiteralPath $pkgSrc" not in build_script
    assert "function Remove-PythonBytecodeCaches" in build_script
    assert 'Filter "__pycache__"' in build_script
    assert '$env:PYTHONDONTWRITEBYTECODE = "1"' in build_script
    assert "& $python -B @arguments" in build_script
