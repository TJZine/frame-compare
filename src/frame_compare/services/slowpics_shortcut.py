"""Filesystem shortcut creation for slow.pics comparison URLs."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from frame_compare.errors import PathEscapesRootError
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.paths import require_managed_descendant
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.utils.types import WorkspacePaths

_WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_UNSAFE_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SlowpicsShortcutResult:
    """Result of attempting to create a slow.pics URL shortcut."""

    success: bool
    path: Path | None = None
    warning: RunWarning | None = None


def create_slowpics_url_shortcut(
    *,
    workspace: WorkspacePaths,
    slowpics_url: str,
    collection_title: str,
) -> SlowpicsShortcutResult:
    """Create a deterministic Windows InternetShortcut-style file."""
    raise_if_cancelling()
    try:
        output_dir = _select_shortcut_directory(workspace)
    except (OSError, RuntimeError, PathEscapesRootError) as exc:
        return SlowpicsShortcutResult(
            success=False,
            warning=RunWarning(
                "slow.pics",
                "warning",
                "slow.pics shortcut:",
                f"failed to resolve URL shortcut directory: {exc}",
            ),
        )
    if output_dir is None:
        return SlowpicsShortcutResult(
            success=False,
            warning=RunWarning(
                "slow.pics",
                "warning",
                "slow.pics shortcut:",
                "no reserved run directory is available",
            ),
        )

    shortcut_path = output_dir / _shortcut_filename(
        collection_title=collection_title,
        slowpics_url=slowpics_url,
    )
    content = f"[InternetShortcut]\nURL={slowpics_url}\n"
    try:
        write_text_atomic(shortcut_path, content, publish_guard=raise_if_cancelling)
    except OSError as exc:
        return SlowpicsShortcutResult(
            success=False,
            path=shortcut_path,
            warning=RunWarning(
                "slow.pics",
                "warning",
                "slow.pics shortcut:",
                f"failed to write URL shortcut {shortcut_path}: {exc}",
            ),
        )

    return SlowpicsShortcutResult(success=True, path=shortcut_path)


def _select_shortcut_directory(workspace: WorkspacePaths) -> Path | None:
    if workspace.run_dir is None:
        return None
    resolved_run_dir = require_managed_descendant(workspace.generated_root, workspace.run_dir)
    resolved_generated_root = workspace.generated_root.resolve()
    if (
        workspace.run_dir.is_symlink()
        or workspace.run_dir.is_junction()
        or resolved_run_dir.parent != resolved_generated_root
    ):
        return None
    return resolved_run_dir


def _shortcut_filename(
    *,
    collection_title: str,
    slowpics_url: str,
) -> str:
    stem = _safe_filename_stem(collection_title)
    if stem is not None:
        return f"{stem}.url"
    return f"{_fallback_stem_from_url(slowpics_url)}.url"


def _safe_filename_stem(value: str) -> str | None:
    stem = _UNSAFE_FILENAME_CHARS_RE.sub(" ", value)
    stem = _WHITESPACE_RE.sub(" ", stem).strip(" .")
    if not stem:
        return None
    if stem.upper() in _WINDOWS_RESERVED_FILENAMES:
        stem = f"{stem}-slowpics"
    return stem


def _fallback_stem_from_url(slowpics_url: str) -> str:
    parsed = urlparse(slowpics_url)
    key = Path(parsed.path).name.strip()
    stem = _safe_filename_stem(key)
    if stem is not None:
        return stem
    return hashlib.sha256(slowpics_url.encode("utf-8")).hexdigest()[:12]
