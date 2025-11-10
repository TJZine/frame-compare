from __future__ import annotations

from pathlib import Path

import pytest

import src.frame_compare.preflight as preflight_module
from src.frame_compare.cli_runtime import CLIAppError


def test_resolve_workspace_root_rejects_site_packages(tmp_path: Path) -> None:
    site_root = tmp_path / "lib" / "python" / "site-packages" / "frame_compare"
    site_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(CLIAppError):
        preflight_module.resolve_workspace_root(str(site_root))


def test_resolve_subdir_rejects_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    with pytest.raises(CLIAppError):
        preflight_module.resolve_subdir(workspace, "../escape", purpose="test path")
