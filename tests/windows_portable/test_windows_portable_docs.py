from __future__ import annotations

from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_docs_do_not_disclose_private_key_on_command_line(
    repo_root: Path,
) -> None:
    portable_readme = _read_text_or_fail(repo_root / "tools" / "windows_portable" / "README.txt")
    assert "-PrivateKeyXml" not in portable_readme


def test_windows_portable_docs_describe_external_generated_data_preservation(
    repo_root: Path,
) -> None:
    docs = "\n".join(
        (
            _read_text_or_fail(repo_root / "docs" / "windows-portable.md"),
            _read_text_or_fail(repo_root / "tools" / "windows_portable" / "README.txt"),
        )
    )

    assert "Generated data location" in docs
    assert "external" in docs.lower()
    assert "updater" in docs.lower()
    assert "uninstaller" in docs.lower()
    assert "cache identity" in docs.lower()
    assert "top-level bundle `screenshots/` directory is not a runtime" in docs


def test_windows_portable_docs_do_not_promote_removed_path_fields(repo_root: Path) -> None:
    docs = "\n".join(
        (
            _read_text_or_fail(repo_root / "docs" / "windows-portable.md"),
            _read_text_or_fail(repo_root / "tools" / "windows_portable" / "README.txt"),
        )
    )
    assert "screenshots_dir" not in docs
    assert "use_run_folders" not in docs
    assert "output_dir" not in docs
