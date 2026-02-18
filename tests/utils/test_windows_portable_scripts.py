import json
import re
from pathlib import Path


def _first_significant_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return stripped
    return ""


def test_first_significant_line_returns_empty_for_blank_or_comment_only() -> None:
    assert _first_significant_line("") == ""
    assert _first_significant_line("# comment\n# another") == ""
    assert _first_significant_line("\n\n\n") == ""


def _read_text_or_fail(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def test_install_from_source_param_block_is_first_statement(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    script_text = _read_text_or_fail(script_path)
    assert _first_significant_line(script_text).startswith("Param(")


def test_install_from_source_avoids_pscore_only_windows_variable(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    script_text = _read_text_or_fail(script_path)
    assert "$IsWindows" not in script_text


def test_root_install_cmd_exists_and_calls_install_ps1(repo_root: Path) -> None:
    path = repo_root / "install.cmd"
    assert path.exists()
    text = _read_text_or_fail(path).lower()
    assert "powershell" in text
    assert "-noprofile" in text
    assert "-executionpolicy bypass" in text
    assert "-file" in text
    assert "install.ps1" in text


def test_root_install_ps1_exists_and_delegates_to_install_from_source(repo_root: Path) -> None:
    path = repo_root / "install.ps1"
    assert path.exists()
    text = _read_text_or_fail(path)
    assert _first_significant_line(text).startswith("Param(")
    normalized = text.replace("\\\\", "/").replace("\\", "/")
    assert "tools/windows_portable/install-from-source.ps1" in normalized


def test_install_from_source_mentions_uv_auto_install(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    text = _read_text_or_fail(script_path).lower()
    assert "winget" in text
    assert "pip" in text
    assert "uv" in text
    assert "docs: https://docs.astral.sh/uv/getting-started/installation/" in text
    assert "curl" not in text
    assert "invoke-expression" not in text


def test_install_from_source_uv_install_order_is_deterministic(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "windows_portable" / "install-from-source.ps1"
    text = _read_text_or_fail(script_path).lower()

    # The plan requires winget first, then pip as fallback.
    winget_idx = text.index("winget install")
    pip_idx = text.index("pip install --user uv")
    assert winget_idx < pip_idx

    # Recovery block must be copy/paste friendly and include both commands.
    assert "winget install --id astral-sh.uv -e --source winget" in text
    assert "py -m pip install --user uv" in text


def test_windows_portable_workflow_does_not_flatten_zip_contents(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    wf = _read_text_or_fail(wf_path)
    assert 'Compress-Archive -Path "$bundle/*"' not in wf


def test_windows_portable_workflow_zips_bundle_folder(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    wf = _read_text_or_fail(wf_path)
    assert "Compress-Archive -Path $bundle -DestinationPath $zip" in wf


def test_windows_portable_workflow_verifies_zip_required_entries(repo_root: Path) -> None:
    wf_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    wf = _read_text_or_fail(wf_path)
    required = [
        "frame-compare-portable-win-x64/install.cmd",
        "frame-compare-portable-win-x64/install.ps1",
        "frame-compare-portable-win-x64/frame-compare.ps1",
        "frame-compare-portable-win-x64/frame-compare-update.cmd",
        "frame-compare-portable-win-x64/shim/frame-compare.cmd",
        "frame-compare-portable-win-x64/shim/frame-compare-update.cmd",
        "frame-compare-portable-win-x64/frame-compare-update.ps1",
        "frame-compare-portable-win-x64/shim/frame-compare-update.ps1",
    ]
    for entry in required:
        assert entry in wf


def test_windows_portable_shim_runs_bundle_launcher_from_bundle_root(repo_root: Path) -> None:
    shim_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    shim = _read_text_or_fail(shim_path)
    assert "Push-Location $bundlePath" in shim
    assert "Pop-Location" in shim


def test_windows_portable_bundle_launcher_sets_cwd_to_bundle_root(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "Push-Location $bundleRoot" in build_script
    assert "Pop-Location" in build_script


def test_windows_portable_shim_injects_state_config_when_missing_explicit_config(
    repo_root: Path,
) -> None:
    shim_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    shim = _read_text_or_fail(shim_path)
    assert re.search(r"\$stateDir\s*=\s*Join-Path\s+\$installRoot\s+\"state\"", shim)
    assert re.search(r"\$stateConfigToml\s*=\s*Join-Path\s+\$stateDir\s+\"config\.toml\"", shim)
    assert re.search(r"function\s+Test-ArgsContainConfigFlag\b", shim)
    assert re.search(r"function\s+Get-ConfigInjectionIndex\b", shim)
    assert re.search(r"function\s+Add-ArgsAtIndex\b", shim)
    assert re.search(r"\$command\s*-eq\s*\"run\".*\$command\s*-eq\s*\"wizard\"", shim, re.DOTALL)
    assert re.search(r"\$command\s*-eq\s*\"preset\"", shim)
    assert re.search(r"\$subcommand\s*-eq\s*\"list\".*\"apply\".*\"save\"", shim, re.DOTALL)
    assert re.search(r"\$arg\.StartsWith\(\"--config=\"\)", shim)
    assert re.search(r"\$arg\s*-match\s*'\^-c", shim)
    assert re.search(r"&\s*\$bundleLauncher\s+@forwardArgs", shim)
    assert "@extraArgs @args" not in shim


def test_windows_portable_shim_preset_apply_injects_config_before_positional(
    repo_root: Path,
) -> None:
    """Get-ConfigInjectionIndex should inject after `preset apply` and before positional args."""
    shim_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    shim = _read_text_or_fail(shim_path)
    assert re.search(r"\$subcommand\s*-eq\s*\"apply\"", shim)
    assert re.search(r"return\s+\$subcommandIndex\s*\+\s*1", shim)


def test_windows_portable_shim_supports_dot_sourcing_without_execution(repo_root: Path) -> None:
    shim_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    shim = _read_text_or_fail(shim_path)
    assert re.search(r'\$MyInvocation\.InvocationName\s*-ne\s*"\."', shim) or re.search(
        r"\$MyInvocation\.InvocationName\s*-ne\s*'\.'", shim
    )


def test_windows_portable_installer_initializes_state_config_toml(repo_root: Path) -> None:
    installer_path = repo_root / "tools" / "windows_portable" / "install.ps1"
    installer = _read_text_or_fail(installer_path)
    assert '$portableConfigToml = Join-Path $stateDir "config.toml"' in installer
    assert (
        '$bundleConfigToml = Join-Path (Join-Path $bundleRoot "config") "config.toml"' in installer
    )
    assert (
        "Copy-Item -LiteralPath $bundleConfigToml -Destination $portableConfigToml -Force"
        in installer
    )
    assert "[paths]" in installer


def test_windows_portable_build_creates_default_workspace_directories(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert '$bundleConfigDir = Join-Path $OutDir "config"' in build_script
    assert '$bundleInputDir = Join-Path $OutDir "comparison_videos"' in build_script
    assert "Ensure-Directory -Path $bundleConfigDir" in build_script
    assert "Ensure-Directory -Path $bundleInputDir" in build_script


def test_windows_portable_docs_describe_default_workspace_directories(repo_root: Path) -> None:
    readme_path = repo_root / "README.md"
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    readme = _read_text_or_fail(readme_path)
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "config/ and comparison_videos/ directories in the bundle root" in readme
    assert "comparison_videos" in portable_readme


def test_pyproject_defines_vspreview_optional_dependency(repo_root: Path) -> None:
    pyproject_path = repo_root / "pyproject.toml"
    pyproject = _read_text_or_fail(pyproject_path)
    assert "[project.optional-dependencies]" in pyproject
    assert re.search(r"vspreview\s*=\s*\[", pyproject)
    assert re.search(r'"vspreview([^"]*)"', pyproject)
    assert re.search(r'"PySide6([^"]*)"', pyproject)


def test_windows_portable_build_exports_vspreview_extra(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "--extra vspreview" in build_script
    assert "requirements.lock.txt" in build_script


def test_windows_portable_build_runtime_validation_checks_qt_stack(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "import vspreview" in build_script
    assert "import PySide6" in build_script


def test_windows_portable_build_writes_bundle_info_file(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "bundle_info.json" in build_script
    assert "requirements_lock_sha256" in build_script
    assert "bundle_kind" in build_script
    assert "platform" in build_script


def test_windows_portable_update_artifacts_exist(repo_root: Path) -> None:
    paths = [
        repo_root / "tools" / "windows_portable" / "update_manifest.schema.json",
        repo_root / "tools" / "windows_portable" / "bundle_info.schema.json",
        repo_root / "tools" / "windows_portable" / "update_public_key.xml",
        repo_root / "tools" / "windows_portable" / "build_update.ps1",
        repo_root / "tools" / "windows_portable" / "sign_update.ps1",
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1",
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.cmd",
    ]
    for path in paths:
        assert path.exists(), f"Required file not found: {path}"


def test_windows_portable_installer_copies_update_shims(repo_root: Path) -> None:
    installer_path = repo_root / "tools" / "windows_portable" / "install.ps1"
    installer = _read_text_or_fail(installer_path)
    assert "frame-compare-update.ps1" in installer
    assert "frame-compare-update.cmd" in installer
    assert "update_public_key.xml" in installer


def test_windows_portable_workflow_verifies_workspace_directories(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)
    assert '$bundleConfigDir = Join-Path $bundle "config"' in workflow
    assert '$bundleInputDir = Join-Path $bundle "comparison_videos"' in workflow
    assert "Test-Path -LiteralPath $bundleConfigDir -PathType Container" in workflow
    assert "Test-Path -LiteralPath $bundleInputDir -PathType Container" in workflow
    assert 'throw "Missing default workspace directory in bundle:' in workflow


def test_windows_portable_docs_disambiguate_source_bundle_root(repo_root: Path) -> None:
    readme_path = repo_root / "README.md"
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    readme = _read_text_or_fail(readme_path)
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "dist/frame-compare-portable-win-x64" in readme
    assert "not the repository root" in readme
    assert "includes VSPreview + PySide6" in readme
    assert "frame-compare-update apply" in readme
    assert "frame-compare-update apply" in portable_readme


def test_windows_portable_docs_use_frozen_uv_sync_for_vspreview_extra(repo_root: Path) -> None:
    readme_path = repo_root / "README.md"
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    readme = _read_text_or_fail(readme_path)
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "uv sync --group dev --extra vspreview --frozen" in readme
    assert "uv sync --group dev --extra vspreview --frozen" in portable_readme


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


def test_windows_portable_workflow_validates_update_public_key_on_release(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)
    assert "Validate update public key" in workflow
    assert "tools/windows_portable/update_public_key.xml" in workflow.replace("\\", "/")
    assert (
        "if: github.event_name == 'release' || github.event_name == 'workflow_dispatch'" in workflow
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


def test_windows_portable_updater_always_clears_rsa_in_signature_verification(
    repo_root: Path,
) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    signature_fn = re.search(
        r"function\s+Verify-ManifestSignature\b[\s\S]*?\n\}",
        updater,
        flags=re.DOTALL,
    )
    assert signature_fn is not None
    assert re.search(r"\bfinally\b", signature_fn.group(0))
    assert re.search(r"\$rsa\.Clear\(\)", signature_fn.group(0))


def test_windows_portable_build_update_validates_normalized_from_app_version_min(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_update.ps1"
    build_script = _read_text_or_fail(build_path)
    fn = re.search(r"function\s+Get-FromVersionMin\b[\s\S]*?\n\}", build_script, flags=re.DOTALL)
    assert fn is not None
    assert re.search(r"\bthrow\b", fn.group(0))
    assert re.search(r"\bTest-StringInRange\b", fn.group(0))


def test_windows_portable_build_update_hashes_staged_payload_files(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_update.ps1"
    build_script = _read_text_or_fail(build_path)
    fn = re.search(r"function\s+New-ManifestFiles\b[\s\S]*?\n\}", build_script, flags=re.DOTALL)
    assert fn is not None
    assert re.search(
        r"Copy-Item\s+-LiteralPath\s+\$sourceFile\.FullName\s+-Destination\s+\$destFile",
        fn.group(0),
    )
    assert re.search(r"Get-FileHash\s+-LiteralPath\s+\$destFile\s+-Algorithm\s+SHA256", fn.group(0))


def test_windows_portable_build_portable_updater_launcher_fails_closed_without_exit_code(
    repo_root: Path,
) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert "& $updater @args" in build_script
    assert "if ($null -eq $LASTEXITCODE) {" in build_script
    assert "exit 1" in build_script
    assert "if ($?)" not in build_script


def test_windows_portable_readme_release_signing_header_has_no_leading_space(
    repo_root: Path,
) -> None:
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "\nRELEASE SIGNING (Maintainers):" in portable_readme


def test_windows_portable_sign_update_avoids_private_key_path_cli_argument(repo_root: Path) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    assert "PrivateKeyXml" not in sign_script
    assert "SIGNING_KEY_XML_PATH" in sign_script
    assert "Read-Host" in sign_script
    assert "UserInteractive" in sign_script
    assert "IsInputRedirected" in sign_script


def test_windows_portable_docs_do_not_show_private_key_path_on_command_line(
    repo_root: Path,
) -> None:
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "-PrivateKeyXml" not in portable_readme
    assert "SIGNING_KEY_XML_PATH" in portable_readme


def test_windows_portable_updater_restores_original_on_rename_failure(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    assert "Rename current frame_compare to .old" in updater
    assert "Rename .new into place" in updater
    assert "Restore .old after rename failure" in updater or "Rename failed; restoring" in updater


def test_windows_portable_build_copies_dist_info_licenses_when_present(repo_root: Path) -> None:
    build_path = repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    build_script = _read_text_or_fail(build_path)
    assert (
        re.search(r"dist-info\\\\licenses", build_script) or "dist-info\\licenses" in build_script
    )


def test_windows_portable_updater_warns_when_installed_version_missing(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    assert "Get-BundleAppVersion" in updater
    assert "Write-Warning" in updater
    assert "skipping version range check" in updater.lower()


def test_windows_portable_updater_finally_does_not_mask_exception(repo_root: Path) -> None:
    updater_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare-update.ps1"
    updater = _read_text_or_fail(updater_path)
    invoke_apply = re.search(
        r"function\s+Invoke-ApplyUpdate\b[\s\S]*?\n\}", updater, flags=re.DOTALL
    )
    assert invoke_apply is not None
    assert "finally" in invoke_apply.group(0)
    assert re.search(r"try\s*\{\s*Release-UpdateLock", invoke_apply.group(0))
    assert "Write-Warning" in invoke_apply.group(0)


def test_windows_portable_sign_update_write_string_entry_always_disposes_stream(
    repo_root: Path,
) -> None:
    sign_path = repo_root / "tools" / "windows_portable" / "sign_update.ps1"
    sign_script = _read_text_or_fail(sign_path)
    fn = re.search(r"function\s+Write-StringEntry\b[\s\S]*?\n\}", sign_script, flags=re.DOTALL)
    assert fn is not None
    assert "finally" in fn.group(0)
    assert re.search(r"\$stream\.Dispose\(\)", fn.group(0))
