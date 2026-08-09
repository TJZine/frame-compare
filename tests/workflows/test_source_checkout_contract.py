"""Tests for the bounded source checkout build helper."""

from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
from pathlib import Path

import pytest


def _embedded_python_source(script: str) -> str:
    return script.split("python - \"$destination\" <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]


def _list_string_constants(node: ast.AST) -> set[str]:
    if not isinstance(node, ast.List):
        return set()
    return {
        element.value
        for element in node.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    }


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


def _run_checkout(
    repo_root: Path,
    script: Path,
    timeout_command: Path,
    repository: Path,
    commit: str,
    tree_digest: str,
    destination: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PATH"] = f"{timeout_command.parent}{os.pathsep}{environment['PATH']}"
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

    assert 'run_bounded "source-tree digest" python - "$destination"' in script

    shell_source = script.split("actual_tree_sha256=$(run_bounded", 1)[0]
    assert not re.search(r"^\s*git(?:\s|-C)", shell_source, re.MULTILINE)

    module = ast.parse(_embedded_python_source(script))
    calls = [node for node in ast.walk(module) if isinstance(node, ast.Call)]
    check_output_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute) and node.func.attr == "check_output"
    ]
    assert len(check_output_calls) == 1
    timeout_keywords = [
        keyword for keyword in check_output_calls[0].keywords if keyword.arg == "timeout"
    ]
    assert len(timeout_keywords) == 1
    assert isinstance(timeout_keywords[0].value, ast.Name)
    assert timeout_keywords[0].value.id == "GIT_SUBPROCESS_TIMEOUT_SECONDS"

    git_output_ls_tree_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "git_output"
        and node.args
        and {"ls-tree", "-rz", "--full-tree"} <= _list_string_constants(node.args[0])
    ]
    assert len(git_output_ls_tree_calls) == 1

    popen_batch_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Attribute)
        and node.func.attr == "Popen"
        and node.args
        and {"cat-file", "--batch"} <= _list_string_constants(node.args[0])
    ]
    assert len(popen_batch_calls) == 1
    assert any(
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "communicate"
        and any(keyword.arg == "timeout" for keyword in node.keywords)
        for node in calls
    )


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
