import json
import types
import importlib
import pathlib
from pathlib import Path
from collections.abc import Iterable, Sequence
from typing import Any, Mapping, cast

import pytest
from click.testing import CliRunner, Result
from rich.console import Console

import frame_compare
from src.audio_alignment import AlignmentMeasurement, AudioStreamInfo
from src.analysis import CacheLoadResult, FrameMetricsCacheInfo
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
def runner() -> CliRunner:
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


JsonMapping = Mapping[str, Any]


def _expect_mapping(value: object) -> JsonMapping:
    assert isinstance(value, Mapping)
    return cast(JsonMapping, value)


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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    """
    Ensure run_cli refuses cache or offsets paths that escape the media root.
    """

    cfg = frame_compare._fresh_app_config()
    section_name, attr_name = field.split(".")
    setattr(getattr(cfg, section_name), attr_name, value)

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

    with pytest.raises(frame_compare.CLIAppError) as excinfo:
        frame_compare.run_cli("ignored", None, root_override=str(tmp_path))

    assert field in str(excinfo.value)


def _make_config(input_dir: Path) -> AppConfig:
    """
    Builds a test-oriented AppConfig populated with sensible defaults and example overrides.
    
    Parameters:
        input_dir (Path): Directory used as the config's input path (stored in paths.input_dir).
    
    Returns:
        AppConfig: An AppConfig instance with prepared sub-configs for analysis, screenshots,
        cli, color, slowpics, tmdb, naming, paths, runtime, overrides, source, and audio_alignment.
        Notable defaults: screenshots.directory_name is "screens", runtime.ram_limit_mb is 4096,
        audio_alignment is disabled, and overrides include sample trim and fps entries.
    """
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


