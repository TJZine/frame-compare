"""Unit tests for preflight validation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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

    @pytest.mark.parametrize(
        ("explicit", "has_config", "subdirectory"),
        [(True, False, False), (False, True, False), (False, True, True), (False, False, False)],
        ids=["explicit-root", "cwd-config", "upward-config", "cwd-fallback"],
    )
    def test_resolve_workspace(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        explicit: bool,
        has_config: bool,
        subdirectory: bool,
    ) -> None:
        if has_config:
            _create_config(tmp_path)
        cwd = tmp_path / "subdir" if subdirectory else tmp_path
        if subdirectory:
            cwd.mkdir()
        if not explicit:
            monkeypatch.chdir(cwd)
        result = resolve_workspace(tmp_path if explicit else None)
        assert result == (tmp_path.resolve() if explicit else tmp_path)


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

    @pytest.mark.parametrize(
        ("field", "external_name", "link_name", "environment"),
        [
            pytest.param("input_dir", "media", None, False, id="absolute-input"),
            pytest.param(
                "generated_dir",
                "generated-on-external-volume",
                None,
                False,
                id="absolute-generated",
            ),
            pytest.param(
                "generated_dir", "generated-from-env", None, True, id="environment-generated"
            ),
            pytest.param(
                "generated_dir",
                "external-generated",
                "generated-link",
                False,
                id="symlink-generated",
            ),
            pytest.param("input_dir", "media", "linked-media", False, id="symlink-input"),
        ],
    )
    def test_resolve_paths_external_directories(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        field: Literal["input_dir", "generated_dir"],
        external_name: str,
        link_name: str | None,
        environment: bool,
    ) -> None:
        root = tmp_path / "workspace"
        external = tmp_path / external_name
        root.mkdir()
        external.mkdir()
        value = str(external)
        if link_name is not None:
            link = root / link_name
            link.symlink_to(external, target_is_directory=True)
            value = str(link) if field == "generated_dir" else link_name
        if environment:
            monkeypatch.setenv("FRAME_COMPARE_GENERATED_ROOT", str(external))
            value = "$FRAME_COMPARE_GENERATED_ROOT"
        config = ConfigSchema(paths=PathsConfig.model_validate({field: value}))
        result = resolve_paths(config, root)
        if field == "input_dir":
            assert result.input_dir == external.resolve()
            if link_name is None:
                assert result.generated_root.is_relative_to(root.resolve())
        else:
            assert result.generated_root == external.resolve()
            if link_name is None and not environment:
                assert result.generated_dir == external.resolve()
                assert not (root / "generated").exists()

    @pytest.mark.parametrize(
        ("generated_dir", "descendant", "error", "expected_message"),
        [
            pytest.param(
                "generated-loop",
                "",
                RuntimeError("symlink loop"),
                "generated-loop",
                id="generated-root",
            ),
            pytest.param(
                "generated",
                "cache/analysis",
                OSError("managed path unavailable"),
                "managed path unavailable",
                id="managed-cache",
            ),
        ],
    )
    def test_resolve_paths_maps_resolution_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        generated_dir: str,
        descendant: str,
        error: Exception,
        expected_message: str,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        failing_path = root / generated_dir / descendant
        config = ConfigSchema(paths=PathsConfig(generated_dir=generated_dir))
        original_resolve = Path.resolve

        def fail_resolve(path: Path, *args: object, **kwargs: object) -> Path:
            if path == failing_path:
                raise error
            return original_resolve(path, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", fail_resolve)
        with pytest.raises(ConfigValidationError) as exc_info:
            resolve_paths(config, root)
        assert exc_info.value.code == "FC-1003"
        assert expected_message in str(exc_info.value)
        assert "Reconnect" in (exc_info.value.hint or "")
        assert not failing_path.exists()

    @pytest.mark.parametrize(
        ("name", "is_directory"),
        [("analysis", True), ("tmdb.toml", False)],
        ids=["analysis", "tmdb"],
    )
    def test_resolve_paths_rejects_shared_cache_symlink_escape(
        self, tmp_path: Path, name: str, is_directory: bool
    ) -> None:
        root = tmp_path / "workspace"
        generated_root = root / "generated"
        external_cache = tmp_path / "external-cache"
        (generated_root / "cache").mkdir(parents=True)
        external_cache.mkdir()
        external_path = external_cache if is_directory else external_cache / name
        (generated_root / "cache" / name).symlink_to(
            external_path, target_is_directory=is_directory
        )
        config = ConfigSchema(paths=PathsConfig(generated_dir="generated"))
        with pytest.raises(PathEscapesRootError) as exc_info:
            resolve_paths(config, root)
        assert exc_info.value.context.details == {
            "path": str(external_path.resolve()),
            "root": str(generated_root.resolve()),
        }

    @pytest.mark.parametrize(
        (
            "generated_dir",
            "environment",
            "symlink",
            "validation",
            "nonempty_hint",
            "absent_generated",
        ),
        [
            pytest.param("", False, False, True, True, False, id="blank"),
            pytest.param(" ", False, False, True, True, False, id="space"),
            pytest.param("\t\n", False, False, True, True, False, id="whitespace"),
            pytest.param(
                "$FRAME_COMPARE_EMPTY_GENERATED_ROOT",
                True,
                False,
                False,
                False,
                False,
                id="environment-empty",
            ),
            pytest.param("/", False, False, True, False, True, id="posix-root"),
            pytest.param("C:\\", False, False, True, False, True, id="windows-root"),
            pytest.param("\\\\server\\share", False, False, True, False, True, id="unc-root"),
            pytest.param("root-link", False, True, False, False, False, id="symlink-root"),
        ],
    )
    def test_resolve_paths_rejects_invalid_generated_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        generated_dir: str,
        environment: bool,
        symlink: bool,
        validation: bool,
        nonempty_hint: bool,
        absent_generated: bool,
    ) -> None:
        root = tmp_path / "workspace"
        root.mkdir()
        if environment:
            monkeypatch.setenv("FRAME_COMPARE_EMPTY_GENERATED_ROOT", "")
        if symlink:
            (root / "root-link").symlink_to(Path("/"), target_is_directory=True)
        config = ConfigSchema(paths=PathsConfig(generated_dir=generated_dir))
        with pytest.raises(ConfigValidationError) as exc_info:
            resolve_paths(config, root)
        if validation:
            assert exc_info.value.context.details is not None
            assert exc_info.value.context.details["validation_errors"]
        if nonempty_hint:
            assert "non-empty" in (exc_info.value.hint or "")
        if absent_generated:
            assert not (root / "generated").exists()

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

    @pytest.mark.parametrize(
        ("names", "expected"),
        [(["b.mkv", "A.mkv"], ["A.mkv", "b.mkv"]), (["VIDEO.MKV"], ["VIDEO.MKV"])],
        ids=["casefold-order", "extension-case"],
    )
    def test_discover_inputs_case_insensitive(
        self, tmp_path: Path, names: list[str], expected: list[str]
    ) -> None:
        _create_video_files(tmp_path, *names)
        result = discover_inputs(tmp_path, ["*.mkv"])
        assert [path.name for path in result] == expected

    @pytest.mark.parametrize(
        ("names", "pattern", "expected"),
        [
            (["a.mkv", "A.mkv"], "*.mkv", ["A.mkv", "a.mkv"]),
            (
                ["z/same.mkv", "a/same.mkv", "A/same.mkv"],
                "**/*.mkv",
                ["A/same.mkv", "a/same.mkv", "z/same.mkv"],
            ),
        ],
        ids=["exact-name", "recursive-relative-path"],
    )
    def test_discover_inputs_breaks_casefold_ties(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        names: list[str],
        pattern: str,
        expected: list[str],
    ) -> None:
        candidates = [tmp_path / name for name in names]
        if pattern == "**/*.mkv":
            monkeypatch.setattr(Path, "rglob", lambda _path, _pattern: iter(candidates))
        else:
            monkeypatch.setattr(Path, "iterdir", lambda _path: iter(candidates))
        monkeypatch.setattr(Path, "is_file", lambda path: path in candidates)
        result = discover_inputs(tmp_path, [pattern])
        assert [path.relative_to(tmp_path).as_posix() for path in result] == expected

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

    @pytest.mark.parametrize(
        ("has_config", "has_input_dir", "error_type"),
        [
            (False, False, ConfigNotFoundError),
            (True, False, DirectoryNotFoundError),
            (True, True, NoVideosFoundError),
        ],
        ids=["missing-config", "missing-input", "empty-input"],
    )
    def test_prepare_preflight_missing_inputs(
        self,
        tmp_path: Path,
        has_config: bool,
        has_input_dir: bool,
        error_type: type[ConfigNotFoundError]
        | type[DirectoryNotFoundError]
        | type[NoVideosFoundError],
    ) -> None:
        if has_config:
            _create_config(tmp_path)
        input_dir = tmp_path / "comparison_videos"
        if has_input_dir:
            input_dir.mkdir(parents=True)
        with pytest.raises(error_type) as exc_info:
            prepare_preflight(root=tmp_path)
        if has_input_dir:
            error = exc_info.value
            assert isinstance(error, NoVideosFoundError)
            assert error.path == input_dir.resolve()
            assert "*.mkv" in error.patterns

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
