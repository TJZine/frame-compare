"""Tests for path containment security invariant (FC-3009).

Verifies that all path operations stay within allowed workspace boundaries.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.tier_a


class TestPathContainment:
    """Test path containment validation.

    Security invariant: No path operation should escape the workspace root.
    Error code: FC-3009 (PATH_ESCAPES_ROOT)
    """

    def test_relative_path_within_root_passes(self, tmp_path: Path) -> None:
        """Relative path within root is allowed."""
        from frame_compare.utils.paths import resolve_safe_path

        root = tmp_path / "workspace"
        root.mkdir()

        # Should resolve without error
        result = resolve_safe_path("subdir/file.png", root)
        assert result.is_relative_to(root)

    def test_absolute_path_within_root_passes(self, tmp_path: Path) -> None:
        """Absolute path within root is allowed."""
        from frame_compare.utils.paths import resolve_safe_path

        root = tmp_path / "workspace"
        root.mkdir()
        absolute = root / "subdir" / "file.png"

        result = resolve_safe_path(str(absolute), root)
        assert result.is_relative_to(root)

    def test_parent_traversal_blocked(self, tmp_path: Path) -> None:
        """Path with .. escaping root raises PathEscapesRootError."""
        from frame_compare.errors import PathEscapesRootError
        from frame_compare.utils.paths import resolve_safe_path

        root = tmp_path / "workspace"
        root.mkdir()

        with pytest.raises(PathEscapesRootError) as exc_info:
            resolve_safe_path("../../../etc/passwd", root)

        assert exc_info.value.code == "FC-3009"

    def test_symlink_escape_blocked(self, tmp_path: Path) -> None:
        """Symlink pointing outside root is blocked."""
        from frame_compare.errors import PathEscapesRootError
        from frame_compare.utils.paths import resolve_safe_path

        root = tmp_path / "workspace"
        root.mkdir()

        # Create symlink pointing outside workspace
        evil_link = root / "evil_link"
        evil_link.symlink_to(tmp_path.parent)

        with pytest.raises(PathEscapesRootError):
            resolve_safe_path("evil_link/sensitive", root)

    def test_null_byte_rejected(self, tmp_path: Path) -> None:
        """Path containing null byte is rejected."""
        from frame_compare.errors import InvalidPathError
        from frame_compare.utils.paths import resolve_safe_path

        root = tmp_path / "workspace"
        root.mkdir()

        with pytest.raises(InvalidPathError):
            resolve_safe_path("file\x00.png", root)
