from __future__ import annotations

from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_docs_describe_default_workspace_directories(repo_root: Path) -> None:
    readme_path = repo_root / "README.md"
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    readme = _read_text_or_fail(readme_path)
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "config/ and comparison_videos/ directories in the bundle root" in readme
    assert "comparison_videos" in portable_readme


def test_windows_portable_docs_disambiguate_source_bundle_root(repo_root: Path) -> None:
    readme_path = repo_root / "README.md"
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    readme = _read_text_or_fail(readme_path)
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "dist/frame-compare-portable-win-x64" in readme
    assert "not the repository root" in readme
    assert "includes VSPreview + PyQt6" in readme
    assert "frame-compare-update apply" in readme
    assert "frame-compare-update apply" in portable_readme


def test_windows_portable_docs_use_frozen_uv_sync_for_vspreview_extra(repo_root: Path) -> None:
    readme_path = repo_root / "README.md"
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    readme = _read_text_or_fail(readme_path)
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "uv sync --group dev --extra vspreview --frozen" in readme
    assert "uv sync --group dev --extra vspreview --frozen" in portable_readme


def test_windows_portable_readme_release_signing_header_has_no_leading_space(
    repo_root: Path,
) -> None:
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "\nRELEASE SIGNING (Maintainers):" in portable_readme


def test_windows_portable_docs_do_not_show_private_key_path_on_command_line(
    repo_root: Path,
) -> None:
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "-PrivateKeyXml" not in portable_readme
    assert "SIGNING_KEY_XML_PATH" in portable_readme
