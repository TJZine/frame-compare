from __future__ import annotations

from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_docs_describe_default_workspace_directories(repo_root: Path) -> None:
    readme_path = repo_root / "README.md"
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    readme = _read_text_or_fail(readme_path)
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "default `config/` and\n`comparison_videos/` directories in the bundle root" in readme
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
    windows_guide_path = repo_root / "docs" / "windows-portable.md"
    portable_readme_path = repo_root / "tools" / "windows_portable" / "README.txt"
    windows_guide = _read_text_or_fail(windows_guide_path)
    portable_readme = _read_text_or_fail(portable_readme_path)
    assert "uv sync --group dev --extra vspreview --frozen" in windows_guide
    assert "uv sync --group dev --extra vspreview --frozen" in portable_readme


def test_windows_portable_docs_include_a_safe_first_run_sequence(repo_root: Path) -> None:
    windows_guide = _read_text_or_fail(repo_root / "docs" / "windows-portable.md")
    portable_readme = _read_text_or_fail(repo_root / "tools" / "windows_portable" / "README.txt")

    expected_steps = (
        "frame-compare wizard",
        "frame-compare doctor",
        "frame-compare run --dry-run",
    )
    positions = [windows_guide.index(step) for step in expected_steps]
    final_run_position = windows_guide.index("   frame-compare run\n", positions[-1])
    assert positions == sorted(positions)
    assert final_run_position > positions[-1]
    for step in (*expected_steps, "frame-compare run"):
        assert step in portable_readme
    assert "Optional or network warnings do not make doctor exit" in windows_guide
    assert "open a new terminal" in windows_guide


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
