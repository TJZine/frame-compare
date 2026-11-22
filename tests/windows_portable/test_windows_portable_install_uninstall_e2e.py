from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ._helpers import snapshot_bytes as _snapshot_bytes

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


type _RegistryPath = tuple[str | list[str] | int | bytes | None, int]


def _get_user_path() -> _RegistryPath | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, kind = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        return None
    return value, kind


def _set_user_path(state: _RegistryPath | None) -> None:
    import ctypes
    import winreg

    if _get_user_path() == state:
        return
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, "Environment", access=winreg.KEY_SET_VALUE
    ) as key:
        if state is None:
            winreg.DeleteValue(key, "Path")
        else:
            value, kind = state
            winreg.SetValueEx(key, "Path", 0, kind, value)
    # Restore the environment seen by applications as well as the registry bytes.
    result = ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(
        ctypes.c_void_p(0xFFFF),
        0x001A,
        ctypes.c_size_t(),
        ctypes.c_wchar_p("Environment"),
        0x0002,
        1000,
        ctypes.byref(result),
    )


@pytest.mark.integration
@windows_install_uninstall_e2e
@pytest.mark.parametrize("interpreter", ["powershell", "pwsh"])
@pytest.mark.parametrize("path_case", ["literal", "expanded", "empty", "absent"])
@pytest.mark.xdist_group("windows-install-lifecycle")
def test_windows_portable_uninstall_preserves_user_files_across_reinstall(
    tmp_path: Path, repo_root: Path, interpreter: str, path_case: str
) -> None:
    exe = shutil.which(interpreter)
    if exe is None:
        pytest.skip(f"{interpreter} unavailable for install/uninstall lifecycle")

    import winreg

    source_dir = repo_root / "tools" / "windows_portable"
    bundle_dir = tmp_path / "bundle"
    shim_dir = bundle_dir / "shim"
    config_dir = bundle_dir / "config"
    shim_dir.mkdir(parents=True)
    config_dir.mkdir()

    install_script = bundle_dir / "install.ps1"
    uninstall_script = bundle_dir / "uninstall.ps1"
    for name in ("install.ps1", "uninstall.ps1", "portable_activation.ps1", "path_safety.ps1"):
        shutil.copy2(source_dir / name, bundle_dir / name)
    (bundle_dir / "frame-compare.ps1").write_text("exit 0\n", encoding="utf-8")

    managed_bin_files = (
        "frame-compare.ps1",
        "frame-compare.cmd",
        "frame-compare-update.ps1",
        "frame-compare-version.ps1",
        "frame-compare-update.cmd",
        "update_public_key.xml",
    )
    for index, filename in enumerate(managed_bin_files):
        (shim_dir / filename).write_bytes(f"managed-{index}\r\n".encode("ascii"))
    (config_dir / "config.toml").write_bytes(b'[paths]\r\ninput_dir = "initial"\r\n')

    # Keep the generated-data sentinel outside every install, bundle, state, and
    # backup subtree so lifecycle checks cannot pass by merely preserving an
    # in-bundle path.
    external_generated_root = tmp_path / "external-generated-root"
    sentinel_run = external_generated_root / "Movie (2026)"
    sentinel_screenshot = sentinel_run / "screenshots" / "frame.png"
    sentinel_cache = external_generated_root / "cache" / "analysis" / "clip.compframes"
    sentinel_screenshot.parent.mkdir(parents=True)
    sentinel_cache.parent.mkdir(parents=True)
    sentinel_run.joinpath("report.html").write_bytes(b"<html>sentinel</html>\x00")
    sentinel_screenshot.write_bytes(b"PNG-SENTINEL\x00")
    sentinel_cache.write_bytes(b"CACHE-SENTINEL\x00")
    external_snapshot = _snapshot_bytes(external_generated_root)

    local_app_data = tmp_path / "local-app-data"
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(local_app_data)
    install_root = local_app_data / "Programs" / "FrameCompare"
    bin_dir = install_root / "bin"
    state_dir = install_root / "state"
    expected_bin_path = str(bin_dir)

    original_user_path = _get_user_path()
    env["FC_TEST_LOCAL_ROOT"] = str(local_app_data)
    tokenized_entry = r'"%FC_TEST_LOCAL_ROOT%\PROGRAMS\FRAMECOMPARE\BIN\"'
    unrelated = r' %SystemRoot%\System32 ;;"C:\FrameCompare-E2E\preserve-me" ;'
    if path_case == "expanded":
        seed_path = (f"{unrelated};{tokenized_entry};{expected_bin_path}", winreg.REG_EXPAND_SZ)
        installed_path = (f"{unrelated};{tokenized_entry}", winreg.REG_EXPAND_SZ)
        removed_path = (unrelated, winreg.REG_EXPAND_SZ)
    elif path_case == "literal":
        literal_path = f"{unrelated};{tokenized_entry}"
        seed_path = (literal_path, winreg.REG_SZ)
        installed_path = (f"{literal_path};{expected_bin_path}", winreg.REG_SZ)
        removed_path = seed_path
    elif path_case == "empty":
        seed_path = ("", winreg.REG_EXPAND_SZ)
        installed_path = (expected_bin_path, winreg.REG_EXPAND_SZ)
        removed_path = seed_path
    else:
        seed_path = None
        installed_path = (expected_bin_path, winreg.REG_SZ)
        removed_path = ("", winreg.REG_SZ)

    authored_generated = str(external_generated_root).replace("\\", "/")
    edited_config = (
        f'\ufeff[paths]\r\ninput_dir = "edited-✓"\r\ngenerated_dir = "{authored_generated}"\r\n'
    ).encode()
    unknown_files = {
        install_root / "root-user.bin": b"root-user-data\x00",
        bin_dir / "bin-user.bin": b"bin-user-data\x00",
        state_dir / "state-user.bin": b"state-user-data\x00",
    }

    try:
        _set_user_path(seed_path)
        if path_case in {"absent", "empty"}:
            inactive = _run_script(exe=exe, script=uninstall_script, env=env)
            assert inactive.returncode == 0, (inactive.stdout, inactive.stderr)
            assert _get_user_path() == seed_path

        installed = _run_script(exe=exe, script=install_script, env=env)
        assert installed.returncode == 0, (
            f"stdout:\n{installed.stdout}\n\nstderr:\n{installed.stderr}"
        )

        assert _get_user_path() == installed_path
        for filename in managed_bin_files:
            assert (bin_dir / filename).read_bytes() == (shim_dir / filename).read_bytes()

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
        assert _get_user_path() == removed_path
        assert _snapshot_bytes(external_generated_root) == external_snapshot

        replacement_bundle = tmp_path / "bundle-replacement"
        shutil.copytree(bundle_dir, replacement_bundle)
        replacement_install = replacement_bundle / "install.ps1"
        activation = replacement_bundle / "portable_activation.ps1"
        original_activation = activation.read_bytes()
        source = activation.read_text(encoding="utf-8")
        after_path = "      $committed = $true"
        assert source.count(after_path) == 1
        # Fail only after observing the value actually written by registration.
        probe = tmp_path / "path-written.json"
        env["FC_TEST_PATH_WRITTEN"] = str(probe)
        drift_states = (
            (
                None,
                (installed_path[0], winreg.REG_SZ),
                (installed_path[0] + ";C:\\external", installed_path[1]),
                (["%LOCALAPPDATA%\\external", r"C:\second"], winreg.REG_MULTI_SZ),
            )
            if path_case == "expanded"
            else (None,)
        )
        activation.write_text(
            source.replace(
                after_path,
                """      $written = Get-PortableUserPath
      [IO.File]::WriteAllText($env:FC_TEST_PATH_WRITTEN, ($written | ConvertTo-Json -Compress))
      if ($env:FC_TEST_PATH_DRIFT) {
        $drift = $env:FC_TEST_PATH_DRIFT | ConvertFrom-Json
        $kind = [Microsoft.Win32.RegistryValueKind]$drift.Kind
        $value = $drift.Value
        if ($kind -eq [Microsoft.Win32.RegistryValueKind]::MultiString) {
          $value = [string[]]$value
          $moved = Join-Path $BundleRoot 'generated/rollback-sentinel.bin'
          if (!(Test-Path -LiteralPath $moved -PathType Leaf) -or
              (Test-Path -LiteralPath $env:FC_TEST_PREVIOUS_DATA) -or
              !(Test-Path -LiteralPath $pendingMigrationPath -PathType Leaf)) {
            throw "User data did not move before the injected failure"
          }
        }
        Set-PortableUserPath ([pscustomobject]@{ Value = $value; Kind = $kind })
      }
      throw "Injected failure after user Path registration"
""",
            ),
            encoding="ascii",
        )
        pointer = state_dir / "config.json"
        previous_generated = bundle_dir / "generated"
        replacement_config = replacement_bundle / "config/config.toml"
        for drift in drift_states:
            migration_snapshot = None
            if drift is not None and drift[1] == winreg.REG_MULTI_SZ:
                active = _run_script(exe=exe, script=install_script, env=env)
                assert active.returncode == 0, (active.stdout, active.stderr)
                (bundle_dir / "bundle_info.json").write_text("{}", encoding="utf-8")
                original_pointer = b"  " + pointer.read_bytes() + b"\r\n"
                pointer.write_bytes(original_pointer)
                replacement_config_bytes = replacement_config.read_bytes()
                replacement_config.unlink()
                previous_generated.mkdir()
                (previous_generated / "rollback-sentinel.bin").write_bytes(b"moved user data\x00")
                migration_snapshot = (
                    original_pointer,
                    _snapshot_bytes(previous_generated),
                    replacement_config_bytes,
                )
                env["FC_TEST_PREVIOUS_DATA"] = str(previous_generated)
            _set_user_path(seed_path)
            env["FC_TEST_PATH_DRIFT"] = (
                json.dumps({"Value": drift[0], "Kind": drift[1]}) if drift else ""
            )
            failed = _run_script(exe=exe, script=replacement_install, env=env)
            assert failed.returncode != 0
            output = failed.stdout + failed.stderr
            assert "Injected failure after user Path registration" in output
            assert "Recovery failed" not in output
            assert json.loads(probe.read_text(encoding="utf-8")) == {
                "Value": installed_path[0],
                "Kind": installed_path[1],
            }
            assert _get_user_path() == (drift if drift else seed_path)
            assert not (state_dir / "source-migration.pending.json").exists()
            if migration_snapshot is not None:
                original_pointer, previous_data, replacement_config_bytes = migration_snapshot
                assert pointer.read_bytes() == original_pointer
                assert _snapshot_bytes(previous_generated) == previous_data
                assert not (replacement_bundle / "generated").exists()
                assert (config_dir / "config.toml").read_bytes() == replacement_config_bytes
                assert not list(replacement_config.parent.iterdir())
                replacement_config.write_bytes(replacement_config_bytes)
                for filename in managed_bin_files:
                    assert (bin_dir / filename).read_bytes() == (shim_dir / filename).read_bytes()
                _set_user_path(seed_path)
                cleaned = _run_script(exe=exe, script=uninstall_script, env=env)
                assert cleaned.returncode == 0, (cleaned.stdout, cleaned.stderr)
            else:
                assert not pointer.exists()
                for filename in managed_bin_files:
                    assert not (bin_dir / filename).exists()
        _set_user_path(seed_path)
        activation.write_bytes(original_activation)

        reinstalled = _run_script(exe=exe, script=replacement_install, env=env)
        assert reinstalled.returncode == 0, (
            f"stdout:\n{reinstalled.stdout}\n\nstderr:\n{reinstalled.stderr}"
        )

        assert config_path.read_bytes() == edited_config
        for path, content in unknown_files.items():
            assert path.read_bytes() == content
        for filename in managed_bin_files:
            assert (bin_dir / filename).read_bytes() == (
                replacement_bundle / "shim" / filename
            ).read_bytes()
        assert (state_dir / "config.json").is_file()
        assert _get_user_path() == installed_path
        config_json = json.loads((state_dir / "config.json").read_text(encoding="utf-8"))
        assert config_json["bundle_path"] == str(replacement_bundle)
        assert _snapshot_bytes(external_generated_root) == external_snapshot
    finally:
        _set_user_path(original_user_path)
