from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


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
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def powershell_exe() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def run_shim(
    *,
    exe: str,
    shim_path: Path,
    env: dict[str, str],
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(shim_path), *args],
        env=env,
        check=False,
        capture_output=True,
        text=True,
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
