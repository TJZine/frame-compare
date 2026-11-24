from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.workflow_helpers import dockerfile_stages, read_text_or_fail
from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import step_by_name as _step_by_name


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


@pytest.mark.parametrize(
    ("channel", "branch", "workflow_name"),
    [
        ("rc", "pre-release", "rc.yml"),
        ("stable", "main", "release.yml"),
    ],
)
def test_release_workflows_plan_the_live_head_and_require_windows_scan(
    repo_root: Path, channel: str, branch: str, workflow_name: str
) -> None:
    path = repo_root / ".github/workflows" / workflow_name
    workflow = _load_workflow(path)
    assert workflow["on"] == {"push": {"branches": [branch]}}
    assert workflow["concurrency"] == {"group": f"release-{channel}", "cancel-in-progress": "false"}
    assert workflow["permissions"] == {}
    jobs = workflow["jobs"]
    plan, source, windows, publish = (
        jobs[name] for name in ("plan", "source-security", "windows", "publish")
    )
    assert plan["permissions"] == {"contents": "write"}
    assert _step_by_name(plan, "Fetch live branch heads and tags")["with"] == {
        "ref": f"refs/heads/{branch}",
        "fetch-depth": "0",
        "persist-credentials": "false",
    }
    plan_step = _step_by_name(plan, f"Plan {channel} release")
    assert plan_step["run"] == f"python3 -B -m scripts.release_plan plan-{channel}"
    assert "continue-on-error" not in plan and "continue-on-error" not in plan_step

    for job in (source, windows, publish):
        assert job["if"] == "needs.plan.outputs.status == 'publish'"
    sha = "${{ needs.plan.outputs.sha }}"
    assert source["uses"] == "./.github/workflows/source-security.yml"
    assert source["with"] == {"expected_sha": sha}
    assert windows["needs"] == ["plan", "source-security"]
    assert windows["uses"] == "./.github/workflows/windows-portable.yml"
    assert windows["with"] == {"sha": sha, "release_build": "true"}
    assert source["permissions"] == windows["permissions"] == {"contents": "read"}
    assert publish["permissions"] == {"contents": "write"}
    assert publish["needs"] == ["plan", "source-security", "windows"]
    assert _step_by_name(publish, "Checkout exact release source")["with"]["ref"] == sha
    download = _step_by_name(publish, "Download the scanned ZIP")
    assert download["with"] == {
        "artifact-ids": "${{ needs.windows.outputs.bundle_id }}",
        "path": "${{ runner.temp }}/release-assets",
        "skip-decompress": "true",
        "digest-mismatch": "error",
    }
    proof = _step_by_name(publish, "Require the exact build artifact")
    assert proof["env"]["BUNDLE_ID"] == "${{ needs.windows.outputs.bundle_id }}"
    assert proof["env"]["BUNDLE_DIGEST"] == "${{ needs.windows.outputs.bundle_digest }}"
    assert "git rev-parse HEAD" in proof["run"]
    owner = _step_by_name(publish, "Upload and verify the draft before publishing")
    assert owner["env"]["BUNDLE_DIGEST"] == proof["env"]["BUNDLE_DIGEST"]
    assert owner["env"]["RELEASE_SHA"] == sha
    assert "python3 -B -m scripts.release_plan publish" in owner["run"]
    assert '--digest "$BUNDLE_DIGEST"' in owner["run"]
    assert owner["env"]["GH_TOKEN"] == plan_step["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert owner["env"].get("RELEASE_PUBLISH_TOKEN") == (
        "${{ secrets.RELEASE_PUBLISH_TOKEN }}" if channel == "rc" else None
    )
    assert path.read_text(encoding="utf-8").count("secrets.RELEASE_PUBLISH_TOKEN") == (
        1 if channel == "rc" else 0
    )
    steps = publish["steps"]
    assert steps.index(proof) < steps.index(download) < steps.index(owner)
    assert all("continue-on-error" not in step for step in (proof, download, owner))
    assert "label" not in jobs if channel == "rc" else "label" in jobs


def test_stable_label_runs_for_existing_complete_release_or_successful_publish(
    repo_root: Path,
) -> None:
    stable = _load_workflow(repo_root / ".github/workflows/release.yml")
    label = stable["jobs"]["label"]
    assert label["needs"] == ["plan", "publish"]
    assert label["permissions"] == {"contents": "read", "pull-requests": "write"}
    assert label["if"] == (
        "always() && needs.plan.result == 'success' && "
        "(needs.plan.outputs.status == 'complete' || needs.publish.result == 'success')"
    )
    step = _step_by_name(label, "Mark the merged Release Please PR as tagged")
    assert step["env"]["VERSION"] == "${{ needs.plan.outputs.version }}"
    assert step["run"] == 'python3 -B -m scripts.release_plan label --version "$VERSION"'


