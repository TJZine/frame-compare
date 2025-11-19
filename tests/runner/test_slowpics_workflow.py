"""Slowpics + TMDB workflow regression tests for the runner CLI."""

from __future__ import annotations

import types
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, SupportsIndex, cast, overload

import pytest
from click.testing import CliRunner, Result

import frame_compare
import src.frame_compare.core as core_module
import src.frame_compare.tmdb_workflow as tmdb_utils
from src.datatypes import (
    AnalysisConfig,
    AppConfig,
    AudioAlignmentConfig,
    CLIConfig,
    ColorConfig,
    DiagnosticsConfig,
    NamingConfig,
    OverridesConfig,
    PathsConfig,
    ReportConfig,
    RunnerConfig,
    RuntimeConfig,
    ScreenshotConfig,
    SlowpicsConfig,
    SourceConfig,
    TMDBConfig,
)
from src.frame_compare import runner as runner_module
from src.frame_compare.analysis import CacheLoadResult, FrameMetricsCacheInfo, SelectionDetail
from src.frame_compare.services.publishers import UploadProgressTracker
from src.tmdb import TMDBAmbiguityError, TMDBCandidate, TMDBResolution, TMDBResolutionError
from tests.helpers.runner_env import (
    _CliRunnerEnv,
    _expect_mapping,
    _make_config,
    _make_runner_preflight,
    _patch_core_helper,
    _patch_load_config,
    _patch_runner_module,
    _patch_vs_core,
    _selection_details_to_json,
)

pytestmark = pytest.mark.usefixtures("runner_vs_core_stub", "dummy_progress")  # type: ignore[attr-defined]


