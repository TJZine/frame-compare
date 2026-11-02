from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.workflow_helpers import load_workflow

REPOSITORY = "TJZine/frame-compare"
TAG = "v0.7.0"


@pytest.fixture
def maintenance(repo_root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "recreate_pre_release", repo_root / "scripts/recreate_pre_release.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class Remote:
    work: Path
    bare: Path
    accepted: str
    published: str
    previous: str

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *arguments],
            cwd=self.work,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()

    def refs(self) -> str:
        return self.git("ls-remote", "--refs", "origin")

    @property
    def archive(self) -> str:
        return f"refs/tags/pre-release-archive/{TAG}-{self.accepted}"


@pytest.fixture
def remote(tmp_path: Path) -> Remote:
    work = tmp_path / "work"
    work.mkdir()
    bare = tmp_path / "origin.git"
    state = Remote(work, bare, "", "", "")
    state.git("init", "--bare", str(bare))
    state.git("init", "-b", "main")
    state.git("config", "user.name", "Release verification")
    state.git("config", "user.email", "release-tests@frame-compare.invalid")
    (work / "release.txt").write_text("previous release\n", encoding="utf-8")
    state.git("add", ".")
    state.git("commit", "-m", "previous stable release")
    state.previous = state.git("rev-parse", "HEAD")
    state.git("switch", "-c", "pre-release")
    for content in ("first feature\n", "accepted release\n"):
        (work / "release.txt").write_text(content, encoding="utf-8")
        state.git("commit", "-am", content.strip())
    state.accepted = state.git("rev-parse", "HEAD")
    tree = state.git("rev-parse", "HEAD^{tree}")
    state.published = state.git(
        "commit-tree", tree, "-p", state.previous, "-m", "chore(release): 0.7.0"
    )
    state.git("update-ref", "refs/heads/main", state.published)
    state.git("tag", TAG, state.published)
    state.git("remote", "add", "origin", str(bare))
    state.git("push", "origin", "main", "pre-release", f"refs/tags/{TAG}")
    return state


class Metadata:
    def __init__(self, remote: Remote) -> None:
        self.release: dict[str, Any] = {
            "draft": False,
            "prerelease": False,
            "tag_name": TAG,
            "target_commitish": remote.published,
            "published_at": "2026-10-15T12:00:00Z",
        }
        self.promotions: list[dict[str, Any]] = [
            {
                "title": "chore(release): 0.7.0",
                "merged_at": "2026-10-15T11:00:00Z",
                "merge_commit_sha": remote.published,
                "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
                "head": {
                    "ref": "pre-release",
                    "sha": remote.accepted,
                    "repo": {"full_name": REPOSITORY},
                },
            }
        ]
        self.open: list[dict[str, Any]] = []
        self.open_reads = 0

    def get(self, path: str) -> dict[str, Any]:
        assert path == f"releases/tags/{TAG}"
        return self.release

    def pulls(self, path: str) -> list[dict[str, Any]]:
        if path.startswith("commits/"):
            return self.promotions
        assert path == "pulls?state=open&per_page=100"
        self.open_reads += 1
        return self.open


def run_recreation(
    maintenance: ModuleType,
    remote: Remote,
    metadata: Metadata,
    *,
    late_head: str | None = None,
    late_ref: str = "refs/heads/pre-release",
) -> str:
    def git(*arguments: str) -> str:
        if late_head is not None and arguments[0] == "push":
            # Simulate another contributor winning after the final metadata reads.
            flags = ["--force"] if late_ref.startswith("refs/tags/") else []
            remote.git("push", *flags, "origin", f"{late_head}:{late_ref}")
        try:
            return remote.git(*arguments)
        except subprocess.CalledProcessError:
            raise maintenance.RecreationError("Remote Git operation rejected.") from None

    return maintenance.recreate(metadata, git, remote.published, TAG)


def new_commit(remote: Remote, parent: str) -> str:
    tree = remote.git("rev-parse", f"{parent}^{{tree}}")
    return remote.git("commit-tree", tree, "-p", parent, "-m", "new work after acceptance")


def test_published_squash_starts_fresh_cycle_and_preserves_history(
    maintenance: ModuleType, remote: Remote
) -> None:
    metadata = Metadata(remote)
    run_recreation(maintenance, remote, metadata)
    assert remote.git("ls-remote", "origin", "refs/heads/main").split()[0] == remote.published
    assert (
        remote.git("ls-remote", "origin", "refs/heads/pre-release").split()[0] == remote.published
    )
    assert remote.git("ls-remote", "origin", remote.archive).split()[0] == remote.accepted
    # The complete development history remains reachable through the saved head.
    assert remote.git("rev-list", "--count", f"{remote.previous}..{remote.accepted}") == "2"
    refs = remote.refs()
    assert "Already recreated" in run_recreation(maintenance, remote, metadata)
    assert remote.refs() == refs


