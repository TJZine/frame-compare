from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.services.slowpics_shortcut import create_slowpics_url_shortcut
from frame_compare.utils.types import WorkspacePaths


def _workspace(
    root: Path,
    *,
    run_dir: Path | None = None,
    screenshots_dir: Path | None = None,
    generated_dir: Path | None = None,
) -> WorkspacePaths:
    return WorkspacePaths(
        root=root,
        input_dir=root / "comparison_videos",
        generated_root=generated_dir or root / "generated",
        run_dir=run_dir,
        screenshots_dir=screenshots_dir or root / "screenshots",
        generated_dir=generated_dir or root / "generated",
        config_dir=root / "config",
        config_file=root / "config" / "config.toml",
    )


def test_create_slowpics_url_shortcut_prefers_run_dir_and_collection_title(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    run_dir = root / "generated" / "Collateral"
    result = create_slowpics_url_shortcut(
        workspace=_workspace(
            root,
            run_dir=run_dir,
            screenshots_dir=root / "elsewhere" / "screenshots",
            generated_dir=root / "generated",
        ),
        slowpics_url="https://slow.pics/c/collateral-key",
        collection_title="Collateral",
    )

    shortcut_path = run_dir / "Collateral.url"
    assert result.success is True
    assert result.path == shortcut_path
    assert result.warning is None
    assert shortcut_path.read_text(encoding="utf-8") == (
        "[InternetShortcut]\nURL=https://slow.pics/c/collateral-key\n"
    )


def test_create_slowpics_url_shortcut_requires_reserved_run_dir(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    output_parent = root / "output"
    result = create_slowpics_url_shortcut(
        workspace=_workspace(
            root,
            screenshots_dir=output_parent / "screenshots",
            generated_dir=output_parent / "generated",
        ),
        slowpics_url="https://slow.pics/c/example-key",
        collection_title="Encode Screenshots",
    )

    assert result.success is False
    assert result.path is None
    assert result.warning is not None
    assert "no reserved run directory" in result.warning
    assert not output_parent.exists()


def test_create_slowpics_url_shortcut_returns_warning_for_parent_outside_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    output_parent = tmp_path / "outside"

    result = create_slowpics_url_shortcut(
        workspace=_workspace(
            root,
            screenshots_dir=output_parent / "screenshots",
            generated_dir=output_parent / "generated",
        ),
        slowpics_url="https://slow.pics/c/example-key",
        collection_title="Collateral",
    )

    assert result.success is False
    assert result.path is None
    assert result.warning is not None
    assert "no reserved run directory" in result.warning
    assert not output_parent.exists()


def test_create_slowpics_url_shortcut_rejects_junctioned_run_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "workspace"
    run_dir = root / "generated" / "Example"
    monkeypatch.setattr(Path, "is_junction", lambda path: path == run_dir)

    result = create_slowpics_url_shortcut(
        workspace=_workspace(root, run_dir=run_dir),
        slowpics_url="https://slow.pics/c/example-key",
        collection_title="Example",
    )

    assert result.success is False
    assert result.path is None
    assert result.warning is not None
    assert "no reserved run directory" in result.warning
    assert not run_dir.exists()


def test_create_slowpics_url_shortcut_treats_home_common_parent_as_unsafe() -> None:
    home = Path.home().resolve()

    result = create_slowpics_url_shortcut(
        workspace=_workspace(
            home,
            screenshots_dir=home / "frame-compare-shortcut-test-screenshots",
            generated_dir=home / "frame-compare-shortcut-test-generated",
        ),
        slowpics_url="https://slow.pics/c/example-key",
        collection_title="Collateral",
    )

    assert result.success is False
    assert result.warning is not None
    assert "no reserved run directory" in result.warning


def test_create_slowpics_url_shortcut_sanitizes_title_and_falls_back_to_url_key(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    output_parent = root / "generated"
    run_dir = output_parent / "Example"

    title_result = create_slowpics_url_shortcut(
        workspace=_workspace(
            root,
            run_dir=run_dir,
            screenshots_dir=output_parent / "screenshots",
            generated_dir=output_parent,
        ),
        slowpics_url="https://slow.pics/c/title-key",
        collection_title='The: Movie / Finale * "Special"',
    )
    fallback_result = create_slowpics_url_shortcut(
        workspace=_workspace(
            root,
            run_dir=run_dir,
            screenshots_dir=output_parent / "screenshots",
            generated_dir=output_parent,
        ),
        slowpics_url="https://slow.pics/c/url-key",
        collection_title="<>:?*",
    )

    assert title_result.path == run_dir / "The Movie Finale Special.url"
    assert fallback_result.path == run_dir / "url-key.url"


def test_create_slowpics_url_shortcut_overwrites_same_deterministic_path(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    run_dir = root / "generated" / "Example"
    shortcut_path = run_dir / "Example.url"
    shortcut_path.parent.mkdir(parents=True)
    shortcut_path.write_text("stale", encoding="utf-8")

    first = create_slowpics_url_shortcut(
        workspace=_workspace(root, run_dir=run_dir),
        slowpics_url="https://slow.pics/c/one",
        collection_title="Example",
    )
    second = create_slowpics_url_shortcut(
        workspace=_workspace(root, run_dir=run_dir),
        slowpics_url="https://slow.pics/c/two",
        collection_title="Example",
    )

    assert first.path == shortcut_path
    assert second.path == shortcut_path
    assert shortcut_path.read_text(encoding="utf-8") == (
        "[InternetShortcut]\nURL=https://slow.pics/c/two\n"
    )


def test_create_slowpics_url_shortcut_returns_warning_for_write_failure(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"

    def _raise_write_error(_path: Path, _content: str) -> None:
        raise PermissionError("locked")

    result = create_slowpics_url_shortcut(
        workspace=_workspace(root, run_dir=root / "generated" / "Example"),
        slowpics_url="https://slow.pics/c/example-key",
        collection_title="Example",
        text_writer=_raise_write_error,
    )

    assert result.success is False
    assert result.path == root / "generated" / "Example" / "Example.url"
    assert result.warning is not None
    assert "failed to write URL shortcut" in result.warning
    assert "locked" in result.warning
