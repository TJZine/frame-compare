"""CLI entry + runner orchestration regression tests."""

from __future__ import annotations

import asyncio
import types
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, ClassVar, cast

import click
import pytest
from click.testing import CliRunner, Result
from rich.console import Console

import frame_compare
import src.frame_compare.core as core_module
import src.frame_compare.tmdb_workflow as tmdb_utils
from src.analysis import CacheLoadResult, FrameMetricsCacheInfo, SelectionDetail
from src.datatypes import (
    AnalysisConfig,
    AppConfig,
    AudioAlignmentConfig,
    CLIConfig,
    ColorConfig,
    NamingConfig,
    OverridesConfig,
    PathsConfig,
    ReportConfig,
    RuntimeConfig,
    ScreenshotConfig,
    SlowpicsConfig,
    SourceConfig,
    TMDBConfig,
)
from src.frame_compare import runner as runner_module
from src.frame_compare.cli_runtime import CliOutputManager
from tests.helpers.runner_env import (
    _CliRunnerEnv,
    _make_config,
    _make_runner_preflight,
    _patch_core_helper,
    _patch_load_config,
    _patch_runner_module,
    _patch_vs_core,
    _selection_details_to_json,
)

pytestmark = pytest.mark.usefixtures("runner_vs_core_stub", "dummy_progress")  # type: ignore[attr-defined]


def test_runner_no_impl_attrs() -> None:
    """Helper indirection list was removed in favor of direct imports."""

    import importlib

    runner_refreshed = importlib.reload(runner_module)
    assert not hasattr(runner_refreshed, "_IMPL_ATTRS")

@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("analysis.frame_data_filename", "../escape.compframes"),
        ("analysis.frame_data_filename", "/tmp/outside.compframes"),
        ("audio_alignment.offsets_filename", "../escape_offsets.toml"),
        ("audio_alignment.offsets_filename", "/tmp/outside_offsets.toml"),
    ),
)
def test_run_cli_rejects_subpath_escape(
    cli_runner_env: _CliRunnerEnv,
    field: str,
    value: str,
) -> None:
    """
    Ensure run_cli refuses cache or offsets paths that escape the media root.
    """

    cfg = cli_runner_env.cfg
    section_name, attr_name = field.split(".")
    setattr(getattr(cfg, section_name), attr_name, value)

    cli_runner_env.reinstall(cfg)

    with pytest.raises(core_module.CLIAppError) as excinfo:
        frame_compare.run_cli(None, None)

    assert field in str(excinfo.value)

def test_validate_tonemap_overrides_accepts_valid_values() -> None:
    core_module._validate_tonemap_overrides(
        {
            "knee_offset": 0.5,
            "dst_min_nits": 0.0,
            "target_nits": 250.0,
            "post_gamma": 0.95,
            "dpd_preset": "fast",
            "dpd_black_cutoff": 0.02,
            "smoothing_period": 5.0,
            "scene_threshold_low": 0.5,
            "scene_threshold_high": 1.5,
            "percentile": 99.9,
            "contrast_recovery": 0.2,
            "metadata": "hdr10",
            "use_dovi": True,
            "visualize_lut": False,
            "show_clipping": True,
        }
    )

def test_validate_tonemap_overrides_rejects_invalid_cutoff() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"dpd_black_cutoff": 0.2})

def test_validate_tonemap_overrides_rejects_bad_knee() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"knee_offset": 1.5})

def test_validate_tonemap_overrides_rejects_bad_gamma() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"post_gamma": 1.5})

def test_validate_tonemap_overrides_rejects_bad_preset() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"dpd_preset": "turbo"})

def test_validate_tonemap_overrides_rejects_bad_percentile() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"percentile": 120.0})

def test_validate_tonemap_overrides_rejects_scene_range() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides(
            {"scene_threshold_low": 2.0, "scene_threshold_high": 1.0}
        )

def test_validate_tonemap_overrides_rejects_unknown_metadata() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"metadata": "foobar"})

def test_validate_tonemap_overrides_rejects_nonfinite_numbers() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"dst_min_nits": float("nan")})

def test_validate_tonemap_overrides_rejects_nonpositive_target_nits() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"target_nits": 0})

def test_validate_tonemap_overrides_rejects_infinite_scene_threshold() -> None:
    with pytest.raises(click.ClickException):
        core_module._validate_tonemap_overrides({"scene_threshold_low": float("inf")})

