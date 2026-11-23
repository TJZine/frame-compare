from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from tests.workflow_helpers import read_text_or_fail as _read_text_or_fail


def first_significant_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return stripped
    return ""


def read_text_or_fail(path: Path) -> str:
    return _read_text_or_fail(path)


def powershell_exe() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def normalized_powershell_output(output: str) -> str:
    output = re.sub(r"\r?\n\s*\|\s?", " ", output)
    return " ".join(output.split())


def normalized_process_output(result: subprocess.CompletedProcess[str]) -> str:
    return normalized_powershell_output(f"{result.stdout}\n{result.stderr}")


def snapshot_bytes(root: Path) -> dict[str, bytes]:
    """Return a deterministic relative-path-to-bytes snapshot of a file tree."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def run_shim(
    *,
    exe: str,
    shim_path: Path,
    env: dict[str, str],
    args: list[str],
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(shim_path), *args],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def write_valid_config_json(
    *, state_dir: Path, bundle_dir: Path, schema_version: object = 1
) -> None:
    (state_dir / "config.json").write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "install_type": "portable_bundle",
                "bundle_path": str(bundle_dir),
            }
        ),
        encoding="utf-8",
    )


def setup_install_layout(*, tmp_path: Path, repo_root: Path) -> tuple[Path, Path, Path, Path]:
    repo_shim = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    install_root = tmp_path / "install"
    shim_dir = install_root / "shim"
    state_dir = install_root / "state"
    bundle_dir = install_root / "bundle"
    shim_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    bundle_dir.mkdir(parents=True)

    shim_path = shim_dir / "frame-compare.ps1"
    shim_path.write_text(repo_shim.read_text(encoding="utf-8"), encoding="utf-8")
    return install_root, shim_path, state_dir, bundle_dir


type _RegistryPath = tuple[str | list[str] | int | bytes | None, int]


def get_user_path() -> _RegistryPath | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, kind = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        return None
    return value, kind


def set_user_path(state: _RegistryPath | None) -> None:
    import ctypes
    import winreg

    if get_user_path() == state:
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