def test_audio_alignment_vspreview_suggestion_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VSPreview flow surfaces offsets without mutating trims or writing offsets."""

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.use_vspreview = True
    cfg.audio_alignment.confirm_with_screenshots = False
    cfg.audio_alignment.frame_offset_bias = 0

    reference_plan = frame_compare._ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
        clip=None,
    )
    target_plan = frame_compare._ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
        clip=None,
    )
    target_plan.trim_start = 120
    target_plan.has_trim_start_override = True

    measurement = AlignmentMeasurement(
        file=target_path,
        offset_seconds=0.5,
        frames=12,
        correlation=0.92,
        reference_fps=24.0,
        target_fps=24.0,
    )

    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "probe_audio_streams",
        lambda _path: [],
    )

    def _fake_measure(
        _ref: Path,
        targets: list[Path],
        *,
        progress_callback,
        **_kwargs: object,
    ):
        progress_callback(len(targets))
        return [measurement]

    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "measure_offsets",
        _fake_measure,
    )
    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "load_offsets",
        lambda _path: (None, {}),
    )

    def _fail_update(*_args, **_kwargs):
        raise AssertionError("update_offsets_file should not be called in VSPreview mode")

    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "update_offsets_file",
        _fail_update,
    )

    summary, display = frame_compare._maybe_apply_audio_alignment(
        [reference_plan, target_plan],
        cfg,
        reference_path,
        tmp_path,
        {},
        reporter=None,
    )

    assert summary is not None
    assert display is not None
    assert summary.suggestion_mode is True
    assert summary.applied_frames == {}
    assert summary.suggested_frames[target_path.name] == 12
    assert summary.manual_trim_starts[target_path.name] == 120
    assert target_plan.trim_start == 120, "Trim should remain unchanged in suggestion mode"
    assert any("VSPreview manual alignment enabled" in warning for warning in display.warnings)
    assert any("Existing manual trim" in line for line in display.offset_lines)


def test_launch_vspreview_generates_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VSPreview launcher should emit a script and attempt to execute it."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.use_vspreview = True

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    reference_plan = frame_compare._ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = frame_compare._ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )
    target_plan.trim_start = 10
    target_plan.has_trim_start_override = True
    plans = [reference_plan, target_plan]

    summary = frame_compare._AudioAlignmentSummary(
        offsets_path=tmp_path / "offsets.toml",
        reference_name=reference_path.name,
        measurements=(),
        applied_frames={},
        baseline_shift=0,
        statuses={},
        reference_plan=reference_plan,
        final_adjustments={},
        swap_details={},
        suggested_frames={target_path.name: 7},
        suggestion_mode=True,
        manual_trim_starts={target_path.name: 10},
    )

    reporter = _RecordingOutputManager()
    json_tail = _make_json_tail_stub()
    audio_block = json_tail["audio_alignment"]

    monkeypatch.setattr(frame_compare.sys.stdin, "isatty", lambda: True)

    recorded_command: list[list[str]] = []

    class _Result:
        def __init__(self, returncode: int = 0) -> None:
            self.returncode = returncode

    monkeypatch.setattr(frame_compare.shutil, "which", lambda _: None)
    monkeypatch.setattr(frame_compare.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        frame_compare.subprocess,
        "run",
        lambda cmd, env=None, check=False: recorded_command.append(list(cmd)) or _Result(0),
    )

    display = frame_compare._AudioAlignmentDisplayData(
        stream_lines=[],
        estimation_line=None,
        offset_lines=[],
        offsets_file_line="Offsets file: offsets.toml",
        json_reference_stream=None,
        json_target_streams={},
        json_offsets_sec={},
        json_offsets_frames={},
        warnings=[],
    )

    prompt_calls: list[dict[str, int] | None] = []
    monkeypatch.setattr(
        frame_compare,
        "_prompt_vspreview_offsets",
        lambda *args, **kwargs: prompt_calls.append({}) or {},
    )

    apply_calls: list[Mapping[str, int]] = []

    def _record_apply(
        _plans: Sequence[frame_compare._ClipPlan],
        _summary: frame_compare._AudioAlignmentSummary,
        offsets: Mapping[str, int],
        *_args: object,
        **_kwargs: object,
    ) -> None:
        apply_calls.append(dict(offsets))

    monkeypatch.setattr(frame_compare, "_apply_vspreview_manual_offsets", _record_apply)

    frame_compare._launch_vspreview(plans, summary, display, cfg, tmp_path, reporter, json_tail)

    script_path_str = audio_block.get("vspreview_script")
    assert script_path_str, "Script path should be recorded in JSON tail"
    script_path = Path(script_path_str)
    assert script_path.exists()
    script_text = script_path.read_text(encoding="utf-8")
    assert "OFFSET_MAP" in script_text
    assert "vs_core.configure" in script_text
    assert "ColorConfig" in script_text
    assert "AssumeFPS" in script_text
    assert recorded_command, "VSPreview command should be invoked when interactive"
    assert recorded_command[0][0] == frame_compare.sys.executable
    assert recorded_command[0][-1] == str(script_path)
    assert audio_block.get("vspreview_invoked") is True
    assert audio_block.get("vspreview_exit_code") == 0
    assert prompt_calls, "Prompt should be invoked even when returning default offsets"
    assert apply_calls == [{}]


def _make_json_tail_stub() -> frame_compare.JsonTail:
    audio_block: frame_compare.AudioAlignmentJSON = {
        "enabled": False,
        "reference_stream": None,
        "target_stream": {},
        "offsets_sec": {},
        "offsets_frames": {},
        "preview_paths": [],
        "confirmed": None,
        "offsets_filename": "offsets.toml",
        "manual_trim_summary": [],
        "suggestion_mode": True,
        "suggested_frames": {},
        "manual_trim_starts": {},
        "vspreview_manual_offsets": {},
        "vspreview_manual_deltas": {},
        "vspreview_reference_trim": None,
        "vspreview_script": None,
        "vspreview_invoked": False,
        "vspreview_exit_code": None,
    }
    tail: frame_compare.JsonTail = {
        "clips": [],
        "trims": {"per_clip": {}},
        "window": {},
        "alignment": {"manual_start_s": 0.0, "manual_end_s": "unchanged"},
        "audio_alignment": audio_block,
        "analysis": {},
        "render": {},
        "tonemap": {},
        "overlay": {},
        "verify": {
            "count": 0,
            "threshold": 0.0,
            "delta": {
                "max": None,
                "average": None,
                "frame": None,
                "file": None,
                "auto_selected": None,
            },
            "entries": [],
        },
        "cache": {},
        "slowpics": {
            "enabled": False,
            "title": {
                "inputs": {
                    "resolved_base": None,
                    "collection_name": None,
                    "collection_suffix": "",
                },
                "final": None,
            },
            "url": None,
            "shortcut_path": None,
            "deleted_screens_dir": False,
            "is_public": False,
            "is_hentai": False,
            "remove_after_days": 0,
        },
        "warnings": [],
        "workspace": {
            "root": "",
            "media_root": "",
            "config_path": "",
            "legacy_config": False,
        },
    }
    return tail


def _make_display_stub() -> frame_compare._AudioAlignmentDisplayData:
    return frame_compare._AudioAlignmentDisplayData(
        stream_lines=[],
        estimation_line=None,
        offset_lines=[],
        offsets_file_line="Offsets file: offsets.toml",
        json_reference_stream=None,
        json_target_streams={},
        json_offsets_sec={},
        json_offsets_frames={},
        warnings=[],
    )


def test_vspreview_manual_offsets_positive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_plan = frame_compare._ClipPlan(path=reference_path, metadata={"label": "Reference"})
    target_plan = frame_compare._ClipPlan(path=target_path, metadata={"label": "Target"})
    target_plan.trim_start = 5
    target_plan.has_trim_start_override = True
    summary = frame_compare._AudioAlignmentSummary(
        offsets_path=tmp_path / "offsets.toml",
        reference_name=reference_path.name,
        measurements=(),
        applied_frames={},
        baseline_shift=0,
        statuses={},
        reference_plan=reference_plan,
        final_adjustments={},
        swap_details={},
        suggested_frames={target_path.name: 3},
        suggestion_mode=True,
        manual_trim_starts={target_path.name: 5},
    )

    reporter = _RecordingOutputManager()
    json_tail = _make_json_tail_stub()
    display = _make_display_stub()

    captured: dict[str, object] = {}

    def fake_update(
        path: Path,
        reference_name: str,
        measurements: Sequence[AlignmentMeasurement],
        existing: Mapping[str, Mapping[str, object]],
        notes: Mapping[str, str],
    ) -> tuple[dict[str, int], dict[str, str]]:
        captured["path"] = path
        captured["reference"] = reference_name
        captured["measurements"] = list(measurements)
        captured["existing"] = dict(existing)
        captured["notes"] = dict(notes)
        applied = {m.file.name: int(m.frames or 0) for m in measurements}
        return applied, {name: "manual" for name in applied}

    monkeypatch.setattr(frame_compare.audio_alignment, "update_offsets_file", fake_update)

    frame_compare._apply_vspreview_manual_offsets(
        [reference_plan, target_plan],
        summary,
        {target_path.name: 7},
        reporter,
        json_tail,
        display,
    )

    assert target_plan.trim_start == 12
    assert summary.suggestion_mode is False
    assert summary.manual_trim_starts[target_path.name] == 12
    assert summary.vspreview_manual_offsets[target_path.name] == 12
    assert summary.vspreview_manual_deltas[target_path.name] == 7
    audio_block = json_tail["audio_alignment"]
    offsets_map = cast(dict[str, int], audio_block.get("vspreview_manual_offsets", {}))
    deltas_map = cast(dict[str, int], audio_block.get("vspreview_manual_deltas", {}))
    assert offsets_map[target_path.name] == 12
    assert deltas_map[target_path.name] == 7
    notes_map = cast(dict[str, str], captured["notes"])
    existing_map = cast(dict[str, Mapping[str, object]], captured["existing"])
    assert notes_map[target_path.name] == "VSPreview"
    entry = cast(dict[str, object], existing_map[target_path.name])
    assert entry.get("status") == "manual"
    assert int(cast(int | float, entry.get("frames", 0))) == 12
    assert any("VSPreview manual offset applied" in line for line in reporter.lines)


def test_vspreview_manual_offsets_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_plan = frame_compare._ClipPlan(path=reference_path, metadata={"label": "Reference"})
    target_plan = frame_compare._ClipPlan(path=target_path, metadata={"label": "Target"})
    target_plan.trim_start = 4
    summary = frame_compare._AudioAlignmentSummary(
        offsets_path=tmp_path / "offsets.toml",
        reference_name=reference_path.name,
        measurements=(),
        applied_frames={},
        baseline_shift=0,
        statuses={},
        reference_plan=reference_plan,
        final_adjustments={},
        swap_details={},
        suggested_frames={target_path.name: 0},
        suggestion_mode=True,
        manual_trim_starts={target_path.name: 4},
    )

    reporter = _RecordingOutputManager()
    json_tail = _make_json_tail_stub()
    display = _make_display_stub()

    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "update_offsets_file",
        lambda *_args, **_kwargs: ({target_path.name: 4, reference_path.name: 0}, {target_path.name: "manual", reference_path.name: "manual"}),
    )

    frame_compare._apply_vspreview_manual_offsets(
        [reference_plan, target_plan],
        summary,
        {target_path.name: 0},
        reporter,
        json_tail,
        display,
    )

    assert target_plan.trim_start == 4
    assert summary.manual_trim_starts[target_path.name] == 4
    assert summary.vspreview_manual_deltas[target_path.name] == 0
    audio_block = json_tail["audio_alignment"]
    offsets_map = cast(dict[str, int], audio_block.get("vspreview_manual_offsets", {}))
    assert offsets_map[target_path.name] == 4


def test_vspreview_manual_offsets_negative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_plan = frame_compare._ClipPlan(path=reference_path, metadata={"label": "Reference"})
    target_plan = frame_compare._ClipPlan(path=target_path, metadata={"label": "Target"})
    target_plan.trim_start = 3
    summary = frame_compare._AudioAlignmentSummary(
        offsets_path=tmp_path / "offsets.toml",
        reference_name=reference_path.name,
        measurements=(),
        applied_frames={},
        baseline_shift=0,
        statuses={},
        reference_plan=reference_plan,
        final_adjustments={},
        swap_details={},
        suggested_frames={target_path.name: -5},
        suggestion_mode=True,
        manual_trim_starts={target_path.name: 3},
    )

    reporter = _RecordingOutputManager()
    json_tail = _make_json_tail_stub()
    display = _make_display_stub()

    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "update_offsets_file",
        lambda *_args, **_kwargs: (
            {target_path.name: 0, reference_path.name: 4},
            {target_path.name: "manual", reference_path.name: "manual"},
        ),
    )

    frame_compare._apply_vspreview_manual_offsets(
        [reference_plan, target_plan],
        summary,
        {target_path.name: -7},
        reporter,
        json_tail,
        display,
    )

    assert target_plan.trim_start == 0
    assert reference_plan.trim_start == 4
    assert summary.manual_trim_starts[target_path.name] == 0
    assert summary.vspreview_manual_offsets[reference_path.name] == 4
    assert summary.vspreview_manual_deltas[target_path.name] == -3
    assert summary.vspreview_manual_deltas[reference_path.name] == 4
    audio_block = json_tail["audio_alignment"]
    assert audio_block.get("vspreview_reference_trim") == 4
    assert any("reference adjustment" in line for line in reporter.lines)


def test_vspreview_manual_offsets_multiple_negative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference_path = tmp_path / "Ref.mkv"
    target_a_path = tmp_path / "A.mkv"
    target_b_path = tmp_path / "B.mkv"
    reference_plan = frame_compare._ClipPlan(path=reference_path, metadata={"label": "Reference"})
    target_a_plan = frame_compare._ClipPlan(path=target_a_path, metadata={"label": "A"})
    target_b_plan = frame_compare._ClipPlan(path=target_b_path, metadata={"label": "B"})
    target_a_plan.trim_start = 5
    target_b_plan.trim_start = 5
    summary = frame_compare._AudioAlignmentSummary(
        offsets_path=tmp_path / "offsets.toml",
        reference_name=reference_path.name,
        measurements=(),
        applied_frames={},
        baseline_shift=0,
        statuses={},
        reference_plan=reference_plan,
        final_adjustments={},
        swap_details={},
        suggested_frames={
            target_a_path.name: -3,
            target_b_path.name: -7,
        },
        suggestion_mode=True,
        manual_trim_starts={
            target_a_path.name: 5,
            target_b_path.name: 5,
        },
    )

    reporter = _RecordingOutputManager()
    json_tail = _make_json_tail_stub()
    display = _make_display_stub()

    captured: dict[str, object] = {}

    def fake_update(
        path: Path,
        reference_name: str,
        measurements: Sequence[AlignmentMeasurement],
        existing: Mapping[str, Mapping[str, object]],
        notes: Mapping[str, str],
    ) -> tuple[dict[str, int], dict[str, str]]:
        captured["path"] = path
        captured["reference"] = reference_name
        captured["measurements"] = list(measurements)
        captured["existing"] = dict(existing)
        captured["notes"] = dict(notes)
        applied = {m.file.name: int(m.frames or 0) for m in measurements}
        return applied, {name: "manual" for name in applied}

    monkeypatch.setattr(frame_compare.audio_alignment, "update_offsets_file", fake_update)

    frame_compare._apply_vspreview_manual_offsets(
        [reference_plan, target_a_plan, target_b_plan],
        summary,
        {target_a_path.name: -3, target_b_path.name: -7},
        reporter,
        json_tail,
        display,
    )

    assert target_a_plan.trim_start == 4
    assert target_b_plan.trim_start == 0
    assert reference_plan.trim_start == 2
    assert summary.suggestion_mode is False
    assert summary.manual_trim_starts[target_a_path.name] == 4
    assert summary.manual_trim_starts[target_b_path.name] == 0
    assert summary.vspreview_manual_offsets[target_a_path.name] == 4
    assert summary.vspreview_manual_offsets[target_b_path.name] == 0
    assert summary.vspreview_manual_offsets[reference_path.name] == 2
    assert summary.vspreview_manual_deltas[target_a_path.name] == -1
    assert summary.vspreview_manual_deltas[target_b_path.name] == -5
    assert summary.vspreview_manual_deltas[reference_path.name] == 2

    audio_block = json_tail["audio_alignment"]
    offsets_map = cast(dict[str, int], audio_block.get("vspreview_manual_offsets", {}))
    deltas_map = cast(dict[str, int], audio_block.get("vspreview_manual_deltas", {}))
    assert offsets_map[target_a_path.name] == 4
    assert offsets_map[target_b_path.name] == 0
    assert offsets_map[reference_path.name] == 2
    assert deltas_map[target_a_path.name] == -1
    assert deltas_map[target_b_path.name] == -5
    assert deltas_map[reference_path.name] == 2

    measurements = cast(list[AlignmentMeasurement], captured["measurements"])
    assert {m.file.name for m in measurements} == {
        reference_path.name,
        target_a_path.name,
        target_b_path.name,
    }
    assert any("manual offset applied" in line for line in reporter.lines)
def _comparison_fixture_root() -> Path:
    """Return the repository-level comparison fixture directory."""

    return frame_compare.PROJECT_ROOT / "comparison_videos"


def test_cli_applies_overrides_and_naming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    first = tmp_path / "AAA - 01.mkv"
    second = tmp_path / "BBB - 01.mkv"
    for file in (first, second):
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)

    parse_calls: list[tuple[str, dict[str, object]]] = []

    def fake_parse(name: str, **kwargs: object) -> dict[str, object]:
        parse_calls.append((name, dict(kwargs)))
        if name.startswith("AAA"):
            return {"label": "AAA Short", "release_group": "AAA", "file_name": name}
        return {"label": "BBB Short", "release_group": "BBB", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

    ram_limits: list[int] = []
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit_mb: ram_limits.append(int(limit_mb)))

    init_calls: list[tuple[str, int, int | None, tuple[int, int] | None, str | None]] = []

    def fake_init_clip(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
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

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init_clip)

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

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

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

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    result: Result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
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

    expected_cache_dir = str(tmp_path.resolve())
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
    assert cache_info.path == (tmp_path / cfg.analysis.frame_data_filename).resolve()
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

    monkeypatch.setattr(frame_compare, "load_config", lambda _path: cfg)
    monkeypatch.setattr(frame_compare.vs_core, "configure", lambda *args, **kwargs: None)

    recorded_roots: list[Path] = []

    def fake_discover(root: Path) -> list[Path]:
        recorded_roots.append(root)
        raise frame_compare.CLIAppError("sentinel")

    monkeypatch.setattr(frame_compare, "_discover_media", fake_discover)

    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.toml"

    with pytest.raises(frame_compare.CLIAppError, match="sentinel"):
        frame_compare.run_cli(str(config_path))

    expected_root = (tmp_path / "comparison_videos").resolve()
    assert recorded_roots == [expected_root]


def test_run_cli_does_not_fallback_for_cli_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure run_cli reports missing CLI overrides instead of using fallbacks."""

    cfg = _make_config(tmp_path)

    monkeypatch.setattr(frame_compare, "load_config", lambda _path: cfg)
    def _fail_discover(*_args: object, **_kwargs: object) -> list[Path]:
        raise AssertionError("should not discover")

    monkeypatch.setattr(frame_compare, "_discover_media", _fail_discover)

    config_path = tmp_path / "config.toml"
    monkeypatch.chdir(tmp_path)

    with pytest.raises(frame_compare.CLIAppError, match="Input directory not found"):
        frame_compare.run_cli(str(config_path), input_dir="comparison_videos")