def test_cli_input_override_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
) -> None:
    default_dir = tmp_path / "default"
    default_dir.mkdir()
    override_dir = tmp_path / "override"
    override_dir.mkdir()
    files = [override_dir / "A.mkv", override_dir / "B.mkv"]
    for file in files:
        file.write_bytes(b"data")

    cfg = AppConfig(
        analysis=AnalysisConfig(frame_count_dark=0, frame_count_bright=0, frame_count_motion=0, random_frames=0),
        screenshots=ScreenshotConfig(directory_name="screens", add_frame_info=False),
        cli=CLIConfig(),
        runner=RunnerConfig(),
        color=ColorConfig(),
        slowpics=SlowpicsConfig(auto_upload=True, delete_screen_dir_after_upload=True, open_in_browser=False, create_url_shortcut=False),
        tmdb=TMDBConfig(),
        naming=NamingConfig(always_full_filename=True, prefer_guessit=False),
        paths=PathsConfig(input_dir=str(default_dir)),
        runtime=RuntimeConfig(ram_limit_mb=1024),
        overrides=OverridesConfig(),
        source=SourceConfig(),
        audio_alignment=AudioAlignmentConfig(enable=False),
        report=ReportConfig(enable=False),
        diagnostics=DiagnosticsConfig(),
    )

    _patch_load_config(monkeypatch, cfg)

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
        return [7]

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
        path = out_dir / "image.png"
        path.write_text("img", encoding="utf-8")
        return [str(path)]

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

    uploads: list[tuple[list[str], Path]] = []

    def fake_upload(
        image_paths: list[str],
        screen_dir: Path,
        cfg_slow: SlowpicsConfig,
        **kwargs: object,
    ) -> str:
        uploads.append((image_paths, screen_dir))
        return "https://slow.pics/c/abc/def"

    _patch_runner_module(monkeypatch, "upload_comparison", fake_upload)

    result: Result = runner.invoke(
        frame_compare.main,
        ["--input", str(override_dir), "--no-color", "--legacy-runner"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert uploads
    screen_dir = Path(override_dir / cfg.screenshots.directory_name).resolve()
    assert not screen_dir.exists()
    assert uploads[0][1] == screen_dir

def test_runner_auto_upload_cleans_screens_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    media_root = workspace / "media"
    workspace.mkdir(parents=True, exist_ok=True)
    media_root.mkdir(parents=True, exist_ok=True)
    for name in ("Alpha.mkv", "Beta.mkv"):
        (media_root / name).write_bytes(b"data")

    cfg = _make_config(media_root)
    cfg.tmdb.api_key = "token"
    cfg.analysis.frame_count_dark = 0
    cfg.analysis.frame_count_bright = 0
    cfg.analysis.frame_count_motion = 0
    cfg.analysis.random_frames = 0
    cfg.analysis.save_frames_data = False
    cfg.report.enable = False
    cfg.slowpics.auto_upload = True
    cfg.slowpics.delete_screen_dir_after_upload = True
    cfg.slowpics.open_in_browser = False
    cfg.slowpics.create_url_shortcut = False
    monkeypatch.setattr(
        tmdb_utils,
        "resolve_workflow",
        lambda **_: tmdb_utils.TMDBLookupResult(
            resolution=None,
            manual_override=None,
            error_message=None,
            ambiguous=False,
        ),
    )

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

    def fake_init_clip(*_args, **_kwargs):
        return types.SimpleNamespace(
            width=1280,
            height=720,
            fps_num=24000,
            fps_den=1001,
            num_frames=120,
        )

    monkeypatch.setattr(runner_module.vs_core, "init_clip", fake_init_clip)

    def fake_select(
        *_args,
        **_kwargs,
    ):
        selection_details = {
            10: SelectionDetail(frame_index=10, label="Auto", score=None, source="Test", timecode="00:00:10.0")
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

    uploads: list[tuple[list[str], Path]] = []

    def fake_upload(image_paths, screen_dir, cfg_slow, **kwargs):
        uploads.append((list(image_paths), screen_dir))
        return "https://slow.pics/test"

    monkeypatch.setattr(runner_module, "upload_comparison", fake_upload)
    monkeypatch.setattr(runner_module, "build_shortcut_filename", lambda *_: "slowpics.url")

    monkeypatch.setattr(runner_module, "impl", frame_compare, raising=False)
    request = runner_module.RunRequest(
        config_path=str(preflight.config_path),
        root_override=str(workspace),
        service_mode_override=False,
    )
    result = runner_module.run(request)

    assert uploads, "Slow.pics upload should be invoked"
    assert result.slowpics_url == "https://slow.pics/test"
    assert result.json_tail is not None
    slowpics_json = _expect_mapping(result.json_tail["slowpics"])
    assert slowpics_json["url"] == "https://slow.pics/test"

def test_cli_tmdb_resolution_populates_slowpics(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "SourceA.mkv"
    second = cli_runner_env.media_root / "SourceB.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.tmdb.api_key = "token"
    cfg.slowpics.auto_upload = True
    cfg.slowpics.collection_name = "${Title} (${Year}) [${TMDBCategory}]"
    cfg.slowpics.delete_screen_dir_after_upload = False

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **_: object) -> dict[str, str]:
        return {
            "label": name,
            "release_group": "",
            "file_name": name,
            "title": "Metadata Title",
            "year": "2020",
            "anime_title": "",
            "imdb_id": "",
            "tvdb_id": "",
        }

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    candidate = TMDBCandidate(
        category="MOVIE",
        tmdb_id="12345",
        title="Resolved Title",
        original_title="Original Title",
        year=2023,
        score=0.95,
        original_language="en",
        reason="primary-title",
        used_filename_search=True,
        payload={"id": 12345},
    )
    resolution = TMDBResolution(candidate=candidate, margin=0.4, source_query="Resolved")

    async def fake_resolve(*_, **__):  # pragma: no cover - simple stub
        return resolution

    _patch_runner_module(monkeypatch, "resolve_tmdb", fake_resolve)
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)

    def fake_init(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
        **_kwargs: object,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            width=1280,
            height=720,
            fps_num=24000,
            fps_den=1001,
            num_frames=1800,
        )

    _patch_vs_core(monkeypatch, "init_clip", fake_init)

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
        assert frame_window is not None
        return [12, 24]

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
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(files))]

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

    uploads: list[tuple[list[str], Path, str, str]] = []

    def fake_upload(
        image_paths: list[str],
        screen_dir: Path,
        cfg_slow: SlowpicsConfig,
        **kwargs: object,
    ) -> str:
        uploads.append((list(image_paths), screen_dir, cfg_slow.tmdb_id, cfg_slow.collection_name))
        return "https://slow.pics/c/example"

    _patch_runner_module(monkeypatch, "upload_comparison", fake_upload)


    result = frame_compare.run_cli(None, None, service_mode_override=False)

    assert uploads
    _, _, upload_tmdb_id, upload_collection = uploads[0]
    assert upload_tmdb_id == "12345"
    assert "Resolved Title (2023)" in upload_collection
    assert result.config.slowpics.tmdb_id == "12345"
    assert result.config.slowpics.tmdb_category == "MOVIE"
    assert result.config.slowpics.collection_name == "Resolved Title (2023) [MOVIE]"
    assert result.json_tail is not None
    slowpics_value = result.json_tail.get("slowpics")
    assert slowpics_value is not None
    slowpics_json = _expect_mapping(slowpics_value)
    title_json = _expect_mapping(slowpics_json["title"])
    inputs_json = _expect_mapping(title_json["inputs"])
    assert title_json["final"] == "Resolved Title (2023) [MOVIE]"
    assert inputs_json["resolved_base"] == "Resolved Title (2023)"
    assert slowpics_json["url"] == "https://slow.pics/c/example"
    assert slowpics_json["shortcut_path"].endswith("Resolved_Title_2023_MOVIE.url")
    assert slowpics_json["deleted_screens_dir"] is False


