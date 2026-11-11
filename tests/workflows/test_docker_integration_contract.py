from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

from tests.workflow_helpers import load_workflow

from ._helpers import SCRIPT_SUBPROCESS_TIMEOUT_SECONDS
from ._helpers import bash_executable_or_skip as _bash_executable_or_skip
from ._helpers import bash_path_or_skip as _bash_path_or_skip
from ._helpers import with_bash_env as _with_bash_env
from ._helpers import write_bash_env as _write_bash_env

RESOURCE_TEST = "tests/integration/test_alignment_streaming_resources.py"

DOCKER_TRIGGER_PATHS = (
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
  printf '%s\\n' "$@" >> "$FRAME_COMPARE_DOCKER_INVOCATION"
  mode="$FRAME_COMPARE_DOCKER_MODE"
  case "$mode" in
    fail) exit 17 ;;
    *)
      if printf '%s' "$*" | grep -q 'frame-compare-test'; then
        for container_command do :; done
        artifact_arg="$(grep 'FRAME_COMPARE_E2E_ARTIFACTS=' "$FRAME_COMPARE_DOCKER_INVOCATION" | tail -n 1 | cut -d= -f2-)"
        artifact_path="$PWD/$(printf '%s' "$artifact_arg" | sed 's#^/workspace/##')"
        mkdir -p "$artifact_path"
        printf 'current verifier artifacts\\n' > "$artifact_path/current.txt"
        cat <<'MARKERS'
DOCKER_PROOF cli=ok version_output=0.6.0
DOCKER_PROOF non_root=ok uid=1000
DOCKER_PROOF vapoursynth_import=ok version=R81 api=4.3
DOCKER_PROOF plugin_dir=/home/framecompare/.local/lib/python3.13/site-packages/vapoursynth
DOCKER_PROOF extra_plugin_path=/opt/vapoursynth-extra-plugins
DOCKER_PROOF core_plugins=lsmas,ffms2,vs_placebo
DOCKER_PROOF lsmash_works=ok release=1310.0.0.0 functions=LibavSMASHSource,LWLibavSource index=proof.ffindex
DOCKER_PROOF ffms2=ok release=5.0 runtime=5.0.0.0 functions=Source,index index=proof.ffindex
DOCKER_PROOF vs_placebo=ok version=2.0.4 functions=Tonemap output=RGBS
DOCKER_PROOF debian_ffmpeg=7:7.1.5-0+deb13u1
DOCKER_PROOF ffmpeg_version=ffmpeg version 7.1.5
DOCKER_PROOF ffprobe_version=ffprobe version 7.1.5
DOCKER_PROOF software_vulkan=ok
DOCKER_PROOF native_shared_libraries=ok
DOCKER_PROOF obuparse=ok linkage=shared soname=libobuparse.so.2 provenance=verified
DOCKER_PROOF source_provenance=ok strategy=git-commit-tracked-tree-sha256
DOCKER_PROOF doctor_json=ok
DOCKER_PROOF generated_fixture_matrix=ok fixtures=h264_limited
DOCKER_PROOF real_frame_render=ok frames=lwlibavsource,ffms2,placebo
MARKERS
        case "$mode" in
          missing) ;;
          unreadable) mkdir "$artifact_path/pytest.xml" ;;
          malformed) printf '<testsuites' > "$artifact_path/pytest.xml" ;;
          empty)
            printf '<testsuites><testsuite tests="0"/></testsuites>' > "$artifact_path/pytest.xml"
            ;;
          skip|xfail|xpass)
            # Run the emitted pytest command with local paths, a tiny supplied
            # fixture and a quiet summary. Keep the actual report/strict options.
            pytest_cache_dir="$artifact_path/cache"
            export pytest_cache_dir PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
            pytest_command="$(printf '%s\\n' "$container_command" | tail -n 1 |
              sed 's#^python -m pytest -n 10 --dist loadgroup -v #python3 -m pytest -qq #; s#--junitxml=/workspace/#--junitxml=#')"
            exec bash -c "$pytest_command"
            ;;
          success|late-tee)
            printf '<testsuites><testsuite tests="1"><testcase name="example"/></testsuite></testsuites>' > "$artifact_path/pytest.xml"
            ;;
          *) exit 99 ;;
        esac
        exit 0
      fi
      if printf '%s' "$*" | grep -q 'frame-compare-run'; then
        proof_dir="$(find -L "$PWD/generated" -maxdepth 1 -type d -name '.docker-integration-proof.*' | head -n 1)"
        run_dir="$proof_dir/run"
        mkdir -p "$run_dir/screenshots" "$run_dir/generated" "$proof_dir/cache/analysis"
        printf '<html></html>\\n' > "$run_dir/report.html"
        cat > "$run_dir/run_info.toml" <<'RECORD'
version = 2

[media_runtime.fingerprints]
full = "916760dd9ca2156521326493fbe92c395118d6f1ee36cc421d9bb9e2f66a8697"
RECORD
        cat > "$run_dir/run_result.toml" <<'RECORD'
