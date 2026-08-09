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

  if [[ $status -eq 124 ]]; then
    echo "${description} timed out after ${GIT_COMMAND_TIMEOUT_SECONDS}s" >&2
  elif [[ $status -eq 137 ]]; then
    echo "${description} timed out or was killed after ${GIT_COMMAND_TIMEOUT_SECONDS}s (exit status 137)" >&2
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

destination_created=0
destination_identity=""

directory_identity() {
  # The builder image uses GNU coreutils, while local validation may run on
  # macOS. Keep the ownership check portable without weakening the atomic
  # `mkdir` boundary.
  stat -c '%d:%i' -- "$1" 2>/dev/null || stat -f '%d:%i' -- "$1" 2>/dev/null
}

cleanup_destination() {
  local status=$?
  trap - EXIT

  if (( status != 0 && destination_created == 1 )); then
    local current_identity=""
    current_identity=$(directory_identity "$destination" || true)
    if [[ -n $destination_identity && $current_identity == "$destination_identity" ]]; then
      if ! rm -rf -- "$destination"; then
        echo "failed to clean up source destination after error: $destination" >&2
      fi
    elif [[ -z $destination_identity && -d $destination ]]; then
      # If the identity lookup itself failed immediately after mkdir, only
      # remove an empty directory. Never recursively delete an unverified path.
      if ! rmdir -- "$destination"; then
        echo "source destination could not be safely cleaned up: $destination" >&2
      fi
    elif [[ -e $destination ]]; then
      echo "source destination changed during validation; refusing cleanup: $destination" >&2
    fi
  fi

  exit "$status"
}

# `mkdir` is the ownership boundary: it succeeds only when the destination was
# absent at that instant. This avoids deleting a path that pre-existed or was
# created by a concurrent caller if a later Git operation fails.
if mkdir -- "$destination"; then
  destination_created=1
else
  status=$?
  if [[ -e $destination ]]; then
    echo "source destination already exists: $destination" >&2
  else
    echo "failed to create source destination: $destination" >&2
  fi
  exit "$status"
fi
trap cleanup_destination EXIT
destination_identity=$(directory_identity "$destination")

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
from typing import BinaryIO

GIT_SUBPROCESS_TIMEOUT_SECONDS = 300.0
BATCH_READ_SIZE = 1024 * 1024
BATCH_HEADER_MAX_BYTES = 256

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


def read_blob_payload(stream: BinaryIO, size: int, object_id: bytes) -> bytes:
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        chunk = stream.read(min(remaining, BATCH_READ_SIZE))
        if not chunk:
            raise RuntimeError(
                f"git cat-file --batch returned {size - remaining} bytes for "
                f"{object_id.decode('ascii')} but declared {size}"
            )
        digest.update(chunk)
        remaining -= len(chunk)

    delimiter = stream.read(1)
    if delimiter != b"\n":
        raise RuntimeError(
            f"git cat-file --batch response for {object_id.decode('ascii')} "
            "is missing its record delimiter"
        )
    return digest.digest()


def read_blob_response(
    process: subprocess.Popen[bytes], object_id: bytes
) -> tuple[bytes, bytes]:
    stream = process.stdout
    if stream is None:
        raise RuntimeError("git cat-file --batch stdout is unavailable")

    header = stream.readline(BATCH_HEADER_MAX_BYTES)
    if not header.endswith(b"\n"):
        raise RuntimeError("git cat-file --batch returned an incomplete response header")
    fields = header[:-1].split(b" ")
    if len(fields) != 3:
        raise RuntimeError(
            f"malformed git cat-file --batch response header: {header.rstrip()!r}"
        )

    returned_id, object_type, size_raw = fields
    if returned_id != object_id:
        raise RuntimeError(
            "git cat-file --batch returned an unexpected object id: "
            f"expected={object_id.decode('ascii')} actual={returned_id!r}"
        )
    if object_type != b"blob":
        raise RuntimeError(
            f"git cat-file --batch returned unexpected object type: {object_type!r}"
        )
    if not size_raw or not size_raw.isdigit():
        raise RuntimeError(
            f"git cat-file --batch returned an invalid blob size: {size_raw!r}"
        )

    size = int(size_raw)
    digest = read_blob_payload(stream, size, object_id)
    return str(size).encode("ascii"), digest


def finish_batch(process: subprocess.Popen[bytes]) -> None:
    try:
        extra_stdout, stderr = process.communicate(
            timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise RuntimeError(
            "git cat-file --batch timed out after "
            f"{GIT_SUBPROCESS_TIMEOUT_SECONDS:g}s"
        ) from exc

    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(
            f"git cat-file --batch failed with exit status {process.returncode}{suffix}"
        )
    if extra_stdout:
        raise RuntimeError(
            "git cat-file --batch returned unexpected trailing output: "
            f"{extra_stdout[:80]!r}"
        )


def abort_batch(process: subprocess.Popen[bytes]) -> None:
    try:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=GIT_SUBPROCESS_TIMEOUT_SECONDS)
    except BaseException:
        # Preserve the protocol or digest error that caused the abort. The
        # outer `timeout` boundary still bounds the complete helper.
        try:
            process.kill()
        except BaseException:
            pass


blob_results: dict[bytes, tuple[bytes, bytes]] = {}
batch_process: subprocess.Popen[bytes] | None = None

try:
    for record in records.split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.split(b" ", 2)
        add_field(mode)
        add_field(object_type)
        add_field(path)
        if object_type == b"blob":
            blob_result = blob_results.get(object_id)
            if blob_result is None:
                if batch_process is None:
                    batch_process = subprocess.Popen(
                        ["git", "-C", str(root), "cat-file", "--batch"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                if batch_process.stdin is None:
                    raise RuntimeError("git cat-file --batch stdin is unavailable")
                batch_process.stdin.write(object_id + b"\n")
                batch_process.stdin.flush()
                blob_result = read_blob_response(batch_process, object_id)
                blob_results[object_id] = blob_result
            blob_length, blob_digest = blob_result
            add_field(blob_length)
            add_field(blob_digest)
        elif object_type == b"commit":
            add_field(object_id)
        else:
            raise RuntimeError(f"unsupported git tree object type: {object_type!r}")

    if batch_process is not None:
        finish_batch(batch_process)
        batch_process = None
except BaseException:
    if batch_process is not None:
        abort_batch(batch_process)
    raise

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
