from pathlib import Path
import json
import types

import pytest
from click.testing import CliRunner

import frame_compare
from src.audio_alignment import AlignmentMeasurement, AudioStreamInfo
from src.datatypes import (
    AnalysisConfig,
    AppConfig,
    AudioAlignmentConfig,
    CLIConfig,
    ColorConfig,
    NamingConfig,
    OverridesConfig,
    PathsConfig,
    RuntimeConfig,
    ScreenshotConfig,
    SlowpicsConfig,
    SourceConfig,
    TMDBConfig,
)
from src.tmdb import TMDBAmbiguityError, TMDBCandidate, TMDBResolution


@pytest.fixture
def runner():
    return CliRunner()


class DummyProgress:
    def __init__(self, *_, **__):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_task(self, *_, **__):
        return 1

    def update(self, *_, **__):
        return None


def _make_config(input_dir: Path) -> AppConfig:
    return AppConfig(
        analysis=AnalysisConfig(
            frame_count_dark=1,
            frame_count_bright=1,
            frame_count_motion=1,
            random_frames=0,
            user_frames=[],
        ),
        screenshots=ScreenshotConfig(directory_name="screens", add_frame_info=False),
        cli=CLIConfig(),
        color=ColorConfig(),
        slowpics=SlowpicsConfig(auto_upload=False),
        tmdb=TMDBConfig(),
        naming=NamingConfig(always_full_filename=False, prefer_guessit=False),
        paths=PathsConfig(input_dir=str(input_dir)),
        runtime=RuntimeConfig(ram_limit_mb=4096),
        overrides=OverridesConfig(
            trim={"0": 5},
            trim_end={"BBB - 01.mkv": -12},
            change_fps={"BBB - 01.mkv": "set"},
        ),
        source=SourceConfig(preferred="lsmas"),
        audio_alignment=AudioAlignmentConfig(enable=False),
    )


def test_cli_applies_overrides_and_naming(tmp_path, monkeypatch, runner):
    first = tmp_path / "AAA - 01.mkv"
    second = tmp_path / "BBB - 01.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

    parse_calls = []

    def fake_parse(name, **kwargs):
        parse_calls.append((name, kwargs))
        if name.startswith("AAA"):
            return {"label": "AAA Short", "release_group": "AAA", "file_name": name}
        return {"label": "BBB Short", "release_group": "BBB", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

    ram_limits = []
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit_mb: ram_limits.append(limit_mb))

    init_calls = []

    def fake_init_clip(path, *, trim_start=0, trim_end=None, fps_map=None, cache_dir=None):
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

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init_clip)

    cache_infos = []

    def fake_select(
        clip,
        analysis_cfg,
        files,
        file_under_analysis,
        cache_info=None,
        progress=None,
        *,
        frame_window=None,
        return_metadata=False,
        color_cfg=None,
    ):
        cache_infos.append(cache_info)
        assert frame_window is not None
        assert isinstance(frame_window, tuple)
        return [10, 20]

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

    generated_metadata = []

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, color_cfg, **kwargs):
        generated_metadata.append(metadata)
        assert kwargs.get("trim_offsets") == [5, 0]
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(files))]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "[DISCOVER]" in result.output
    assert "• ref=AAA Short" in result.output
    assert "• tgt=BBB Short" in result.output

    assert "[PREPARE]" in result.output
    assert "• Ref:  lead=  5f" in result.output
    assert "• Tgt:  lead=  0f" in result.output
    assert "ignore_lead=0.00s" in result.output
    assert "[SUMMARY]" in result.output
    assert "• Clips:" in result.output
    assert "Output frames:" in result.output

    assert ram_limits == [cfg.runtime.ram_limit_mb]

    expected_cache_dir = str(tmp_path.resolve())
    assert len(init_calls) >= 2
    # Reference clip (BBB) initialised without fps override but with trim_end applied
    assert (str(second), 0, -12, None, expected_cache_dir) in init_calls
    # First clip adopts reference fps and trim override
    assert (str(first), 5, None, (24000, 1001), expected_cache_dir) in init_calls

    assert generated_metadata and generated_metadata[0][0]["label"].startswith("AAA")
    assert generated_metadata[0][1]["label"].startswith("BBB")

    assert cache_infos and cache_infos[0].path == (tmp_path / cfg.analysis.frame_data_filename).resolve()
    assert cache_infos[0].files == ["AAA - 01.mkv", "BBB - 01.mkv"]
    assert len(parse_calls) == 2



