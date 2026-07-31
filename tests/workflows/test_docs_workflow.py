from __future__ import annotations

import re
from pathlib import Path

from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import read_text_or_fail
from tests.workflow_helpers import step_by_name as _step_by_name

EXPECTED_PATHS = {
    "docs/**",
    "README.md",
    "CONTRIBUTING.md",
    "zensical.toml",
    "pyproject.toml",
    "uv.lock",
    ".gitignore",
    ".github/workflows/docs.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    "scripts/generate_api_docs.py",
    "scripts/api_docs/**",
    "tests/workflows/test_docs_workflow.py",
}
EXPECTED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "astral-sh/setup-uv": "c771a70e6277c0a99b617c7a806ffedaca235ff9",
    "actions/configure-pages": "45bfe0192ca1faeb007ade9deae92b16b8254a0d",
    "actions/upload-pages-artifact": "fc324d3547104276b827a68afc52ff2a11cc49c9",
    "actions/deploy-pages": "cd2ce8fcbc39b97be8ca5fce6e763baed58fa128",
}
EXPECTED_DEPLOY_GATE = (
    "github.ref == 'refs/heads/main' && "
    "(github.event_name == 'push' || github.event_name == 'workflow_dispatch')"
)


def test_docs_workflow_events_and_paths_are_scoped(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "docs.yml")
    events = workflow["on"]

    assert set(events) == {"pull_request", "push", "workflow_dispatch"}
    assert events["pull_request"]["branches"] == ["main", "cleanup"]
    assert events["push"]["branches"] == ["main"]
    assert set(events["pull_request"]["paths"]) == EXPECTED_PATHS
    assert set(events["push"]["paths"]) == EXPECTED_PATHS


def test_docs_workflow_permissions_and_concurrency_are_isolated(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "docs.yml")
    build = workflow["jobs"]["build"]
    deploy = workflow["jobs"]["deploy"]

    assert workflow["permissions"] == {"contents": "read"}
    assert "concurrency" not in workflow
    assert build["concurrency"] == {
        "group": "docs-${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": "true",
    }
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert deploy["concurrency"] == {"group": "pages", "cancel-in-progress": "false"}


def test_docs_workflow_builds_strictly_from_locked_docs_group(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "docs.yml"
    source = read_text_or_fail(workflow_path)
    workflow = _load_workflow(workflow_path)
    build = workflow["jobs"]["build"]

    assert _step_by_name(build, "Set up Python")["with"]["python-version"] == "3.13"
    uv_step = _step_by_name(build, "Set up uv")
    assert uv_step["with"] == {"version": "0.11.31", "enable-cache": "false"}
    assert not re.search(r"version:\s*[\"']?latest[\"']?", source, re.IGNORECASE)
    assert _step_by_name(build, "Install documentation dependencies")["run"] == (
        "uv sync --only-group docs --locked"
    )
    assert _step_by_name(build, "Check generated API documentation")["run"] == (
        "uv run --no-sync python scripts/generate_api_docs.py --check"
    )
    assert _step_by_name(build, "Build documentation")["run"] == (
        "uv run --no-sync zensical build --clean --strict"
    )
    search_scope_check = _step_by_name(build, "Check user documentation search scope")["run"]
    assert 'Path("site/search.json")' in search_scope_check
    assert '("TODO/", "plans/")' in search_scope_check


def test_docs_workflow_gates_pages_steps_and_deployment(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "docs.yml")
    build = workflow["jobs"]["build"]
    deploy = workflow["jobs"]["deploy"]

    configure = _step_by_name(build, "Configure GitHub Pages")
    upload = _step_by_name(build, "Upload GitHub Pages artifact")
    assert configure["if"] == EXPECTED_DEPLOY_GATE
    assert upload["if"] == EXPECTED_DEPLOY_GATE
    assert upload["with"]["path"] == "site/"
    assert deploy["if"] == EXPECTED_DEPLOY_GATE
    assert deploy["needs"] == "build"
    assert deploy["environment"] == {
        "name": "github-pages",
        "url": "${{ steps.deployment.outputs.page_url }}",
    }


def test_docs_workflow_pins_actions_to_expected_full_shas(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "docs.yml"
    source = read_text_or_fail(workflow_path)
    workflow = _load_workflow(workflow_path)
    action_uses = [
        step["uses"] for job in workflow["jobs"].values() for step in job["steps"] if "uses" in step
    ]

    assert len(action_uses) == len(EXPECTED_ACTIONS)
    for action, sha in EXPECTED_ACTIONS.items():
        assert f"{action}@{sha}" in action_uses
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", use) for use in action_uses)
    assert "persist-credentials: false" in source
