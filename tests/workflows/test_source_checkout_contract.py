"""Tests for the bounded source checkout build helper."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_POSIX_PROCESS_PROOF = pytest.mark.skipif(
    os.name == "nt",
    reason="source checkout process proof requires POSIX process and rename semantics",
)

_GIT_REPOSITORY_ENVIRONMENT = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE",
    "GIT_PREFIX",
    "GIT_SHALLOW_FILE",
    "GIT_COMMON_DIR",
)


@pytest.fixture(autouse=True)
def _isolate_git_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in _GIT_REPOSITORY_ENVIRONMENT:
        monkeypatch.delenv(variable, raising=False)

    global_config = tmp_path / "gitconfig-global"
    system_config = tmp_path / "gitconfig-system"
    global_config.touch()
    system_config.touch()
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system_config))


def _embedded_python_source(script: str) -> str:
    return script.split("python - \"$staging_directory\" <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 10.0,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        timeout=timeout,
    )


def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return _run(["git", "-C", str(cwd), *arguments], timeout=10.0)


def _tree_digest(repo: Path) -> str:
    records = _git(repo, "ls-tree", "-rz", "--full-tree", "HEAD").stdout
    result = hashlib.sha256()

    def add_field(value: bytes) -> None:
        result.update(len(value).to_bytes(8, "big"))
        result.update(value)

    for record in records.split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.split(b" ", 2)
        add_field(mode)
        add_field(object_type)
        add_field(path)
        if object_type == b"blob":
            content = _git(repo, "cat-file", "blob", object_id.decode("ascii")).stdout
            add_field(str(len(content)).encode("ascii"))
            add_field(hashlib.sha256(content).digest())
        elif object_type == b"commit":
            add_field(object_id)
        else:
            raise AssertionError(f"unexpected object type in test repository: {object_type!r}")

    return result.hexdigest()


def _create_source_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "source-repo"
    repo.mkdir()
    _run(["git", "init", "-q", str(repo)])
    _git(repo, "config", "user.email", "frame-compare-tests@example.invalid")
    _git(repo, "config", "user.name", "Frame Compare Tests")

    # Two paths intentionally point to the same blob so the batch client must
    # reuse the cached response without changing record order or digest fields.
    (repo / "first.txt").write_bytes(b"duplicate blob\n")
    (repo / "second.txt").write_bytes(b"duplicate blob\n")
    (repo / "nested").mkdir()
    (repo / "nested" / "payload.bin").write_bytes(bytes(range(256)) * 32)

    submodule_repo = tmp_path / "submodule-repo"
    submodule_repo.mkdir()
    _run(["git", "init", "-q", str(submodule_repo)])
    _git(submodule_repo, "config", "user.email", "frame-compare-tests@example.invalid")
    _git(submodule_repo, "config", "user.name", "Frame Compare Tests")
    (submodule_repo / "tracked.txt").write_bytes(b"gitlink target\n")
    _run(["git", "-C", str(submodule_repo), "add", "."])
    _run(["git", "-C", str(submodule_repo), "commit", "-qm", "gitlink target"])
    submodule_commit = (
        _run(["git", "-C", str(submodule_repo), "rev-parse", "HEAD"]).stdout.strip().decode("ascii")
    )

    _run(
        [
            "git",
            "-C",
            str(repo),
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{submodule_commit},external-submodule",
        ]
    )
    _run(["git", "-C", str(repo), "add", "."])
    _run(["git", "-C", str(repo), "commit", "-qm", "source fixture"])
    commit = _git(repo, "rev-parse", "HEAD").stdout.strip().decode("ascii")
    return repo, commit, _tree_digest(repo)


def _timeout_shim(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "timeout"
    shim.write_text(
        "#!/bin/sh\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  case "$1" in\n'
        "    --signal=*|--kill-after=*) shift ;;\n"
        "    *) break ;;\n"
        "  esac\n"
        "done\n"
        "shift\n"
        'exec "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim


def _race_git_shim(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    shim = bin_dir / "git"
    real_git = shutil.which("git")
    assert real_git is not None
    shim.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-C" ] && [ "$3" = "fetch" ]; then\n'
        '  mkdir "$FC_RACE_DESTINATION"\n'
        '  printf "caller-owned\\n" > "$FC_RACE_DESTINATION/marker"\n'
        "fi\n"
        'exec "$FC_REAL_GIT" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim


def _recording_mktemp_shim(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    shim = bin_dir / "mktemp"
    shim.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$3" > "$FC_MKTEMP_RECORD"\nexit 1\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim


def _run_checkout(
    repo_root: Path,
    script: Path,
    timeout_command: Path,
    repository: Path,
    commit: str,
    tree_digest: str,
    destination: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PATH"] = f"{timeout_command.parent}{os.pathsep}{environment['PATH']}"
    if extra_env is not None:
        environment.update(extra_env)
    return subprocess.run(
        [
            "bash",
            str(script),
            str(repository),
            commit,
            tree_digest,
            str(destination),
        ],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30.0,
    )


def test_source_checkout_bounds_every_git_boundary(repo_root: Path) -> None:
    script = (repo_root / "tools/checkout_source_commit.sh").read_text(encoding="utf-8")

    assert "readonly GIT_COMMAND_TIMEOUT_SECONDS=300" in script
    assert "readonly GIT_COMMAND_KILL_AFTER_SECONDS=10" in script
    assert 'timed out after ${GIT_COMMAND_TIMEOUT_SECONDS}s"' in script
    assert (
        "timed out or was killed after ${GIT_COMMAND_TIMEOUT_SECONDS}s (exit status 137)" in script
    )
    assert (
        '    --kill-after="${GIT_COMMAND_KILL_AFTER_SECONDS}s" \\\n'
        '    "${GIT_COMMAND_TIMEOUT_SECONDS}s" \\\n'
        '    "$@"'
    ) in script

    for description in (
        "git init",
        "git remote add",
        "git fetch",
        "git checkout",
        "git rev-parse",
    ):
        assert re.search(rf'run_bounded "{re.escape(description)}" git(?: |$)', script)

    assert 'run_bounded "source-tree digest" python - "$staging_directory"' in script
    assert 'rm -rf -- "$destination"' not in script
    assert "renameat2" in script
    assert "renameatx_np" in script

    shell_source = script.split("actual_tree_sha256=$(run_bounded", 1)[0]
    assert not re.search(r"^\s*git(?:\s|-C)", shell_source, re.MULTILINE)

    embedded_source = _embedded_python_source(script)
    assert (
        'records = git_output(["git", "-C", str(root), "ls-tree", "-rz", "--full-tree", "HEAD"])'
        in embedded_source
    )
    assert (
        "subprocess.check_output(command, timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS)"
        in embedded_source
    )
    assert embedded_source.count('"cat-file", "--batch"') == 1
    assert re.search(
        r"process\.communicate\(\s*timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS", embedded_source
    )


@_POSIX_PROCESS_PROOF
def test_source_checkout_uses_root_as_absolute_staging_parent(
    repo_root: Path, tmp_path: Path
) -> None:
    timeout_shim = _timeout_shim(tmp_path)
    _recording_mktemp_shim(tmp_path)
    record_path = tmp_path / "mktemp-template"
    destination = Path("/") / f"frame-compare-root-edge-{tmp_path.name}"
    assert not destination.exists()

    completed = _run_checkout(
        repo_root,
        repo_root / "tools/checkout_source_commit.sh",
        timeout_shim,
        Path("/nonexistent-source-repository"),
        "0" * 40,
        "0" * 64,
        destination,
        extra_env={"FC_MKTEMP_RECORD": str(record_path)},
    )

    assert completed.returncode == 1
    assert record_path.read_text(encoding="utf-8") == (f"/.{destination.name}.staging.XXXXXXXX\n")


@_POSIX_PROCESS_PROOF
def test_source_checkout_verifies_digest_and_preserves_commit_records(
    repo_root: Path, tmp_path: Path
) -> None:
    repository, commit, tree_digest = _create_source_repo(tmp_path)
    destination = tmp_path / "verified-source"
    completed = _run_checkout(
        repo_root,
        repo_root / "tools/checkout_source_commit.sh",
        _timeout_shim(tmp_path),
        repository,
        commit,
        tree_digest,
        destination,
    )

    assert completed.returncode == 0, completed.stderr
    assert f"commit={commit}" in completed.stdout
    assert f"sha256={tree_digest}" in completed.stdout
    assert destination.is_dir()
    assert not (destination / ".git").exists()
    assert (destination / "first.txt").read_bytes() == b"duplicate blob\n"
    assert (destination / "second.txt").read_bytes() == b"duplicate blob\n"
    assert (destination / "nested" / "payload.bin").stat().st_size == 8192


@pytest.mark.parametrize("failure", ["fetch", "tree"])
@_POSIX_PROCESS_PROOF
def test_source_checkout_cleans_owned_destination_on_failure(
    repo_root: Path, tmp_path: Path, failure: str
) -> None:
    repository, commit, _tree_digest = _create_source_repo(tmp_path)
    destination = tmp_path / f"failed-{failure}"
    requested_commit = "0" * 40 if failure == "fetch" else commit
    requested_tree = "0" * 64 if failure == "fetch" else "f" * 64

    completed = _run_checkout(
        repo_root,
        repo_root / "tools/checkout_source_commit.sh",
        _timeout_shim(tmp_path),
        repository,
        requested_commit,
        requested_tree,
        destination,
    )

    assert completed.returncode != 0
    assert not destination.exists()
    if failure == "tree":
        assert f"source-tree mismatch: expected={requested_tree}" in completed.stderr
    else:
        assert "git fetch failed" in completed.stderr


@_POSIX_PROCESS_PROOF
def test_source_checkout_refuses_pre_existing_destination(repo_root: Path, tmp_path: Path) -> None:
    repository, commit, tree_digest = _create_source_repo(tmp_path)
    destination = tmp_path / "pre-existing"
    destination.mkdir()
    marker = destination / "preserve-me.txt"
    marker.write_text("caller-owned\n", encoding="utf-8")

    completed = _run_checkout(
        repo_root,
        repo_root / "tools/checkout_source_commit.sh",
        _timeout_shim(tmp_path),
        repository,
        commit,
        tree_digest,
        destination,
    )

    assert completed.returncode == 2
    assert completed.stderr == f"source destination already exists: {destination}\n"
    assert marker.read_text(encoding="utf-8") == "caller-owned\n"


@_POSIX_PROCESS_PROOF
def test_source_checkout_never_cleans_replaced_final_destination(
    repo_root: Path, tmp_path: Path
) -> None:
    repository, commit, _tree_digest = _create_source_repo(tmp_path)
    destination = tmp_path / "replaced-destination"
    timeout_shim = _timeout_shim(tmp_path)
    _race_git_shim(tmp_path)
    real_git = shutil.which("git")
    assert real_git is not None

    completed = _run_checkout(
        repo_root,
        repo_root / "tools/checkout_source_commit.sh",
        timeout_shim,
        repository,
        commit,
        "f" * 64,
        destination,
        extra_env={
            "FC_RACE_DESTINATION": str(destination),
            "FC_REAL_GIT": real_git,
        },
    )

    assert completed.returncode != 0
    assert destination.is_dir()
    assert (destination / "marker").read_text(encoding="utf-8") == "caller-owned\n"
    assert not list(tmp_path.glob(".replaced-destination.staging.*"))


@_POSIX_PROCESS_PROOF
def test_source_checkout_publishes_without_clobbering_late_destination(
    repo_root: Path, tmp_path: Path
) -> None:
    repository, commit, tree_digest = _create_source_repo(tmp_path)
    destination = tmp_path / "late-destination"
    timeout_shim = _timeout_shim(tmp_path)
    _race_git_shim(tmp_path)
    real_git = shutil.which("git")
    assert real_git is not None

    completed = _run_checkout(
        repo_root,
        repo_root / "tools/checkout_source_commit.sh",
        timeout_shim,
        repository,
        commit,
        tree_digest,
        destination,
        extra_env={
            "FC_RACE_DESTINATION": str(destination),
            "FC_REAL_GIT": real_git,
        },
    )

    assert completed.returncode == 2
    assert completed.stderr == f"source destination already exists: {destination}\n"
    assert (destination / "marker").read_text(encoding="utf-8") == "caller-owned\n"
    assert not list(tmp_path.glob(".late-destination.staging.*"))