def test_cli_disables_json_tail_output(tmp_path, monkeypatch, runner):
    first = tmp_path / "AAA - 01.mkv"
    second = tmp_path / "BBB - 01.mkv"
    for file_path in (first, second):
        file_path.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.cli.emit_json_tail = False

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit_mb: None)

    def fake_parse(name, **kwargs):
        return {"label": name, "release_group": "", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

    def fake_init(path, *, trim_start=0, trim_end=None, fps_map=None, cache_dir=None):
        return types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=600)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)

    monkeypatch.setattr(
        frame_compare,
        "select_frames",
        lambda clip, cfg, files, file_under_analysis, cache_info=None, progress=None, *, frame_window=None, return_metadata=False, color_cfg=None: [12],
    )

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, color_cfg, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / "frame.png")]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert '{"analysis"' not in result.output


def test_label_dedupe_preserves_short_labels(tmp_path, monkeypatch, runner):
    first = tmp_path / "Group - 01.mkv"
    second = tmp_path / "Group - 02.mkv"
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
        paths=PathsConfig(input_dir=str(tmp_path)),
        runtime=RuntimeConfig(ram_limit_mb=1024),
        overrides=OverridesConfig(),
        source=SourceConfig(),
        audio_alignment=AudioAlignmentConfig(enable=False),
    )

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

    def fake_parse(name, **kwargs):
        return {"label": "[Group]", "release_group": "Group", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init_clip(path, *, trim_start=0, trim_end=None, fps_map=None, cache_dir=None):
        return types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init_clip)
    monkeypatch.setattr(
        frame_compare,
        "select_frames",
        lambda clip, cfg, files, file_under_analysis, cache_info=None, progress=None, *, frame_window=None, return_metadata=False, color_cfg=None: [42],
    )

    captured = []

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, color_cfg, **kwargs):
        captured.append([meta["label"] for meta in metadata])
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / "shot.png")]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert captured
    labels = captured[0]
    assert len(labels) == 2
    assert labels[0] != first.name and labels[1] != second.name
    assert labels[0] != labels[1]


def test_cli_reuses_frame_cache(tmp_path, monkeypatch, runner):
    files = [tmp_path / "A.mkv", tmp_path / "B.mkv"]
    for file in files:
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.analysis.save_frames_data = True

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init(path, *, trim_start=0, trim_end=None, fps_map=None, cache_dir=None):
        return types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)

    call_state = {"calls": 0, "cache_hits": 0}

    def fake_select(
        clip,
        analysis_cfg,
        files,
        file_under_analysis,
        cache_info=None,
        progress=None,
        *,
        frame_window=None,
        return_metadata=False,
        color_cfg=None,
    ):
        call_state["calls"] += 1
        assert cache_info is not None
        assert frame_window is not None
        if cache_info.path.exists():
            call_state["cache_hits"] += 1
        else:
            cache_info.path.write_text("cached", encoding="utf-8")
        return [12]

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, color_cfg, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        for index in range(len(clips)):
            (out_dir / f"shot_{index}.png").write_text("data", encoding="utf-8")
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(clips))]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)

    assert call_state["calls"] == 2
    assert call_state["cache_hits"] == 1


