from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_TIMEOUT_SECONDS = 20.0
OTHER_SHA = "b" * 40


def _write_release_state(
    root: Path,
    *,
    version: str,
    changelog_version: str | None = None,
    release_config_overrides: dict[str, object] | None = None,
) -> None:
    package_dir = root / "src" / "frame_compare"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text(
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "frame-compare"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (root / ".release-please-manifest.json").write_text(
        json.dumps({".": version}),
        encoding="utf-8",
    )
    release_config: dict[str, object] = {
        "release-type": "python",
        "packages": {".": {"release-type": "python"}},
    }
    if release_config_overrides:
        release_config.update(release_config_overrides)
    (root / "release-please-config.json").write_text(
        json.dumps(release_config),
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        "\n".join(
            (
                "version = 1",
                "",
                "[[package]]",
                'name = "frame-compare"',
                f'version = "{version}"',
                'source = { editable = "." }',
                "",
            )
        ),
        encoding="utf-8",
    )
    heading_version = changelog_version if changelog_version is not None else version
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{heading_version}]\n\n- Release proof.\n",
        encoding="utf-8",
    )


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_SECONDS,
    )


def _commit_release_state(root: Path) -> str:
    _git(root, "init", "--quiet")
    _git(root, "config", "user.name", "Frame Compare Tests")
    _git(root, "config", "user.email", "tests@frame-compare.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "--quiet", "-m", "test: release state")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _run_contract(
    repo_root: Path,
    state_root: Path,
    *,
    channel: str,
    version: str,
    tag: str,
    expected_sha: str,
    main_sha: str | None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_root / "scripts" / "validate_release_contract.py"),
        "--repo-root",
        str(state_root),
        "--channel",
        channel,
        "--version",
        version,
        "--tag",
        tag,
        "--expected-sha",
        expected_sha,
    ]
    if main_sha is not None:
        command.extend(("--main-sha", main_sha))
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_SECONDS,
    )


def test_stable_release_contract_accepts_exact_final_state(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    _write_release_state(tmp_path, version="0.1.0")
    sha = _commit_release_state(tmp_path)

    result = _run_contract(
        repo_root,
        tmp_path,
        channel="stable",
        version="0.1.0",
        tag="v0.1.0",
        expected_sha=sha,
        main_sha=sha,
    )

    assert result.returncode == 0, result.stderr
    assert "Release contract valid: channel=stable version=0.1.0 tag=v0.1.0" in result.stdout


def test_rc_release_contract_accepts_pep440_version_and_rc_tag(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    _write_release_state(tmp_path, version="0.1.0rc2")
    sha = _commit_release_state(tmp_path)

    result = _run_contract(
        repo_root,
        tmp_path,
        channel="rc",
        version="0.1.0rc2",
        tag="v0.1.0-rc.2",
        expected_sha=sha,
        main_sha=None,
    )

    assert result.returncode == 0, result.stderr
    assert "Release contract valid: channel=rc version=0.1.0rc2" in result.stdout


@pytest.mark.parametrize(
    ("channel", "version", "tag", "message"),
    [
        ("stable", "0.1.0rc1", "v0.1.0-rc.1", "Stable version must be"),
        ("stable", "0.1.0", "v0.1.0-rc.1", "stable tag must be exactly v0.1.0"),
        ("rc", "0.1.0", "v0.1.0-rc.1", "RC version must use PEP 440"),
        ("rc", "0.1.0rc1", "v0.1.0", "rc tag must be exactly v0.1.0-rc.1"),
    ],
)
def test_release_contract_rejects_channel_version_tag_mismatch(
    repo_root: Path,
    tmp_path: Path,
    channel: str,
    version: str,
    tag: str,
    message: str,
) -> None:
    _write_release_state(tmp_path, version=version)
    sha = _commit_release_state(tmp_path)

    result = _run_contract(
        repo_root,
        tmp_path,
        channel=channel,
        version=version,
        tag=tag,
        expected_sha=sha,
        main_sha=sha if channel == "stable" else None,
    )

    assert result.returncode != 0
    assert message in result.stderr


def test_release_contract_rejects_version_source_disagreement(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    _write_release_state(tmp_path, version="0.1.0")
    sha = _commit_release_state(tmp_path)
    (tmp_path / ".release-please-manifest.json").write_text(
        json.dumps({".": "0.1.1"}),
        encoding="utf-8",
    )

    result = _run_contract(
        repo_root,
        tmp_path,
        channel="stable",
        version="0.1.0",
        tag="v0.1.0",
        expected_sha=sha,
        main_sha=sha,
    )

    assert result.returncode != 0
    assert "version sources disagree" in result.stderr


def test_release_contract_rejects_non_main_stable_sha(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    _write_release_state(tmp_path, version="0.1.0")
    sha = _commit_release_state(tmp_path)

    result = _run_contract(
        repo_root,
        tmp_path,
        channel="stable",
        version="0.1.0",
        tag="v0.1.0",
        expected_sha=sha,
        main_sha=OTHER_SHA,
    )

    assert result.returncode != 0
    assert "is not current main head" in result.stderr


def test_release_contract_rejects_temporary_bootstrap_fields_for_stable(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    _write_release_state(
        tmp_path,
        version="0.1.0",
        release_config_overrides={
            "bootstrap-sha": OTHER_SHA,
            "release-as": "0.1.0",
        },
    )
    sha = _commit_release_state(tmp_path)

    result = _run_contract(
        repo_root,
        tmp_path,
        channel="stable",
        version="0.1.0",
        tag="v0.1.0",
        expected_sha=sha,
        main_sha=sha,
    )

    assert result.returncode != 0
    assert "bootstrap-sha, release-as" in result.stderr


def test_release_contract_rejects_missing_changelog_version(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    _write_release_state(
        tmp_path,
        version="0.1.0",
        changelog_version="Unreleased",
    )
    sha = _commit_release_state(tmp_path)

    result = _run_contract(
        repo_root,
        tmp_path,
        channel="stable",
        version="0.1.0",
        tag="v0.1.0",
        expected_sha=sha,
        main_sha=sha,
    )

    assert result.returncode != 0
    assert "[0.1.0]" in result.stderr


def test_release_contract_rejects_checked_out_sha_mismatch(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    _write_release_state(tmp_path, version="0.1.0")
    sha = _commit_release_state(tmp_path)

    result = _run_contract(
        repo_root,
        tmp_path,
        channel="stable",
        version="0.1.0",
        tag="v0.1.0",
        expected_sha=OTHER_SHA,
        main_sha=sha,
    )

    assert result.returncode != 0
    assert f"Checked-out HEAD {sha} does not equal expected SHA {OTHER_SHA}" in result.stderr
