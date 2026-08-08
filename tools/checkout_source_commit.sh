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

git init --quiet "$destination"
git -C "$destination" remote add origin "$repository_url"
git -C "$destination" fetch --quiet --depth=1 --no-tags origin "$expected_commit"
git -C "$destination" -c advice.detachedHead=false checkout --quiet --detach FETCH_HEAD

actual_commit=$(git -C "$destination" rev-parse HEAD)
[[ $actual_commit == "$expected_commit" ]] || {
  echo "source commit mismatch: expected=$expected_commit actual=$actual_commit" >&2
  exit 1
}

actual_tree_sha256=$(python - "$destination" <<'PY'
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
records = subprocess.check_output(
    ["git", "-C", str(root), "ls-tree", "-rz", "--full-tree", "HEAD"]
)
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
        content = subprocess.check_output(
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