def test_cli_input_override_and_cleanup(tmp_path, monkeypatch, runner):
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
        color=ColorConfig(),
        slowpics=SlowpicsConfig(auto_upload=True, delete_screen_dir_after_upload=True, open_in_browser=False, create_url_shortcut=False),
        tmdb=TMDBConfig(),
        naming=NamingConfig(always_full_filename=True, prefer_guessit=False),
        paths=PathsConfig(input_dir=str(default_dir)),
        runtime=RuntimeConfig(ram_limit_mb=1024),
        overrides=OverridesConfig(),
        source=SourceConfig(),
        audio_alignment=AudioAlignmentConfig(enable=False),
    )

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init(path, *, trim_start=0, trim_end=None, fps_map=None, cache_dir=None):
        return types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)
    monkeypatch.setattr(
        frame_compare,
        "select_frames",
        lambda clip, cfg, files, file_under_analysis, cache_info=None, progress=None, *, frame_window=None, return_metadata=False, color_cfg=None: [7],
    )

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, color_cfg, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "image.png"
        path.write_text("img", encoding="utf-8")
        return [str(path)]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    uploads = []

    def fake_upload(image_paths, screen_dir, cfg_slow, **kwargs):
        uploads.append((image_paths, screen_dir))
        return "https://slow.pics/c/abc/def"

    monkeypatch.setattr(frame_compare, "upload_comparison", fake_upload)

    result = runner.invoke(
        frame_compare.main,
        ["--config", "dummy", "--input", str(override_dir), "--no-color"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert uploads
    screen_dir = Path(override_dir / cfg.screenshots.directory_name).resolve()
    assert not screen_dir.exists()
    assert uploads[0][1] == screen_dir


def test_cli_tmdb_resolution_populates_slowpics(tmp_path, monkeypatch):
    first = tmp_path / "SourceA.mkv"
    second = tmp_path / "SourceB.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.tmdb.api_key = "token"
    cfg.slowpics.auto_upload = True
    cfg.slowpics.collection_name = "${Title} (${Year}) [${TMDBCategory}]"
    cfg.slowpics.delete_screen_dir_after_upload = False

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

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

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

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

    monkeypatch.setattr(frame_compare, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init(path, *, trim_start=0, trim_end=None, fps_map=None, cache_dir=None):
        return types.SimpleNamespace(
            width=1280,
            height=720,
            fps_num=24000,
            fps_den=1001,
            num_frames=1800,
        )

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)

    def fake_select(
        clip,
        analysis_cfg,
        files,
        file_under_analysis,
        cache_info=None,
        progress=None,
        *,
        frame_window=None,
        return_metadata=False,
        color_cfg=None,
    ):
        assert frame_window is not None
        return [12, 24]

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, color_cfg, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(files))]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    uploads: list[tuple[list[str], Path, str, str]] = []

    def fake_upload(image_paths, screen_dir, cfg_slow, **kwargs):
        uploads.append((list(image_paths), screen_dir, cfg_slow.tmdb_id, cfg_slow.collection_name))
        return "https://slow.pics/c/example"

    monkeypatch.setattr(frame_compare, "upload_comparison", fake_upload)

    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

    assert uploads
    _, _, upload_tmdb_id, upload_collection = uploads[0]
    assert upload_tmdb_id == "12345"
    assert "Resolved Title (2023)" in upload_collection
    assert result.config.slowpics.tmdb_id == "12345"
    assert result.config.slowpics.tmdb_category == "MOVIE"
    assert result.config.slowpics.collection_name == "Resolved Title (2023) [MOVIE]"
    slowpics_json = result.json_tail["slowpics"]
    assert slowpics_json["title"]["final"] == "Resolved Title (2023) [MOVIE]"
    assert slowpics_json["title"]["inputs"]["resolved_base"] == "Resolved Title (2023)"
    assert slowpics_json["url"] == "https://slow.pics/c/example"
    assert slowpics_json["shortcut_path"].endswith("slowpics_example.url")
    assert slowpics_json["deleted_screens_dir"] is False