def test_cli_disables_json_tail_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    first = tmp_path / "AAA - 01.mkv"
    second = tmp_path / "BBB - 01.mkv"
    for file_path in (first, second):
        file_path.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.cli.emit_json_tail = False

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit_mb: None)

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

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)

    def fake_init(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
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

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)

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

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

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

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    result: Result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert '{"analysis"' not in result.output


def test_label_dedupe_preserves_short_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
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

    def fake_parse(name: str, **kwargs: object) -> dict[str, str]:
        return {"label": "[Group]", "release_group": "Group", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init_clip(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init_clip)
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

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

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

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    result: Result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert captured
    labels = captured[0]
    assert len(labels) == 2
    assert labels[0] != first.name and labels[1] != second.name
    assert labels[0] != labels[1]


def test_cli_reuses_frame_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    files = [tmp_path / "A.mkv", tmp_path / "B.mkv"]
    for file in files:
        file.write_bytes(b"data")

    cfg = _make_config(tmp_path)
    cfg.analysis.save_frames_data = True

    monkeypatch.setattr(frame_compare, "load_config", lambda _: cfg)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)

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

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

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

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)

    assert call_state["calls"] == 2
    assert call_state["cache_hits"] == 1


def test_cli_input_override_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
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

    def fake_init(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800)

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)
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

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

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

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    uploads: list[tuple[list[str], Path]] = []

    def fake_upload(
        image_paths: list[str],
        screen_dir: Path,
        cfg_slow: SlowpicsConfig,
        **kwargs: object,
    ) -> str:
        uploads.append((image_paths, screen_dir))
        return "https://slow.pics/c/abc/def"

    monkeypatch.setattr(frame_compare, "upload_comparison", fake_upload)

    result: Result = runner.invoke(
        frame_compare.main,
        ["--config", "dummy", "--input", str(override_dir), "--no-color"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert uploads
    screen_dir = Path(override_dir / cfg.screenshots.directory_name).resolve()
    assert not screen_dir.exists()
    assert uploads[0][1] == screen_dir


def test_cli_tmdb_resolution_populates_slowpics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    def fake_init(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
    ) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            width=1280,
            height=720,
            fps_num=24000,
            fps_den=1001,
            num_frames=1800,
        )

    monkeypatch.setattr(frame_compare.vs_core, "init_clip", fake_init)

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

    monkeypatch.setattr(frame_compare, "select_frames", fake_select)

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

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    uploads: list[tuple[list[str], Path, str, str]] = []

    def fake_upload(
        image_paths: list[str],
        screen_dir: Path,
        cfg_slow: SlowpicsConfig,
        **kwargs: object,
    ) -> str:
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
    assert result.json_tail is not None
    slowpics_value = result.json_tail.get("slowpics")
    assert slowpics_value is not None
    slowpics_json = _expect_mapping(slowpics_value)
    title_json = _expect_mapping(slowpics_json["title"])
    inputs_json = _expect_mapping(title_json["inputs"])
    assert title_json["final"] == "Resolved Title (2023) [MOVIE]"
    assert inputs_json["resolved_base"] == "Resolved Title (2023)"
    assert slowpics_json["url"] == "https://slow.pics/c/example"
    assert slowpics_json["shortcut_path"].endswith("slowpics_example.url")
    assert slowpics_json["deleted_screens_dir"] is False


def test_cli_tmdb_resolution_sets_default_collection_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    monkeypatch.setattr(
        frame_compare.vs_core,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800),
    )
    monkeypatch.setattr(frame_compare, "select_frames", lambda *_, **__: [10, 20])
    monkeypatch.setattr(frame_compare, "generate_screenshots", lambda *args, **kwargs: [str(tmp_path / "shot.png")])
    monkeypatch.setattr(frame_compare, "upload_comparison", lambda *args, **kwargs: "https://slow.pics/c/example")
    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    def fake_resolve(*_: object, **__: object) -> None:
        raise TMDBAmbiguityError([candidate])

    monkeypatch.setattr(frame_compare, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(frame_compare, "_prompt_manual_tmdb", lambda candidates: ("TV", "9999"))
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)
    monkeypatch.setattr(
        frame_compare.vs_core,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400),
    )
    monkeypatch.setattr(frame_compare, "select_frames", lambda *_, **__: [3, 6])
    monkeypatch.setattr(frame_compare, "generate_screenshots", lambda *args, **kwargs: [str(tmp_path / "img.png")])
    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

    assert result.config.slowpics.tmdb_id == "9999"
    assert result.config.slowpics.tmdb_category == "TV"
    assert result.config.slowpics.collection_name == "Label for Alpha.mkv"


