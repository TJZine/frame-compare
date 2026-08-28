from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from tests.workflow_helpers import load_workflow as _load_workflow


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step
        for job in workflow.get("jobs", {}).values()
        for step in job.get("steps", [])
        if isinstance(step, dict)
    ]


def test_workflows_pin_actions_to_full_commit_shas(repo_root: Path) -> None:
    for path in (repo_root / ".github" / "workflows").glob("*.yml"):
        workflow = _load_workflow(path)
        references = [job.get("uses") for job in workflow.get("jobs", {}).values()]
        references.extend(step.get("uses") for step in _steps(workflow))

        for reference in references:
            if isinstance(reference, str) and not reference.startswith("./"):
                assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference), (
                    path,
                    reference,
                )


def test_release_workflows_preserve_triggers_permissions_and_windows_owner(
    repo_root: Path,
) -> None:
    release = _load_workflow(repo_root / ".github" / "workflows" / "release.yml")
    portable = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable-build.yml")

    assert set(release["on"]) == {"workflow_call"}
    assert release["permissions"] == {}
    attestation_permissions = {
        "attestations": "write",
        "contents": "read",
        "id-token": "write",
    }
    assert release["jobs"]["preflight"]["permissions"] == {"contents": "read"}
    assert release["jobs"]["windows"]["permissions"] == attestation_permissions
    assert release["jobs"]["publish"]["permissions"] == {"contents": "write"}
    assert release["jobs"]["windows"]["uses"].endswith("windows-portable-build.yml")
    assert portable["on"]["workflow_call"] is not None
    assert "permissions" not in portable
    assert "permissions" not in portable["jobs"]["build"]