def test_cli_tmdb_resolution_sets_default_collection_name(tmp_path, monkeypatch):
    first = tmp_path / "SourceA.mkv"
    second = tmp_path / "SourceB.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.tmdb.api_key = "token"
    cfg.slowpics.auto_upload = True
    cfg.slowpics.collection_name = ""
    cfg.slowpics.delete_screen_dir_after_upload = False

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

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

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

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

    monkeypatch.setattr(frame_compare, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)
    monkeypatch.setattr(frame_compare.vs_core, "init_clip", lambda *_, **__: types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800))
    monkeypatch.setattr(frame_compare, "select_frames", lambda *_, **__: [10, 20])
    monkeypatch.setattr(frame_compare, "generate_screenshots", lambda *args, **kwargs: [str(tmp_path / "shot.png")])
    monkeypatch.setattr(frame_compare, "upload_comparison", lambda *args, **kwargs: "https://slow.pics/c/example")
    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

    assert result.config.slowpics.collection_name.startswith("Resolved Title (2023)")
    assert result.config.slowpics.tmdb_id == "12345"
    assert result.config.slowpics.tmdb_category == "MOVIE"
    slowpics_json = result.json_tail["slowpics"]
    assert slowpics_json["title"]["final"].startswith("Resolved Title (2023)")
    assert slowpics_json["title"]["inputs"]["collection_suffix"] == ""
    assert slowpics_json["deleted_screens_dir"] is False


def test_collection_suffix_appended(tmp_path, monkeypatch):
    first = tmp_path / "Movie.mkv"
    second = tmp_path / "Movie2.mkv"
    for file_path in (first, second):
        file_path.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.tmdb.api_key = "token"
    cfg.slowpics.auto_upload = False
    cfg.slowpics.collection_name = ""
    cfg.slowpics.collection_suffix = "[Hybrid]"

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

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

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

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

    monkeypatch.setattr(frame_compare, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)
    monkeypatch.setattr(frame_compare.vs_core, "init_clip", lambda *_, **__: types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1200))
    monkeypatch.setattr(frame_compare, "select_frames", lambda *_, **__: [5, 15])
    monkeypatch.setattr(frame_compare, "generate_screenshots", lambda *args, **kwargs: [str(tmp_path / "shot.png")])
    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

    assert result.config.slowpics.collection_name == "Sample Movie (2021) [Hybrid]"
    slowpics_json = result.json_tail["slowpics"]
    assert slowpics_json["title"]["final"] == "Sample Movie (2021) [Hybrid]"
    assert slowpics_json["title"]["inputs"]["collection_suffix"] == "[Hybrid]"
    assert slowpics_json["title"]["inputs"]["collection_name"] == "Sample Movie (2021) [Hybrid]"

def test_cli_tmdb_manual_override(tmp_path, monkeypatch):
    first = tmp_path / "Alpha.mkv"
    second = tmp_path / "Beta.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.tmdb.api_key = "token"
    cfg.tmdb.unattended = False
    cfg.slowpics.collection_name = "${Label}"

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

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

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

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

    def fake_resolve(*_, **__):
        raise TMDBAmbiguityError([candidate])

    monkeypatch.setattr(frame_compare, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(frame_compare, "_prompt_manual_tmdb", lambda candidates: ("TV", "9999"))
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)
    monkeypatch.setattr(frame_compare.vs_core, "init_clip", lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400))
    monkeypatch.setattr(frame_compare, "select_frames", lambda *_, **__: [3, 6])
    monkeypatch.setattr(frame_compare, "generate_screenshots", lambda *args, **kwargs: [str(tmp_path / "img.png")])
    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

    assert result.config.slowpics.tmdb_id == "9999"
    assert result.config.slowpics.tmdb_category == "TV"
    assert result.config.slowpics.collection_name == "Label for Alpha.mkv"


