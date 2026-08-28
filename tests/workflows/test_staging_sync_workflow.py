from __future__ import annotations

from pathlib import Path

import yaml

from tests.workflow_helpers import load_workflow as _load_workflow


def test_dependabot_version_updates_target_staging(repo_root: Path) -> None:
    config_path = repo_root / ".github" / "dependabot.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["version"] == 2
    assert config["updates"]
    assert all(update["target-branch"] == "staging" for update in config["updates"])


def test_sync_staging_is_non_destructive_and_fail_closed(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "sync-staging.yml"
    workflow = _load_workflow(workflow_path)
    source = workflow_path.read_text(encoding="utf-8")

    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in workflow["on"]
    assert workflow["permissions"] == {"contents": "write"}
    assert workflow["concurrency"] == {"group": "sync-staging"}
    job = workflow["jobs"]["sync"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["runs-on"] == "ubuntu-24.04"
    assert job["timeout-minutes"] == "10"
    checkout = job["steps"][0]
    assert checkout["with"] == {"fetch-depth": "0"}

    for required in (
        "git fetch --no-tags origin main staging",
        'git merge --ff-only "$main_sha"',
        'git merge --no-ff --no-edit "$main_sha"',
        'git push origin "HEAD:refs/heads/staging"',
        "main advanced while this sync was running",
        'latest_main_sha="$(git rev-parse origin/main)"',
        "main changed during the sync",
    ):
        assert required in source
    assert "--force" not in source


def test_staging_check_triggers_do_not_change_release_please_scope(repo_root: Path) -> None:
    ci = _load_workflow(repo_root / ".github" / "workflows" / "ci.yml")
    docs = _load_workflow(repo_root / ".github" / "workflows" / "docs.yml")
    docker = _load_workflow(repo_root / ".github" / "workflows" / "docker-integration.yml")
    release_please = _load_workflow(repo_root / ".github" / "workflows" / "release-please.yml")

    assert ci["on"]["push"]["branches"] == ["main", "staging"]
    assert ci["on"]["pull_request"]["branches"] == [
        "main",
        "cleanup",
        "staging",
    ]
    assert docs["on"]["push"]["branches"] == ["main", "staging"]
    assert docs["on"]["pull_request"]["branches"] == ["main", "cleanup", "staging"]
    assert docker["on"]["pull_request"]["branches"] == [
        "main",
        "cleanup",
        "staging",
    ]
    assert release_please["on"]["push"]["branches"] == ["main"]