def test_cli_tmdb_confirmation_manual_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    async def fake_resolve(*_: object, **__: object) -> TMDBResolution:
        return resolution

    monkeypatch.setattr(frame_compare, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(frame_compare, "_prompt_tmdb_confirmation", lambda res: (True, ("MOVIE", "999")))
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)
    monkeypatch.setattr(
        frame_compare.vs_core,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400),
    )
    monkeypatch.setattr(frame_compare, "select_frames", lambda *_, **__: [1, 2])
    monkeypatch.setattr(frame_compare, "generate_screenshots", lambda *args, **kwargs: [str(tmp_path / "img.png")])
    monkeypatch.setattr(frame_compare, "Progress", DummyProgress)

    result = frame_compare.run_cli("dummy", None)

    assert result.config.slowpics.tmdb_id == "999"
    assert result.config.slowpics.tmdb_category == "MOVIE"


def test_cli_tmdb_confirmation_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    async def fake_resolve(*_: object, **__: object) -> TMDBResolution:
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



def test_audio_alignment_block_and_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
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

    def fake_parse(name: str, **_kwargs: object) -> dict[str, str]:
        """
        Create a minimal fake parse result for a clip name.
        
        Parameters:
            name (str): Clip identifier or filename used to derive the returned label. Additional keyword arguments are ignored.
        
        Returns:
            dict: Mapping with keys:
                - "label" (str): "Clip A" if `name` starts with "ClipA", otherwise "Clip B".
                - "file_name" (str): The original `name` value.
        """
        if name.startswith("ClipA"):
            return {"label": "Clip A", "file_name": name}
        return {"label": "Clip B", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init_clip(
        path: str | Path,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | Path | None = None,
    ) -> types.SimpleNamespace:
        """
        Create a lightweight fake clip object for tests that resembles the real clip interface.
        
        Parameters:
            path: Path-like or str specifying the clip file path.
            trim_start (int): Ignored in this fake; present for compatibility with callers.
            trim_end (int | None): Ignored in this fake; present for compatibility with callers.
            fps_map: Ignored in this fake; present for compatibility with callers.
            cache_dir: Ignored in this fake; present for compatibility with callers.
        
        Returns:
            SimpleNamespace: An object with attributes:
                - path (Path): Resolved Path of the provided `path`.
                - width (int): Horizontal resolution (1920).
                - height (int): Vertical resolution (1080).
                - fps_num (int): Frame rate numerator (24000).
                - fps_den (int): Frame rate denominator (1001).
                - num_frames (int): Total frame count (24000).
        """
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
        Create a fake set of screenshot files in out_dir and return their file paths.
        
        This helper ensures out_dir exists and produces a list of string paths representing generated shot images; the number of returned paths is len(frames) * len(files).
        
        Parameters:
            out_dir (Path): Directory where fake screenshot files are created.
            frames (Sequence): Sequence of frame descriptors used to determine per-file shot count.
            files (Sequence): Sequence of input files; combined with frames to compute total shots.
        
        Returns:
            list[str]: Paths to the generated shot image files as strings.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / f"shot_{idx}.png") for idx in range(len(frames) * len(files))]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    def fake_probe(path: Path) -> list[AudioStreamInfo]:
        """
        Create a fake audio probe result for the given file path.
        
        Parameters:
            path (Path): File path to probe; compared against the module-level `reference_path` to determine which mock stream to return.
        
        Returns:
            list[AudioStreamInfo]: A single-item list with a mocked audio stream. If `path == reference_path` the stream has `index=0`, `language='eng'`, and `is_default=True`; otherwise the stream has `index=1`, `language='jpn'`, and `is_default=False`.
        """
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

    def fake_update(
        _path: Path,
        reference_name: str,
        measurements: Iterable[AlignmentMeasurement],
        _existing: Mapping[str, int],
        _negative_notes: Mapping[str, str],
    ) -> tuple[dict[str, int], dict[str, str]]:
        """
        Produce applied frame indices and status labels for a set of measurement objects.
        
        This test helper assigns 0 to the provided reference_name and, for each item in measurements,
        maps the measurement's file name to its frames value or 0 when frames is falsy. It also
        marks every measurement's status as "auto".
        
        Parameters:
        	reference_name (str): Identifier to be added to the applied frames mapping with value 0.
        	measurements (Iterable): Iterable of objects with `file.name` and `frames` attributes.
        
        Returns:
        	tuple: A pair (applied_frames, statuses).
        	- applied_frames (dict): Mapping of names (reference_name and each measurement.file.name) to integer frame indices.
        	- statuses (dict): Mapping of each measurement.file.name to the string `"auto"`.
        """
        applied_frames: dict[str, int] = {reference_name: 0}
        applied_frames.update({m.file.name: m.frames or 0 for m in measurements})
        statuses: dict[str, str] = {m.file.name: "auto" for m in measurements}
        return applied_frames, statuses

    monkeypatch.setattr(frame_compare.audio_alignment, "update_offsets_file", fake_update)

    result: Result = runner.invoke(
        frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False
    )
    assert result.exit_code == 0

    output_lines: list[str] = result.output.splitlines()
    streams_idx = next(i for i, line in enumerate(output_lines) if line.strip().startswith("Streams:"))
    assert 'ref="Clip A->' in output_lines[streams_idx]
    clip_b_line = output_lines[streams_idx + 1] if streams_idx + 1 < len(output_lines) else ""
    assert "Clip B" in (output_lines[streams_idx] + clip_b_line)
    assert any("Estimating audio offsets" in line for line in output_lines)
    offset_idx = next((i for i, line in enumerate(output_lines) if line.strip().startswith("Offset:")), None)
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
    payload: dict[str, Any] = json.loads(json_payload)
    audio_json = payload["audio_alignment"]
    assert audio_json["reference_stream"].startswith("Clip A")
    assert audio_json["target_stream"]["Clip B"].startswith("aac/jpn")
    assert audio_json["offsets_sec"]["Clip B"] == pytest.approx(0.1)
    assert audio_json["offsets_frames"]["Clip B"] == 3
    assert audio_json["preview_paths"] == []
    assert audio_json["confirmed"] == "auto"
    tonemap_json = payload["tonemap"]
    assert tonemap_json["overlay_mode"] == "diagnostic"