def test_cli_tmdb_confirmation_manual_id(tmp_path, monkeypatch):
    first = tmp_path / "Alpha.mkv"
    second = tmp_path / "Beta.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.tmdb.api_key = "token"
    cfg.tmdb.unattended = False
    cfg.tmdb.confirm_matches = True

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

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

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

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

    async def fake_resolve(*_, **__):
        return resolution

    monkeypatch.setattr(frame_compare, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(frame_compare, "_prompt_tmdb_confirmation", lambda res: (True, ("MOVIE", "999")))
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)
    monkeypatch.setattr(frame_compare.vs_core, "init_clip", lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400))
    monkeypatch.setattr(frame_compare, "select_frames", lambda *_, **__: [1, 2])
    monkeypatch.setattr(frame_compare, "generate_screenshots", lambda *args, **kwargs: [str(tmp_path / "img.png")])
    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

    assert result.config.slowpics.tmdb_id == "999"
    assert result.config.slowpics.tmdb_category == "MOVIE"


def test_cli_tmdb_confirmation_rejects(tmp_path, monkeypatch):
    first = tmp_path / "Alpha.mkv"
    second = tmp_path / "Beta.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.tmdb.api_key = "token"
    cfg.tmdb.unattended = False
    cfg.tmdb.confirm_matches = True

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

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

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

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

    async def fake_resolve(*_, **__):
        return resolution

    monkeypatch.setattr(frame_compare, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(frame_compare, "_prompt_tmdb_confirmation", lambda res: (False, None))
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)
    monkeypatch.setattr(frame_compare.vs_core, "init_clip", lambda *_, **__: types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800))
    monkeypatch.setattr(frame_compare, "select_frames", lambda *_, **__: [1, 2])
    monkeypatch.setattr(frame_compare, "generate_screenshots", lambda *args, **kwargs: [str(tmp_path / "img.png")])
    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

    assert result.config.slowpics.tmdb_id == ""
    assert result.config.slowpics.tmdb_category == ""



