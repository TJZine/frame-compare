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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_install_from_source_param_block_is_first_statement() -> None:
    script_path = _repo_root() / "tools" / "windows_portable" / "install-from-source.ps1"
    script_text = script_path.read_text(encoding="utf-8")
    assert _first_significant_line(script_text).startswith("Param(")


def test_install_from_source_avoids_pscore_only_windows_variable() -> None:
    script_path = _repo_root() / "tools" / "windows_portable" / "install-from-source.ps1"
    script_text = script_path.read_text(encoding="utf-8")
    assert "$IsWindows" not in script_text


def test_root_install_cmd_exists_and_calls_install_ps1() -> None:
    path = _repo_root() / "install.cmd"
    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    assert "powershell" in text
    assert "-noprofile" in text
    assert "-executionpolicy bypass" in text
    assert "-file" in text
    assert "install.ps1" in text


def test_root_install_ps1_exists_and_delegates_to_install_from_source() -> None:
    path = _repo_root() / "install.ps1"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert _first_significant_line(text).startswith("Param(")
    normalized = text.replace("\\\\", "/").replace("\\", "/")
    assert "tools/windows_portable/install-from-source.ps1" in normalized


def test_install_from_source_mentions_uv_auto_install() -> None:
    script_path = _repo_root() / "tools" / "windows_portable" / "install-from-source.ps1"
    text = script_path.read_text(encoding="utf-8").lower()
    assert "winget" in text
    assert "pip" in text
    assert "uv" in text
    assert "docs: https://docs.astral.sh/uv/getting-started/installation/" in text
    assert "curl" not in text
    assert "invoke-expression" not in text


def test_install_from_source_uv_install_order_is_deterministic() -> None:
    script_path = _repo_root() / "tools" / "windows_portable" / "install-from-source.ps1"
    text = script_path.read_text(encoding="utf-8").lower()

    # The plan requires winget first, then pip as fallback.
    winget_idx = text.index("winget install")
    pip_idx = text.index("pip install --user uv")
    assert winget_idx < pip_idx

    # Recovery block must be copy/paste friendly and include both commands.
    assert "winget install --id astral-sh.uv -e --source winget" in text
    assert "py -m pip install --user uv" in text


def test_windows_portable_workflow_does_not_flatten_zip_contents() -> None:
    wf = (_repo_root() / ".github" / "workflows" / "windows-portable.yml").read_text(
        encoding="utf-8"
    )
    assert 'Compress-Archive -Path "$bundle/*"' not in wf


def test_windows_portable_workflow_zips_bundle_folder() -> None:
    wf = (_repo_root() / ".github" / "workflows" / "windows-portable.yml").read_text(
        encoding="utf-8"
    )
    assert "Compress-Archive -Path $bundle -DestinationPath $zip" in wf


def test_windows_portable_workflow_verifies_zip_required_entries() -> None:
    wf = (_repo_root() / ".github" / "workflows" / "windows-portable.yml").read_text(
        encoding="utf-8"
    )
    required = [
        "frame-compare-portable-win-x64/install.cmd",
        "frame-compare-portable-win-x64/install.ps1",
        "frame-compare-portable-win-x64/frame-compare.ps1",
        "frame-compare-portable-win-x64/shim/frame-compare.cmd",
    ]
    for entry in required:
        assert entry in wf


def test_windows_portable_shim_runs_bundle_launcher_from_bundle_root() -> None:
    shim = (_repo_root() / "tools" / "windows_portable" / "shim" / "frame-compare.ps1").read_text(
        encoding="utf-8"
    )
    assert "Push-Location $bundlePath" in shim
    assert "Pop-Location" in shim


def test_windows_portable_bundle_launcher_sets_cwd_to_bundle_root() -> None:
    build_script = (_repo_root() / "tools" / "windows_portable" / "build_portable.ps1").read_text(
        encoding="utf-8"
    )
    assert "Push-Location $bundleRoot" in build_script
    assert "Pop-Location" in build_script


def test_windows_portable_shim_injects_state_config_when_missing_explicit_config() -> None:
    shim = (_repo_root() / "tools" / "windows_portable" / "shim" / "frame-compare.ps1").read_text(
        encoding="utf-8"
    )
    assert '$stateDir = Join-Path $installRoot "state"' in shim
    assert '$stateConfigToml = Join-Path $stateDir "config.toml"' in shim
    assert "Test-ArgsContainConfigFlag" in shim
    assert "Get-ConfigInjectionIndex" in shim
    assert "Insert-ArgsAtIndex" in shim
    assert '$command -eq "run" -or $command -eq "wizard"' in shim
    assert '$command -eq "preset"' in shim
    assert '$subcommand -eq "list" -or $subcommand -eq "apply" -or $subcommand -eq "save"' in shim
    assert '$arg.StartsWith("--config=")' in shim
    assert '$arg.StartsWith("-c")' in shim
    assert "& $bundleLauncher @forwardArgs" in shim
    assert "@extraArgs @args" not in shim


def test_windows_portable_installer_initializes_state_config_toml() -> None:
    installer = (_repo_root() / "tools" / "windows_portable" / "install.ps1").read_text(
        encoding="utf-8"
    )
    assert '$portableConfigToml = Join-Path $stateDir "config.toml"' in installer
    assert (
        '$bundleConfigToml = Join-Path (Join-Path $bundleRoot "config") "config.toml"' in installer
    )
    assert (
        "Copy-Item -LiteralPath $bundleConfigToml -Destination $portableConfigToml -Force"
        in installer
    )
    assert "[paths]" in installer


def test_windows_portable_build_creates_default_workspace_directories() -> None:
    build_script = (_repo_root() / "tools" / "windows_portable" / "build_portable.ps1").read_text(
        encoding="utf-8"
    )
    assert '$bundleConfigDir = Join-Path $OutDir "config"' in build_script
    assert '$bundleInputDir = Join-Path $OutDir "comparison_videos"' in build_script
    assert "Ensure-Directory -Path $bundleConfigDir" in build_script
    assert "Ensure-Directory -Path $bundleInputDir" in build_script


def test_windows_portable_docs_describe_default_workspace_directories() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    portable_readme = (_repo_root() / "tools" / "windows_portable" / "README.txt").read_text(
        encoding="utf-8"
    )
    assert "config/ and comparison_videos/ directories in the bundle root" in readme
    assert "comparison_videos" in portable_readme


def test_windows_portable_workflow_verifies_workspace_directories() -> None:
    workflow = (_repo_root() / ".github" / "workflows" / "windows-portable.yml").read_text(
        encoding="utf-8"
    )
    assert '$bundleConfigDir = Join-Path $bundle "config"' in workflow
    assert '$bundleInputDir = Join-Path $bundle "comparison_videos"' in workflow
    assert "Test-Path -LiteralPath $bundleConfigDir -PathType Container" in workflow
    assert "Test-Path -LiteralPath $bundleInputDir -PathType Container" in workflow
    assert 'throw "Missing default workspace directory in bundle:' in workflow


def test_windows_portable_docs_disambiguate_source_bundle_root() -> None:
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    assert "dist/frame-compare-portable-win-x64" in readme
    assert "not the repository root" in readme