def test_all_dependabot_updates_target_pre_release(repo_root: Path) -> None:
    config = _load_workflow(repo_root / ".github/dependabot.yml")
    assert {item["package-ecosystem"] for item in config["updates"]} == {
        "uv",
        "github-actions",
        "docker",
        "docker-compose",
    }
    assert {item["target-branch"] for item in config["updates"]} == {"pre-release"}


def test_ci_and_docker_workflows_keep_required_triggers_and_permissions(
    repo_root: Path,
) -> None:
    ci = _load_workflow(repo_root / ".github" / "workflows" / "ci.yml")
    docker = _load_workflow(repo_root / ".github" / "workflows" / "docker-integration.yml")

    assert set(ci["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert set(ci["on"]["push"]["branches"]) == {"main", "pre-release"}
    assert ci["permissions"] == {"contents": "read"}
    assert set(docker["on"]) == {"pull_request", "workflow_dispatch"}
    assert docker["permissions"] == {"contents": "read"}
    assert docker["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}",
        "cancel-in-progress": "true",
    }
    # Integration PRs must be checked regardless of their base branch.
    for workflow in (ci, docker):
        pr_options = workflow["on"]["pull_request"] or {}
        assert "branches" not in pr_options
        assert "branches-ignore" not in pr_options
    assert not ci["on"]["pull_request"]
    workflow_paths = docker["on"]["pull_request"]["paths"]
    assert {
        "src/**",
        "tests/**",
        "pyproject.toml",
        "uv.lock",
        "Dockerfile",
        "README.md",
        "LICENSE",
        "docker-compose*.yml",
        "tools/verify_docker_*.sh",
        "tools/docker_runtime_smoke.py",
        "tools/checkout_source_commit.sh",
        ".dockerignore",
        ".github/workflows/docker-integration.yml",
    } == set(workflow_paths)
    assert "paths-ignore" not in docker["on"]["pull_request"]


def test_compose_services_run_headless(repo_root: Path) -> None:
    compose = yaml.safe_load(read_text_or_fail(repo_root / "docker-compose.yml"))
    services = compose["services"]
    assert set(services) == {
        "frame-compare",
        "frame-compare-test",
        "frame-compare-run",
        "frame-compare-wizard",
    }

    dockerfile = read_text_or_fail(repo_root / "Dockerfile")
    stages = dockerfile_stages(dockerfile)
    default_target = stages[-1][1]
    assert default_target == "default-runtime"
    software_rendering = {}
    for base, stage, body in stages:
        value = software_rendering.get(base)
        for instruction in re.findall(r"^ENV[ \t]+(.+)$", body.replace("\\\n", " "), re.MULTILINE):
            for assignment in shlex.split(instruction):
                key, _, setting = assignment.partition("=")
                if key == "LIBGL_ALWAYS_SOFTWARE":
                    value = setting
        software_rendering[stage] = value

    for name, service in services.items():
        if name == "frame-compare-wizard":
            assert service["profiles"] == ["setup"]
        else:
            assert "profiles" not in service, name
        assert "gpus" not in service, name
        assert service.get("runtime") != "nvidia", name
        assert not service.get("devices"), name
        assert (
            not service.get("deploy", {})
            .get("resources", {})
            .get("reservations", {})
            .get("devices")
        ), name

        build = service["build"]
        assert build["context"] == "." and build["dockerfile"] == "Dockerfile", name
        inherited = software_rendering[build.get("target", default_target)]
        assert inherited == "1", name
        environment = service.get("environment", {})
        if isinstance(environment, list):
            entries = (entry.partition("=") for entry in environment)
            environment = {key: value for key, _, value in entries}
        assert str(environment.get("LIBGL_ALWAYS_SOFTWARE", inherited)) == "1", name
        assert not any(key.startswith("NVIDIA_") for key in environment), name


def test_docker_verifies_both_native_architectures(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github/workflows/docker-integration.yml")
    job = workflow["jobs"]["docker-integration"]
    assert job["name"] == "${{ matrix.name }}"
    assert job["runs-on"] == "${{ matrix.runner }}"
    assert job["strategy"]["fail-fast"] == "false"
    variants = {variant["arch"]: variant for variant in job["strategy"]["matrix"]["include"]}
    assert set(variants) == {"amd64", "arm64"}
    assert variants["amd64"]["runner"] == "ubuntu-latest"
    assert variants["amd64"]["name"] == "Docker Integration Tests"
    assert variants["arm64"]["runner"] == "ubuntu-24.04-arm"
    assert variants["arm64"]["name"] == "Docker Integration Tests (ARM64)"
    assert {variant["artifact"] for variant in variants.values()} == {
        "docker-e2e-artifacts",
        "docker-e2e-artifacts-arm64",
    }

    steps = {step.get("name"): step for step in job["steps"]}
    assert steps["Run opt-in alignment resource proof"]["if"] == "matrix.arch == 'amd64'"


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
    workflow = _load_workflow(repo_root / ".github/workflows/release-please.yml")
    guard = workflow["jobs"]["stable_release_guard"]
    release = workflow["jobs"]["release_please"]
    action = next(step for step in release["steps"] if "uses" in step)
    checkout = _step_by_name(guard, "Fetch live integration head and tags")
    guard_step = _step_by_name(guard, "Require the published stable version in integration history")

    assert workflow["permissions"] == guard["permissions"] == {"contents": "read"}
    assert release["needs"] == "stable_release_guard"
    assert release["if"] == "needs.stable_release_guard.outputs.enabled == 'true'"
    assert release["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert action["with"]["skip-github-release"] == "true"
    assert action["with"]["target-branch"] == "pre-release"
    assert workflow["on"] == {"push": {"branches": ["pre-release"]}}
    assert checkout["with"] == {
        "ref": "refs/heads/pre-release",
        "fetch-depth": "0",
        "persist-credentials": "false",
    }
    assert guard_step["run"] == "python3 -B -m scripts.release_plan release-please-guard"
    for step in _steps(workflow):
        assert "gh pr merge" not in str(step.get("run", ""))

    config = json.loads((repo_root / "release-please-config.json").read_bytes())
    files = config["packages"]["."]["extra-files"]
    assert {item["path"]: item["type"] for item in files} == {
        "uv.lock": "toml",
        "src/frame_compare/__init__.py": "generic",
    }
    assert re.search(
        r'^__version__ = "[^"]+" +# x-release-please-version$',
        (repo_root / "src/frame_compare/__init__.py").read_text(encoding="utf-8"),
        re.M,
    )


def test_ci_keeps_test_audit_browser_and_distribution_gates(
    repo_root: Path,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "ci.yml")
    jobs = workflow["jobs"]

    lint_run = "\n".join(str(step.get("run", "")) for step in jobs["lint"]["steps"])
    assert "uv run --no-sync ruff check ." in lint_run
    assert "uv run --no-sync ruff format --check ." in lint_run
    test_run = "\n".join(str(step.get("run", "")) for step in jobs["test"]["steps"])
    assert "pytest -q -n auto --dist loadgroup --ignore=tests/browser" in test_run
    browser_runs = [str(step.get("run", "")) for step in jobs["report-browser"]["steps"]]
    assert any("command -v google-chrome" in run for run in browser_runs)
    assert any("tests/browser/test_report_browser_smoke.py" in run for run in browser_runs)
    security_caller = jobs["source-security"]
    assert security_caller["uses"] == "./.github/workflows/source-security.yml"
    assert security_caller["with"]["expected_sha"] == (
        "${{ github.event.pull_request.head.sha || github.sha }}"
    )
    security = _load_workflow(repo_root / ".github/workflows/source-security.yml")
    security_jobs = security["jobs"]
    assert set(security_jobs) == {"security", "dependency-audit"}
    for job in security_jobs.values():
        assert job["steps"][0]["with"] == {
            "ref": "${{ inputs.expected_sha }}",
            "persist-credentials": "false",
        }
        assert "git rev-parse HEAD" in job["steps"][1]["run"]
        assert job["steps"][1]["env"]["EXPECTED_SHA"] == "${{ inputs.expected_sha }}"
    assert security_jobs["security"]["steps"][-1]["run"] == "bash tools/check_python_security.sh"
    audit_run = "\n".join(
        str(step.get("run", "")) for step in security_jobs["dependency-audit"]["steps"]
    )
    assert all(flag in audit_run for flag in ("--strict", "--require-hashes", "--disable-pip"))
    assert "--ignore-vuln" not in audit_run
    package_run = "\n".join(str(step.get("run", "")) for step in jobs["package"]["steps"])
    assert "uv build --out-dir dist" in package_run
    assert "scripts/verify_distribution.py" in package_run
    assert "uv pip install" in package_run
    required_jobs = {
        "lint",
        "source-security",
        "typecheck",
        "test",
        "import-lints",
        "package",
        "report-browser",
    }
    assert set(jobs["ci-pass"]["needs"]) == required_jobs
    audit_runners = set(security_jobs["dependency-audit"]["strategy"]["matrix"]["os"])
    assert any("ubuntu" in runner for runner in audit_runners)
    assert any("windows" in runner for runner in audit_runners)


def test_docker_build_inputs_are_immutable(repo_root: Path) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    for image in re.findall(r"^FROM\s+(\S+)", dockerfile, re.MULTILINE):
        if image in {"runtime", "scratch"}:
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
    assert "COPY --from=application-inputs" in dockerfile
    assert not re.search(r"^COPY\s+(?:--\S+\s+)*\.\s+", dockerfile, re.MULTILINE)


def test_setup_uv_uses_one_concrete_version(repo_root: Path) -> None:
    versions: set[str] = set()
    for path in (repo_root / ".github" / "workflows").glob("*.yml"):
        for step in _steps(_load_workflow(path)):
            if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
                version = str(step.get("with", {}).get("version", ""))
                assert re.fullmatch(r"\d+\.\d+\.\d+", version), (path, version)
                versions.add(version)
    assert len(versions) == 1
