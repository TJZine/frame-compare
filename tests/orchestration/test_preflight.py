"""Unit tests for preflight validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.orchestration.errors import (
    DirectoryNotFoundError,
    NoVideosFoundError,
)
from frame_compare.orchestration.preflight import (
    PreflightResult,
    discover_inputs,
    prepare_preflight,
    resolve_paths,
    resolve_workspace,
)

# Minimal valid TOML config content
MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
screenshots_dir = "screenshots"
generated_dir = "generated"
config_dir = "config"
"""


def _create_config(tmp_path: Path, content: str = MINIMAL_CONFIG) -> Path:
    """Create a config file in the standard location."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(content)
    return config_file


def _create_video_files(input_dir: Path, *filenames: str) -> None:
    """Create empty video files for testing."""
    input_dir.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (input_dir / name).touch()


class TestResolveWorkspace:
    """Tests for resolve_workspace function."""

    def test_resolve_workspace_explicit_root(self, tmp_path: Path) -> None:
        """Given explicit root=tmp_path → returns tmp_path."""
        result = resolve_workspace(tmp_path)
        assert result == tmp_path.resolve()

    def test_resolve_workspace_cwd_with_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given tmp_path/config/config.toml exists and cwd=tmp_path → returns tmp_path."""
        _create_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = resolve_workspace(None)
        assert result == tmp_path

    def test_resolve_workspace_searches_upward(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given tmp_path/config/config.toml exists and cwd is subdir → returns tmp_path."""
        _create_config(tmp_path)
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        result = resolve_workspace(None)
        assert result == tmp_path

    def test_resolve_workspace_fallback_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given no config found and cwd=tmp_path → returns tmp_path."""
        monkeypatch.chdir(tmp_path)

        result = resolve_workspace(None)
        assert result == tmp_path


class TestResolvePaths:
    """Tests for resolve_paths function (2-arg SSOT signature)."""

    def test_resolve_paths_relative_to_root(self, tmp_path: Path) -> None:
        """Given config with relative paths → resolves relative to root."""
        from frame_compare.config.schema import ConfigSchema, PathsConfig

        config = ConfigSchema(
            paths=PathsConfig(
                input_dir="comparison_videos",
                screenshots_dir="screenshots",
                generated_dir="generated",
                config_dir="config",
            )
        )

        result = resolve_paths(config, tmp_path)

        assert result.root == tmp_path.resolve()
        assert result.input_dir == (tmp_path / "comparison_videos").resolve()
        assert result.screenshots_dir == (tmp_path / "screenshots").resolve()
        assert result.generated_dir == (tmp_path / "generated").resolve()
        assert result.cache_dir == (tmp_path / "generated" / "cache" / "analysis").resolve()
        assert result.config_dir == (tmp_path / "config").resolve()
        # config_file is derived as config_dir / "config.toml"
        assert result.config_file == (tmp_path / "config" / "config.toml").resolve()

    def test_resolve_paths_expands_env_vars(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given config with env var input_dir → resolved path expands env var."""
        from frame_compare.config.schema import ConfigSchema, PathsConfig

        test_root = str(tmp_path)
        monkeypatch.setenv("TEST_ROOT", test_root)

        config = ConfigSchema(
            paths=PathsConfig(
                input_dir="$TEST_ROOT/in",
                screenshots_dir="screenshots",
                generated_dir="generated",
                config_dir="config",
            )
        )

        result = resolve_paths(config, tmp_path)

        # The env var should be expanded
        assert result.input_dir == (Path(test_root) / "in").resolve()


class TestDiscoverInputs:
    """Tests for discover_inputs helper (determinism)."""

    def test_discover_inputs_sorted_case_insensitive(self, tmp_path: Path) -> None:
        """Given files b.mkv and A.mkv → discovered list is [A.mkv, b.mkv]."""
        _create_video_files(tmp_path, "b.mkv", "A.mkv")

        result = discover_inputs(tmp_path, ["*.mkv"])

        # Assert exact ordering: case-insensitive sort means A.mkv < b.mkv
        assert len(result) == 2
        assert result[0].name == "A.mkv"
        assert result[1].name == "b.mkv"

    def test_discover_inputs_matches_extensions_case_insensitive(self, tmp_path: Path) -> None:
        _create_video_files(tmp_path, "VIDEO.MKV")
        result = discover_inputs(tmp_path, ["*.mkv"])
        assert [p.name for p in result] == ["VIDEO.MKV"]

    def test_discover_inputs_empty_raises_no_videos_found_error_preserves_patterns(
        self, tmp_path: Path
    ) -> None:
        """Given no matching files → raises NoVideosFoundError with default patterns."""
        with pytest.raises(NoVideosFoundError) as exc_info:
            discover_inputs(tmp_path)

        error = exc_info.value
        assert error.code == "FC-3001"
        assert error.path == tmp_path.resolve()
        assert error.patterns == ["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]

    def test_discover_inputs_oserror_raises_input_discovery_error(self, tmp_path: Path) -> None:
        """Given a path that raises OSError on listdir/iterdir → raises InputDiscoveryError."""
        from unittest.mock import patch

        from frame_compare.orchestration.errors import InputDiscoveryError

        with (
            patch.object(Path, "iterdir", side_effect=OSError("Permission denied")),
            pytest.raises(InputDiscoveryError) as exc_info,
        ):
            discover_inputs(tmp_path)

        assert exc_info.value.code == "FC-3010"
        assert exc_info.value.path == tmp_path


class TestPreparePreflight:
    """Tests for prepare_preflight function."""

    def test_prepare_preflight_success(self, tmp_path: Path) -> None:
        """Given valid config dir with video files → returns PreflightResult."""
        _create_config(tmp_path)
        input_dir = tmp_path / "comparison_videos"
        _create_video_files(input_dir, "source.mkv", "encode.mp4")

        result = prepare_preflight(root=tmp_path)

        assert isinstance(result, PreflightResult)
        assert result.config is not None
        assert result.workspace.root == tmp_path.resolve()
        assert result.workspace.input_dir == input_dir.resolve()

    def test_prepare_preflight_config_not_found(self, tmp_path: Path) -> None:
        """Given missing config/config.toml → raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError):
            prepare_preflight(root=tmp_path)

    def test_prepare_preflight_missing_input_dir_raises_directory_not_found(
        self, tmp_path: Path
    ) -> None:
        """Given missing input dir → raises DirectoryNotFoundError."""
        _create_config(tmp_path)
        # Don't create the comparison_videos directory

        with pytest.raises(DirectoryNotFoundError):
            prepare_preflight(root=tmp_path)

    def test_prepare_preflight_empty_input_dir(self, tmp_path: Path) -> None:
        """Given empty input dir → raises NoVideosFoundError."""
        _create_config(tmp_path)
        input_dir = tmp_path / "comparison_videos"
        input_dir.mkdir(parents=True)
        # Don't create any video files

        with pytest.raises(NoVideosFoundError) as exc_info:
            prepare_preflight(root=tmp_path)

        # Verify error has path and patterns attributes
        error = exc_info.value
        assert error.path == input_dir.resolve()
        assert "*.mkv" in error.patterns

    def test_prepare_preflight_discovers_inputs_sorted_case_insensitive(
        self, tmp_path: Path
    ) -> None:
        """Given files b.mkv and A.mkv → preflight succeeds (ordering tested in TestDiscoverInputs)."""
        _create_config(tmp_path)
        input_dir = tmp_path / "comparison_videos"
        _create_video_files(input_dir, "b.mkv", "A.mkv")

        result = prepare_preflight(root=tmp_path)

        # Preflight should succeed (detailed ordering tested via _discover_inputs)
        assert isinstance(result, PreflightResult)

    def test_prepare_preflight_with_explicit_config_path(self, tmp_path: Path) -> None:
        """Given explicit config_path → loads that config file."""
        config_file = _create_config(tmp_path)
        input_dir = tmp_path / "comparison_videos"
        _create_video_files(input_dir, "test.mkv")

        result = prepare_preflight(config_path=config_file)

        assert result.workspace.config_file == config_file.resolve()

    def test_prepare_preflight_overrides_input_dir_before_validation(self, tmp_path: Path) -> None:
        """Overrides input_dir before validating directory existence."""
        _create_config(tmp_path)
        override_dir = tmp_path / "override_videos"
        _create_video_files(override_dir, "override.mkv")

        result = prepare_preflight(
            root=tmp_path,
            overrides={"paths": {"input_dir": "override_videos"}},
        )

        assert result.workspace.input_dir == override_dir.resolve()