version = 1
status = "completed"
report_path = "report.html"
screenshot_dir = "screenshots"
RECORD
        printf '\\211PNG\\r\\n\\032\\n\\000\\000\\000\\rIHDR\\000\\000\\000\\001\\000\\000\\000\\001' > "$run_dir/screenshots/frame.png"
        printf 'version = "1"\\n' > "$proof_dir/clip_probe.toml"
        printf 'version = "1"\\n' > "$run_dir/generated/clip_probe.toml"
        printf 'cache\\n' > "$proof_dir/cache/analysis/frames.compframes"
        printf 'DOCKER_PROOF production_tooling_absent=ok\\n'
        exit 0
      fi
      ;;
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
    repo_root: Path,
    tmp_path: Path,
    *,
    mode: str = "fail",
    extra_args: list[str] | None = None,
    seed_previous: bool = False,
    symlink_generated: bool = False,
) -> tuple[subprocess.CompletedProcess[str], str]:
    bash = _bash_executable_or_skip()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker")
    # The copied verifier must use the same installed project as this test process.
    python_wrapper = fake_bin / "python3"
    python_wrapper.write_text(
        f'#!/bin/sh\nexec {shlex.quote(_bash_path_or_skip(bash, Path(sys.executable)))} "$@"\n',
        encoding="utf-8",
    )
    python_wrapper.chmod(0o755)
    invocation = tmp_path / "docker-invocation.txt"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["FRAME_COMPARE_DOCKER_INVOCATION"] = str(invocation)
    environment["FRAME_COMPARE_DOCKER_MODE"] = mode
    # Run a copy from a temporary root so the script's generated output stays
    # isolated from the developer's checkout.
    script_root = tmp_path / "repo"
    (script_root / "tools").mkdir(parents=True)
    for name in ("verify_docker_integration.sh", "docker_runtime_smoke.py"):
        shutil.copy2(repo_root / "tools" / name, script_root / "tools")
    if mode in {"skip", "xfail", "xpass"}:
        fixture = {
            "skip": "pytest.skip('controlled skip')",
            "xfail": "pytest.xfail('controlled xfail')",
            "xpass": "assert True",
        }[mode]
        marker = "@pytest.mark.xfail(reason='controlled xpass')\n" if mode == "xpass" else ""
        (script_root / "test_outcome.py").write_text(
            f"import pytest\n\n{marker}def test_outcome():\n    {fixture}\n",
            encoding="utf-8",
        )
    if mode == "late-tee":
        bash_env = tmp_path / "tee.env"
        _write_bash_env(
            bash_env,
            """tee() {
  command tee "$@"
  if grep -Fq 'DOCKER_PROOF cli=ok' "$1"; then
    return 23
  fi
}""",
        )
        environment = _with_bash_env(environment, bash_env)
    if seed_previous:
        generated_root = (
            tmp_path / "foreign-generated" if symlink_generated else script_root / "generated"
        )
        previous_artifacts = generated_root / "e2e" / "previous"
        previous_artifacts.mkdir(parents=True)
        (previous_artifacts / "sentinel.txt").write_text("retain this run", encoding="utf-8")
        if symlink_generated:
            (script_root / "generated").symlink_to(generated_root, target_is_directory=True)
    result = subprocess.run(
        [bash, "tools/verify_docker_integration.sh", "--no-build", *(extra_args or [])],
        cwd=script_root,
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
    assert "docker integration tests failed (exit 17)" in result.stderr
    command = shlex.split(invocation.splitlines()[-1])
    environment = _docker_environment_args(invocation)
    assert ("FRAME_COMPARE_U4_MEDIA_FULL=1" in environment) is not explicit
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


@pytest.mark.parametrize(
    ("mode", "status", "diagnostic"),
    [
        ("missing", 3, "invalid pytest JUnit report"),
        ("unreadable", 3, "invalid pytest JUnit report"),
        ("malformed", 3, "invalid pytest JUnit report"),
        ("empty", 3, "expected a pytest suite with at least one test"),
        ("late-tee", 23, "tee exit 23"),
    ],
)
def test_verifier_rejects_invalid_or_incomplete_proof(
    repo_root: Path, tmp_path: Path, mode: str, status: int, diagnostic: str
) -> None:
    result, _ = _run_verifier(repo_root, tmp_path, mode=mode)

    assert result.returncode == status, result.stderr
    assert diagnostic in result.stderr
    assert "passed with zero skips" not in result.stdout


@pytest.mark.parametrize(
    ("mode", "status", "diagnostic"),
    [
        ("skip", 3, "zero non-passing outcomes"),
        ("xfail", 3, "zero non-passing outcomes"),
        ("xpass", 1, "docker integration tests failed (exit 1)"),
    ],
)
def test_verifier_rejects_skipped_xfailed_and_xpassed_tests(
    repo_root: Path, tmp_path: Path, mode: str, status: int, diagnostic: str
) -> None:
    result, _ = _run_verifier(
        repo_root, tmp_path, mode=mode, extra_args=["--pytest-path", "test_outcome.py"]
    )

    assert result.returncode == status, result.stdout + result.stderr
    assert diagnostic in result.stderr
    assert "passed with zero skips" not in result.stdout


def test_verifier_passes_host_user_media_environment_and_artifacts(
    repo_root: Path, tmp_path: Path
) -> None:
    result, invocation = _run_verifier(repo_root, tmp_path)

    assert result.returncode == 17
    assert (
        'python /home/framecompare/frame-compare/tools/docker_runtime_smoke.py "$media_path" "$doctor_path" "$ffindex_path"'
        in invocation
    )
    environment_args = set(_docker_environment_args(invocation))
    assert {
        "HOME=/tmp/framecompare-home",
        "PYTHONUSERBASE=/home/framecompare/.local",
        "FRAME_COMPARE_E2E_REQUIRE_MEDIA=1",
    } <= environment_args
    assert any(
        value.startswith("FRAME_COMPARE_E2E_ARTIFACTS=/workspace/generated/e2e/run.")
        for value in environment_args
    )
    args = _docker_invocation_args(invocation)
    user_index = args.index("--user")
    uid_gid = args[user_index + 1].split(":")
    assert len(uid_gid) == 2
    assert all(part.isdigit() for part in uid_gid)


@pytest.mark.parametrize("mode,expected_returncode", [("fail", 17), ("success", 0)])
@pytest.mark.parametrize("symlink_generated", [False, True], ids=["ordinary-root", "linked-root"])
def test_verifier_preserves_previous_artifacts_and_owns_fresh_invocation_directory(
    repo_root: Path,
    tmp_path: Path,
    mode: str,
    expected_returncode: int,
    symlink_generated: bool,
) -> None:
    result, invocation = _run_verifier(
        repo_root,
        tmp_path,
        mode=mode,
        seed_previous=True,
        symlink_generated=symlink_generated,
    )

    assert result.returncode == expected_returncode, result.stderr
    generated_root = (
        tmp_path / "foreign-generated" if symlink_generated else tmp_path / "repo/generated"
    )
    sentinel = generated_root / "e2e/previous/sentinel.txt"
    assert sentinel.read_text(encoding="utf-8") == "retain this run"

    artifact_values = [
        line.split("=", 1)[1]
        for line in invocation.splitlines()
        if line.startswith("FRAME_COMPARE_E2E_ARTIFACTS=")
    ]
    assert len(artifact_values) == 1
    artifact_path = tmp_path / "repo" / Path(artifact_values[0]).relative_to("/workspace")
    assert artifact_path.parent == tmp_path / "repo/generated/e2e"
    assert artifact_path.name != "previous"
    assert artifact_path.is_dir()
    assert result.stdout.count("Docker E2E artifacts: generated/e2e/") == 1
    if mode == "success":
        assert (artifact_path / "current.txt").read_text(encoding="utf-8") == (
            "current verifier artifacts\n"
        )
        assert (artifact_path / "pytest.xml").is_file()


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


@pytest.mark.parametrize(
    ("path", "selected"),
    [
        ("tools/checkout_source_commit.sh", True),
        ("tools/docker_runtime_smoke.py", True),
        (".dockerignore", True),
        ("docs/current-architecture.md", False),
        ("README.md", True),
        ("LICENSE", True),
    ],
)
def test_workflow_path_filter_has_positive_and_negative_controls(
    repo_root: Path, path: str, selected: bool
) -> None:
    workflow_paths = _pull_request_paths(repo_root)

    assert _path_matches_workflow(path, workflow_paths) is selected


def test_dockerignore_excludes_local_residue_without_excluding_image_inputs(
    repo_root: Path,
) -> None:
    patterns = {
        line.strip()
        for line in (repo_root / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {
        ".tmp",
        ".codex",
        ".claude",
        ".handoff",
        ".codanna",
        ".desloppify",
        ".agent",
        ".hypothesis",
        ".uv_cache",
        ".portable_cache",
        "site",
        "tools/old_*.py",
    } <= patterns

    image_inputs = (
        "pyproject.toml",
        "uv.lock",
        "src/frame_compare/cli/entry.py",
        "tests/workflows/test_docker_integration_contract.py",
        "tools/checkout_source_commit.sh",
        "tools/verify_docker_integration.sh",
        "tools/docker_runtime_smoke.py",
        "Dockerfile",
    )
    assert not any(
        fnmatchcase(path, pattern) or fnmatchcase(Path(path).name, pattern)
        for path in image_inputs
        for pattern in patterns
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
        "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9"
    )
    assert upload_step["with"] == {
        "name": "docker-e2e-artifacts",
        "path": "generated/e2e",
        "if-no-files-found": "warn",
        "retention-days": "14",
    }