def test_audio_alignment_block_and_json(tmp_path, monkeypatch, runner):
    reference_path = tmp_path / "ClipA.mkv"
    target_path = tmp_path / "ClipB.mkv"
    for file in (reference_path, target_path):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.confirm_with_screenshots = False
    cfg.audio_alignment.max_offset_seconds = 5.0
    cfg.audio_alignment.offsets_filename = "alignment.toml"
    cfg.audio_alignment.frame_offset_bias = 0
    cfg.audio_alignment.start_seconds = 0.25
    cfg.audio_alignment.duration_seconds = 1.5
    cfg.color.overlay_mode = "diagnostic"

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

    def fake_parse(name: str, **_kwargs):
        if name.startswith("ClipA"):
            return {"label": "Clip A", "file_name": name}
        return {"label": "Clip B", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init_clip(path, *, trim_start=0, trim_end=None, fps_map=None, cache_dir=None):
        return types.SimpleNamespace(
            path=Path(path),
            width=1920,
            height=1080,
            fps_num=24000,
            fps_den=1001,
            num_frames=24000,
        )

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init_clip)

    monkeypatch.setattr(
        frame_compare,
        "select_frames",
        lambda *args, **kwargs: [42],
    )

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, color_cfg, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(files))]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    def fake_probe(path: Path):
        if Path(path) == reference_path:
            return [
                AudioStreamInfo(
                    index=0,
                    language="eng",
                    codec_name="aac",
                    channels=2,
                    channel_layout="stereo",
                    sample_rate=48000,
                    bitrate=192000,
                    is_default=True,
                    is_forced=False,
                )
            ]
        return [
            AudioStreamInfo(
                index=1,
                language="jpn",
                codec_name="aac",
                channels=2,
                channel_layout="stereo",
                sample_rate=48000,
                bitrate=192000,
                is_default=False,
                is_forced=False,
            )
        ]

    monkeypatch.setattr(frame_compare.audio_alignment, "probe_audio_streams", fake_probe)

    measurement = AlignmentMeasurement(
        file=target_path,
        offset_seconds=0.1,
        frames=3,
        correlation=0.93,
        reference_fps=24.0,
        target_fps=24.0,
    )

    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "measure_offsets",
        lambda *args, **kwargs: [measurement],
    )

    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "load_offsets",
        lambda *_args, **_kwargs: ({}, {}),
    )

    def fake_update(_path, reference_name, measurements, _existing, _negative_notes):
        applied_frames = {reference_name: 0}
        applied_frames.update({m.file.name: m.frames or 0 for m in measurements})
        statuses = {m.file.name: "auto" for m in measurements}
        return applied_frames, statuses

    monkeypatch.setattr(frame_compare.audio_alignment, "update_offsets_file", fake_update)

    result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    assert result.exit_code == 0

    output_lines = result.output.splitlines()
    streams_idx = next(i for i, line in enumerate(output_lines) if line.strip().startswith("Streams:"))
    assert 'ref="Clip A->' in output_lines[streams_idx]
    clip_b_line = output_lines[streams_idx + 1] if streams_idx + 1 < len(output_lines) else ""
    assert "Clip B" in (output_lines[streams_idx] + clip_b_line)
    assert any("Estimating audio offsets" in line for line in output_lines)
    offset_idx = next(i for i, line in enumerate(output_lines) if line.strip().startswith("Offset:"), None)
    assert offset_idx is not None
    offset_block = output_lines[offset_idx]
    if offset_idx + 1 < len(output_lines):
        offset_block += output_lines[offset_idx + 1]
    assert "Clip B" in offset_block
    assert "Confirm:" in result.output
    assert "alignment.toml" in result.output
    assert "mode=diagnostic" in result.output

    json_start = result.output.rfind('{"clips":')
    json_payload = result.output[json_start:].replace('\n', '')
    payload = json.loads(json_payload)
    audio_json = payload["audio_alignment"]
    assert audio_json["reference_stream"].startswith("Clip A")
    assert audio_json["target_stream"]["Clip B"].startswith("aac/jpn")
    assert audio_json["offsets_sec"]["Clip B"] == pytest.approx(0.1)
    assert audio_json["offsets_frames"]["Clip B"] == 3
    assert audio_json["preview_paths"] == []
    assert audio_json["confirmed"] == "auto"
    tonemap_json = payload["tonemap"]
    assert tonemap_json["overlay_mode"] == "diagnostic"


def test_audio_alignment_default_duration_avoids_zero_window(tmp_path, monkeypatch, runner):
    reference_path = tmp_path / "ClipA.mkv"
    target_path = tmp_path / "ClipB.mkv"
    for file in (reference_path, target_path):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.confirm_with_screenshots = False
    cfg.audio_alignment.max_offset_seconds = 5.0
    cfg.audio_alignment.start_seconds = None
    cfg.audio_alignment.duration_seconds = None

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

    def fake_parse(name: str, **_kwargs):
        if name.startswith("ClipA"):
            return {"label": "Clip A", "file_name": name}
        return {"label": "Clip B", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init_clip(path, *, trim_start=0, trim_end=None, fps_map=None, cache_dir=None):
        return types.SimpleNamespace(
            path=Path(path),
            width=1920,
            height=1080,
            fps_num=24000,
            fps_den=1001,
            num_frames=24000,
        )

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init_clip)

    monkeypatch.setattr(
        frame_compare,
        "select_frames",
        lambda *args, **kwargs: [42],
    )

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, color_cfg, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / "shot.png")]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    def fake_probe(path: Path):
        if Path(path) == reference_path:
            return [
                AudioStreamInfo(
                    index=0,
                    language="eng",
                    codec_name="aac",
                    channels=2,
                    channel_layout="stereo",
                    sample_rate=48000,
                    bitrate=192000,
                    is_default=True,
                    is_forced=False,
                )
            ]
        return [
            AudioStreamInfo(
                index=1,
                language="jpn",
                codec_name="aac",
                channels=2,
                channel_layout="stereo",
                sample_rate=48000,
                bitrate=192000,
                is_default=False,
                is_forced=False,
            )
        ]

    monkeypatch.setattr(frame_compare.audio_alignment, "probe_audio_streams", fake_probe)

    measurement = AlignmentMeasurement(
        file=target_path,
        offset_seconds=0.1,
        frames=3,
        correlation=0.9,
        reference_fps=24.0,
        target_fps=24.0,
    )

    captured_kwargs: dict[str, object] = {}

    def fake_measure(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return [measurement]

    monkeypatch.setattr(frame_compare.audio_alignment, "measure_offsets", fake_measure)
    monkeypatch.setattr(frame_compare.audio_alignment, "load_offsets", lambda *_args, **_kwargs: ({}, {}))
    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "update_offsets_file",
        lambda *_args, **_kwargs: ({target_path.name: 3}, {target_path.name: "auto"}),
    )

    result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert captured_kwargs.get("duration_seconds") is None


