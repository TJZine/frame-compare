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
[[ ! -e $destination && ! -L $destination ]] || {
  echo "source destination already exists: $destination" >&2
  exit 2
}

destination_for_staging=$destination
while [[ $destination_for_staging == */ && $destination_for_staging != "/" ]]; do
  destination_for_staging=${destination_for_staging%/}
done
destination_parent=${destination_for_staging%/*}
if [[ $destination_parent == "$destination_for_staging" ]]; then
  destination_parent=.
fi
if [[ -z $destination_parent ]]; then
  if [[ $destination_for_staging == /* ]]; then
    destination_parent=/
  else
    destination_parent=.
  fi
fi
destination_name=${destination_for_staging##*/}
if [[ -z $destination_name ]]; then
  echo "invalid source destination: $destination" >&2
  exit 2
fi

# Keep all mutable checkout state in a private sibling. The final destination
# stays absent until every Git, digest, and .git-removal step has succeeded.
# Sibling placement keeps publication on one filesystem, so the no-clobber
# rename below is atomic on both the Debian builder and macOS validation hosts.
staging_directory=""
if [[ $destination_parent == "/" ]]; then
  staging_template="/.${destination_name}.staging.XXXXXXXX"
else
  staging_template="${destination_parent}/.${destination_name}.staging.XXXXXXXX"
fi
if staging_directory=$(mktemp -d -- "$staging_template"); then
  :
else
  status=$?
  echo "failed to create private source staging directory near destination: $destination" >&2
  exit "$status"
fi

cleanup_staging() {
  local status=$?
  trap - EXIT

  if (( status != 0 )) && [[ -n $staging_directory ]]; then
    # Only this unpredictable, script-created path is recursively removed.
    # The caller-controlled final destination is never cleanup input.
    if ! rm -rf -- "$staging_directory"; then
      echo "failed to clean up private source staging directory after error: $destination" >&2
    fi
  fi

  exit "$status"
}
trap cleanup_staging EXIT

publish_staging_directory() {
  python - "$1" "$2" <<'PY'
from __future__ import annotations

import ctypes
import errno
import os
import sys


source = os.fsencode(sys.argv[1])
destination = os.fsencode(sys.argv[2])
try:
    libc = ctypes.CDLL(None, use_errno=True)
except OSError as exc:
    print(f"failed to publish source destination {sys.argv[2]}: {exc}", file=sys.stderr)
    raise SystemExit(1)

try:
    if sys.platform == "darwin":
        # macOS exposes the atomic no-replace primitive as renameatx_np with
        # RENAME_EXCL. AT_FDCWD is -2 on Darwin.
        rename_no_replace = libc.renameatx_np
        rename_no_replace.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_no_replace.restype = ctypes.c_int
        old_directory_fd = new_directory_fd = -2
        no_replace_flag = 0x00000004
    elif sys.platform == "linux":
        # Debian's glibc provides renameat2 with RENAME_NOREPLACE. AT_FDCWD is
        # -100 on Linux. Fail closed rather than falling back to a check-then-move
        # sequence if a runtime libc does not expose the primitive.
        rename_no_replace = libc.renameat2
        rename_no_replace.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_no_replace.restype = ctypes.c_int
        old_directory_fd = new_directory_fd = -100
        no_replace_flag = 0x00000001
    else:
        raise RuntimeError(
            f"atomic no-clobber publication is unsupported on {sys.platform}"
        )
except (AttributeError, OSError, RuntimeError) as exc:
    print(f"failed to publish source destination {sys.argv[2]}: {exc}", file=sys.stderr)
    raise SystemExit(1)

if rename_no_replace(
    old_directory_fd,
    source,
    new_directory_fd,
    destination,
    no_replace_flag,
) != 0:
    error_number = ctypes.get_errno()
    if error_number in (errno.EEXIST, errno.ENOTEMPTY):
        print(f"source destination already exists: {sys.argv[2]}", file=sys.stderr)
        raise SystemExit(2)
    detail = os.strerror(error_number)
    print(
        f"failed to publish source destination {sys.argv[2]}: {detail}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
}

run_bounded "git init" git init --quiet "$staging_directory"
run_bounded "git remote add" git -C "$staging_directory" remote add origin "$repository_url"
run_bounded "git fetch" git -C "$staging_directory" fetch --quiet --depth=1 --no-tags origin "$expected_commit"
run_bounded "git checkout" git -C "$staging_directory" -c advice.detachedHead=false checkout --quiet --detach FETCH_HEAD

actual_commit=$(run_bounded "git rev-parse" git -C "$staging_directory" rev-parse HEAD)
[[ $actual_commit == "$expected_commit" ]] || {
  echo "source commit mismatch: expected=$expected_commit actual=$actual_commit" >&2
  exit 1
}

actual_tree_sha256=$(run_bounded "source-tree digest" python - "$staging_directory" <<'PY'
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

rm -rf -- "$staging_directory/.git"
if publish_staging_directory "$staging_directory" "$destination"; then
  # The no-replace rename consumed the private staging directory. Clearing the
  # cleanup input prevents a later shell failure from touching the final tree.
  staging_directory=""
else
  status=$?
  exit "$status"
fi
printf 'verified_source_tree=%s commit=%s sha256=%s\n' \
  "$repository_url" "$actual_commit" "$actual_tree_sha256"
