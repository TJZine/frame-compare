from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def _resolve_target_mode(path: Path) -> int:
    """Match normal write semantics for new files and preserve existing file mode."""
    if path.exists():
        return stat.S_IMODE(path.stat().st_mode)

    current_umask = os.umask(0)
    os.umask(current_umask)
    return 0o666 & ~current_umask


def write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Atomically write text content to a file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, _resolve_target_mode(path))
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_bytes_atomic(path: Path, content: bytes) -> None:
    """Atomically write byte content to a file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, _resolve_target_mode(path))
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