def _build_alignment_context(tmp_path):
    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.confirm_with_screenshots = True

    reference_clip = types.SimpleNamespace(num_frames=10)
    target_clip = types.SimpleNamespace(num_frames=10)

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.touch()
    target_path.touch()

    reference_plan = frame_compare._ClipPlan(
        path=reference_path,
        metadata={"label": "Reference Clip"},
        clip=reference_clip,
    )
    target_plan = frame_compare._ClipPlan(
        path=target_path,
        metadata={"label": "Target Clip"},
        clip=target_clip,
    )

    summary = frame_compare._AudioAlignmentSummary(
        offsets_path=tmp_path / "alignment.toml",
        reference_name="Reference Clip",
        measurements=(),
        applied_frames={"Reference Clip": 0},
        baseline_shift=0,
        statuses={},
        reference_plan=reference_plan,
        final_adjustments={},
        swap_details={},
    )

    display = frame_compare._AudioAlignmentDisplayData(
        stream_lines=[],
        estimation_line=None,
        offset_lines=[],
        offsets_file_line="",
        json_reference_stream=None,
        json_target_streams={},
        json_offsets_sec={},
        json_offsets_frames={},
        warnings=[],
    )

    return cfg, [reference_plan, target_plan], summary, display


class _ListReporter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def line(self, message: str) -> None:
        self.lines.append(message)


def test_confirm_alignment_reports_preview_paths(monkeypatch, tmp_path):
    cfg, plans, summary, display = _build_alignment_context(tmp_path)

    reporter = _ListReporter()
    generated_paths = []

    def fake_generate(*args, **_kwargs):
        out_dir = args[4]
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = [out_dir / "shot_0.png", out_dir / "shot_1.png"]
        generated_paths.extend(paths)
        return paths

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)
    monkeypatch.setattr(frame_compare.sys, "stdin", types.SimpleNamespace(isatty=lambda: False))

    frame_compare._confirm_alignment_with_screenshots(
        plans,
        summary,
        cfg,
        tmp_path,
        reporter,
        display,
    )

    expected_paths = [str(path) for path in generated_paths]
    assert display.preview_paths == expected_paths
    assert any("Preview saved:" in line for line in reporter.lines)


def test_confirm_alignment_raises_cli_error_on_screenshot_failure(monkeypatch, tmp_path):
    cfg, plans, summary, display = _build_alignment_context(tmp_path)

    def fake_generate(*_args, **_kwargs):
        raise frame_compare.ScreenshotError("boom")

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    with pytest.raises(frame_compare.CLIAppError, match="Alignment preview failed"):
        frame_compare._confirm_alignment_with_screenshots(
            plans,
            summary,
            cfg,
            tmp_path,
            _ListReporter(),
            display,
        )


