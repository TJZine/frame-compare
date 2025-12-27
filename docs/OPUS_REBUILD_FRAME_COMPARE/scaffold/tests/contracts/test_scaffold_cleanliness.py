"""Scaffold cleanliness tests.

Ensures the scaffold template has proper .gitignore configuration to exclude
build artifacts. We can't check for absence of __pycache__ at runtime since
pytest creates them during test execution.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Path to scaffold root
SCAFFOLD_DIR = Path(__file__).parent.parent.parent


@pytest.mark.tier_a
class TestScaffoldCleanliness:
    """Tests that scaffold is configured to exclude build artifacts."""

    def test_gitignore_exists(self) -> None:
        """Scaffold has a .gitignore file."""
        gitignore_path = SCAFFOLD_DIR / ".gitignore"
        assert gitignore_path.exists(), (
            f"Missing .gitignore in scaffold: {SCAFFOLD_DIR}"
        )

    def test_gitignore_excludes_venv(self) -> None:
        """Scaffold .gitignore excludes virtual environments."""
        gitignore_path = SCAFFOLD_DIR / ".gitignore"
        if not gitignore_path.exists():
            pytest.skip(".gitignore does not exist")

        content = gitignore_path.read_text()
        assert ".venv" in content or "venv/" in content, (
            ".gitignore should exclude virtual environments"
        )

    def test_gitignore_excludes_pycache(self) -> None:
        """Scaffold .gitignore excludes __pycache__."""
        gitignore_path = SCAFFOLD_DIR / ".gitignore"
        if not gitignore_path.exists():
            pytest.skip(".gitignore does not exist")

        content = gitignore_path.read_text()
        assert "__pycache__" in content or "*.pyc" in content, (
            ".gitignore should exclude __pycache__ or *.pyc"
        )

    def test_gitignore_excludes_pytest_cache(self) -> None:
        """Scaffold .gitignore excludes pytest cache."""
        gitignore_path = SCAFFOLD_DIR / ".gitignore"
        if not gitignore_path.exists():
            pytest.skip(".gitignore does not exist")

        content = gitignore_path.read_text()
        assert ".pytest_cache" in content, (
            ".gitignore should exclude .pytest_cache"
        )

    def test_no_tracked_artifacts(self) -> None:
        """No build artifacts are tracked in git under scaffold.

        This test uses `git ls-files` to check tracked files, avoiding
        false positives from pytest creating __pycache__ at runtime.
        """
        import subprocess

        # Find project root (contains .git)
        project_root = SCAFFOLD_DIR
        while project_root.parent != project_root:
            if (project_root / ".git").exists():
                break
            project_root = project_root.parent
        else:
            pytest.skip("Not in a git repository")

        result = subprocess.run(
            ["git", "ls-files", str(SCAFFOLD_DIR)],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        if result.returncode != 0:
            pytest.skip(f"git ls-files failed: {result.stderr}")

        tracked_files = result.stdout.splitlines()
        artifact_patterns = [
            "__pycache__",
            ".pyc",
            ".pytest_cache",
            ".ruff_cache",
            ".mypy_cache",
        ]

        artifacts = [
            f for f in tracked_files
            if any(p in f for p in artifact_patterns)
        ]

        assert not artifacts, (
            f"Build artifacts tracked in git under scaffold: {artifacts}\\n"
            "Remove them with: git rm -r --cached <path>"
        )
