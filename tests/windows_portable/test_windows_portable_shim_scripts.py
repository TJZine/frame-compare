from __future__ import annotations

import re
from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_shim_preserves_launch_and_config_boundaries(
    repo_root: Path,
) -> None:
    shim = _read_text_or_fail(
        repo_root / "tools" / "windows_portable" / "shim" / "frame-compare.ps1"
    )

    assert "Push-Location $bundlePath" in shim
    assert "Pop-Location" in shim
    assert re.search(r"function\s+Test-ArgsContainConfigFlag\b", shim)
    assert re.search(r"function\s+Get-ConfigInjectionIndex\b", shim)
    assert re.search(r"\$arg\.StartsWith\(\"--config=\"\)", shim)
    assert re.search(r"&\s*\$bundleLauncher\s+@forwardArgs", shim)
    assert re.search(r'\$MyInvocation\.InvocationName\s*-ne\s*["\']\.[\'"]', shim)