def test_cli_applies_overrides_and_naming(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "AAA - 01.mkv"
    second = cli_runner_env.media_root / "BBB - 01.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cli_runner_env.reinstall(cfg)

    parse_calls: list[tuple[str, dict[str, object]]] = []

    def fake_parse(name: str, **kwargs: object) -> dict[str, object]:
        parse_calls.append((name, dict(kwargs)))
        if name.startswith("AAA"):
            return {"label": "AAA Short", "release_group": "AAA", "file_name": name}
        return {"label": "BBB Short", "release_group": "BBB", "file_name": name}

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    ram_limits: list[int] = []
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit_mb: ram_limits.append(int(limit_mb)))

    init_calls: list[tuple[str, int, int | None, tuple[int, int] | None, str | None]] = []

    def fake_init_clip(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
        **_kwargs: object,
    ) -> types.SimpleNamespace:
        clip = types.SimpleNamespace(
            path=path,
            width=1920,
            height=1080,
            fps_num=24000,
            fps_den=1001,
            num_frames=24000,
        )
        init_calls.append((path, trim_start, trim_end, fps_map, cache_dir))
        return clip

    _patch_vs_core(monkeypatch, "init_clip", fake_init_clip)

    cache_infos: list[FrameMetricsCacheInfo | None] = []

    def fake_select(
        clip: types.SimpleNamespace,
        analysis_cfg: AnalysisConfig,
        files: list[str],
        file_under_analysis: str,
        cache_info: FrameMetricsCacheInfo | None = None,
        progress: object = None,
        *,
        frame_window: tuple[int, int] | None = None,
        return_metadata: bool = False,
        color_cfg: ColorConfig | None = None,
        cache_probe: CacheLoadResult | None = None,
    ) -> list[int]:
        cache_infos.append(cache_info)
        assert frame_window is not None
        assert isinstance(frame_window, tuple)
        return [10, 20]

    _patch_runner_module(monkeypatch, "select_frames", fake_select)

    generated_metadata: list[list[dict[str, object]]] = []

    def fake_generate(
        clips: list[types.SimpleNamespace],
        frames: list[int],
        files: list[str],
        metadata: list[dict[str, object]],
        out_dir: Path,
        cfg_screens: ScreenshotConfig,
        color_cfg: ColorConfig,
        **kwargs: object,
    ) -> list[str]:
        generated_metadata.append(metadata)
        assert kwargs.get("trim_offsets") == [5, 0]
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(files))]

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

    result: Result = runner.invoke(frame_compare.main, ["--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "[DISCOVER]" in result.output
    assert "• ref=AAA Short" in result.output
    assert "• tgt=BBB Short" in result.output

    assert "[PREPARE]" in result.output
    assert "• Ref: lead=  5f" in result.output
    assert "• Tgt: lead=  0f" in result.output
    assert "ignore_lead=0.00s" in result.output
    assert "[SUMMARY]" in result.output
    assert "• Clips:" in result.output
    assert "Output frames (" in result.output

    assert ram_limits == [cfg.runtime.ram_limit_mb]

    expected_cache_dir = str(cli_runner_env.media_root.resolve())
    assert len(init_calls) >= 2
    # Reference clip (BBB) initialised without fps override but with trim_end applied
    assert (str(second), 0, -12, None, expected_cache_dir) in init_calls
    # First clip adopts reference fps and trim override
    assert (str(first), 5, None, (24000, 1001), expected_cache_dir) in init_calls

    assert generated_metadata
    first_meta = generated_metadata[0][0]
    second_meta = generated_metadata[0][1]
    assert cast(str, first_meta["label"]).startswith("AAA")
    assert cast(str, second_meta["label"]).startswith("BBB")

    assert cache_infos and cache_infos[0] is not None
    cache_info = cache_infos[0]
    assert cache_info.path == (cli_runner_env.media_root / cfg.analysis.frame_data_filename).resolve()
    assert cache_info.files == ["AAA - 01.mkv", "BBB - 01.mkv"]
    assert len(parse_calls) == 2

def test_run_cli_falls_back_to_project_root_for_relative_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Ensure run_cli resolves a relative input directory using the project root fallback.

    The config reports "comparison_videos" as the input directory and the test executes from a
    temporary working directory so the initial resolution fails. The helper should then fall back
    to `<repo>/comparison_videos`, which we verify by intercepting `_discover_media`.
    """

    cfg = _make_config(Path("comparison_videos"))

    _patch_load_config(monkeypatch, cfg)
    _patch_vs_core(monkeypatch, "configure", lambda *args, **kwargs: None)

    recorded_roots: list[Path] = []

    def fake_discover(root: Path) -> list[Path]:
        recorded_roots.append(root)
        raise core_module.CLIAppError("sentinel")

    _patch_core_helper(monkeypatch, "_discover_media", fake_discover)

    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.toml"

    with pytest.raises(core_module.CLIAppError, match="sentinel"):
        frame_compare.run_cli(str(config_path))

    expected_root = (tmp_path / "comparison_videos").resolve()
    assert recorded_roots == [expected_root]

def test_run_cli_does_not_fallback_for_cli_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure run_cli reports missing CLI overrides instead of using fallbacks."""

    cfg = _make_config(tmp_path)

    _patch_load_config(monkeypatch, cfg)
    def _fail_discover(*_args: object, **_kwargs: object) -> list[Path]:
        raise AssertionError("should not discover")

    _patch_core_helper(monkeypatch, "_discover_media", _fail_discover)

    config_path = tmp_path / "config.toml"
    monkeypatch.chdir(tmp_path)

    with pytest.raises(core_module.CLIAppError, match="Input directory not found"):
        frame_compare.run_cli(str(config_path), input_dir="comparison_videos")

def test_cli_disables_json_tail_output(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "AAA - 01.mkv"
    second = cli_runner_env.media_root / "BBB - 01.mkv"
    for file_path in (first, second):
        file_path.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.cli.emit_json_tail = False

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **kwargs: object) -> dict[str, str]:
        """
        Produce a minimal parsed filename metadata dictionary.

        Parameters:
            name (str): The filename or label to use for the parsed metadata.
            **kwargs: Additional keyword arguments are accepted and ignored.

        Returns:
            dict: A mapping with keys:
                - "label": same as `name`
                - "release_group": empty string
                - "file_name": same as `name`
        """
        return {"label": name, "release_group": "", "file_name": name}

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    def fake_init(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
        **_kwargs: object,
    ) -> types.SimpleNamespace:
        """
        Create a fake clip-like object with fixed video properties.

        Parameters:
            path (str | Path): Input path (accepted but ignored).
            trim_start (int): Trim start in frames (accepted but ignored).
            trim_end (int | None): Trim end in frames (accepted but ignored).
            fps_map (Any): FPS mapping (accepted but ignored).
            cache_dir (str | Path | None): Cache directory (accepted but ignored).

        Returns:
            types.SimpleNamespace: An object with attributes:
                - width (int): 1920
                - height (int): 1080
                - fps_num (int): 24000
                - fps_den (int): 1001
                - num_frames (int): 600
        """
        return types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=600)

    _patch_vs_core(monkeypatch, "init_clip", fake_init)

    def fake_select(
        clip: types.SimpleNamespace,
        cfg: AnalysisConfig,
        files: list[str],
        file_under_analysis: str,
        cache_info: FrameMetricsCacheInfo | None = None,
        progress: object = None,
        *,
        frame_window: tuple[int, int] | None = None,
        return_metadata: bool = False,
        color_cfg: ColorConfig | None = None,
        cache_probe: CacheLoadResult | None = None,
    ) -> list[int]:
        return [12]

    _patch_runner_module(monkeypatch, "select_frames", fake_select)

    def fake_generate(
        clips: list[types.SimpleNamespace],
        frames: list[int],
        files: list[str],
        metadata: list[dict[str, object]],
        out_dir: Path,
        cfg_screens: ScreenshotConfig,
        color_cfg: ColorConfig,
        **kwargs: object,
    ) -> list[str]:
        """
        Produce a single placeholder screenshot file inside out_dir and return its path.

        Parameters:
            out_dir (Path): Directory to create and place the placeholder image.
            **kwargs: Ignored; accepted for compatibility with the real generator.

        Returns:
            List[str]: A list containing the string path to "frame.png" created under out_dir.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / "frame.png")]

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

    result: Result = runner.invoke(frame_compare.main, ["--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert '{"analysis"' not in result.output

def test_label_dedupe_preserves_short_labels(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "Group - 01.mkv"
    second = cli_runner_env.media_root / "Group - 02.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = AppConfig(
        analysis=AnalysisConfig(frame_count_dark=0, frame_count_bright=0, frame_count_motion=0, random_frames=0),
        screenshots=ScreenshotConfig(directory_name="screens", add_frame_info=False),
        cli=CLIConfig(),
        color=ColorConfig(),
        slowpics=SlowpicsConfig(auto_upload=False),
        tmdb=TMDBConfig(),
        naming=NamingConfig(always_full_filename=False, prefer_guessit=False),
        paths=PathsConfig(input_dir=str(cli_runner_env.media_root)),
        runtime=RuntimeConfig(ram_limit_mb=1024),
        overrides=OverridesConfig(),
        source=SourceConfig(),
        audio_alignment=AudioAlignmentConfig(enable=False),
        report=ReportConfig(enable=False),
    )

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **kwargs: object) -> dict[str, str]:
        return {"label": "[Group]", "release_group": "Group", "file_name": name}

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    def fake_init_clip(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
        **_kwargs: object,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400)

    _patch_vs_core(monkeypatch, "init_clip", fake_init_clip)
    def fake_select(
        clip: types.SimpleNamespace,
        cfg: AnalysisConfig,
        files: list[str],
        file_under_analysis: str,
        cache_info: FrameMetricsCacheInfo | None = None,
        progress: object = None,
        *,
        frame_window: tuple[int, int] | None = None,
        return_metadata: bool = False,
        color_cfg: ColorConfig | None = None,
        cache_probe: CacheLoadResult | None = None,
    ) -> list[int]:
        return [42]

    _patch_runner_module(monkeypatch, "select_frames", fake_select)

    captured: list[list[str]] = []

    def fake_generate(
        clips: list[types.SimpleNamespace],
        frames: list[int],
        files: list[str],
        metadata: list[dict[str, object]],
        out_dir: Path,
        cfg_screens: ScreenshotConfig,
        color_cfg: ColorConfig,
        **kwargs: object,
    ) -> list[str]:
        captured.append([str(meta["label"]) for meta in metadata])
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / "shot.png")]

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

    result: Result = runner.invoke(frame_compare.main, ["--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert captured
    labels = captured[0]
    assert len(labels) == 2
    assert labels[0] != first.name and labels[1] != second.name
    assert labels[0] != labels[1]

def test_cli_reuses_frame_cache(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    files = [cli_runner_env.media_root / "A.mkv", cli_runner_env.media_root / "B.mkv"]
    for file in files:
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.analysis.save_frames_data = True

    cli_runner_env.reinstall(cfg)

    def fake_init(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
        **_kwargs: object,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800)

    _patch_vs_core(monkeypatch, "init_clip", fake_init)

    call_state: dict[str, int] = {"calls": 0, "cache_hits": 0}

    def fake_select(
        clip: types.SimpleNamespace,
        analysis_cfg: AnalysisConfig,
        selected_files: list[str],
        file_under_analysis: str,
        cache_info: FrameMetricsCacheInfo | None = None,
        progress: object = None,
        *,
        frame_window: tuple[int, int] | None = None,
        return_metadata: bool = False,
        color_cfg: ColorConfig | None = None,
        cache_probe: CacheLoadResult | None = None,
    ) -> list[int]:
        call_state["calls"] += 1
        assert cache_info is not None
        assert frame_window is not None
        if cache_info.path.exists():
            call_state["cache_hits"] += 1
        else:
            cache_info.path.write_text("cached", encoding="utf-8")
        return [12]

    _patch_runner_module(monkeypatch, "select_frames", fake_select)

    def fake_generate(
        clips: list[types.SimpleNamespace],
        frames: list[int],
        files_for_run: list[str],
        metadata: list[dict[str, object]],
        out_dir: Path,
        cfg_screens: ScreenshotConfig,
        color_cfg: ColorConfig,
        **kwargs: object,
    ) -> list[str]:
        out_dir.mkdir(parents=True, exist_ok=True)
        for index in range(len(clips)):
            (out_dir / f"shot_{index}.png").write_text("data", encoding="utf-8")
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(clips))]

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

    runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)

    assert call_state["calls"] == 2
    assert call_state["cache_hits"] == 1

def test_runner_quiet_uses_null_reporter(
    monkeypatch: pytest.MonkeyPatch, cli_runner_env: _CliRunnerEnv
) -> None:
    """When quiet=True the runner should instantiate the null reporter instead of the CLI renderer."""

    cli_runner_env.reinstall()
    sentinel = RuntimeError("stop")

    def _raise_stop(*_: object) -> list[Path]:
        raise sentinel

    _patch_core_helper(monkeypatch, "_discover_media", _raise_stop)

    created: list[str] = []

    class _RecorderNull(runner_module.NullCliOutputManager):
        def __init__(self, **kwargs: Any) -> None:
            created.append("null")
            super().__init__(**kwargs)

    class _RecorderCli(CliOutputManager):
        def __init__(self, **kwargs: Any) -> None:
            created.append("cli")
            super().__init__(**kwargs)

    monkeypatch.setattr(runner_module, "NullCliOutputManager", _RecorderNull)
    monkeypatch.setattr(runner_module, "CliOutputManager", _RecorderCli)
    monkeypatch.setattr(frame_compare, "NullCliOutputManager", _RecorderNull)
    monkeypatch.setattr(frame_compare, "CliOutputManager", _RecorderCli)

    request = runner_module.RunRequest(
        config_path=str(cli_runner_env.config_path),
        quiet=True,
    )

    with pytest.raises(RuntimeError, match="stop"):
        runner_module.run(request)

    assert created == ["null"]

def test_runner_reporter_factory_overrides_default(
    monkeypatch: pytest.MonkeyPatch, cli_runner_env: _CliRunnerEnv
) -> None:
    """Programmatic callers can inject a custom reporter factory."""

    cli_runner_env.reinstall()
    sentinel = RuntimeError("stop")

    def _raise_stop(*_: object) -> list[Path]:
        raise sentinel

    _patch_core_helper(monkeypatch, "_discover_media", _raise_stop)

    class _FailingReporter:
        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - should not run
            raise AssertionError("Default CliOutputManager should not be used when a reporter factory is provided")

    monkeypatch.setattr(runner_module, "CliOutputManager", _FailingReporter)

    factory_calls: list[Path] = []

    def reporter_factory(
        request: runner_module.RunRequest,
        layout_path: Path,
        console: Console,
    ) -> CliOutputManager:
        factory_calls.append(layout_path)
        return CliOutputManager(
            quiet=request.quiet,
            verbose=request.verbose,
            no_color=request.no_color,
            layout_path=layout_path,
            console=console,
        )

    request = runner_module.RunRequest(
        config_path=str(cli_runner_env.config_path),
        reporter_factory=reporter_factory,
    )

    with pytest.raises(RuntimeError, match="stop"):
        runner_module.run(request)

    assert len(factory_calls) == 1

def test_runner_uses_explicit_reporter_instance(
    monkeypatch: pytest.MonkeyPatch, cli_runner_env: _CliRunnerEnv
) -> None:
    """RunRequest.reporter shortcuts the default reporter construction."""

    cli_runner_env.reinstall()
    sentinel = RuntimeError("stop")

    def _raise_stop(*_: object) -> list[Path]:
        raise sentinel

    _patch_core_helper(monkeypatch, "_discover_media", _raise_stop)

    created: list[str] = []

    class _FailingReporter(CliOutputManager):
        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - should not run
            created.append("default")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(runner_module, "CliOutputManager", _FailingReporter)
    monkeypatch.setattr(frame_compare, "CliOutputManager", _FailingReporter)
    monkeypatch.setattr(runner_module, "NullCliOutputManager", _FailingReporter)
    monkeypatch.setattr(frame_compare, "NullCliOutputManager", _FailingReporter)

    layout_path = Path(frame_compare.__file__).with_name("cli_layout.v1.json")
    custom_reporter = CliOutputManager(
        quiet=False,
        verbose=False,
        no_color=False,
        layout_path=layout_path,
        console=Console(width=80, record=True),
    )

    request = runner_module.RunRequest(
        config_path=str(cli_runner_env.config_path),
        reporter=custom_reporter,
    )

    with pytest.raises(RuntimeError, match="stop"):
        runner_module.run(request)

    assert created == []

def test_runner_handles_existing_event_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    media_root = workspace / "media"
    workspace.mkdir(parents=True, exist_ok=True)
    media_root.mkdir(parents=True, exist_ok=True)
    for name in ("Alpha.mkv", "Beta.mkv"):
        (media_root / name).write_bytes(b"data")

    cfg = _make_config(media_root)
    cfg.tmdb.api_key = "token"
    cfg.slowpics.auto_upload = False
    cfg.analysis.frame_count_dark = 0
    cfg.analysis.frame_count_bright = 0
    cfg.analysis.frame_count_motion = 0
    cfg.analysis.random_frames = 0
    cfg.analysis.save_frames_data = False

    preflight = _make_runner_preflight(workspace, media_root, cfg)
    _patch_core_helper(monkeypatch, "prepare_preflight", lambda **_: preflight)

    files = [media_root / "Alpha.mkv", media_root / "Beta.mkv"]
    metadata = [{"label": "Alpha"}, {"label": "Beta"}]
    plans = [
        core_module._ClipPlan(path=files[0], metadata={"label": "Alpha"}),
        core_module._ClipPlan(path=files[1], metadata={"label": "Beta"}),
    ]
    plans[0].use_as_reference = True

    _patch_core_helper(monkeypatch, "_discover_media", lambda _root: list(files))
    _patch_core_helper(monkeypatch, "parse_metadata", lambda *_: list(metadata))
    _patch_core_helper(monkeypatch, "_build_plans", lambda *_: list(plans))
    monkeypatch.setattr(runner_module.core, "_pick_analyze_file", lambda *_args, **_kwargs: files[0])

    cache_info = FrameMetricsCacheInfo(
        path=workspace / cfg.analysis.frame_data_filename,
        files=[file.name for file in files],
        analyzed_file=files[0].name,
        release_group="",
        trim_start=0,
        trim_end=None,
        fps_num=24000,
        fps_den=1001,
    )
    _patch_core_helper(monkeypatch, "_build_cache_info", lambda *_: cache_info)
    _patch_core_helper(monkeypatch, "_maybe_apply_audio_alignment", lambda *args, **kwargs: (None, None))

    monkeypatch.setattr(runner_module.vs_core, "configure", lambda **_: None)
    monkeypatch.setattr(runner_module.vs_core, "set_ram_limit", lambda *_: None)
    monkeypatch.setattr(
        runner_module.vs_core,
        "init_clip",
        lambda *args, **kwargs: types.SimpleNamespace(
            width=1280,
            height=720,
            fps_num=24000,
            fps_den=1001,
            num_frames=120,
        ),
    )

    def fake_select(*_args, **_kwargs):
        selection_details = {
            10: SelectionDetail(
                frame_index=10,
                label="Auto",
                score=None,
                source="Test",
                timecode="00:00:10.0",
            )
        }
        return [10], {10: "Auto"}, selection_details

    monkeypatch.setattr(runner_module, "select_frames", fake_select)
    monkeypatch.setattr(runner_module, "selection_details_to_json", _selection_details_to_json)
    monkeypatch.setattr(
        runner_module,
        "probe_cached_metrics",
        lambda *_: CacheLoadResult(metrics=None, status="missing", reason=None),
    )
    monkeypatch.setattr(runner_module, "selection_hash_for_config", lambda *_: "selection-hash")
    monkeypatch.setattr(runner_module, "write_selection_cache_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner_module, "export_selection_metadata", lambda *args, **kwargs: None)

    def fake_generate(
        clips: Sequence[object],
        frames: Sequence[int],
        files_for_run: Sequence[Path],
        metadata_list: Sequence[Mapping[str, Any]],
        out_dir: Path,
        cfg_screens: ScreenshotConfig,
        color_cfg: ColorConfig,
        **kwargs: Any,
    ) -> list[str]:
        out_dir.mkdir(parents=True, exist_ok=True)
        shot = out_dir / "shot.png"
        shot.write_text("data", encoding="utf-8")
        return [str(shot)]

    monkeypatch.setattr(runner_module, "generate_screenshots", fake_generate)

    tmdb_calls: list[dict[str, object]] = []

    def fake_tmdb_workflow(**kwargs: object) -> tmdb_utils.TMDBLookupResult:
        tmdb_calls.append(kwargs)
        return tmdb_utils.TMDBLookupResult(
            resolution=None,
            manual_override=None,
            error_message=None,
            ambiguous=False,
        )

    monkeypatch.setattr(tmdb_utils, "resolve_workflow", fake_tmdb_workflow)

    request = runner_module.RunRequest(
        config_path=str(preflight.config_path),
        root_override=str(workspace),
    )

    async def _invoke() -> runner_module.RunResult:
        return runner_module.run(request)

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_invoke())
    finally:
        loop.close()
    assert result.frames == [10]
    assert tmdb_calls, "TMDB helper should be invoked once"

def test_run_cli_coalesces_duplicate_pivot_logs(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    """Duplicate pivot notifications are emitted once per run."""

    cfg = _make_config(cli_runner_env.media_root)
    cfg.analysis.save_frames_data = False

    cli_runner_env.reinstall(cfg)

    for name in ("Alpha.mkv", "Beta.mkv"):
        (cli_runner_env.media_root / name).write_bytes(b"data")

    def fake_parse(name: str, **_: object) -> dict[str, str]:
        return {
            "label": name,
            "file_name": name,
            "title": "",
            "anime_title": "",
            "year": "",
            "imdb_id": "",
            "tvdb_id": "",
        }

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)
    _patch_vs_core(monkeypatch, "configure", lambda *args, **kwargs: None)
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda *args, **kwargs: None)

    def fake_init_clip(
        path: str | Path,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | Path | None = None,
        **_kwargs: object,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            path=Path(path),
            width=1920,
            height=1080,
            fps_num=24000,
            fps_den=1001,
            num_frames=120,
        )

    _patch_vs_core(monkeypatch, "init_clip", fake_init_clip)
    _patch_vs_core(monkeypatch, "resolve_effective_tonemap", lambda _cfg: {})

    def fake_select(
        clip: types.SimpleNamespace,
        analysis_cfg: AnalysisConfig,
        files: list[str],
        file_under_analysis: str,
        *,
        cache_info: FrameMetricsCacheInfo | None = None,
        progress: Callable[[int], None] | None = None,
        frame_window: tuple[int, int] | None = None,
        return_metadata: bool = False,
        color_cfg: ColorConfig | None = None,
        cache_probe: CacheLoadResult | None = None,
    ) -> tuple[list[int], dict[int, str], dict[int, SelectionDetail]]:
        if progress is not None:
            progress(1)
        frames = [10, 20]
        categories = {10: "Auto", 20: "Auto"}
        details = {
            10: SelectionDetail(
                frame_index=10,
                label="Auto",
                score=None,
                source="auto",
                timecode="00:00:10.000",
            ),
            20: SelectionDetail(
                frame_index=20,
                label="Auto",
                score=None,
                source="auto",
                timecode="00:00:20.000",
            ),
        }
        return frames, categories, details

    _patch_runner_module(monkeypatch, "select_frames", fake_select)

    class RecordingConsole(Console):
        pivot_logs: ClassVar[list[str]] = []

        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)

        def log(self, *objects: object, **_kwargs: object) -> None:  # type: ignore[override]
            message = objects[0] if objects else ""
            RecordingConsole.pivot_logs.append(str(message))

    RecordingConsole.pivot_logs = []
    monkeypatch.setattr(frame_compare, "Console", RecordingConsole)

    def fake_generate(
        clips: list[types.SimpleNamespace],
        frames: list[int],
        files: list[str],
        metadata: list[dict[str, object]],
        out_dir: Path,
        cfg_screens: ScreenshotConfig,
        color_cfg: ColorConfig,
        **kwargs: object,
    ) -> list[str]:
        pivot_notifier = kwargs.get("pivot_notifier")
        if callable(pivot_notifier):
            pivot_notifier("Full-chroma pivot active (YUV444P16)")
            pivot_notifier("Full-chroma pivot active (YUV444P16)")
            pivot_notifier("Full-chroma pivot resolved")
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(files))]

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)
    _patch_runner_module(monkeypatch, "export_selection_metadata", lambda *args, **kwargs: None)
    _patch_runner_module(monkeypatch, "write_selection_cache_file", lambda *args, **kwargs: None)

    result = frame_compare.run_cli(None, None)

    assert result.image_paths
    assert RecordingConsole.pivot_logs == [
        "Full-chroma pivot active (YUV444P16)",
        "Full-chroma pivot resolved",
    ]
