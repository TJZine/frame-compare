"""Unit tests for preflight validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.config.errors import ConfigNotFoundError, ConfigValidationError
from frame_compare.config.schema import ConfigSchema, PathsConfig
from frame_compare.errors import PathEscapesRootError
from frame_compare.orchestration.errors import (
    DirectoryNotFoundError,
    NoVideosFoundError,
)
from frame_compare.orchestration.preflight import (
    PreflightResult,
    discover_inputs,
    prepare_preflight,
    resolve_contained_path,
    resolve_paths,
    resolve_selected_config_path,
    resolve_workspace,
    validate_and_normalize_config_paths,
)

# Minimal valid TOML config content
MINIMAL_CONFIG = """\
[paths]
input_dir = "comparison_videos"
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
                generated_dir="generated",
                config_dir="config",
            )
        )

        result = resolve_paths(config, tmp_path)

        assert result.root == tmp_path.resolve()
        assert result.input_dir == (tmp_path / "comparison_videos").resolve()
        assert result.generated_root == (tmp_path / "generated").resolve()
        assert result.screenshots_dir == (tmp_path / "generated" / "screenshots").resolve()
        assert result.generated_dir == (tmp_path / "generated").resolve()
        assert result.cache_dir == (tmp_path / "generated" / "cache" / "analysis").resolve()
        assert (
            result.shared_alignment_cache_dir
            == (tmp_path / "generated" / "cache" / "alignment").resolve()
        )
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
                generated_dir="generated",
                config_dir="config",
            )
        )

        result = resolve_paths(config, tmp_path)

        # The env var should be expanded
        assert result.input_dir == (Path(test_root) / "in").resolve()

    @pytest.mark.parametrize(
        "field_name",
        ["config_dir"],
    )
    @pytest.mark.parametrize("escape_kind", ["relative", "absolute", "symlink"])
    def test_contained_config_paths_reject_resolved_escapes(
        self,
        tmp_path: Path,
        field_name: str,
        escape_kind: str,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        external = tmp_path / "external"
        external.mkdir()
        if escape_kind == "relative":
            escaped_value = "../external/output"
        elif escape_kind == "absolute":
            escaped_value = str(external / "output")
        else:
            (root / "linked-outside").symlink_to(external, target_is_directory=True)
            escaped_value = "linked-outside/output"

        paths = PathsConfig().model_copy(update={field_name: escaped_value})
        config = ConfigSchema(paths=paths)

        with pytest.raises(PathEscapesRootError) as exc_info:
            resolve_paths(config, root)

        error = exc_info.value
        assert error.code == "FC-3009"
        assert error.context.details == {
            "path": str((external / "output").resolve()),
            "root": str(root.resolve()),
        }

    def test_resolve_paths_allows_absolute_external_input(self, tmp_path: Path) -> None:
        root = tmp_path / "workspace"
        external_input = tmp_path / "media"
        root.mkdir()
        external_input.mkdir()
        config = ConfigSchema(
            paths=PathsConfig(input_dir=str(external_input)),
        )

        result = resolve_paths(config, root)

        assert result.input_dir == external_input.resolve()
        assert result.generated_root.is_relative_to(root.resolve())

    def test_resolve_paths_allows_absolute_external_generated_root(self, tmp_path: Path) -> None:
        root = tmp_path / "workspace"
        external_generated = tmp_path / "generated-on-external-volume"
        root.mkdir()
        external_generated.mkdir()
        config = ConfigSchema(paths=PathsConfig(generated_dir=str(external_generated)))

        result = resolve_paths(config, root)

        assert result.generated_root == external_generated.resolve()
        assert result.generated_dir == external_generated.resolve()
        assert not (root / "generated").exists()

    def test_resolve_paths_expands_absolute_generated_root_environment_value(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "workspace"
        external_generated = tmp_path / "generated-from-env"
        root.mkdir()
        external_generated.mkdir()
        monkeypatch.setenv("FRAME_COMPARE_GENERATED_ROOT", str(external_generated))
        config = ConfigSchema(paths=PathsConfig(generated_dir="$FRAME_COMPARE_GENERATED_ROOT"))

        result = resolve_paths(config, root)

        assert result.generated_root == external_generated.resolve()
        assert config.paths.generated_dir == "$FRAME_COMPARE_GENERATED_ROOT"

    def test_resolve_paths_allows_generated_root_reached_through_symlink(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "workspace"
        external_generated = tmp_path / "external-generated"
        root.mkdir()
        external_generated.mkdir()
        link = root / "generated-link"
        link.symlink_to(external_generated, target_is_directory=True)
        config = ConfigSchema(paths=PathsConfig(generated_dir=str(link)))

        result = resolve_paths(config, root)

        assert result.generated_root == external_generated.resolve()

    def test_resolve_paths_maps_generated_root_resolve_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        generated_loop = root / "generated-loop"
        config = ConfigSchema(paths=PathsConfig(generated_dir="generated-loop"))
        original_resolve = Path.resolve

        def _fail_generated_resolve(path: Path, *args: object, **kwargs: object) -> Path:
            if path == generated_loop:
                raise RuntimeError("symlink loop")
            return original_resolve(path, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", _fail_generated_resolve)

        with pytest.raises(ConfigValidationError) as exc_info:
            resolve_paths(config, root)

        assert exc_info.value.code == "FC-1003"
        assert "generated-loop" in str(exc_info.value)
        assert "Reconnect" in (exc_info.value.hint or "")
        assert not generated_loop.exists()

    def test_resolve_paths_maps_managed_cache_resolve_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        generated_root = root / "generated"
        managed_loop = generated_root / "cache" / "analysis"
        config = ConfigSchema(paths=PathsConfig(generated_dir="generated"))
        original_resolve = Path.resolve

        def _fail_managed_resolve(path: Path, *args: object, **kwargs: object) -> Path:
            if path == managed_loop:
                raise OSError("managed path unavailable")
            return original_resolve(path, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", _fail_managed_resolve)

        with pytest.raises(ConfigValidationError) as exc_info:
            resolve_paths(config, root)

        assert exc_info.value.code == "FC-1003"
        assert "managed path unavailable" in str(exc_info.value)
        assert "Reconnect" in (exc_info.value.hint or "")
        assert not managed_loop.exists()

    @pytest.mark.parametrize("generated_dir", ["/", "C:\\", "\\\\server\\share"])
    def test_resolve_paths_rejects_filesystem_root_generated_directory(
        self,
        tmp_path: Path,
        generated_dir: str,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        config = ConfigSchema(paths=PathsConfig(generated_dir=generated_dir))

        with pytest.raises(ConfigValidationError) as exc_info:
            resolve_paths(config, root)

        assert exc_info.value.context.details is not None
        assert exc_info.value.context.details["validation_errors"]
        assert not (root / "generated").exists()

    def test_resolve_paths_rejects_generated_root_symlink_to_filesystem_root(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        (root / "root-link").symlink_to(Path("/"), target_is_directory=True)
        config = ConfigSchema(paths=PathsConfig(generated_dir="root-link"))

        with pytest.raises(ConfigValidationError):
            resolve_paths(config, root)

    def test_resolve_paths_allows_symlinked_external_input(self, tmp_path: Path) -> None:
        root = tmp_path / "workspace"
        external_input = tmp_path / "media"
        root.mkdir()
        external_input.mkdir()
        (root / "linked-media").symlink_to(external_input, target_is_directory=True)
        config = ConfigSchema(paths=PathsConfig(input_dir="linked-media"))

        result = resolve_paths(config, root)

        assert result.input_dir == external_input.resolve()

    def test_generated_root_accepts_external_absolute_directory_without_mutating_config(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "workspace"
        external = tmp_path / "external-generated"
        root.mkdir()
        config = ConfigSchema(paths=PathsConfig(generated_dir=str(external)))

        normalized = validate_and_normalize_config_paths(config, root)

        assert normalized is config
        assert config.paths.generated_dir == str(external)
        assert resolve_paths(config, root).generated_root == external.resolve()

    def test_resolve_contained_path_expands_environment_variables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CONTAINED_OUTPUT", "generated/custom")

        assert (
            resolve_contained_path("$CONTAINED_OUTPUT", tmp_path)
            == (tmp_path / "generated" / "custom").resolve()
        )

    def test_selected_config_allows_exact_windows_portable_state_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Patch the owner seam so this Windows-only policy remains unit-testable
        # on every supported development platform.
        root = tmp_path / "workspace"
        root.mkdir()
        portable_config = tmp_path / "portable-state" / "config.toml"
        monkeypatch.setattr(
            "frame_compare.orchestration.preflight._windows_portable_state_config_path",
            lambda: portable_config,
        )

        assert resolve_selected_config_path(portable_config, root) == portable_config.resolve()

    def test_selected_config_windows_exception_rejects_external_sibling(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        state_dir = tmp_path / "portable-state"
        portable_config = state_dir / "config.toml"
        monkeypatch.setattr(
            "frame_compare.orchestration.preflight._windows_portable_state_config_path",
            lambda: portable_config,
        )

        with pytest.raises(PathEscapesRootError):
            resolve_selected_config_path(state_dir / "other.toml", root)

    def test_selected_config_windows_exception_rejects_symlinked_leaf_escape(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        state_dir = tmp_path / "portable-state"
        state_dir.mkdir()
        portable_config = state_dir / "config.toml"
        external_config = tmp_path / "external.toml"
        external_config.write_text("", encoding="utf-8")
        portable_config.symlink_to(external_config)
        monkeypatch.setattr(
            "frame_compare.orchestration.preflight._windows_portable_state_config_path",
            lambda: portable_config,
        )

        with pytest.raises(PathEscapesRootError) as exc_info:
            resolve_selected_config_path(portable_config, root)

        assert exc_info.value.context.details == {
            "path": str(external_config.resolve()),
            "root": str(root.resolve()),
        }


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

    def test_discover_inputs_uses_exact_name_to_break_casefold_ties(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        candidates = [tmp_path / "a.mkv", tmp_path / "A.mkv"]
        monkeypatch.setattr(Path, "iterdir", lambda _path: iter(candidates))
        monkeypatch.setattr(Path, "is_file", lambda path: path in candidates)

        result = discover_inputs(tmp_path, ["*.mkv"])

        assert [path.name for path in result] == ["A.mkv", "a.mkv"]

    def test_discover_inputs_uses_relative_path_to_break_recursive_basename_ties(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        candidates = [
            tmp_path / "z" / "same.mkv",
            tmp_path / "a" / "same.mkv",
            tmp_path / "A" / "same.mkv",
        ]
        monkeypatch.setattr(Path, "rglob", lambda _path, _pattern: iter(candidates))
        monkeypatch.setattr(Path, "is_file", lambda path: path in candidates)

        result = discover_inputs(tmp_path, ["**/*.mkv"])

        assert [path.relative_to(tmp_path).as_posix() for path in result] == [
            "A/same.mkv",
            "a/same.mkv",
            "z/same.mkv",
        ]

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

    def test_prepare_preflight_allows_external_input_override(self, tmp_path: Path) -> None:
        root = tmp_path / "workspace"
        _create_config(root)
        external_input = tmp_path / "media"
        _create_video_files(external_input, "external.mkv")

        result = prepare_preflight(
            root=root,
            overrides={"paths": {"input_dir": str(external_input)}},
        )

        assert result.workspace.input_dir == external_input.resolve()
        assert result.workspace.generated_dir.is_relative_to(root.resolve())

    def test_prepare_preflight_allows_external_generated_root(self, tmp_path: Path) -> None:
        root = tmp_path / "workspace"
        external_generated = tmp_path / "external-generated"
        _create_config(
            root,
            MINIMAL_CONFIG.replace(
                'generated_dir = "generated"',
                f'generated_dir = "{external_generated.as_posix()}"',
            ),
        )
        _create_video_files(root / "comparison_videos", "external.mkv")

        result = prepare_preflight(root=root)

        assert result.workspace.generated_root == external_generated.resolve()
        assert not (root / "generated").exists()

    def test_prepare_preflight_allows_symlinked_external_input(self, tmp_path: Path) -> None:
        root = tmp_path / "workspace"
        _create_config(root, MINIMAL_CONFIG.replace('"comparison_videos"', '"linked-media"'))
        external_input = tmp_path / "media"
        _create_video_files(external_input, "external.mkv")
        (root / "linked-media").symlink_to(external_input, target_is_directory=True)

        result = prepare_preflight(root=root)

        assert result.workspace.input_dir == external_input.resolve()

    def test_prepare_preflight_rejects_external_config_before_exists_or_load(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        external_config = tmp_path / "missing" / "config.toml"

        def _unexpected_load(*_args: object, **_kwargs: object) -> ConfigSchema:
            raise AssertionError("load_config must not run for an external config path")

        monkeypatch.setattr("frame_compare.orchestration.preflight.load_config", _unexpected_load)

        with pytest.raises(PathEscapesRootError) as exc_info:
            prepare_preflight(root=root, config_path=external_config)

        assert exc_info.value.code == "FC-3009"
        assert exc_info.value.context.details is not None
        assert exc_info.value.context.details["path"] == str(external_config.resolve())
