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