@pytest.mark.parametrize(
    "failure",
    [
        "advanced_main",
        "advanced_integration",
        "open_incoming_pr",
        "open_outgoing_pr",
        "unpublished",
        "draft",
        "prerelease",
        "wrong_release_sha",
        "wrong_release_tag",
        "missing_promotion",
        "unmerged_promotion",
        "wrong_head",
        "wrong_base",
        "forked_head",
        "foreign_base",
        "wrong_merge_sha",
        "multiple_promotions",
        "merge_commit",
        "different_tree",
        "archive_collision",
        "wrong_tag_target",
        "null_head",
        "null_base",
        "null_head_repo",
        "null_base_repo",
    ],
)
def test_refuses_unsafe_cycle_transition_without_changing_remote_refs(
    maintenance: ModuleType, remote: Remote, failure: str
) -> None:
    metadata = Metadata(remote)
    promotion = metadata.promotions[0]
    if failure in {"advanced_main", "advanced_integration"}:
        branch = "main" if failure == "advanced_main" else "pre-release"
        parent = remote.published if branch == "main" else remote.accepted
        advanced = new_commit(remote, parent)
        remote.git("push", "origin", f"{advanced}:refs/heads/{branch}")
    elif failure == "open_incoming_pr":
        metadata.open = [{"base": {"ref": "pre-release"}}]
    elif failure == "open_outgoing_pr":
        metadata.open = [{"head": {"ref": "pre-release", "repo": {"full_name": REPOSITORY}}}]
    elif failure == "unpublished":
        metadata.release["published_at"] = None
    elif failure in {"draft", "prerelease"}:
        metadata.release[failure] = True
    elif failure == "wrong_release_sha":
        metadata.release["target_commitish"] = remote.accepted
    elif failure == "wrong_release_tag":
        metadata.release["tag_name"] = "v0.8.0"
    elif failure == "missing_promotion":
        metadata.promotions = []
    elif failure == "unmerged_promotion":
        promotion["merged_at"] = None
    elif failure in {"wrong_head", "wrong_base"}:
        promotion["head" if failure == "wrong_head" else "base"]["ref"] = "development"
    elif failure in {"forked_head", "foreign_base"}:
        promotion["head" if failure == "forked_head" else "base"]["repo"]["full_name"] = (
            "other/repo"
        )
    elif failure == "wrong_merge_sha":
        promotion["merge_commit_sha"] = remote.accepted
    elif failure == "multiple_promotions":
        metadata.promotions.append(copy.deepcopy(promotion))
    elif failure in {"merge_commit", "different_tree"}:
        tree = remote.git("rev-parse", f"{remote.accepted}^{{tree}}")
        parents = ["-p", remote.previous, "-p", remote.accepted]
        if failure == "different_tree":
            tree = remote.git("rev-parse", f"{remote.previous}^{{tree}}")
            parents = ["-p", remote.previous]
        remote.published = remote.git("commit-tree", tree, *parents, "-m", "invalid promotion")
        remote.git("push", "--force", "origin", f"{remote.published}:refs/heads/main")
        remote.git("push", "--force", "origin", f"{remote.published}:refs/tags/{TAG}")
        metadata.release["target_commitish"] = remote.published
        promotion["merge_commit_sha"] = remote.published
    elif failure == "archive_collision":
        remote.git("push", "origin", f"{remote.previous}:{remote.archive}")
    elif failure == "wrong_tag_target":
        remote.git("push", "--force", "origin", f"{remote.previous}:refs/tags/{TAG}")
    elif failure in {"null_head", "null_base"}:
        promotion["head" if failure == "null_head" else "base"] = None
    elif failure in {"null_head_repo", "null_base_repo"}:
        promotion["head" if failure == "null_head_repo" else "base"]["repo"] = None
    before = remote.refs()
    with pytest.raises(maintenance.RecreationError):
        run_recreation(maintenance, remote, metadata)
    assert remote.refs() == before


