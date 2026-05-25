from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from ._helpers import powershell_exe as _powershell_exe
from ._helpers import run_shim as _run_shim
from ._helpers import setup_install_layout as _setup_install_layout
from ._helpers import write_valid_config_json as _write_valid_config_json


@pytest.mark.integration
def test_windows_portable_shim_preset_apply_injection_e2e(tmp_path: Path, repo_root: Path) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )

    state_config_toml = state_dir / "config.toml"
    state_config_toml.write_text('[paths]\ninput_dir = "inputs"\n', encoding="utf-8")

    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    args_file = tmp_path / "args.txt"
    cwd_file = tmp_path / "cwd.txt"
    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                "$argsFile = $env:FC_TEST_ARGS_FILE",
                "$cwdFile = $env:FC_TEST_CWD_FILE",
                "if ($null -eq $argsFile -or $null -eq $cwdFile) { exit 2 }",
                'Set-Content -LiteralPath $argsFile -Value ($args -join "|") -Encoding UTF8',
                "Set-Content -LiteralPath $cwdFile -Value (Get-Location).Path -Encoding UTF8",
                '$configIndex = [Array]::IndexOf($args, "--config")',
                "if ($configIndex -lt 0) { exit 3 }",
                "if (($configIndex + 1) -ge $args.Count) { exit 4 }",
                "$cfg = [string]$args[$configIndex + 1]",
                "if (!(Test-Path -LiteralPath $cfg)) { exit 5 }",
                '$boostIndex = [Array]::IndexOf($args, "boost")',
                "if ($boostIndex -lt 0) { exit 6 }",
                "if ($configIndex -gt $boostIndex) { exit 7 }",
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    # Verify Get-ConfigInjectionIndex directly (dot-sourcing should not execute the shim).
    cmd = (
        f". '{shim_path}'; "
        "$idx = Get-ConfigInjectionIndex -ArgsValues @('preset','apply','boost'); "
        "Write-Output $idx"
    )
    proc = subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == "2"

    # Execute shim end-to-end and assert injected args reach bundle launcher.
    env = os.environ.copy()
    env["FC_TEST_ARGS_FILE"] = str(args_file)
    env["FC_TEST_CWD_FILE"] = str(cwd_file)
    proc2 = _run_shim(exe=exe, shim_path=shim_path, env=env, args=["preset", "apply", "boost"])
    assert proc2.returncode == 0, f"stdout:\n{proc2.stdout}\n\nstderr:\n{proc2.stderr}"

    forwarded = args_file.read_text(encoding="utf-8-sig").rstrip("\r\n")
    parts = forwarded.split("|")
    assert parts[:2] == ["preset", "apply"]
    assert parts[2:4] == ["--config", str(state_config_toml)]
    assert parts[4] == "boost"

    recorded_cwd = cwd_file.read_text(encoding="utf-8-sig").strip()
    assert Path(recorded_cwd).resolve() == bundle_dir.resolve()


@pytest.mark.integration
def test_windows_portable_shim_missing_state_config_toml_skips_injection(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    args_file = tmp_path / "args.txt"
    cwd_file = tmp_path / "cwd.txt"
    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                "$argsFile = $env:FC_TEST_ARGS_FILE",
                "$cwdFile = $env:FC_TEST_CWD_FILE",
                "if ($null -eq $argsFile -or $null -eq $cwdFile) { exit 2 }",
                'Set-Content -LiteralPath $argsFile -Value ($args -join "|") -Encoding UTF8',
                "Set-Content -LiteralPath $cwdFile -Value (Get-Location).Path -Encoding UTF8",
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["FC_TEST_ARGS_FILE"] = str(args_file)
    env["FC_TEST_CWD_FILE"] = str(cwd_file)
    proc = _run_shim(exe=exe, shim_path=shim_path, env=env, args=["preset", "apply", "boost"])
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"

    forwarded = args_file.read_text(encoding="utf-8-sig").rstrip("\r\n")
    parts = forwarded.split("|")
    assert len(parts) == 3
    assert parts[:3] == ["preset", "apply", "boost"]
    assert "--config" not in parts


@pytest.mark.integration
def test_windows_portable_shim_preserves_bundle_stdout(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                'Write-Output "frame-compare 0.1.0"',
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    proc = _run_shim(exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["version"])
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    assert proc.stdout.strip() == "frame-compare 0.1.0"