def test_shortcut_write_failure_sets_json_tail(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "Alpha.mkv"
    second = cli_runner_env.media_root / "Beta.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.tmdb.api_key = "token"
    cfg.slowpics.auto_upload = True
    cfg.slowpics.collection_name = "Shortcut Failure"
    cfg.slowpics.delete_screen_dir_after_upload = False
    cfg.slowpics.create_url_shortcut = True
    cfg.slowpics.open_in_browser = False

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **_: object) -> dict[str, str]:
        return {
            "label": name,
            "release_group": "",
            "file_name": name,
            "title": "Alpha Title",
            "year": "2022",
            "anime_title": "",
            "imdb_id": "",
            "tvdb_id": "",
        }

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    candidate = TMDBCandidate(
        category="MOVIE",
        tmdb_id="abc123",
        title="Alpha Title",
        original_title="Alpha Title",
        year=2022,
        score=0.9,
        original_language="en",
        reason="primary-title",
        used_filename_search=True,
        payload={"id": 123},
    )
    resolution = TMDBResolution(candidate=candidate, margin=0.5, source_query="Alpha Title")

    async def fake_resolve(*_, **__):  # pragma: no cover - deterministic stub
        return resolution

    _patch_runner_module(monkeypatch, "resolve_tmdb", fake_resolve)
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(
        monkeypatch,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=1200),
    )
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [5, 15])

    def fake_generate(
        clips: list[types.SimpleNamespace],
        frames: list[int],
        files: list[str],
        metadata: list[dict[str, object]],
        out_dir: Path,
        cfg_screens: ScreenshotConfig,
        color_cfg: ColorConfig,
        **_: object,
    ) -> list[str]:
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx, _ in enumerate(frames)]

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

    def fake_upload(
        image_paths: list[str],
        screen_dir: Path,
        cfg_slow: SlowpicsConfig,
        **kwargs: object,
    ) -> str:  # pragma: no cover - deterministic stub
        assert image_paths
        assert screen_dir.exists()
        assert cfg_slow.collection_name == "Shortcut Failure"
        return "https://slow.pics/c/writefail"

    _patch_runner_module(monkeypatch, "upload_comparison", fake_upload)

    result = frame_compare.run_cli(None, None, service_mode_override=False)

    assert result.json_tail is not None
    slowpics_value = result.json_tail.get("slowpics")
    assert slowpics_value is not None
    slowpics_json = _expect_mapping(slowpics_value)
    assert slowpics_json["url"] == "https://slow.pics/c/writefail"
    assert isinstance(slowpics_json["shortcut_path"], str)
    assert slowpics_json["shortcut_written"] is False
    assert slowpics_json["shortcut_error"] == "write_failed"
    assert not Path(slowpics_json["shortcut_path"]).exists()

