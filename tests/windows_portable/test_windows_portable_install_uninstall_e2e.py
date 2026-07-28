from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ._helpers import powershell_exe as _powershell_exe

windows_install_uninstall_e2e = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows portable install/uninstall E2E requires Windows user PATH semantics",
)


def _run_script(*, exe: str, script: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _get_user_path(exe: str) -> str | None:
    command = (
        '$value = [Environment]::GetEnvironmentVariable("Path", "User"); '
        "if ($null -eq $value) { "
        '[Console]::Out.Write("null") '
        "} else { "
        "[Console]::Out.Write(($value | ConvertTo-Json -Compress)) "
        "}"
    )
    result = subprocess.run(
        [exe, "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    value = json.loads(result.stdout)
    assert value is None or isinstance(value, str)
    return value


def _set_user_path(exe: str, value: str | None) -> None:
    env = os.environ.copy()
    if value is None:
        command = '[Environment]::SetEnvironmentVariable("Path", $null, "User")'
    else:
        env["FC_TEST_USER_PATH"] = value
        command = '[Environment]::SetEnvironmentVariable("Path", $env:FC_TEST_USER_PATH, "User")'
    subprocess.run(
        [exe, "-NoProfile", "-Command", command],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.integration
@windows_install_uninstall_e2e
def test_windows_portable_uninstall_preserves_user_files_across_reinstall(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    assert exe is not None, "Windows PowerShell is required for the portable installer"

    source_dir = repo_root / "tools" / "windows_portable"
    bundle_dir = tmp_path / "bundle"
    shim_dir = bundle_dir / "shim"
    config_dir = bundle_dir / "config"
    shim_dir.mkdir(parents=True)
    config_dir.mkdir()

    install_script = bundle_dir / "install.ps1"
    uninstall_script = bundle_dir / "uninstall.ps1"
    shutil.copy2(source_dir / "install.ps1", install_script)
    shutil.copy2(source_dir / "uninstall.ps1", uninstall_script)
    (bundle_dir / "frame-compare.ps1").write_text("exit 0\n", encoding="utf-8")

    managed_bin_files = (
        "frame-compare.ps1",
        "frame-compare.cmd",
        "frame-compare-update.ps1",
        "frame-compare-update.cmd",
        "update_public_key.xml",
    )
    for index, filename in enumerate(managed_bin_files):
        (shim_dir / filename).write_bytes(f"managed-{index}\r\n".encode("ascii"))
    (config_dir / "config.toml").write_bytes(b'[paths]\r\ninput_dir = "initial"\r\n')

    local_app_data = tmp_path / "local-app-data"
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(local_app_data)
    install_root = local_app_data / "Programs" / "FrameCompare"
    bin_dir = install_root / "bin"
    state_dir = install_root / "state"
    expected_bin_path = str(bin_dir)

    original_user_path = _get_user_path(exe)
    controlled_user_path = r"C:\FrameCompare-E2E\preserve-me"
    edited_config = b'\xef\xbb\xbf[paths]\r\ninput_dir = "edited-\xe2\x9c\x93"\r\n'
    unknown_files = {
        install_root / "root-user.bin": b"root-user-data\x00",
        bin_dir / "bin-user.bin": b"bin-user-data\x00",
        state_dir / "state-user.bin": b"state-user-data\x00",
    }

    try:
        _set_user_path(exe, controlled_user_path)

        installed = _run_script(exe=exe, script=install_script, env=env)
        assert installed.returncode == 0, (
            f"stdout:\n{installed.stdout}\n\nstderr:\n{installed.stderr}"
        )

        config_path = state_dir / "config.toml"
        config_path.write_bytes(edited_config)
        for path, content in unknown_files.items():
            path.write_bytes(content)

        uninstalled = _run_script(exe=exe, script=uninstall_script, env=env)
        assert uninstalled.returncode == 0, (
            f"stdout:\n{uninstalled.stdout}\n\nstderr:\n{uninstalled.stderr}"
        )

        assert config_path.read_bytes() == edited_config
        for path, content in unknown_files.items():
            assert path.read_bytes() == content
        for filename in managed_bin_files:
            assert not (bin_dir / filename).exists()
        assert not (state_dir / "config.json").exists()
        assert _get_user_path(exe) == controlled_user_path

        reinstalled = _run_script(exe=exe, script=install_script, env=env)
        assert reinstalled.returncode == 0, (
            f"stdout:\n{reinstalled.stdout}\n\nstderr:\n{reinstalled.stderr}"
        )

        assert config_path.read_bytes() == edited_config
        for path, content in unknown_files.items():
            assert path.read_bytes() == content
        for filename in managed_bin_files:
            assert (bin_dir / filename).is_file()
        assert (state_dir / "config.json").is_file()
        assert _get_user_path(exe).split(";") == [
            controlled_user_path,
            expected_bin_path,
        ]
    finally:
        _set_user_path(exe, original_user_path)
