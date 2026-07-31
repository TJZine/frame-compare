from __future__ import annotations

from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_docs_do_not_disclose_private_key_on_command_line(
    repo_root: Path,
) -> None:
    portable_readme = _read_text_or_fail(repo_root / "tools" / "windows_portable" / "README.txt")
    assert "-PrivateKeyXml" not in portable_readme
