from __future__ import annotations

import re
from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_shim_source_recognizes_equals_config_flag(
    repo_root: Path,
) -> None:
    shim = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    )

    assert re.search(r"\$arg\.StartsWith\(\"--config=\"\)", shim)
    assert "Push-Location $bundlePath" in shim
    assert "Pop-Location" in shim
    assert re.search(r"&\s*\$bundleLauncher\s+@forwardArgs", shim)
    assert re.search(r'\$MyInvocation\.InvocationName\s*-ne\s*["\']\.[\'"]', shim)


def test_published_shims_read_install_state_as_utf8(repo_root: Path) -> None:
    for name in ("frame-compare.ps1", "frame-compare-update.ps1"):
        shim = _read_text_or_fail(repo_root / "tools/windows_portable/shim" / name)
        assert "Get-Content -LiteralPath $configPath -Raw -Encoding UTF8" in shim


def test_windows_51_shims_read_bomless_nonascii_bundle_state(
    repo_root: Path, tmp_path: Path
) -> None:
    import json
    import os
    import subprocess

    import pytest

    if os.name != "nt":
        pytest.skip("Windows PowerShell 5.1 encoding semantics required")
    exe = Path(os.environ["SYSTEMROOT"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not exe.exists():
        pytest.skip("Windows PowerShell 5.1 not available")
    install_root = tmp_path / "install"
    shim_dir = install_root / "shim"
    state_dir = install_root / "state"
    bundle_dir = install_root / "café-日本語"
    for directory in (shim_dir, state_dir, bundle_dir):
        directory.mkdir(parents=True)
    (state_dir / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "install_type": "portable_bundle",
                "bundle_path": str(bundle_dir),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (bundle_dir / "frame-compare.ps1").write_text(
        'Write-Output "frame-compare 1.0.0"; exit 0', encoding="utf-8"
    )
    for name, args, expected in (
        ("frame-compare.ps1", ["version"], "frame-compare 1.0.0"),
        ("frame-compare-update.ps1", ["list-backups"], "No backups found."),
    ):
        shim = shim_dir / name
        shim.write_bytes((repo_root / "tools/windows_portable/shim" / name).read_bytes())
        proc = subprocess.run(
            [str(exe), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(shim), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert expected in proc.stdout
