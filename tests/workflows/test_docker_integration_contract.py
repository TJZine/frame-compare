from __future__ import annotations

import os
import shlex
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path

from tests.workflow_helpers import load_workflow

from ._helpers import SCRIPT_SUBPROCESS_TIMEOUT_SECONDS
from ._helpers import bash_executable_or_skip as _bash_executable_or_skip

RESOURCE_TEST = "tests/integration/test_alignment_streaming_resources.py"

ALIGNMENT_TRIGGER_PATHS = (
    ".github/workflows/docker-integration.yml",
    "src/frame_compare/services/alignment*.py",
    "src/frame_compare/services/errors.py",
    "src/frame_compare/services/types.py",
    "src/frame_compare/orchestration/phase_alignment.py",
    "src/frame_compare/orchestration/execution.py",
    "src/frame_compare/orchestration/execution_types.py",
    "src/frame_compare/orchestration/context.py",
    "src/frame_compare/utils/subproc.py",
    "src/frame_compare/utils/types.py",
)

ALIGNMENT_TEST_TRIGGER_PATTERNS = (
    "tests/services/test_alignment*.py",
    "tests/services/alignment_request_test_support.py",
    "tests/orchestration/test_phase_alignment*.py",
    "tests/orchestration/test_phase_tasks_alignment.py",
    "tests/orchestration/phase_task_helpers.py",
)


