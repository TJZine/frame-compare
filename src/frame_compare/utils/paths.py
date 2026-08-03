"""Dependency-light filesystem path helpers."""

from __future__ import annotations

from pathlib import Path

from frame_compare.errors import PathEscapesRootError


def require_managed_descendant(owner: Path, descendant: Path) -> Path:
    """Return a resolved managed descendant or reject an escaped target.

    Callers provide an already selected owner and descendant path. Resolving both
    here keeps symlink/junction targets part of the containment decision while
    leaving path interpretation and output policy to their owning layers.
    """
    resolved_owner = owner.resolve()
    resolved_descendant = descendant.resolve()
    if not resolved_descendant.is_relative_to(resolved_owner):
        raise PathEscapesRootError(resolved_descendant, resolved_owner)
    return resolved_descendant


def require_managed_immediate_child(owner: Path, child: Path) -> Path:
    """Return a resolved real immediate child or reject a redirected path."""
    resolved_owner = owner.resolve()
    resolved_child = require_managed_descendant(resolved_owner, child)
    if child.is_symlink() or child.is_junction() or resolved_child.parent != resolved_owner:
        raise PathEscapesRootError(resolved_child, resolved_owner)
    return resolved_child


__all__ = ["require_managed_descendant", "require_managed_immediate_child"]
