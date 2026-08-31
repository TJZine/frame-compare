from __future__ import annotations

from pathlib import Path

from ._helpers import read_text_or_fail as _read_text_or_fail


def test_windows_portable_docs_do_not_disclose_private_key_on_command_line(
    repo_root: Path,
) -> None:
    portable_readme = _read_text_or_fail(repo_root / "tools" / "windows_portable" / "README.txt")
    assert "-PrivateKeyXml" not in portable_readme


def test_windows_portable_docs_bind_attestation_to_selected_tag_commit(repo_root: Path) -> None:
    docs = _read_text_or_fail(repo_root / "docs" / "windows-portable.md")

    assert '$tag = "<tag>"' in docs
    assert "git/ref/tags/$tag" in docs
    assert "$tagSha.Count -ne 1" in docs
    assert "^[0-9a-f]{40}$" in docs
    assert "--repo TJZine/frame-compare" in docs
    assert (
        "--signer-workflow TJZine/frame-compare/.github/workflows/windows-portable-build.yml"
    ) in docs
    assert "--source-digest $tagSha" in docs
    assert "--source-ref" not in docs
    assert "Could not resolve release tag" in docs
    assert "Release provenance verification failed" in docs


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


def test_windows_portable_docs_define_native_alignment_handoff(repo_root: Path) -> None:
    docs = _read_text_or_fail(repo_root / "docs" / "windows-portable.md")

    assert "## Native VSView alignment review" in docs
    assert "frame-compare-alignment-review" in docs
    assert "self-contained Python" in docs
    assert "PATH-only VSView executable" in docs
    assert "typed, atomic sibling sidecar" in docs
    assert "bundle_info.schema_version` 3" in docs
    assert "pre-native-panel schema-2 bundles" in docs
    assert "Missing, malformed," in docs
    assert "stale, mixed-session, duplicate, incomplete" in docs
    assert "## Physical Windows handoff" in docs
    assert "Hosted or macOS offscreen proof must not be reported" in docs
    assert "physical Windows desktop acceptance" in docs
    assert "ordinary VSView session" in docs
    assert "Keep current" in docs
