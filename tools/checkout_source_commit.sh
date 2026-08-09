#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: checkout_source_commit.sh <repository-url> <40-char-commit> <tree-sha256> <destination>" >&2
  exit 2
fi

repository_url=$1
expected_commit=$2
expected_tree_sha256=$3
destination=$4

# GNU coreutils `timeout` is part of the Debian builder image. Keep every
# network/local Git operation and the complete tree digest bounded so a source
# checkout cannot hang a repeated Docker build indefinitely.
readonly GIT_COMMAND_TIMEOUT_SECONDS=300
readonly GIT_COMMAND_KILL_AFTER_SECONDS=10

run_bounded() {
  local description=$1
  shift

  local status
  if timeout \
    --signal=TERM \
    --kill-after="${GIT_COMMAND_KILL_AFTER_SECONDS}s" \
    "${GIT_COMMAND_TIMEOUT_SECONDS}s" \
    "$@"
  then
    return 0
  else
    status=$?
  fi

  if [[ $status -eq 124 || $status -eq 137 ]]; then
    echo "${description} timed out after ${GIT_COMMAND_TIMEOUT_SECONDS}s" >&2
  else
    echo "${description} failed with exit status ${status}" >&2
  fi
  return "$status"
}

[[ $expected_commit =~ ^[0-9a-f]{40}$ ]] || {
  echo "invalid source commit: $expected_commit" >&2
  exit 2
}
[[ $expected_tree_sha256 =~ ^[0-9a-f]{64}$ ]] || {
  echo "invalid source-tree SHA-256: $expected_tree_sha256" >&2
  exit 2
}
[[ ! -e $destination ]] || {
  echo "source destination already exists: $destination" >&2
  exit 2
}

run_bounded "git init" git init --quiet "$destination"
run_bounded "git remote add" git -C "$destination" remote add origin "$repository_url"
run_bounded "git fetch" git -C "$destination" fetch --quiet --depth=1 --no-tags origin "$expected_commit"
run_bounded "git checkout" git -C "$destination" -c advice.detachedHead=false checkout --quiet --detach FETCH_HEAD

actual_commit=$(run_bounded "git rev-parse" git -C "$destination" rev-parse HEAD)
[[ $actual_commit == "$expected_commit" ]] || {
  echo "source commit mismatch: expected=$expected_commit actual=$actual_commit" >&2
  exit 1
}

actual_tree_sha256=$(run_bounded "source-tree digest" python - "$destination" <<'PY'
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

GIT_SUBPROCESS_TIMEOUT_SECONDS = 300.0

root = Path(sys.argv[1])


def git_output(command: list[str]) -> bytes:
    try:
        return subprocess.check_output(command, timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        command_text = " ".join(command)
        raise RuntimeError(
            f"{command_text} timed out after {GIT_SUBPROCESS_TIMEOUT_SECONDS:g}s"
        ) from exc


records = git_output(["git", "-C", str(root), "ls-tree", "-rz", "--full-tree", "HEAD"])
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
        content = git_output(
            ["git", "-C", str(root), "cat-file", "blob", object_id.decode("ascii")]
        )
        add_field(str(len(content)).encode("ascii"))
        add_field(hashlib.sha256(content).digest())
    elif object_type == b"commit":
        add_field(object_id)
    else:
        raise RuntimeError(f"unsupported git tree object type: {object_type!r}")

print(result.hexdigest())
PY
)

[[ $actual_tree_sha256 == "$expected_tree_sha256" ]] || {
  echo "source-tree mismatch: expected=$expected_tree_sha256 actual=$actual_tree_sha256" >&2
  exit 1
}

rm -rf "$destination/.git"
printf 'verified_source_tree=%s commit=%s sha256=%s\n' \
  "$repository_url" "$actual_commit" "$actual_tree_sha256"
