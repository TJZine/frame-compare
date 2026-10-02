from __future__ import annotations

import os
import shlex
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

from tests.workflow_helpers import load_workflow

from ._helpers import SCRIPT_SUBPROCESS_TIMEOUT_SECONDS
from ._helpers import bash_executable_or_skip as _bash_executable_or_skip

RESOURCE_TEST = "tests/integration/test_alignment_streaming_resources.py"

DOCKER_TRIGGER_PATHS = (
    "src/**",
    "tests/**",
    "pyproject.toml",
    "uv.lock",
    "Dockerfile",
    "docker-compose*.yml",
    "tools/verify_docker_*.sh",
    ".github/workflows/docker-integration.yml",
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
  case "${FRAME_COMPARE_DOCKER_MODE:-fail}" in
    skip) printf '1 skipped\\n'; exit 0 ;;
    xfailed) printf '1 xfailed\\n'; exit 0 ;;
    xpassed) printf '1 xpassed\\n'; exit 0 ;;
  esac
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


def _docker_invocation_args(invocation: str) -> list[str]:
    lines = invocation.splitlines()
    return lines[: lines.index("-c") + 1]


def _docker_environment_args(invocation: str) -> list[str]:
    args = _docker_invocation_args(invocation)
    return [args[index + 1] for index, value in enumerate(args[:-1]) if value == "-e"]


def _is_upload_artifact_step(step: dict[str, object]) -> bool:
    uses = step.get("uses")
    return isinstance(uses, str) and uses.startswith("actions/upload-artifact@")


@pytest.mark.parametrize("explicit", [False, True], ids=["default", "explicit-resource"])
def test_verifier_selects_pytest_paths_and_default_exclusion(
    repo_root: Path, tmp_path: Path, explicit: bool
) -> None:
    result, invocation = _run_verifier(
        repo_root, tmp_path, extra_args=["--pytest-path", RESOURCE_TEST] if explicit else None
    )
    assert result.returncode == 17
    command = shlex.split(invocation.splitlines()[-1])
    if explicit:
        assert command[-1] == RESOURCE_TEST
        assert "--ignore=" + RESOURCE_TEST not in command
    else:
        assert command[-4:] == [
            "--ignore=" + RESOURCE_TEST,
            "tests/e2e/",
            "tests/integration/",
            "tests/vs/",
        ]


def test_verifier_rejects_skipped_xfailed_and_xpassed_tests(
    repo_root: Path, tmp_path: Path
) -> None:
    for mode in ("skip", "xfailed", "xpassed"):
        mode_tmp = tmp_path / mode
        mode_tmp.mkdir()
        result, _ = _run_verifier(repo_root, mode_tmp, mode=mode)

        assert result.returncode == 3
        assert "zero non-passing outcomes" in result.stderr


def test_verifier_passes_host_user_media_environment_and_artifacts(
    repo_root: Path, tmp_path: Path
) -> None:
    result, invocation = _run_verifier(repo_root, tmp_path)

    assert result.returncode == 17
    assert {
        "HOME=/tmp/framecompare-home",
        "PYTHONUSERBASE=/home/framecompare/.local",
        "FRAME_COMPARE_E2E_REQUIRE_MEDIA=1",
        "FRAME_COMPARE_E2E_ARTIFACTS=/workspace/generated/e2e",
    } <= set(_docker_environment_args(invocation))
    args = _docker_invocation_args(invocation)
    user_index = args.index("--user")
    uid_gid = args[user_index + 1].split(":")
    assert len(uid_gid) == 2
    assert all(part.isdigit() for part in uid_gid)


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


def test_workflow_triggers_all_docker_runtime_and_test_paths(repo_root: Path) -> None:
    workflow_paths = _pull_request_paths(repo_root)

    assert workflow_paths == list(DOCKER_TRIGGER_PATHS)
    assert all(
        _path_matches_workflow(path, workflow_paths)
        for path in (
            "src/frame_compare/services/release_identity.py",
            "src/frame_compare/orchestration/phase_render.py",
            "tests/e2e/test_media_render.py",
            "Dockerfile",
            RESOURCE_TEST,
        )
    )


def test_workflow_uploads_e2e_artifacts_after_verification(repo_root: Path) -> None:
    steps = _docker_steps(repo_root)
    verification_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("run") == "bash tools/verify_docker_integration.sh --no-cache"
    )
    upload_matches = [
        (index, step) for index, step in enumerate(steps) if _is_upload_artifact_step(step)
    ]

    assert len(upload_matches) == 1
    upload_index, upload_step = upload_matches[0]
    assert upload_index > verification_index
    assert upload_step["if"] == "always()"
    assert upload_step["uses"] == (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    )
    assert upload_step["with"] == {
        "name": "docker-e2e-artifacts",
        "path": "generated/e2e",
        "if-no-files-found": "warn",
        "retention-days": "14",
    }
