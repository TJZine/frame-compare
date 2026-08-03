"""Tests for dependency-light managed path containment."""

from pathlib import Path

import pytest

from frame_compare.errors import PathEscapesRootError
from frame_compare.utils.paths import (
    require_managed_descendant,
    require_managed_immediate_child,
)
from frame_compare.utils.types import WorkspacePaths


def test_require_managed_descendant_returns_resolved_contained_path(tmp_path: Path) -> None:
    owner = (tmp_path / "owner").resolve()
    descendant = owner / "run" / "report.html"

    assert require_managed_descendant(owner, descendant) == descendant.resolve()


def test_require_managed_descendant_rejects_symlink_escape(tmp_path: Path) -> None:
    owner = tmp_path / "owner"
    outside = tmp_path / "outside"
    owner.mkdir()
    outside.mkdir()
    (owner / "run").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PathEscapesRootError) as exc_info:
        require_managed_descendant(owner.resolve(), owner / "run" / "report.html")

    assert exc_info.value.context.details == {
        "path": str((outside / "report.html").resolve()),
        "root": str(owner.resolve()),
    }


def test_require_managed_immediate_child_returns_resolved_child(tmp_path: Path) -> None:
    owner = tmp_path / "owner"
    owner.mkdir()
    child = owner / "run"

    assert require_managed_immediate_child(owner, child) == child.resolve()


def test_require_managed_immediate_child_rejects_nested_descendant(tmp_path: Path) -> None:
    owner = tmp_path / "owner"
    owner.mkdir()

    with pytest.raises(PathEscapesRootError):
        require_managed_immediate_child(owner, owner / "nested" / "run")


def test_require_managed_immediate_child_rejects_symlink(
    tmp_path: Path,
) -> None:
    owner = tmp_path / "owner"
    target = owner / "target"
    owner.mkdir()
    target.mkdir()
    child = owner / "run"
    child.symlink_to(target, target_is_directory=True)

    with pytest.raises(PathEscapesRootError):
        require_managed_immediate_child(owner, child)


def test_require_managed_immediate_child_rejects_junction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = tmp_path / "owner"
    owner.mkdir()
    child = owner / "run"
    monkeypatch.setattr(Path, "is_junction", lambda path: path == child)

    with pytest.raises(PathEscapesRootError):
        require_managed_immediate_child(owner, child)


def test_workspace_paths_rejects_junctioned_run_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_root = tmp_path / "generated"
    run_dir = generated_root / "run"
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        generated_root=generated_root,
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=generated_root,
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )

    monkeypatch.setattr(Path, "is_junction", lambda path: path == run_dir)

    with pytest.raises(PathEscapesRootError):
        workspace.with_run_dir(run_dir)


def test_generated_root_junction_alias_is_allowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_root = tmp_path / "generated"
    monkeypatch.setattr(Path, "is_junction", lambda path: path == generated_root)

    from frame_compare.config.schema import ConfigSchema, PathsConfig
    from frame_compare.orchestration.preflight import resolve_paths

    workspace = resolve_paths(
        ConfigSchema(paths=PathsConfig(generated_dir=str(generated_root))),
        tmp_path,
    )

    assert workspace.generated_root == generated_root.resolve()
