"""Path containment utilities for security.

Provides safe path resolution to prevent directory traversal attacks.
All filesystem operations should validate paths through these utilities.
"""

from __future__ import annotations

from pathlib import Path

from frame_compare.errors import InvalidPathError, PathEscapesRootError


def resolve_safe_path(path: str, root: Path) -> Path:
    """Resolve a path ensuring it stays within the root directory.

    Args:
        path: The path to resolve (relative or absolute)
        root: The root directory that paths must be contained within

    Returns:
        The resolved Path object, guaranteed to be within root

    Raises:
        InvalidPathError: If path contains null bytes or invalid characters (FC-3008)
        PathEscapesRootError: If resolved path escapes root via traversal or symlinks (FC-3009)

    Example:
        >>> root = Path("/workspace")
        >>> resolve_safe_path("subdir/file.png", root)
        PosixPath('/workspace/subdir/file.png')
        >>> resolve_safe_path("../../../etc/passwd", root)
        Traceback (most recent call last):
            ...
        PathEscapesRootError: ...
    """
    # Reject null bytes (path injection attack vector)
    if "\x00" in path:
        raise InvalidPathError(
            path=path[:50],
            reason="Path contains null byte",
        )

    # Convert to Path object
    candidate = Path(path)

    # Resolve the root to an absolute path
    resolved_root = root.resolve()

    # If path is absolute, check it's under root
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        # Resolve relative path against root
        resolved = (resolved_root / candidate).resolve()

    # Check containment (must be equal to or under root)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as err:
        raise PathEscapesRootError(
            candidate=str(path),
            root=str(root),
        ) from err

    return resolved
