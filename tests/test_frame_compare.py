from pathlib import Path
import types

import pytest
from click.testing import CliRunner

import frame_compare
from src.datatypes import (
    AnalysisConfig,
    AppConfig,
    NamingConfig,
    OverridesConfig,
    PathsConfig,
    RuntimeConfig,
    ScreenshotConfig,
    SlowpicsConfig,
)


@pytest.fixture
def runner():
    return CliRunner()


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
        slowpics=SlowpicsConfig(auto_upload=False),
        naming=NamingConfig(always_full_filename=False, prefer_guessit=False),
        paths=PathsConfig(input_dir=str(input_dir)),
        runtime=RuntimeConfig(ram_limit_mb=4096),
        overrides=OverridesConfig(
            trim={"0": 5},
            trim_end={"BBB - 01.mkv": -12},
            change_fps={"BBB - 01.mkv": "set"},
        ),
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

    def fake_init_clip(path, *, trim_start=0, trim_end=None, fps_map=None):
        clip = types.SimpleNamespace(
            path=path,
            width=1920,
            height=1080,
            fps_num=24000,
            fps_den=1001,
        )
        init_calls.append((path, trim_start, trim_end, fps_map))
        return clip

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init_clip)

    cache_infos = []

    def fake_select(clip, analysis_cfg, files, file_under_analysis, cache_info=None):
        cache_infos.append(cache_info)
        return [10, 20]

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

    generated_metadata = []

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, **kwargs):
        generated_metadata.append(metadata)
        assert kwargs.get("trim_offsets") == [5, 0]
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(files))]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    result = runner.invoke(frame_compare.main, ["--config", "dummy"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "AAA Short" in result.output
    assert "BBB Short" in result.output

    assert ram_limits == [cfg.runtime.ram_limit_mb]

    assert len(init_calls) == 2
    # Reference clip (BBB) initialised without fps override but with trim_end applied
    assert init_calls[0] == (str(second), 0, -12, None)
    # First clip adopts reference fps and trim override
    assert init_calls[1] == (str(first), 5, None, (24000, 1001))

    assert generated_metadata and generated_metadata[0][0]["label"].startswith("AAA")
    assert generated_metadata[0][1]["label"].startswith("BBB")

    assert cache_infos and cache_infos[0].path == (tmp_path / cfg.analysis.frame_data_filename).resolve()
    assert cache_infos[0].files == ["AAA - 01.mkv", "BBB - 01.mkv"]
    assert len(parse_calls) == 2


def test_label_dedupe_preserves_short_labels(tmp_path, monkeypatch, runner):
    first = tmp_path / "Group - 01.mkv"
    second = tmp_path / "Group - 02.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = AppConfig(
        analysis=AnalysisConfig(frame_count_dark=0, frame_count_bright=0, frame_count_motion=0, random_frames=0),
        screenshots=ScreenshotConfig(directory_name="screens", add_frame_info=False),
        slowpics=SlowpicsConfig(auto_upload=False),
        naming=NamingConfig(always_full_filename=False, prefer_guessit=False),
        paths=PathsConfig(input_dir=str(tmp_path)),
        runtime=RuntimeConfig(ram_limit_mb=1024),
        overrides=OverridesConfig(),
    )

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

    def fake_parse(name, **kwargs):
        return {"label": "[Group]", "release_group": "Group", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init_clip(path, *, trim_start=0, trim_end=None, fps_map=None):
        return types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init_clip)
    monkeypatch.setattr(frame_compare, "select_frames", lambda clip, cfg, files, file_under_analysis, cache_info=None: [42])

    captured = []

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, **kwargs):
        captured.append([meta["label"] for meta in metadata])
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / "shot.png")]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    result = runner.invoke(frame_compare.main, ["--config", "dummy"], catch_exceptions=False)
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

    def fake_init(path, *, trim_start=0, trim_end=None, fps_map=None):
        return types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)

    call_state = {"calls": 0, "cache_hits": 0}

    def fake_select(clip, analysis_cfg, files, file_under_analysis, cache_info=None):
        call_state["calls"] += 1
        assert cache_info is not None
        if cache_info.path.exists():
            call_state["cache_hits"] += 1
        else:
            cache_info.path.write_text("cached", encoding="utf-8")
        return [12]

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        for index in range(len(clips)):
            (out_dir / f"shot_{index}.png").write_text("data", encoding="utf-8")
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(clips))]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    runner.invoke(frame_compare.main, ["--config", "dummy"], catch_exceptions=False)
    runner.invoke(frame_compare.main, ["--config", "dummy"], catch_exceptions=False)

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
        slowpics=SlowpicsConfig(auto_upload=True, delete_screen_dir_after_upload=True, open_in_browser=False, create_url_shortcut=False),
        naming=NamingConfig(always_full_filename=True, prefer_guessit=False),
        paths=PathsConfig(input_dir=str(default_dir)),
        runtime=RuntimeConfig(ram_limit_mb=1024),
        overrides=OverridesConfig(),
    )

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init(path, *, trim_start=0, trim_end=None, fps_map=None):
        return types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)
    monkeypatch.setattr(frame_compare, "select_frames", lambda clip, cfg, files, file_under_analysis, cache_info=None: [7])

    def fake_generate(clips, frames, files, metadata, out_dir, cfg_screens, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "image.png"
        path.write_text("img", encoding="utf-8")
        return [str(path)]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    uploads = []

    def fake_upload(image_paths, screen_dir, cfg_slow):
        uploads.append((image_paths, screen_dir))
        return "https://slow.pics/c/abc/def"

    monkeypatch.setattr(frame_compare, "upload_comparison", fake_upload)

    result = runner.invoke(
        frame_compare.main,
        ["--config", "dummy", "--input", str(override_dir)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert uploads
    screen_dir = Path(override_dir / cfg.screenshots.directory_name).resolve()
    assert not screen_dir.exists()
    assert str(override_dir) in result.output