def _write_fake_docker(path: Path) -> None:
    path.write_text(
        """#!/bin/sh
set -eu

if [ "$1" = compose ] && [ "$2" = version ]; then
  exit 0
fi
if [ "$1" = info ]; then
  exit 0
fi
if [ "$1" = compose ] && [ "$2" = run ]; then
  printf '%s\\n' "$@" > "$FRAME_COMPARE_DOCKER_INVOCATION"
  if [ "${FRAME_COMPARE_DOCKER_MODE:-fail}" = skip ]; then
    printf '1 skipped\\n'
    exit 0
  fi
  exit 17
fi
printf 'unexpected docker invocation: %s\\n' "$*" >&2
exit 99
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_verifier(
    repo_root: Path, tmp_path: Path, *, mode: str = "fail", extra_args: list[str] | None = None
) -> tuple[subprocess.CompletedProcess[str], str]:
    bash = _bash_executable_or_skip()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker")
    invocation = tmp_path / "docker-invocation.txt"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["FRAME_COMPARE_DOCKER_INVOCATION"] = str(invocation)
    environment["FRAME_COMPARE_DOCKER_MODE"] = mode
    environment["FRAME_COMPARE_CHANNEL_CORROBORATION"] = "0"
    result = subprocess.run(
        [bash, "tools/verify_docker_integration.sh", "--no-build", *(extra_args or [])],
        cwd=repo_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    return result, invocation.read_text(encoding="utf-8")


def _docker_steps(repo_root: Path) -> list[dict[str, object]]:
    workflow = load_workflow(repo_root / ".github" / "workflows" / "docker-integration.yml")
    return workflow["jobs"]["docker-integration"]["steps"]


def _pull_request_paths(repo_root: Path) -> list[str]:
    workflow = load_workflow(repo_root / ".github" / "workflows" / "docker-integration.yml")
    return workflow["on"]["pull_request"]["paths"]


def _path_matches_workflow(path: str, workflow_paths: list[str]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in workflow_paths)


def test_default_verifier_excludes_only_opt_in_resource_module(
    repo_root: Path, tmp_path: Path
) -> None:
    result, invocation = _run_verifier(repo_root, tmp_path)

    assert result.returncode == 17
    command = shlex.split(invocation)
    service_index = command.index("frame-compare-test")
    assert command[service_index - 2 : service_index] == [
        "-e",
        "FRAME_COMPARE_CHANNEL_CORROBORATION=1",
    ]
    assert command.count("FRAME_COMPARE_CHANNEL_CORROBORATION=1") == 1
    command = shlex.split(invocation.splitlines()[-1])
    assert command[-3:] == ["--ignore=" + RESOURCE_TEST, "tests/integration/", "tests/vs/"]
    assert command.count("tests/integration/") == 1
    assert command.count("tests/vs/") == 1


def test_verifier_keeps_global_zero_skip_guard(repo_root: Path, tmp_path: Path) -> None:
    result, _ = _run_verifier(repo_root, tmp_path, mode="skip")

    assert result.returncode == 3
    assert "this gate requires zero skips" in result.stderr


def test_explicit_pytest_path_is_not_hidden_by_default_exclusion(
    repo_root: Path, tmp_path: Path
) -> None:
    result, invocation = _run_verifier(
        repo_root,
        tmp_path,
        extra_args=["--pytest-path", RESOURCE_TEST],
    )

    assert result.returncode == 17
    command = shlex.split(invocation.splitlines()[-1])
    assert command[-1] == RESOURCE_TEST
    assert "--ignore=" + RESOURCE_TEST not in command


def test_workflow_runs_opt_in_resources_after_canonical_gate_without_rebuild(
    repo_root: Path,
) -> None:
    steps = _docker_steps(repo_root)
    canonical_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("run") == "bash tools/verify_docker_integration.sh --no-cache"
    )
    resource_matches = [
        (index, str(step["run"]))
        for index, step in enumerate(steps)
        if step.get("name") == "Run opt-in alignment resource proof"
    ]

    assert len(resource_matches) == 1
    resource_index, resource_run = resource_matches[0]
    assert resource_index > canonical_index

    resource_command = shlex.split(resource_run)
    assert resource_command == [
        "docker",
        "compose",
        "run",
        "--rm",
        "--no-deps",
        "-e",
        "FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1",
        "--entrypoint",
        "python",
        "frame-compare-test",
        "-m",
        "pytest",
        "-o",
        "cache_dir=/tmp/frame-compare-resource-pytest-cache",
        RESOURCE_TEST,
        "-rsx",
        "-s",
    ]
    assert "build" not in resource_command
    assert "--build" not in resource_command


def test_workflow_triggers_alignment_resource_owners_and_tests(repo_root: Path) -> None:
    workflow_paths = _pull_request_paths(repo_root)

    assert set(ALIGNMENT_TRIGGER_PATHS) <= set(workflow_paths)
    assert set(ALIGNMENT_TEST_TRIGGER_PATTERNS) <= set(workflow_paths)
    assert "tests/integration/**" in workflow_paths
    assert "tests/workflows/**" in workflow_paths
    assert "src/frame_compare/services/**" not in workflow_paths
    assert "src/frame_compare/orchestration/**" not in workflow_paths

    matching_paths = (
        ".github/workflows/docker-integration.yml",
        "src/frame_compare/services/alignment_audio.py",
        "src/frame_compare/orchestration/execution_types.py",
        "src/frame_compare/utils/subproc.py",
        "tests/services/test_alignment_streaming.py",
        "tests/services/alignment_request_test_support.py",
        "tests/orchestration/test_phase_alignment_contract.py",
        "tests/orchestration/test_phase_tasks_alignment.py",
        "tests/orchestration/phase_task_helpers.py",
        RESOURCE_TEST,
    )
    assert all(_path_matches_workflow(path, workflow_paths) for path in matching_paths)

    alignment_modules = [
        path.relative_to(repo_root).as_posix()
        for path in (repo_root / "src/frame_compare/services").glob("alignment*.py")
    ]
    assert alignment_modules
    assert all(_path_matches_workflow(path, workflow_paths) for path in alignment_modules)


def test_workflow_does_not_trigger_unrelated_service_orchestration_paths(
    repo_root: Path,
) -> None:
    workflow_paths = _pull_request_paths(repo_root)

    unrelated_paths = (
        "src/frame_compare/services/release_identity.py",
        "src/frame_compare/services/update.py",
        "src/frame_compare/services/report/renderer.py",
        "src/frame_compare/orchestration/phase_render.py",
        "src/frame_compare/orchestration/selection_report.py",
        "docs/current-architecture.md",
    )
    assert all(not _path_matches_workflow(path, workflow_paths) for path in unrelated_paths)
