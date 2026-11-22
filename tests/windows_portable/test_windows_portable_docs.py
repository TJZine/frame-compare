from __future__ import annotations

from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_docs_check_the_matching_zip_checksum(repo_root: Path) -> None:
    docs = _read_text_or_fail(repo_root / "docs/getting-started/windows-portable.md")
    assert '$tag = "<tag>"' in docs
    assert '$zip = ".\\frame-compare-portable-win-x64-$tag.zip"' in docs
    assert '$checksumFile = "$zip.sha256"' in docs
    assert "Get-FileHash -LiteralPath $zip -Algorithm SHA256" in docs
    assert "$actual -ne $expected" in docs
    assert "SHA-256 mismatch. Do not install this download." in docs


def test_windows_portable_docs_do_not_promote_removed_path_fields(repo_root: Path) -> None:
    docs = "\n".join(
        (
            _read_text_or_fail(repo_root / "docs" / "getting-started" / "windows-portable.md"),
            _read_text_or_fail(repo_root / "tools" / "windows_portable" / "README.txt"),
        )
    )
    assert "screenshots_dir" not in docs
    assert "use_run_folders" not in docs
    assert "output_dir" not in docs


def test_windows_portable_docs_define_native_alignment_handoff(repo_root: Path) -> None:
    portable = _read_text_or_fail(repo_root / "docs" / "getting-started" / "windows-portable.md")
    review = _read_text_or_fail(repo_root / "docs" / "guides" / "vsview-review.md")
    validation = _read_text_or_fail(repo_root / "docs" / "media-runtime-windows-validation.md")

    assert "## VSView alignment review" in portable
    assert "frame-compare-alignment-review" in portable
    assert "self-contained Python" in portable
    assert "PATH-only VSView executable" in portable
    assert "](../guides/vsview-review.md)" in portable
    assert "bundle_info.schema_version` 3" in portable
    assert "pre-native-panel schema-2 bundles" in portable
    assert "typed, atomic sibling sidecar" in review
    assert "Missing, malformed," in review
    assert "stale, mixed-session, duplicate, incomplete" in review
    assert "ordinary VSView session" in review
    assert "Confirm matching frames" in review
    assert "Keep current alignment" in review
    assert "Keep current offset" not in portable + review
    assert "## 10. Native VSView panel acceptance" in validation
    assert "Hosted or macOS offscreen proof must not be reported" in validation
    assert "physical Windows desktop acceptance" in validation


def test_windows_docs_distinguish_source_prerequisite_and_fresh_reinstall(repo_root: Path) -> None:
    docs = _read_text_or_fail(repo_root / "docs" / "getting-started" / "windows-portable.md")
    assert "PowerShell 7 or newer" in docs
    assert "Windows PowerShell 5.1 remains supported" in docs
    assert "fresh, empty folder" in docs
    assert "Overlaying a full ZIP onto an existing bundle root is unsupported" in docs
    assert "AppData fallback configuration and external user data are preserved" in docs
    assert "install.cmd -UserData Leave" in docs
    assert "Data you moved stays in the newer bundle." in docs