def test_audio_alignment_default_duration_avoids_zero_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    """
    Verifies that leaving audio alignment duration unspecified does not pass a zero-length window to the measurement routine.
    
    Configures audio alignment with start_seconds and duration_seconds set to None, runs the CLI, and asserts that the call to the alignment measurement does not include a `duration_seconds` value of zero (i.e., it remains `None`).
    """
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

    def fake_parse(name: str, **_kwargs: object) -> dict[str, str]:
        """
        Create a minimal fake parse result for a clip name.
        
        Parameters:
            name (str): Clip identifier or filename used to derive the returned label. Additional keyword arguments are ignored.
        
        Returns:
            dict: Mapping with keys:
                - "label" (str): "Clip A" if `name` starts with "ClipA", otherwise "Clip B".
                - "file_name" (str): The original `name` value.
        """
        if name.startswith("ClipA"):
            return {"label": "Clip A", "file_name": name}
        return {"label": "Clip B", "file_name": name}

    monkeypatch.setattr(frame_compare, "parse_filename_metadata", fake_parse)
    monkeypatch.setattr(frame_compare.vs_core, "set_ram_limit", lambda limit: None)

    def fake_init_clip(
        path: str | Path,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | Path | None = None,
    ) -> types.SimpleNamespace:
        """
        Create a lightweight fake clip object for tests that resembles the real clip interface.
        
        Parameters:
            path: Path-like or str specifying the clip file path.
            trim_start (int): Ignored in this fake; present for compatibility with callers.
            trim_end (int | None): Ignored in this fake; present for compatibility with callers.
            fps_map: Ignored in this fake; present for compatibility with callers.
            cache_dir: Ignored in this fake; present for compatibility with callers.
        
        Returns:
            SimpleNamespace: An object with attributes:
                - path (Path): Resolved Path of the provided `path`.
                - width (int): Horizontal resolution (1920).
                - height (int): Vertical resolution (1080).
                - fps_num (int): Frame rate numerator (24000).
                - fps_den (int): Frame rate denominator (1001).
                - num_frames (int): Total frame count (24000).
        """
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
        Create the output directory and return a single fake screenshot path.
        
        Returns:
            list[str]: A one-element list containing the string path to "shot.png" inside `out_dir`.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        return [str(out_dir / "shot.png")]

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    def fake_probe(path: Path) -> list[AudioStreamInfo]:
        """
        Create a fake audio probe result for the given file path.
        
        Parameters:
            path (Path): File path to probe; compared against the module-level `reference_path` to determine which mock stream to return.
        
        Returns:
            list[AudioStreamInfo]: A single-item list with a mocked audio stream. If `path == reference_path` the stream has `index=0`, `language='eng'`, and `is_default=True`; otherwise the stream has `index=1`, `language='jpn'`, and `is_default=False`.
        """
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

    def fake_measure(*args: object, **kwargs: object) -> list[AlignmentMeasurement]:
        """
        Stub measurement function used in tests.
        
        Records any keyword arguments into the enclosing `captured_kwargs` mapping and returns a single-element list containing the preconstructed `measurement` object.
        
        Returns:
            list: A list with the `measurement` object as its only element.
        """
        captured_kwargs.update(kwargs)
        return [measurement]

    monkeypatch.setattr(frame_compare.audio_alignment, "measure_offsets", fake_measure)
    monkeypatch.setattr(frame_compare.audio_alignment, "load_offsets", lambda *_args, **_kwargs: ({}, {}))
    monkeypatch.setattr(
        frame_compare.audio_alignment,
        "update_offsets_file",
        lambda *_args, **_kwargs: ({target_path.name: 3}, {target_path.name: "auto"}),
    )

    result: Result = runner.invoke(frame_compare.main, ["--config", "dummy", "--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert captured_kwargs.get("duration_seconds") is None


def _build_alignment_context(
    tmp_path: Path,
) -> tuple[
    AppConfig,
    list[frame_compare._ClipPlan],
    frame_compare._AudioAlignmentSummary,
    frame_compare._AudioAlignmentDisplayData,
]:
    """
    Builds a minimal audio-alignment test context with example clips, plans, and alignment state.
    
    Parameters:
        tmp_path (Path): Temporary directory used to create sample reference and target clip files.
    
    Returns:
        tuple: A 4-tuple containing:
            - cfg: AppConfig with audio alignment and confirmation-with-screenshots enabled.
            - plans: List containing the reference and target ClipPlan objects for the two sample clips.
            - summary: AudioAlignmentSummary prepopulated for the reference clip.
            - display: AudioAlignmentDisplayData initialized with empty/placeholder display values.
    """
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
        suggested_frames={},
        suggestion_mode=False,
        manual_trim_starts={},
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
        manual_trim_lines=[],
    )

    return cfg, [reference_plan, target_plan], summary, display


class _RecordingOutputManager(frame_compare.CliOutputManager):
    """CliOutputManager test double that records lines emitted during confirmation flows."""

    def __init__(self) -> None:
        layout_path = Path(frame_compare.__file__).with_name("cli_layout.v1.json")
        super().__init__(
            quiet=False,
            verbose=False,
            no_color=True,
            layout_path=layout_path,
            console=Console(record=True, force_terminal=False),
        )
        self.lines: list[str] = []

    def line(self, text: str) -> None:
        """Record the rendered line while still delegating to the base implementation."""
        self.lines.append(text)
        super().line(text)


def test_confirm_alignment_reports_preview_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg, plans, summary, display = _build_alignment_context(tmp_path)

    reporter = _RecordingOutputManager()
    generated_paths: list[Path] = []

    def fake_generate(*args: object, **_kwargs: object) -> list[Path]:
        """
        Test helper that simulates screenshot generation for tests.
        
        This function expects its fifth positional argument (args[4]) to be a pathlib.Path for an output directory; it ensures that directory exists, records two synthetic shot paths by appending them to the module-level list `generated_paths`, and returns the two Path objects.
        
        Parameters:
            *args: Positional arguments where the fifth element (args[4]) is the output directory Path.
            **_kwargs: Ignored.
        
        Returns:
            list[pathlib.Path]: A list containing two shot Path objects (shot_0.png and shot_1.png) inside the output directory.
        """
        out_dir = cast(Path, args[4])
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


def test_confirm_alignment_raises_cli_error_on_screenshot_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg, plans, summary, display = _build_alignment_context(tmp_path)

    def fake_generate(*_args: object, **_kwargs: object) -> list[Path]:
        """
        A stub screenshot-generation function that always fails.

        Raises:
            frame_compare.ScreenshotError: Always raised with the message "boom".
        """
        raise frame_compare.ScreenshotError("boom")

    monkeypatch.setattr(frame_compare, "generate_screenshots", fake_generate)

    with pytest.raises(frame_compare.CLIAppError, match="Alignment preview failed"):
        frame_compare._confirm_alignment_with_screenshots(
            plans,
            summary,
            cfg,
            tmp_path,
            _RecordingOutputManager(),
            display,
        )


def test_run_cli_calls_alignment_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Verifies that running the CLI triggers the audio-alignment confirmation flow when screenshot confirmation is enabled.
    
    Sets up a configuration enabling audio alignment with screenshot confirmation, creates two dummy media files, and monkeypatches discovery, metadata parsing, plan building, selection, and alignment application. Replaces the confirmation function with one that records its arguments and raises a sentinel exception so the test can assert the confirmation was invoked with the expected parameters.
    """
    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.confirm_with_screenshots = True

    monkeypatch.setattr(frame_compare, "load_config", lambda _path: cfg)

    files: list[Path] = [tmp_path / "Ref.mkv", tmp_path / "Tgt.mkv"]
    for file in files:
        file.write_bytes(b"data")

    def fake_discover(_root: Path) -> list[Path]:
        """
        Return a precomputed list of discovered files; the provided `_root` argument is ignored.
        
        Returns:
            files (list): The predefined list of discovered file paths.
        """
        return files

    def fake_parse_metadata(_files: Sequence[Path], _naming: object) -> list[dict[str, str]]:
        """
        Produce metadata for a reference/target pair using the first two entries of the provided files.
        
        Parameters:
            _files (Sequence[pathlib.Path|os.PathLike|object]): Iterable where the first two items represent the reference and target files; only their `.name` is used.
            _naming (any): Unused naming parameter kept for signature compatibility.
        
        Returns:
            list[dict]: Two dictionaries with keys `label`, `file_name`, `year`, `title`, `anime_title`, `imdb_id`, and `tvdb_id`. The `label` values are `"Reference"` and `"Target"`, `file_name` is taken from the corresponding file's `.name`, and the remaining fields are empty strings.
        """
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

    def fake_build_plans(
        _files: Sequence[Path], metadata: Sequence[dict[str, str]], _cfg: AppConfig
    ) -> list[frame_compare._ClipPlan]:
        """
        Builds a list of clip plans from input file paths and corresponding metadata, marking the first clip as the reference.
        
        Parameters:
            _files (Sequence[Path]): Input file paths in the order they should be planned.
            metadata (Sequence): Per-file metadata objects; must have the same length as `_files`.
            _cfg: Configuration object (not used by this fake builder, accepted for signature compatibility).
        
        Returns:
            list[frame_compare._ClipPlan]: A list of ClipPlan objects where the first element has `use_as_reference=True` and all others have `use_as_reference=False`.
        """
        plans: list[frame_compare._ClipPlan] = []
        for idx, path in enumerate(_files):
            plans.append(
                frame_compare._ClipPlan(
                    path=path,
                    metadata=metadata[idx],
                    use_as_reference=(idx == 0),
                )
            )
        return plans

    def fake_pick_analyze(
        _files: Sequence[Path],
        _metadata: Sequence[object],
        _analyze_clip: object,
        cache_dir: Path | None = None,
    ) -> Path:
        """
        Select the first candidate file for analysis.
        
        Parameters:
            _files: Sequence of candidate file paths; the first element is selected.
            _metadata: Ignored.
            _analyze_clip: Ignored.
            cache_dir: Ignored.
        
        Returns:
            The first file from `_files`.
        """
        return files[0]

    offsets_path = tmp_path / "alignment.toml"

    def fake_maybe_apply(
        plans: Sequence[frame_compare._ClipPlan],
        _cfg: AppConfig,
        _analyze_path: Path,
        _root: Path,
        _overrides: object,
        reporter: object | None = None,
    ) -> tuple[frame_compare._AudioAlignmentSummary, frame_compare._AudioAlignmentDisplayData]:
        """
        Create and return a synthetic audio-alignment summary and display objects for testing.
        
        Parameters:
            plans (Sequence): Sequence of clip plan objects; the first plan is used as the reference.
            reporter (optional): Ignored; present for API compatibility.
        
        Returns:
            tuple: A pair (summary, display) where:
                - summary: a frame_compare._AudioAlignmentSummary with the first plan as the reference_plan,
                  empty measurements/applied_frames/statuses, and baseline_shift 0.
                - display: a frame_compare._AudioAlignmentDisplayData containing empty display lines,
                  an offsets file line referencing the module's offsets path, and JSON-ready fields
                  for a single target with zero offset (0.0 seconds, 0 frames).
        """
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
            suggested_frames={},
            suggestion_mode=False,
            manual_trim_starts={},
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
            manual_trim_lines=[],
        )
        return summary, display

    class _DummyReporter:
        def __init__(self, *_, **__):
            """
            Create a no-op progress context used to mock progress handling in tests.
            
            This initializer accepts and ignores any positional or keyword arguments and configures a
            `console` attribute whose `print` method is a no-op to suppress output during tests.
            """
            self.console = types.SimpleNamespace(print=lambda *args, **kwargs: None)

        def update_values(self, *_args, **_kwargs):
            """
            No-op progress update method used to satisfy a progress interface.
            
            Accepts arbitrary positional and keyword arguments and performs no action.
            """
            return None

        def set_flag(self, *_args, **_kwargs):
            """
            No-op method that accepts any positional and keyword arguments and does nothing.
            
            Used as a compatibility stub where a flag-setting method is required but no action is desired.
            """
            return None

        def line(self, *_args, **_kwargs):
            """
            Accepts any positional and keyword arguments and performs no action.
            
            Used as a no-op placeholder to satisfy progress-reporting interfaces.
            """
            return None

        def verbose_line(self, *_args, **_kwargs):
            """
            A no-op placeholder that accepts any positional or keyword arguments and does nothing.
            
            This method intentionally ignores all inputs and always returns None; it can be used where a verbose callback is optional or not required.
            """
            return None

        def render_sections(self, *_args, **_kwargs):
            """
            No-op renderer for section content; accepts any positional and keyword arguments and performs no action.
            
            Parameters:
                *_args: Arbitrary positional arguments that are ignored.
                **_kwargs: Arbitrary keyword arguments that are ignored.
            
            Returns:
                None: Always returns None.
            """
            return None

        def update_progress_state(self, *_args, **_kwargs):
            """
            No-op progress update method that accepts any arguments and has no effect.
            
            Used as a placeholder in contexts where progress updates are optional; accepts arbitrary positional
            and keyword arguments and performs no action.
            """
            return None

        def set_status(self, *_args, **_kwargs):
            """
            No-op status handler that ignores all arguments.
            
            This method accepts any positional and keyword arguments and intentionally performs no action.
            """
            return None

        def create_progress(self, *_args, **_kwargs):
            """
            Create a no-op progress context manager.
            
            Parameters:
                *_args, **_kwargs: Ignored positional and keyword arguments kept for API compatibility.
            
            Returns:
                DummyProgress: A progress-like object that performs no operations and can be used as a context manager.
            """
            return DummyProgress()

    class _SentinelError(Exception):
        pass

    called: dict[str, object] = {}

    def fake_confirm(
        plans: Sequence[frame_compare._ClipPlan],
        summary: frame_compare._AudioAlignmentSummary,
        cfg_obj: AppConfig,
        root: Path,
        reporter: object,
        display: frame_compare._AudioAlignmentDisplayData,
    ) -> None:
        """
        Test helper that records its invocation arguments and then raises a sentinel error.
        
        Parameters:
            plans: The clip plans passed to the confirmation function.
            summary: The summary object produced by analysis or alignment.
            cfg_obj: The application configuration object.
            root: The root path or context used by the caller.
            reporter: The reporter used to emit messages.
            display: The display/preview object provided to the confirmation flow.
        
        Raises:
            _SentinelError: Always raised to signal that this fake confirmation was invoked.
        """
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
