from __future__ import annotations

import os
from pathlib import Path

import pytest

from ._helpers import powershell_exe as _powershell_exe
from ._helpers import run_shim as _run_shim
from ._helpers import setup_install_layout as _setup_install_layout
from ._helpers import write_valid_config_json as _write_valid_config_json


@pytest.mark.integration
def test_windows_portable_shim_missing_config_json_returns_10(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, _state_dir, _bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 10, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
def test_windows_portable_shim_invalid_config_json_returns_11(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, _bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    (state_dir / "config.json").write_text("{not-json", encoding="utf-8")
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 11, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
def test_windows_portable_shim_non_numeric_schema_version_returns_15(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version="abc")
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 15, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
@pytest.mark.parametrize("schema_version", [0, 2])
def test_windows_portable_shim_unsupported_numeric_schema_version_returns_15(
    tmp_path: Path, repo_root: Path, schema_version: int
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(
        state_dir=state_dir, bundle_dir=bundle_dir, schema_version=schema_version
    )
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 15, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"


@pytest.mark.integration
def test_windows_portable_shim_missing_bundle_launcher_returns_14(
    tmp_path: Path, repo_root: Path
) -> None:
    exe = _powershell_exe()
    if exe is None:
        pytest.skip("pwsh/powershell not available")

    _, shim_path, state_dir, bundle_dir = _setup_install_layout(
        tmp_path=tmp_path, repo_root=repo_root
    )
    _write_valid_config_json(state_dir=state_dir, bundle_dir=bundle_dir, schema_version=1)
    proc = _run_shim(
        exe=exe, shim_path=shim_path, env=os.environ.copy(), args=["preset", "apply", "boost"]
    )
    assert proc.returncode == 14, f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
