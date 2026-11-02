from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workflow_helpers import load_workflow
from tests.workflows._helpers import bash_executable_or_skip, bash_path_or_skip


def test_merged_release_delegates_to_guarded_publication(repo_root: Path) -> None:
    workflow = load_workflow(repo_root / ".github/workflows/release-on-merge.yml")
    assert workflow["on"] == {"push": {"branches": ["main"]}}
    assert workflow["permissions"] == {}
    identify = workflow["jobs"]["identify_release"]
    assert identify["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert identify["steps"][0]["with"] == {
        "ref": "${{ github.sha }}",
        "fetch-depth": "0",
        "persist-credentials": "false",
    }
    assert identify["steps"][1]["env"]["PREVIOUS_SHA"] == "${{ github.event.before }}"
    release = workflow["jobs"]["release"]
    assert release["needs"] == "identify_release"
    assert release["if"] == "needs.identify_release.outputs.version != ''"
    assert release["uses"] == "./.github/workflows/release.yml"
    assert release["with"] == {
        "channel": "stable",
        "version": "${{ needs.identify_release.outputs.version }}",
        "tag": "${{ needs.identify_release.outputs.tag }}",
        "expected_sha": "${{ needs.identify_release.outputs.expected_sha }}",
    }
    assert release["permissions"] == {
        "attestations": "write",
        "contents": "write",
        "id-token": "write",
        "pull-requests": "read",
    }
    assert release["secrets"] == {
        "WINDOWS_UPDATE_SIGNING_KEY_XML": "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}"
    }
    manual = load_workflow(repo_root / ".github/workflows/windows-portable.yml")
    assert release["concurrency"]["cancel-in-progress"] == "false"
    assert release["concurrency"]["group"].startswith("frame-compare-release-")
    assert manual["jobs"]["release"]["concurrency"]["group"].startswith("frame-compare-release-")
    guarded = load_workflow(repo_root / ".github/workflows/release.yml")
    assert guarded["jobs"]["windows"]["with"]["require_signing"] == "true"
    for job in (guarded["jobs"]["windows"], guarded["jobs"]["publish"]):
        environment = job.get("environment", job.get("with", {}))
        assert "production" in str(environment)


@pytest.mark.parametrize(
    ("case", "publishes", "succeeds"),
    [
        ("generated", True, True),
        ("manual", True, True),
        ("breaking_manual", True, True),
        ("rebase", True, True),
        ("ordinary", False, True),
        ("wrong_title_version", False, True),
        ("wrong_sha", False, True),
        ("unmerged", False, True),
        ("wrong_base", False, True),
        ("wrong_repo", False, True),
        ("wrong_head", False, True),
        ("fork_head", False, True),
        ("unchanged_version", False, True),
        ("rc", False, True),
        ("no_pr", False, True),
        ("api_failure", False, False),
        ("invalid_response", False, False),
        ("missing_previous_commit", False, False),
    ],
)
def test_release_identification_at_pushed_commit(
    repo_root: Path, tmp_path: Path, case: str, publishes: bool, succeeds: bool
) -> None:
    if shutil.which("jq") is None:
        pytest.skip("jq is required to execute the release workflow script")
    bash = bash_executable_or_skip()
    state = tmp_path / "repo"
    state.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=state,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()

    git("init", "--quiet")
    git("config", "user.name", "Release Tests")
    git("config", "user.email", "tests@frame-compare.invalid")
    manifest = state / ".release-please-manifest.json"
    manifest.write_text(json.dumps({".": "0.6.0"}), encoding="utf-8")
    git("add", ".")
    git("commit", "--quiet", "-m", "previous release")
    previous_sha = git("rev-parse", "HEAD")
    version = {"unchanged_version": "0.6.0", "rc": "0.7.0rc1"}.get(case, "0.7.0")
    manifest.write_text(json.dumps({".": version}), encoding="utf-8")
    git("add", ".")
    git("commit", "--quiet", "--allow-empty", "-m", "merged release")
    if case == "rebase":
        git("commit", "--quiet", "--allow-empty", "-m", "release notes follow-up")
    sha = git("rev-parse", "HEAD")
    title = {
        "manual": "chore(release): prepare Frame Compare v0.7.0",
        "breaking_manual": "chore(release)!: prepare Frame Compare v0.7.0",
        "ordinary": "feat: new comparison option",
        "wrong_title_version": "chore(release): 0.8.0",
    }.get(case, "chore(release): 0.7.0")
    pr = {
        "title": title,
        "merged_at": None if case == "unmerged" else "2026-10-11T12:00:00Z",
        "merge_commit_sha": "a" * 40 if case == "wrong_sha" else sha,
        "base": {
            "ref": "staging" if case == "wrong_base" else "main",
            "repo": {"full_name": "other/repo" if case == "wrong_repo" else "TJZine/frame-compare"},
        },
        "head": {
            "ref": "topic" if case == "wrong_head" else "pre-release",
            "repo": {"full_name": "other/repo" if case == "fork_head" else "TJZine/frame-compare"},
        },
    }
    response = tmp_path / "pulls.json"
    response.write_text(
        "invalid"
        if case == "invalid_response"
        else json.dumps([[], [] if case == "no_pr" else [pr]]),
        encoding="utf-8",
    )
    bash_env = tmp_path / "bash-env"
    bash_env.write_text(
        """gh() {
          [[ "$*" == "api --paginate --slurp repos/$GITHUB_REPOSITORY/commits/$EXPECTED_SHA/pulls" ]] || return 2
          [[ "$API_FAILURE" != true ]] || return 1
          cat "$PULLS_RESPONSE"
        }
""",
        encoding="utf-8",
    )
    output = tmp_path / "github-output"
    workflow = load_workflow(repo_root / ".github/workflows/release-on-merge.yml")
    script = workflow["jobs"]["identify_release"]["steps"][1]["run"]
    result = subprocess.run(
        [bash, "-c", script],
        cwd=state,
        env=os.environ
        | {
            "BASH_ENV": bash_path_or_skip(bash, bash_env),
            "PULLS_RESPONSE": bash_path_or_skip(bash, response),
            "GITHUB_OUTPUT": bash_path_or_skip(bash, output),
            "GITHUB_REPOSITORY": "TJZine/frame-compare",
            "EXPECTED_SHA": sha,
            "PREVIOUS_SHA": "a" * 40 if case == "missing_previous_commit" else previous_sha,
            "API_FAILURE": "true" if case == "api_failure" else "false",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert (result.returncode == 0) is succeeds, result.stderr
    if publishes:
        assert output.read_text(encoding="utf-8") == (
            f"version=0.7.0\ntag=v0.7.0\nexpected_sha={sha}\n"
        )
    else:
        assert not output.exists()