def test_release_workflow_keeps_fail_closed_asset_contract(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "release.yml")
    source = (repo_root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert workflow["jobs"]["publish"]["needs"] == ["preflight", "windows"]
    for asset in (
        "frame-compare-portable-win-x64-${RELEASE_TAG}.zip",
        "frame-compare-portable-win-x64-${RELEASE_TAG}.zip.sha256",
        "frame-compare-update-win-x64-${RELEASE_TAG}.zip",
        "frame-compare-update-win-x64-${RELEASE_TAG}.zip.sha256",
    ):
        assert asset in source
    assert "sha256sum --check" in source
    assert '"update-manifest.sig"' in source
    assert "does not contain the exact mandatory set" in source


def test_release_workflow_orders_external_mutations_and_rechecks_collisions(
    repo_root: Path,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "release.yml")
    steps = workflow["jobs"]["publish"]["steps"]
    names = [step.get("name") for step in steps]
    recheck = steps[names.index("Recheck main, collisions, and create exact tag")]["run"]
    draft = steps[names.index("Create a new draft release")]["run"]
    verify_draft = steps[names.index("Verify draft target and exact remote asset bytes")]["run"]
    publish = steps[names.index("Publish verified release")]["run"]
    verify_final = steps[names.index("Verify final publication state")]["run"]

    assert names.index("Recheck main, collisions, and create exact tag") < names.index(
        "Create a new draft release"
    )
    assert names.index("Create a new draft release") < names.index(
        "Attach every mandatory asset to the new draft"
    )
    assert names.index("Attach every mandatory asset to the new draft") < names.index(
        "Publish verified release"
    )
    assert names.index("Publish verified release") < names.index("Verify final publication state")
    assert "check_absent" in recheck
    assert "git/ref/tags/${RELEASE_TAG}" in recheck
    assert "releases/tags/${RELEASE_TAG}" in recheck
    assert "ref=refs/tags/${RELEASE_TAG}" in recheck
    assert '"draft=true"' in draft
    assert "--method PATCH" in publish and '"draft=false"' in publish
    assert all(
        semantic in verify_draft
        for semantic in (
            '"$remote_tag" != "$RELEASE_TAG"',
            '"$target" != "$EXPECTED_SHA"',
            '"$tag_sha" != "$EXPECTED_SHA"',
            '"${actual[*]}" != "${wanted[*]}"',
            '"$digest" != "sha256:${local_hash}"',
        )
    )
    patch_position = publish.index("--method PATCH")
    for semantic in (
        '"$current_main" != "$EXPECTED_SHA"',
        '"$remote_tag" != "$RELEASE_TAG"',
        '"$target" != "$EXPECTED_SHA"',
        '"$tag_sha" != "$EXPECTED_SHA"',
        '"${actual[*]}" != "${wanted[*]}"',
        '"$digest" != "sha256:${local_hash}"',
    ):
        assert publish.index(semantic) < patch_position
    assert all(
        semantic in verify_final
        for semantic in (
            '"$draft" != "false"',
            '"$current_main" != "$EXPECTED_SHA"',
            '"$remote_tag" != "$RELEASE_TAG"',
            '"$target" != "$EXPECTED_SHA"',
            '"$tag_sha" != "$EXPECTED_SHA"',
            '"${actual[*]}" != "${wanted[*]}"',
            '"$digest" != "sha256:${local_hash}"',
        )
    )


def test_ci_and_docker_workflows_keep_required_triggers_and_permissions(
    repo_root: Path,
) -> None:
    ci = _load_workflow(repo_root / ".github" / "workflows" / "ci.yml")
    docker = _load_workflow(repo_root / ".github" / "workflows" / "docker-integration.yml")

    assert {"push", "pull_request", "workflow_dispatch"} <= set(ci["on"])
    assert ci["permissions"] == {"contents": "read"}
    assert {"pull_request", "workflow_dispatch"} <= set(docker["on"])
    assert docker["permissions"] == {"contents": "read"}
    assert {"main", "cleanup", "staging", "dev/v0.2.0"} <= set(
        docker["on"]["pull_request"]["branches"]
    )
    assert "dev/v0.2.0" not in ci["on"]["push"]["branches"]
    assert "dev/v0.2.0" in ci["on"]["pull_request"]["branches"]
    workflow_paths = docker["on"]["pull_request"]["paths"]
    assert {
        "uv.lock",
        "Dockerfile",
        "docker-compose*.yml",
        "tools/verify_docker_*.sh",
        "tests/workflows/**",
        "src/frame_compare/analysis/**",
        "src/frame_compare/render/**",
        "src/frame_compare/vs/**",
    } <= set(workflow_paths)


def test_pr_title_workflow_can_publish_its_configured_status(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "pr-title.yml")
    lint_job = workflow["jobs"]["pr_title"]
    lint_step = lint_job["steps"][0]

    assert workflow["permissions"] == {"pull-requests": "read"}
    assert lint_job["permissions"] == {
        "pull-requests": "read",
        "statuses": "write",
    }
    assert lint_step["with"]["wip"] == "true"


def test_release_please_remains_guarded_and_non_merging(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "release-please.yml")
    guard = workflow["jobs"]["initial_release_guard"]
    release = workflow["jobs"]["release_please"]
    action = next(step for step in release["steps"] if "uses" in step)
    checkout = next(
        step for step in guard["steps"] if str(step.get("uses", "")).startswith("actions/checkout@")
    )
    guard_step = next(step for step in guard["steps"] if step.get("id") == "guard")
    guard_run = str(guard_step["run"])

    assert workflow["permissions"] == {"contents": "read"}
    assert guard["permissions"] == {"contents": "read"}
    assert release["needs"] == "initial_release_guard"
    assert release["if"] == "needs.initial_release_guard.outputs.enabled == 'true'"
    assert release["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert action["with"]["skip-github-release"] == "true"
    assert checkout["with"]["fetch-depth"] == "1"
    assert checkout["with"]["persist-credentials"] == "false"
    assert ".release-please-manifest.json" in guard_run
    assert 'release_tag="v${manifest_version}"' in guard_run
    assert "releases/tags/${release_tag}" in guard_run
    assert "git/ref/tags/${release_tag}" in guard_run
    assert "v0.1.0" not in guard_run
    for step in _steps(workflow):
        command = str(step.get("run", ""))
        assert "gh pr merge" not in command, step.get("name")


def test_windows_portable_dispatch_owns_immutable_release_inputs_and_secrets(
    repo_root: Path,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable.yml")
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    jobs = workflow["jobs"]

    assert set(inputs) == {"operation", "channel", "version", "tag", "expected_sha"}
    assert workflow["permissions"] == {}
    assert jobs["release"]["uses"] == "./.github/workflows/release.yml"
    assert set(jobs["release"]["with"]) == {"channel", "version", "tag", "expected_sha"}
    assert jobs["verify_pull_request"]["permissions"] == {"contents": "read"}
    assert jobs["verify_pull_request"]["with"]["require_signing"] == "false"
    assert "secrets" not in jobs["verify_pull_request"]
    assert jobs["verify_manual"]["permissions"] == {"contents": "read"}
    assert jobs["verify_manual"]["with"]["require_signing"] == "true"
    assert set(jobs["verify_manual"]["secrets"]) == {"WINDOWS_UPDATE_SIGNING_KEY_XML"}
    assert jobs["release"]["permissions"] == {
        "attestations": "write",
        "contents": "write",
        "id-token": "write",
    }
    assert set(jobs["release"]["secrets"]) == {"WINDOWS_UPDATE_SIGNING_KEY_XML"}


def test_ci_keeps_coverage_test_audit_browser_and_distribution_gates(
    repo_root: Path,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "ci.yml")
    jobs = workflow["jobs"]

    test_run = "\n".join(str(step.get("run", "")) for step in jobs["test"]["steps"])
    assert "pytest -q" in test_run
    assert "--cov=src/frame_compare" in test_run
    assert "--cov-report=term-missing" in test_run
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["tool"]["coverage"]["run"]["branch"] is True
    assert project["tool"]["coverage"]["report"]["fail_under"] == 80
    browser_runs = [str(step.get("run", "")) for step in jobs["report-browser"]["steps"]]
    assert any("command -v google-chrome" in run for run in browser_runs)
    assert any("tests/browser/test_report_browser_smoke.py" in run for run in browser_runs)
    audit_run = "\n".join(str(step.get("run", "")) for step in jobs["dependency-audit"]["steps"])
    assert all(flag in audit_run for flag in ("--strict", "--require-hashes", "--disable-pip"))
    assert "--ignore-vuln" not in audit_run
    package_run = "\n".join(str(step.get("run", "")) for step in jobs["package"]["steps"])
    assert "uv build --out-dir dist" in package_run
    assert "scripts/verify_distribution.py" in package_run
    assert "uv pip install" in package_run
    required_jobs = {
        "lint",
        "security",
        "dependency-audit",
        "typecheck",
        "test",
        "import-lints",
        "package",
        "report-browser",
    }
    assert set(jobs["ci-pass"]["needs"]) == required_jobs
    audit_runners = set(jobs["dependency-audit"]["strategy"]["matrix"]["os"])
    assert any("ubuntu" in runner for runner in audit_runners)
    assert any("windows" in runner for runner in audit_runners)


def test_docker_build_inputs_are_immutable(repo_root: Path) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    for image in re.findall(r"^FROM\s+(\S+)", dockerfile, re.MULTILINE):
        if image in {"runtime"}:
            continue
        assert re.search(r"@sha256:[0-9a-f]{64}$", image), image
    commits = re.findall(r"^ARG\s+\w+COMMIT=([^\s]+)", dockerfile, re.MULTILINE)
    assert commits
    assert all(re.fullmatch(r"[0-9a-f]{40}", commit) for commit in commits)
    wheel_hashes = re.findall(r"^ARG\s+\w+SHA256=([^\s]+)", dockerfile, re.MULTILINE)
    assert wheel_hashes
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in wheel_hashes)
    assert "uv export --frozen" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "python -m pip install --no-cache-dir --user --no-deps -e ." in dockerfile


def test_setup_uv_uses_one_concrete_version(repo_root: Path) -> None:
    versions: set[str] = set()
    for path in (repo_root / ".github" / "workflows").glob("*.yml"):
        for step in _steps(_load_workflow(path)):
            if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
                version = str(step.get("with", {}).get("version", ""))
                assert re.fullmatch(r"\d+\.\d+\.\d+", version), (path, version)
                versions.add(version)
    assert len(versions) == 1
