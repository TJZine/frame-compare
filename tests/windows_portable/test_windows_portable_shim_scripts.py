from __future__ import annotations

import re
from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_shim_runs_bundle_launcher_from_bundle_root(repo_root: Path) -> None:
    shim_path = repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    shim = _read_text_or_fail(shim_path)
    assert "Push-Location $bundlePath" in shim
    assert "Pop-Location" in shim


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