def test_cli_tmdb_resolution_sets_default_collection_name(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "SourceA.mkv"
    second = cli_runner_env.media_root / "SourceB.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.tmdb.api_key = "token"
    cfg.slowpics.auto_upload = True
    cfg.slowpics.collection_name = ""
    cfg.slowpics.delete_screen_dir_after_upload = False

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **_: object) -> dict[str, str]:
        return {
            "label": name,
            "release_group": "",
            "file_name": name,
            "title": "Metadata Title",
            "year": "2020",
            "anime_title": "",
            "imdb_id": "",
            "tvdb_id": "",
        }

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    candidate = TMDBCandidate(
        category="MOVIE",
        tmdb_id="12345",
        title="Resolved Title",
        original_title="Original Title",
        year=2023,
        score=0.95,
        original_language="en",
        reason="primary-title",
        used_filename_search=True,
        payload={"id": 12345},
    )
    resolution = TMDBResolution(candidate=candidate, margin=0.4, source_query="Resolved")

    async def fake_resolve(*_, **__):
        return resolution

    _patch_runner_module(monkeypatch, "resolve_tmdb", fake_resolve)
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(
        monkeypatch,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800),
    )
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [10, 20])
    _patch_runner_module(
        monkeypatch,
        "generate_screenshots",
        lambda *args, **kwargs: [str(cli_runner_env.media_root / "shot.png")],
    )
    _patch_runner_module(monkeypatch, "upload_comparison", lambda *args, **kwargs: "https://slow.pics/c/example")

    result = frame_compare.run_cli(None, None, service_mode_override=False)

    assert result.config.slowpics.collection_name.startswith("Resolved Title (2023)")
    assert result.config.slowpics.tmdb_id == "12345"
    assert result.config.slowpics.tmdb_category == "MOVIE"
    assert result.json_tail is not None
    slowpics_value = result.json_tail.get("slowpics")
    assert slowpics_value is not None
    slowpics_json = _expect_mapping(slowpics_value)
    title_json = _expect_mapping(slowpics_json["title"])
    inputs_json = _expect_mapping(title_json["inputs"])
    assert title_json["final"].startswith("Resolved Title (2023)")
    assert inputs_json["collection_suffix"] == ""
    assert slowpics_json["deleted_screens_dir"] is False

def test_collection_suffix_appended(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "Movie.mkv"
    second = cli_runner_env.media_root / "Movie2.mkv"
    for file_path in (first, second):
        file_path.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.tmdb.api_key = "token"
    cfg.slowpics.auto_upload = False
    cfg.slowpics.collection_name = ""
    cfg.slowpics.collection_suffix = "[Hybrid]"

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **_: object) -> dict[str, str]:
        return {
            "label": name,
            "release_group": "",
            "file_name": name,
            "title": "Sample Movie",
            "year": "2021",
            "anime_title": "",
            "imdb_id": "",
            "tvdb_id": "",
        }

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    candidate = TMDBCandidate(
        category="MOVIE",
        tmdb_id="42",
        title="Sample Movie",
        original_title="Sample Movie",
        year=2021,
        score=0.9,
        original_language="en",
        reason="primary-title",
        used_filename_search=True,
        payload={"id": 42},
    )
    resolution = TMDBResolution(candidate=candidate, margin=0.3, source_query="Sample")

    async def fake_resolve(*_, **__):
        return resolution

    _patch_runner_module(monkeypatch, "resolve_tmdb", fake_resolve)
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(monkeypatch, "init_clip", lambda *_, **__: types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1200))
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [5, 15])
    _patch_runner_module(
        monkeypatch,
        "generate_screenshots",
        lambda *args, **kwargs: [str(cli_runner_env.media_root / "shot.png")],
    )

    result = frame_compare.run_cli(None, None)

    assert result.config.slowpics.collection_name == "Sample Movie (2021) [Hybrid]"
    assert result.json_tail is not None
    slowpics_value = result.json_tail.get("slowpics")
    assert slowpics_value is not None
    slowpics_json = _expect_mapping(slowpics_value)
    title_json = _expect_mapping(slowpics_json["title"])
    inputs_json = _expect_mapping(title_json["inputs"])
    assert title_json["final"] == "Sample Movie (2021) [Hybrid]"
    assert inputs_json["collection_suffix"] == "[Hybrid]"
    assert inputs_json["collection_name"] == "Sample Movie (2021) [Hybrid]"

