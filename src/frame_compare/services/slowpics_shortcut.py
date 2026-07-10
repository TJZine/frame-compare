"""Filesystem shortcut creation for slow.pics comparison URLs."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from frame_compare.utils.atomic_write import write_text_atomic
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

type ShortcutTextWriter = Callable[[Path, str], None]


@dataclass(frozen=True)
class SlowpicsShortcutResult:
    """Result of attempting to create a slow.pics URL shortcut."""

    success: bool
    path: Path | None = None
    warning: str | None = None


def create_slowpics_url_shortcut(
    *,
    workspace: WorkspacePaths,
    slowpics_url: str,
    collection_title: str,
    text_writer: ShortcutTextWriter = write_text_atomic,
) -> SlowpicsShortcutResult:
    """Create a deterministic Windows InternetShortcut-style file."""
    try:
        output_dir = _select_shortcut_directory(workspace)
    except (OSError, RuntimeError) as exc:
        return SlowpicsShortcutResult(
            success=False,
            warning=f"slow.pics shortcut: failed to resolve URL shortcut directory: {exc}",
        )
    if output_dir is None:
        return SlowpicsShortcutResult(
            success=False,
            warning=(
                "slow.pics shortcut: could not choose a safe output directory from "
                "the run, screenshots, and generated paths"
            ),
        )

    shortcut_path = output_dir / _shortcut_filename(
        collection_title=collection_title,
        slowpics_url=slowpics_url,
    )
    content = f"[InternetShortcut]\nURL={slowpics_url}\n"
    try:
        text_writer(shortcut_path, content)
    except OSError as exc:
        return SlowpicsShortcutResult(
            success=False,
            path=shortcut_path,
            warning=f"slow.pics shortcut: failed to write URL shortcut {shortcut_path}: {exc}",
        )

    return SlowpicsShortcutResult(success=True, path=shortcut_path)


def _select_shortcut_directory(workspace: WorkspacePaths) -> Path | None:
    if workspace.run_dir is not None:
        return workspace.run_dir

    root = workspace.root.resolve()
    screenshots_dir = workspace.screenshots_dir.resolve()
    generated_dir = workspace.generated_dir.resolve()

    if _normalized_anchor(screenshots_dir) != _normalized_anchor(generated_dir):
        return None

    try:
        common_parent = Path(os.path.commonpath((str(screenshots_dir), str(generated_dir))))
    except ValueError:
        return None
    common_parent = common_parent.resolve()

    if not _is_safe_shortcut_parent(common_parent, root):
        return None
    return common_parent


def _is_safe_shortcut_parent(parent: Path, root: Path) -> bool:
    if _normalized_anchor(parent) != _normalized_anchor(root):
        return False
    if not parent.is_relative_to(root):
        return False
    if parent == _anchor_path(parent):
        return False
    try:
        if parent == Path.home().resolve():
            return False
    except RuntimeError:
        return False
    return True


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


def _anchor_path(path: Path) -> Path:
    if path.anchor:
        return Path(path.anchor)
    return path


def _normalized_anchor(path: Path) -> str:
    return os.path.normcase(path.anchor)
