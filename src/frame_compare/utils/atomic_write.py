from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

_TEMP_NAME_ATTEMPTS = 100


def _resolve_existing_target_mode(path: Path) -> int | None:
    """Return an existing target mode, or None so new files keep normal create semantics."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        return None


def _open_temp_for_atomic_write(path: Path) -> tuple[int, str]:
    """Create a sibling temp file using normal file-creation permissions."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    collisions = 0
    for _ in range(_TEMP_NAME_ATTEMPTS):
        tmp_path = path.parent / f".{path.name}.{secrets.token_hex(8)}"
        try:
            return os.open(tmp_path, flags, 0o666), str(tmp_path)
        except FileExistsError:
            collisions += 1

    raise FileExistsError(
        f"could not create a unique temporary file for {path} after {collisions} collisions"
    )


def _preserve_existing_target_mode(path: Path, tmp_name: str) -> None:
    target_mode = _resolve_existing_target_mode(path)
    if target_mode is not None:
        os.chmod(tmp_name, target_mode)


def _cleanup_temp_after_failure(tmp_name: str, original_error: BaseException) -> None:
    tmp_path = Path(tmp_name)
    try:
        tmp_path.unlink(missing_ok=True)
    except OSError as cleanup_error:
        original_error.add_note(
            f"Could not remove temporary file {tmp_path} after atomic write failure: "
            f"{cleanup_error}"
        )


def write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Atomically write text content to a file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = _open_temp_for_atomic_write(path)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _preserve_existing_target_mode(path, tmp_name)
        os.replace(tmp_name, path)
    except Exception as original_error:
        _cleanup_temp_after_failure(tmp_name, original_error)
        raise


def write_bytes_atomic(path: Path, content: bytes) -> None:
    """Atomically write byte content to a file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = _open_temp_for_atomic_write(path)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _preserve_existing_target_mode(path, tmp_name)
        os.replace(tmp_name, path)
    except Exception as original_error:
        _cleanup_temp_after_failure(tmp_name, original_error)
        raise