def test_cli_tmdb_manual_override(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "Alpha.mkv"
    second = cli_runner_env.media_root / "Beta.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.tmdb.api_key = "token"
    cfg.tmdb.unattended = False
    cfg.slowpics.collection_name = "${Label}"

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **_: object) -> dict[str, str]:
        return {
            "label": f"Label for {name}",
            "release_group": "",
            "file_name": name,
            "title": "",
            "year": "",
            "anime_title": "",
            "imdb_id": "",
            "tvdb_id": "",
        }

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    candidate = TMDBCandidate(
        category="TV",
        tmdb_id="777",
        title="Option A",
        original_title=None,
        year=2001,
        score=0.5,
        original_language="ja",
        reason="primary",
        used_filename_search=True,
        payload={"id": 777},
    )

    def fake_resolve(*_: object, **__: object) -> None:
        raise TMDBAmbiguityError([candidate])

    _patch_runner_module(monkeypatch, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(tmdb_utils, "_prompt_manual_tmdb", lambda candidates: ("TV", "9999"))
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(
        monkeypatch,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400),
    )
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [3, 6])
    _patch_runner_module(monkeypatch, "generate_screenshots", lambda *args, **kwargs: [str(cli_runner_env.media_root / "img.png")])

    result = frame_compare.run_cli(None, None)

    assert result.config.slowpics.tmdb_id == "9999"
    assert result.config.slowpics.tmdb_category == "TV"
    assert result.config.slowpics.collection_name == "Label for Alpha.mkv"

def test_cli_tmdb_confirmation_manual_id(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "Alpha.mkv"
    second = cli_runner_env.media_root / "Beta.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.tmdb.api_key = "token"
    cfg.tmdb.unattended = False
    cfg.tmdb.confirm_matches = True

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **_: object) -> dict[str, str]:
        return {
            "label": f"Label {name}",
            "release_group": "",
            "file_name": name,
            "title": "",
            "year": "",
            "anime_title": "",
            "imdb_id": "",
            "tvdb_id": "",
        }

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    candidate = TMDBCandidate(
        category="MOVIE",
        tmdb_id="123",
        title="Option",
        original_title=None,
        year=2015,
        score=0.9,
        original_language="en",
        reason="primary",
        used_filename_search=True,
        payload={"id": 123},
    )
    resolution = TMDBResolution(candidate=candidate, margin=0.3, source_query="Option")

    async def fake_resolve(*_: object, **__: object) -> TMDBResolution:
        return resolution

    _patch_runner_module(monkeypatch, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(tmdb_utils, "_prompt_tmdb_confirmation", lambda res: (True, ("MOVIE", "999")))
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(
        monkeypatch,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400),
    )
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [1, 2])
    _patch_runner_module(monkeypatch, "generate_screenshots", lambda *args, **kwargs: [str(cli_runner_env.media_root / "img.png")])

    result = frame_compare.run_cli(None, None)

    assert result.config.slowpics.tmdb_id == "999"
    assert result.config.slowpics.tmdb_category == "MOVIE"

def test_cli_tmdb_confirmation_rejects(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    first = cli_runner_env.media_root / "Alpha.mkv"
    second = cli_runner_env.media_root / "Beta.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.tmdb.api_key = "token"
    cfg.tmdb.unattended = False
    cfg.tmdb.confirm_matches = True

    cli_runner_env.reinstall(cfg)

    def fake_parse(name: str, **_: object) -> dict[str, str]:
        return {
            "label": f"Label {name}",
            "release_group": "",
            "file_name": name,
            "title": "",
            "year": "",
            "anime_title": "",
            "imdb_id": "",
            "tvdb_id": "",
        }

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)

    candidate = TMDBCandidate(
        category="MOVIE",
        tmdb_id="123",
        title="Option",
        original_title=None,
        year=2015,
        score=0.9,
        original_language="en",
        reason="primary",
        used_filename_search=True,
        payload={"id": 123},
    )
    resolution = TMDBResolution(candidate=candidate, margin=0.3, source_query="Option")

    async def fake_resolve(*_: object, **__: object) -> TMDBResolution:
        return resolution

    _patch_runner_module(monkeypatch, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(tmdb_utils, "_prompt_tmdb_confirmation", lambda res: (False, None))
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(monkeypatch, "init_clip", lambda *_, **__: types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800))
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [1, 2])
    _patch_runner_module(monkeypatch, "generate_screenshots", lambda *args, **kwargs: [str(cli_runner_env.media_root / "img.png")])

    result = frame_compare.run_cli(None, None)

    assert result.config.slowpics.tmdb_id == ""
    assert result.config.slowpics.tmdb_category == ""

