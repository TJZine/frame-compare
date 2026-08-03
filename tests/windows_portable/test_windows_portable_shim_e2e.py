from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ._helpers import powershell_exe as _powershell_exe
from ._helpers import read_text_or_fail as _read_text_or_fail
from ._helpers import run_shim as _run_shim
from ._helpers import setup_install_layout as _setup_install_layout
from ._helpers import write_valid_config_json as _write_valid_config_json

windows_portable_launcher_e2e = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows portable launcher PATH E2E requires Windows process semantics",
)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("args", "expected_prefix"),
    (
        (("wizard",), ("wizard", "--config")),
        (("run", "--diagnose-paths"), ("run", "--config")),
        (("preset", "list"), ("preset", "list", "--config")),
        (("history", "list"), ("history", "list", "--config")),
    ),
)
def test_windows_portable_shim_routes_all_fallback_config_commands_to_one_file(
    tmp_path: Path,
    repo_root: Path,
    args: tuple[str, ...],
    expected_prefix: tuple[str, ...],
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    state_config_toml = state_dir / "config.toml"
    state_config_toml.write_text(
        '[paths]\ngenerated_dir = "external-generated"\n', encoding="utf-8"
    )
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    args_file = tmp_path / "args.txt"
    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        (
            "Set-Content -LiteralPath $env:FC_TEST_ARGS_FILE "
            "-Value ($args -join '|') -Encoding UTF8\n"
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["FC_TEST_ARGS_FILE"] = str(args_file)

    completed = _run_shim(exe=exe, shim_path=shim_path, env=env, args=list(args))
    assert completed.returncode == 0, f"stdout:\n{completed.stdout}\n\nstderr:\n{completed.stderr}"

    forwarded = args_file.read_text(encoding="utf-8-sig").rstrip("\r\n").split("|")
    assert tuple(forwarded[: len(expected_prefix)]) == expected_prefix
    config_index = forwarded.index("--config")
    assert forwarded[config_index + 1] == str(state_config_toml)


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
        timeout=30,
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
def test_windows_portable_shim_history_open_injection_e2e(tmp_path: Path, repo_root: Path) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    state_config_toml = state_dir / "config.toml"
    state_config_toml.write_text('[paths]\ninput_dir = "inputs"\n', encoding="utf-8")
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    args_file = tmp_path / "history-args.txt"
    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                "$argsFile = $env:FC_TEST_ARGS_FILE",
                "if ($null -eq $argsFile) { exit 2 }",
                'Set-Content -LiteralPath $argsFile -Value ($args -join "|") -Encoding UTF8',
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    command = (
        f". '{shim_path}'; "
        "$idx = Get-ConfigInjectionIndex -ArgsValues @('history','open','Exact Run'); "
        "Write-Output $idx"
    )
    direct = subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert direct.stdout.strip() == "2"

    env = os.environ.copy()
    env["FC_TEST_ARGS_FILE"] = str(args_file)
    completed = _run_shim(
        exe=exe,
        shim_path=shim_path,
        env=env,
        args=["history", "open", "Exact Run"],
    )
    assert completed.returncode == 0, completed.stderr
    forwarded = args_file.read_text(encoding="utf-8-sig").rstrip("\r\n").split("|")
    assert forwarded == [
        "history",
        "open",
        "--config",
        str(state_config_toml),
        "Exact Run",
    ]


@pytest.mark.integration
def test_windows_portable_shim_prefers_bundle_config_over_state_config(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )

    state_config_toml = state_dir / "config.toml"
    state_config_toml.write_text('[paths]\ninput_dir = "state-inputs"\n', encoding="utf-8")
    bundle_config_dir = bundle_dir / "config"
    bundle_config_dir.mkdir()
    bundle_config_toml = bundle_config_dir / "config.toml"
    bundle_config_toml.write_text('[paths]\ninput_dir = "bundle-inputs"\n', encoding="utf-8")

    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    args_file = tmp_path / "args.txt"
    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                "$argsFile = $env:FC_TEST_ARGS_FILE",
                "if ($null -eq $argsFile) { exit 2 }",
                'Set-Content -LiteralPath $argsFile -Value ($args -join "|") -Encoding UTF8',
                '$configIndex = [Array]::IndexOf($args, "--config")',
                "if ($configIndex -lt 0) { exit 3 }",
                "if (($configIndex + 1) -ge $args.Count) { exit 4 }",
                "$cfg = [string]$args[$configIndex + 1]",
                f"if ($cfg -ne '{bundle_config_toml}') {{ exit 5 }}",
                f"if ($cfg -eq '{state_config_toml}') {{ exit 6 }}",
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["FC_TEST_ARGS_FILE"] = str(args_file)
    proc = _run_shim(exe=exe, shim_path=shim_path, env=env, args=["run"])
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"

    forwarded = args_file.read_text(encoding="utf-8-sig").rstrip("\r\n")
    parts = forwarded.split("|")
    assert parts[:3] == ["run", "--config", str(bundle_config_toml)]


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
def test_windows_portable_shim_preserves_bundle_stdout(tmp_path: Path, repo_root: Path) -> None:
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


@pytest.mark.integration
def test_windows_portable_shim_restores_environment_after_bundle_exit(
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
                '$env:PATH = "bundle-path;" + $env:PATH',
                '$env:PYTHONUTF8 = "bundle-utf8"',
                '$env:PYTHONPATH = "bundle-pythonpath"',
                '$env:VAPOURSYNTH_EXTRA_PLUGIN_PATH = "bundle-extra-plugins"',
                "Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue",
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    proof_script = tmp_path / "prove-shim-env-restore.ps1"
    proof_script.write_text(
        "\n".join(
            [
                '$ErrorActionPreference = "Stop"',
                '[Environment]::SetEnvironmentVariable("PATH", "outer-path", "Process")',
                '[Environment]::SetEnvironmentVariable("PYTHONUTF8", "outer-utf8", "Process")',
                '[Environment]::SetEnvironmentVariable("PYTHONPATH", "outer-pythonpath", "Process")',
                (
                    '[Environment]::SetEnvironmentVariable("VAPOURSYNTH_EXTRA_PLUGIN_PATH", '
                    '"outer-extra-plugins", "Process")'
                ),
                (
                    '[Environment]::SetEnvironmentVariable("VAPOURSYNTH_PLUGIN_PATH", '
                    '"outer-legacy-plugins", "Process")'
                ),
                f". '{shim_path}'",
                'Invoke-FrameCompareShim -ArgsValues @("version")',
                'Write-Output "EXIT=$script:FrameCompareShimExitCode"',
                'Write-Output "PATH=$env:PATH"',
                'Write-Output "PYTHONUTF8=$env:PYTHONUTF8"',
                'Write-Output "PYTHONPATH=$env:PYTHONPATH"',
                'Write-Output "VAPOURSYNTH_EXTRA_PLUGIN_PATH=$env:VAPOURSYNTH_EXTRA_PLUGIN_PATH"',
                'Write-Output "VAPOURSYNTH_PLUGIN_PATH=$env:VAPOURSYNTH_PLUGIN_PATH"',
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(proof_script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    output = _parse_key_value_output(proc.stdout)
    assert output["EXIT"] == "0"
    assert output["PATH"] == "outer-path"
    assert output["PYTHONUTF8"] == "outer-utf8"
    assert output["PYTHONPATH"] == "outer-pythonpath"
    assert output["VAPOURSYNTH_EXTRA_PLUGIN_PATH"] == "outer-extra-plugins"
    assert output["VAPOURSYNTH_PLUGIN_PATH"] == "outer-legacy-plugins"


@pytest.mark.integration
@windows_portable_launcher_e2e
def test_windows_portable_shim_restores_environment_on_repeat_path_invocation(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    install_root = tmp_path / "install"
    bin_dir = install_root / "bin"
    state_dir = install_root / "state"
    bundle_dir = install_root / "bundle"
    bin_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    bundle_dir.mkdir(parents=True)

    repo_shim = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    shim_path = bin_dir / "frame-compare.ps1"
    shim_path.write_text(repo_shim.read_text(encoding="utf-8"), encoding="utf-8")
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)

    bundle_launcher = bundle_dir / "frame-compare.ps1"
    bundle_launcher.write_text(
        "\n".join(
            [
                '$env:PATH = "bundle-path;" + $env:PATH',
                '$env:PYTHONUTF8 = "bundle-utf8"',
                '$env:PYTHONPATH = "bundle-pythonpath"',
                '$env:VAPOURSYNTH_EXTRA_PLUGIN_PATH = "bundle-extra-plugins"',
                "Remove-Item Env:VAPOURSYNTH_PLUGIN_PATH -ErrorAction SilentlyContinue",
                'Write-Output "bundle launcher ran"',
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )

    proof_script = tmp_path / "prove-repeat-path-invocation.ps1"
    proof_script.write_text(
        "\n".join(
            [
                '$ErrorActionPreference = "Stop"',
                f'$shimBin = "{bin_dir}"',
                '[Environment]::SetEnvironmentVariable("PATH", "$shimBin;outer-path", "Process")',
                '[Environment]::SetEnvironmentVariable("PYTHONUTF8", "outer-utf8", "Process")',
                '[Environment]::SetEnvironmentVariable("PYTHONPATH", "outer-pythonpath", "Process")',
                (
                    '[Environment]::SetEnvironmentVariable("VAPOURSYNTH_EXTRA_PLUGIN_PATH", '
                    '"outer-extra-plugins", "Process")'
                ),
                (
                    '[Environment]::SetEnvironmentVariable("VAPOURSYNTH_PLUGIN_PATH", '
                    '"outer-legacy-plugins", "Process")'
                ),
                '$beforePath = [Environment]::GetEnvironmentVariable("PATH", "Process")',
                "$resolved = Get-Command frame-compare -All | Select-Object -First 1",
                'Write-Output "COMMAND=$($resolved.CommandType):$($resolved.Source)"',
                "frame-compare version",
                '$afterFirstPath = [Environment]::GetEnvironmentVariable("PATH", "Process")',
                "frame-compare version",
                '$afterSecondPath = [Environment]::GetEnvironmentVariable("PATH", "Process")',
                'Write-Output "PATH_UNCHANGED_1=$($beforePath -eq $afterFirstPath)"',
                'Write-Output "PATH_UNCHANGED_2=$($beforePath -eq $afterSecondPath)"',
                'Write-Output "PATH=$afterSecondPath"',
                'Write-Output "PYTHONUTF8=$env:PYTHONUTF8"',
                'Write-Output "PYTHONPATH=$env:PYTHONPATH"',
                'Write-Output "VAPOURSYNTH_EXTRA_PLUGIN_PATH=$env:VAPOURSYNTH_EXTRA_PLUGIN_PATH"',
                'Write-Output "VAPOURSYNTH_PLUGIN_PATH=$env:VAPOURSYNTH_PLUGIN_PATH"',
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(proof_script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    output = _parse_key_value_output(proc.stdout)
    assert output["COMMAND"] == f"ExternalScript:{shim_path}"
    assert output["PATH_UNCHANGED_1"] == "True"
    assert output["PATH_UNCHANGED_2"] == "True"
    assert output["PATH"] == f"{bin_dir};outer-path"
    assert output["PYTHONUTF8"] == "outer-utf8"
    assert output["PYTHONPATH"] == "outer-pythonpath"
    assert output["VAPOURSYNTH_EXTRA_PLUGIN_PATH"] == "outer-extra-plugins"
    assert output["VAPOURSYNTH_PLUGIN_PATH"] == "outer-legacy-plugins"


@pytest.mark.integration
@windows_portable_launcher_e2e
def test_windows_portable_generated_bundle_launcher_restores_environment(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    build_script = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "build_portable.ps1"
    )
    match = re.search(r"\$ps1 = @'\r?\n(?P<launcher>.*?)\r?\n'@", build_script, re.DOTALL)
    assert match is not None

    bundle_dir = tmp_path / "bundle"
    python_dir = bundle_dir / "python"
    cli_dir = bundle_dir / "app" / "src" / "frame_compare" / "cli"
    python_dir.mkdir(parents=True)
    cli_dir.mkdir(parents=True)
    (bundle_dir / "app" / "site-packages").mkdir(parents=True)
    base_python = Path(getattr(sys, "_base_executable", sys.executable))
    shutil.copy2(base_python, python_dir / "python.exe")
    for dll_path in base_python.parent.glob("python*.dll"):
        shutil.copy2(dll_path, python_dir / dll_path.name)

    (cli_dir.parent / "__init__.py").write_text("", encoding="utf-8")
    (cli_dir / "__init__.py").write_text("", encoding="utf-8")
    (cli_dir / "entry.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import os",
                "import sys",
                'os.environ["PATH"] = "bundle-python;" + os.environ.get("PATH", "")',
                'os.environ["PYTHONUTF8"] = "inner-utf8"',
                'os.environ["PYTHONPATH"] = "inner-pythonpath"',
                'os.environ["VAPOURSYNTH_EXTRA_PLUGIN_PATH"] = "inner-extra-plugins"',
                'os.environ.pop("VAPOURSYNTH_PLUGIN_PATH", None)',
                'print("fake entry ran")',
                "sys.exit(0)",
            ]
        ),
        encoding="utf-8",
    )
    launcher_path = bundle_dir / "frame-compare.ps1"
    launcher_path.write_text(match.group("launcher"), encoding="utf-8")

    proof_script = tmp_path / "prove-generated-launcher-env-restore.ps1"
    proof_script.write_text(
        "\n".join(
            [
                '$ErrorActionPreference = "Stop"',
                '[Environment]::SetEnvironmentVariable("PATH", "outer-path", "Process")',
                '[Environment]::SetEnvironmentVariable("PYTHONUTF8", "outer-utf8", "Process")',
                '[Environment]::SetEnvironmentVariable("PYTHONPATH", "outer-pythonpath", "Process")',
                (
                    '[Environment]::SetEnvironmentVariable("VAPOURSYNTH_EXTRA_PLUGIN_PATH", '
                    '"outer-extra-plugins", "Process")'
                ),
                (
                    '[Environment]::SetEnvironmentVariable("VAPOURSYNTH_PLUGIN_PATH", '
                    '"outer-legacy-plugins", "Process")'
                ),
                f"& '{launcher_path}' version",
                'Write-Output "EXIT=$LASTEXITCODE"',
                'Write-Output "PATH=$env:PATH"',
                'Write-Output "PYTHONUTF8=$env:PYTHONUTF8"',
                'Write-Output "PYTHONPATH=$env:PYTHONPATH"',
                'Write-Output "VAPOURSYNTH_EXTRA_PLUGIN_PATH=$env:VAPOURSYNTH_EXTRA_PLUGIN_PATH"',
                'Write-Output "VAPOURSYNTH_PLUGIN_PATH=$env:VAPOURSYNTH_PLUGIN_PATH"',
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(proof_script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    output = _parse_key_value_output(proc.stdout)
    assert output["EXIT"] == "0"
    assert output["PATH"] == "outer-path"
    assert output["PYTHONUTF8"] == "outer-utf8"
    assert output["PYTHONPATH"] == "outer-pythonpath"
    assert output["VAPOURSYNTH_EXTRA_PLUGIN_PATH"] == "outer-extra-plugins"
    assert output["VAPOURSYNTH_PLUGIN_PATH"] == "outer-legacy-plugins"


def _parse_key_value_output(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key] = value
    return parsed
