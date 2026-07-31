"""Shared typed results for optional post-upload side effects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

type PostUploadActionKind = Literal["clipboard", "browser", "shortcut", "webhook"]


@dataclass(frozen=True)
class PostUploadActionResult:
    """Result for an optional post-upload side effect."""

    kind: PostUploadActionKind
    success: bool
    detail: str | None = None
    path: Path | None = None
    message: str | None = None
    warning: str | None = None


type PostUploadActionResults = tuple[PostUploadActionResult, ...]