def test_run_cli_calls_alignment_confirmation(monkeypatch, tmp_path):
    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.confirm_with_screenshots = True

    monkeypatch.setattr(frame_compare, "load_config", lambda _path: cfg)

    files = [tmp_path / "Ref.mkv", tmp_path / "Tgt.mkv"]
    for file in files:
        file.write_bytes(b"data")

    def fake_discover(_root):
        return files

    def fake_parse_metadata(_files, _naming):
        return [
            {
                "label": "Reference",
                "file_name": files[0].name,
                "year": "",
                "title": "",
                "anime_title": "",
                "imdb_id": "",
                "tvdb_id": "",
            },
            {
                "label": "Target",
                "file_name": files[1].name,
                "year": "",
                "title": "",
                "anime_title": "",
                "imdb_id": "",
                "tvdb_id": "",
            },
        ]

    def fake_build_plans(_files, metadata, _cfg):
        plans = []
        for idx, path in enumerate(_files):
            plans.append(
                frame_compare._ClipPlan(
                    path=path,
                    metadata=metadata[idx],
                    use_as_reference=(idx == 0),
                )
            )
        return plans

    def fake_pick_analyze(_files, _metadata, _analyze_clip, cache_dir=None):
        return files[0]

    offsets_path = tmp_path / "alignment.toml"

    def fake_maybe_apply(plans, _cfg, _analyze_path, _root, _overrides, reporter=None):
        summary = frame_compare._AudioAlignmentSummary(
            offsets_path=offsets_path,
            reference_name="Reference",
            measurements=(),
            applied_frames={},
            baseline_shift=0,
            statuses={},
            reference_plan=plans[0],
            final_adjustments={},
            swap_details={},
        )
        display = frame_compare._AudioAlignmentDisplayData(
            stream_lines=[],
            estimation_line=None,
            offset_lines=[],
            offsets_file_line=f"Offsets file: {offsets_path}",
            json_reference_stream="ref",
            json_target_streams={"Target": "tgt"},
            json_offsets_sec={"Target": 0.0},
            json_offsets_frames={"Target": 0},
            warnings=[],
        )
        return summary, display

    class _DummyReporter:
        def __init__(self, *_, **__):
            self.console = types.SimpleNamespace(print=lambda *args, **kwargs: None)

        def update_values(self, *_args, **_kwargs):
            return None

        def set_flag(self, *_args, **_kwargs):
            return None

        def line(self, *_args, **_kwargs):
            return None

        def verbose_line(self, *_args, **_kwargs):
            return None

        def render_sections(self, *_args, **_kwargs):
            return None

        def update_progress_state(self, *_args, **_kwargs):
            return None

        def set_status(self, *_args, **_kwargs):
            return None

        def create_progress(self, *_args, **_kwargs):
            return DummyProgress()

    class _SentinelError(Exception):
        pass

    called: dict[str, object] = {}

    def fake_confirm(plans, summary, cfg_obj, root, reporter, display):
        called["args"] = (plans, summary, cfg_obj, root, reporter, display)
        raise _SentinelError

    monkeypatch.setattr(frame_compare, "_discover_media", fake_discover)
    monkeypatch.setattr(frame_compare, "_parse_metadata", fake_parse_metadata)
    monkeypatch.setattr(frame_compare, "_build_plans", fake_build_plans)
    monkeypatch.setattr(frame_compare, "_pick_analyze_file", fake_pick_analyze)
    monkeypatch.setattr(frame_compare, "_maybe_apply_audio_alignment", fake_maybe_apply)
    monkeypatch.setattr(frame_compare, "CliOutputManager", _DummyReporter)
    monkeypatch.setattr(frame_compare, "_confirm_alignment_with_screenshots", fake_confirm)
    monkeypatch.setattr(frame_compare.vs_core, "configure", lambda *args, **kwargs: None)

    with pytest.raises(_SentinelError):
        frame_compare.run_cli("dummy-config")

    assert "args" in called