def test_resolve_tmdb_workflow_unattended_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = TMDBConfig(api_key="token")
    cfg.unattended = True
    files = [tmp_path / "SourceA.mkv", tmp_path / "SourceB.mkv"]
    for file in files:
        file.write_text("x", encoding="utf-8")

    candidate = TMDBCandidate(
        category="MOVIE",
        tmdb_id="1",
        title="Example",
        original_title=None,
        year=2023,
        score=0.9,
        original_language="en",
        reason="search",
        used_filename_search=True,
        payload={},
    )

    monkeypatch.setattr(
        tmdb_utils,
        "resolve_blocking",
        lambda **_: (_ for _ in ()).throw(TMDBAmbiguityError([candidate])),
    )
    prompted = False

    def _fail_prompt(_: Sequence[TMDBCandidate]) -> tuple[str, str] | None:  # pragma: no cover - should not run
        nonlocal prompted
        prompted = True
        return None

    monkeypatch.setattr(tmdb_utils, "_prompt_manual_tmdb", _fail_prompt)

    result = tmdb_utils.resolve_workflow(
        files=files,
        metadata=[{"label": "Example"}],
        tmdb_cfg=cfg,
    )

    assert result.manual_override is None
    assert result.ambiguous is True
    assert result.error_message is not None
    assert prompted is False

def test_resolve_tmdb_workflow_manual_override(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = TMDBConfig(api_key="token")
    cfg.unattended = False
    files = [Path("SourceA.mkv"), Path("SourceB.mkv")]

    candidate = TMDBCandidate(
        category="MOVIE",
        tmdb_id="1",
        title="Example",
        original_title=None,
        year=2023,
        score=0.9,
        original_language="en",
        reason="search",
        used_filename_search=True,
        payload={},
    )

    monkeypatch.setattr(
        tmdb_utils,
        "resolve_blocking",
        lambda **_: (_ for _ in ()).throw(TMDBAmbiguityError([candidate])),
    )
    manual_return = ("TV", "999")
    monkeypatch.setattr(tmdb_utils, "_prompt_manual_tmdb", lambda _: manual_return)

    result = tmdb_utils.resolve_workflow(
        files=files,
        metadata=[{"label": "Example"}],
        tmdb_cfg=cfg,
    )

    assert result.manual_override == manual_return
    assert result.resolution is None

def test_resolve_tmdb_blocking_retries_transient_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"count": 0}

    async def fake_resolve(*_: object, **__: object) -> TMDBResolution:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TMDBResolutionError("TMDB request failed after retries: boom")
        candidate = TMDBCandidate(
            category="MOVIE",
            tmdb_id="42",
            title="Recovered",
            original_title=None,
            year=2024,
            score=0.99,
            original_language="en",
            reason="search",
            used_filename_search=True,
            payload={},
        )
        return TMDBResolution(candidate=candidate, margin=1.0, source_query="Recovered")

    monkeypatch.setattr(tmdb_utils, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(core_module.time, "sleep", lambda _seconds: None)

    cfg = TMDBConfig(api_key="token")
    result = tmdb_utils.resolve_blocking(
        file_name="Example.mkv",
        tmdb_cfg=cfg,
        year_hint=None,
        imdb_id=None,
        tvdb_id=None,
    )

    assert isinstance(result, TMDBResolution)
    assert attempts["count"] == 2


class _SliceRecordingSequence:
    def __init__(self, values: Sequence[int]) -> None:
        self._values = tuple(values)
        self.slice_accesses = 0

    @overload
    def __getitem__(self, index: SupportsIndex, /) -> int: ...

    @overload
    def __getitem__(self, index: slice, /) -> Sequence[int]: ...

    def __getitem__(self, index: SupportsIndex | slice, /) -> Sequence[int] | int:
        if isinstance(index, slice):
            self.slice_accesses += 1
            raise AssertionError("Upload tracker should not slice file sizes")
        return self._values[int(index)]

    def __len__(self) -> int:
        return len(self._values)


def test_upload_progress_tracker_avoids_slicing() -> None:
    sizes = _SliceRecordingSequence([10, 20, 30])
    tracker = UploadProgressTracker(cast(Sequence[int], sizes))

    files_bytes = [tracker.advance(1)[:2] for _ in range(len(sizes))]

    assert sizes.slice_accesses == 0
    assert files_bytes == [(1, 10), (2, 30), (3, 60)]


def test_upload_progress_tracker_is_thread_safe() -> None:
    tracker = UploadProgressTracker([5, 7, 9, 11])

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(tracker.advance, 1) for _ in range(4)]

    results = sorted((files, bytes_done) for files, bytes_done, _ in (future.result() for future in futures))
    assert results == [(1, 5), (2, 12), (3, 21), (4, 32)]