def test_server_rejection_is_atomic_for_archive_and_integration(
    maintenance: ModuleType, remote: Remote
) -> None:
    hook = remote.bare / "hooks" / "pre-receive"
    hook.write_text(
        "#!/bin/sh\nwhile read old new ref; do\n"
        '  case "$ref" in refs/tags/pre-release-archive/*) exit 1;; esac\n'
        "done\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    before = remote.refs()
    with pytest.raises(maintenance.RecreationError):
        run_recreation(maintenance, remote, Metadata(remote))
    assert remote.refs() == before


def test_concurrent_integration_update_wins_without_partial_archive_write(
    maintenance: ModuleType, remote: Remote
) -> None:
    advanced = new_commit(remote, remote.accepted)
    with pytest.raises(maintenance.RecreationError):
        run_recreation(maintenance, remote, Metadata(remote), late_head=advanced)
    assert remote.git("ls-remote", "origin", "refs/heads/pre-release").split()[0] == advanced
    assert remote.git("ls-remote", "origin", "refs/heads/main").split()[0] == remote.published
    assert remote.git("ls-remote", "origin", remote.archive) == ""


@pytest.mark.parametrize("changed_ref", ["refs/heads/main", f"refs/tags/{TAG}"])
def test_late_main_or_tag_change_reports_reconciliation_and_retains_archive(
    maintenance: ModuleType, remote: Remote, changed_ref: str
) -> None:
    advanced = new_commit(remote, remote.published)
    with pytest.raises(maintenance.RecreationError, match="main advanced|Stable tag"):
        run_recreation(
            maintenance, remote, Metadata(remote), late_head=advanced, late_ref=changed_ref
        )
    # The independent ref race cannot be locked by the integration lease. Report
    # it after the transaction and preserve both accepted and published histories.
    assert remote.git("ls-remote", "origin", changed_ref).split()[0] == advanced
    assert (
        remote.git("ls-remote", "origin", "refs/heads/pre-release").split()[0] == remote.published
    )
    assert remote.git("ls-remote", "origin", remote.archive).split()[0] == remote.accepted


def test_pr_created_during_checks_prevents_ref_changes(
    maintenance: ModuleType, remote: Remote
) -> None:
    class NewPullRequest(Metadata):
        def pulls(self, path: str) -> list[dict[str, Any]]:
            result = super().pulls(path)
            if self.open_reads == 2:
                return [{"base": {"ref": "pre-release"}}]
            return result

    before = remote.refs()
    with pytest.raises(maintenance.RecreationError):
        run_recreation(maintenance, remote, NewPullRequest(remote))
    assert remote.refs() == before


def test_missing_release_preserves_remote_refs(maintenance: ModuleType, remote: Remote) -> None:
    class MissingRelease(Metadata):
        def get(self, path: str) -> dict[str, Any]:
            raise maintenance.RecreationError("Stable release not found.")

    before = remote.refs()
    with pytest.raises(maintenance.RecreationError):
        run_recreation(maintenance, remote, MissingRelease(remote))
    assert remote.refs() == before


def test_paginated_github_pr_response_keeps_second_page_blocker(
    maintenance: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocker = {"base": {"ref": "pre-release"}}

    def api(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert command[:4] == ["gh", "api", "--paginate", "--slurp"]
        return subprocess.CompletedProcess(command, 0, json.dumps([[], [blocker]]))

    monkeypatch.setattr(maintenance.subprocess, "run", api)
    assert maintenance.GitHub().pulls("pulls?state=open&per_page=100") == [blocker]


def test_api_failure_does_not_expose_raw_diagnostics(
    maintenance: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, ["gh"], stderr="private-token-and-diagnostics")

    monkeypatch.setattr(maintenance.subprocess, "run", unavailable)
    with pytest.raises(maintenance.RecreationError) as error:
        maintenance.GitHub().get(f"releases/tags/{TAG}")
    assert "private-token-and-diagnostics" not in str(error.value)


def test_recreation_waits_for_stable_publication_and_separate_main_approval(
    repo_root: Path,
) -> None:
    release = load_workflow(repo_root / ".github/workflows/release.yml")
    recreate = release["jobs"]["recreate_pre_release"]
    assert recreate["needs"] == "publish"
    assert recreate["if"] == "inputs.channel == 'stable'"
    assert recreate["uses"] == "./.github/workflows/recreate-pre-release.yml"
    assert recreate["with"] == {
        "expected_sha": "${{ inputs.expected_sha }}",
        "release_tag": "${{ inputs.tag }}",
    }
    workflow = load_workflow(repo_root / ".github/workflows/recreate-pre-release.yml")
    job = workflow["jobs"]["recreate"]
    assert job["environment"] == {"name": "branch-maintenance"}
    assert job["concurrency"]["cancel-in-progress"] == "false"
    guard = job["steps"][0]
    assert guard["env"]["SOURCE_REF"] == "${{ github.ref }}"
    assert guard["env"]["SOURCE_SHA"] == "${{ github.sha }}"
    assert '"$SOURCE_REF" != "refs/heads/main"' in guard["run"]
    assert '"$EXPECTED_SHA" != "$SOURCE_SHA"' in guard["run"]
    checkout = job["steps"][1]["with"]
    assert checkout["ref"] == "${{ inputs.expected_sha }}"
    assert checkout["persist-credentials"] == "false"
    mint = job["steps"][2]
    assert mint["uses"].startswith("actions/create-github-app-token@")
    assert mint["with"] == {
        "client-id": "${{ vars.BRANCH_MAINTENANCE_CLIENT_ID }}",
        "private-key": "${{ secrets.BRANCH_MAINTENANCE_PRIVATE_KEY }}",
        "owner": "${{ github.repository_owner }}",
        "repositories": "${{ github.event.repository.name }}",
        "permission-contents": "write",
        "permission-workflows": "write",
    }
    environment = job["steps"][3]["env"]
    assert environment["PRE_RELEASE_RESET_TOKEN"] == "${{ steps.maintenance-token.outputs.token }}"
    assert "WINDOWS_UPDATE_SIGNING_KEY_XML" not in str(job)
