import asyncio
import datetime as dt
import json
import types
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, Mapping, cast

import click
import pytest
from click.testing import CliRunner, Result
from rich.console import Console

import frame_compare
import src.frame_compare.alignment_preview as alignment_preview_module
import src.frame_compare.cache as cache_module
import src.frame_compare.config_helpers as config_helpers_module
import src.frame_compare.core as core_module
import src.frame_compare.media as media_module
import src.frame_compare.preflight as preflight_module
from src.analysis import CacheLoadResult, FrameMetricsCacheInfo, SelectionDetail
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
    ReportConfig,
    RuntimeConfig,
    ScreenshotConfig,
    SlowpicsConfig,
    SourceConfig,
    TMDBConfig,
)
from src.frame_compare import runner as runner_module
from src.frame_compare.cli_runtime import (
    AudioAlignmentJSON,
    CliOutputManager,
    JsonTail,
    _AudioAlignmentDisplayData,
    _AudioAlignmentSummary,
    _ClipPlan,
)
from src.screenshot import ScreenshotError
from src.tmdb import TMDBAmbiguityError, TMDBCandidate, TMDBResolution, TMDBResolutionError


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


def _patch_load_config(monkeypatch: pytest.MonkeyPatch, cfg: AppConfig) -> None:
    """Ensure both the CLI shim and core module reuse the provided config."""

    monkeypatch.setattr(core_module, "load_config", lambda *_args, **_kwargs: cfg)
    monkeypatch.setattr(frame_compare, "load_config", lambda *_args, **_kwargs: cfg)
    monkeypatch.setattr(preflight_module, "load_config", lambda *_args, **_kwargs: cfg)
    if hasattr(runner_module, "preflight_utils"):
        monkeypatch.setattr(runner_module.preflight_utils, "load_config", lambda *_args, **_kwargs: cfg, raising=False)


def _selection_details_to_json(details: Mapping[int, SelectionDetail]) -> Dict[int, Dict[str, str]]:
    """Helper used across tests to serialize selection details."""

    return {frame: {"label": detail.label} for frame, detail in details.items()}


@dataclass
class _CliRunnerEnvState:
    """Tracked state for the CLI harness."""

    workspace_root: Path
    media_root: Path
    config_path: Path
    cfg: AppConfig


def _make_cli_preflight(
    base_dir: Path,
    cfg: AppConfig,
    *,
    workspace_name: str | None = None,
) -> core_module.PreflightResult:
    """Build a PreflightResult anchored in a temporary workspace."""

    workspace_root = base_dir / (workspace_name or "workspace")
    workspace_root.mkdir(parents=True, exist_ok=True)

    config_dir = workspace_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    if not config_path.exists():
        config_path.write_text("config = true\n", encoding="utf-8")

    input_dir = Path(cfg.paths.input_dir)
    if input_dir.is_absolute():
        media_root = input_dir
    else:
        media_root = workspace_root / input_dir
    media_root.mkdir(parents=True, exist_ok=True)

    return core_module.PreflightResult(
        workspace_root=workspace_root,
        media_root=media_root,
        config_path=config_path,
        config=cfg,
        warnings=(),
        legacy_config=False,
    )


class _CliRunnerEnv:
    """Factory that installs deterministic CLI preflight results for tests."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, base_dir: Path) -> None:
        self._monkeypatch = monkeypatch
        self._base_dir = base_dir
        self.cfg = core_module._fresh_app_config()
        self.state: _CliRunnerEnvState | None = None
        self.reinstall()

    def reinstall(
        self,
        cfg: AppConfig | None = None,
        *,
        workspace_name: str | None = None,
    ) -> _CliRunnerEnvState:
        """Rebuild the harness with the provided config and workspace label."""

        if cfg is not None:
            self.cfg = cfg
        preflight = _make_cli_preflight(
            self._base_dir,
            self.cfg,
            workspace_name=workspace_name,
        )

        def _fake_preflight(**_kwargs: object) -> core_module.PreflightResult:
            return preflight

        module_targets = (
            core_module,
            frame_compare,
            runner_module.core,
            preflight_module,
            getattr(runner_module, "preflight_utils", None),
        )
        for module in module_targets:
            if module is None:
                continue
            for attr_name in ("prepare_preflight", "_prepare_preflight"):
                self._monkeypatch.setattr(module, attr_name, _fake_preflight, raising=False)

        self.state = _CliRunnerEnvState(
            workspace_root=preflight.workspace_root,
            media_root=preflight.media_root,
            config_path=preflight.config_path,
            cfg=self.cfg,
        )
        return self.state

    @property
    def workspace_root(self) -> Path:
        assert self.state is not None
        return self.state.workspace_root

    @property
    def media_root(self) -> Path:
        assert self.state is not None
        return self.state.media_root

    @property
    def config_path(self) -> Path:
        assert self.state is not None
        return self.state.config_path


def _patch_core_helper(monkeypatch: pytest.MonkeyPatch, attr: str, value: object) -> None:
    """Patch both frame_compare.* and runner_module.core.* helpers simultaneously."""

    alias_map = {
        "prepare_preflight": ("_prepare_preflight",),
        "_prepare_preflight": ("prepare_preflight",),
        "collect_path_diagnostics": ("_collect_path_diagnostics",),
        "_collect_path_diagnostics": ("collect_path_diagnostics",),
    }
    attrs_to_patch = (attr,) + alias_map.get(attr, tuple())

    targets = [
        frame_compare,
        runner_module.core,
        preflight_module,
        media_module,
        cache_module,
        alignment_preview_module,
        config_helpers_module,
        getattr(runner_module, "preflight_utils", None),
        getattr(runner_module, "media_utils", None),
        getattr(runner_module, "cache_utils", None),
        getattr(runner_module, "alignment_preview_utils", None),
        getattr(runner_module, "config_helpers", None),
    ]
    for target in targets:
        if target is None:
            continue
        for attr_name in attrs_to_patch:
            if hasattr(target, attr_name):
                monkeypatch.setattr(target, attr_name, value, raising=False)


def _patch_vs_core(monkeypatch: pytest.MonkeyPatch, attr: str, value: object) -> None:
    """Patch VapourSynth helpers in both the shim module and the runner module."""

    monkeypatch.setattr(frame_compare.vs_core, attr, value, raising=False)
    monkeypatch.setattr(runner_module.vs_core, attr, value, raising=False)


def _patch_runner_module(monkeypatch: pytest.MonkeyPatch, attr: str, value: object) -> None:
    """Patch shared runner dependencies exposed at the runner module level."""

    targets = [
        frame_compare,
        core_module,
        runner_module,
        getattr(runner_module, "preflight_utils", None),
        getattr(runner_module, "media_utils", None),
        getattr(runner_module, "cache_utils", None),
        getattr(runner_module, "alignment_preview_utils", None),
        getattr(runner_module, "config_helpers", None),
        alignment_preview_module,
    ]
    for target in targets:
        if target is None:
            continue
        if hasattr(target, attr):
            monkeypatch.setattr(target, attr, value, raising=False)


def _patch_audio_alignment(monkeypatch: pytest.MonkeyPatch, attr: str, value: object) -> None:
    """Patch audio alignment helpers in both frame_compare and core module namespaces."""

    target = getattr(frame_compare, "audio_alignment", None)
    if target is not None:
        monkeypatch.setattr(target, attr, value, raising=False)
    monkeypatch.setattr(core_module.audio_alignment, attr, value, raising=False)
    monkeypatch.setattr(runner_module.core.audio_alignment, attr, value, raising=False)


@pytest.fixture
def cli_runner_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _CliRunnerEnv:
    """Install a deterministic CLI harness and expose its state to tests."""

    return _CliRunnerEnv(monkeypatch, tmp_path)


@pytest.fixture(autouse=True)
def stub_vs_core(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a default VapourSynth stub so tests never import the real module."""

    def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    def _default_clip(*_args: object, **_kwargs: object) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            width=1280,
            height=720,
            fps_num=24000,
            fps_den=1001,
            num_frames=120,
        )

    _patch_vs_core(monkeypatch, "configure", _noop)
    _patch_vs_core(monkeypatch, "set_ram_limit", _noop)
    _patch_vs_core(monkeypatch, "init_clip", _default_clip)


def test_run_cli_delegates_to_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The run_cli shim should forward requests to the runner module."""

    cfg = core_module._fresh_app_config()
    dummy_result = frame_compare.RunResult(
        files=[],
        frames=[],
        out_dir=tmp_path,
        out_dir_created=False,
        out_dir_created_path=None,
        root=tmp_path,
        config=cfg,
        image_paths=[],
        slowpics_url=None,
        json_tail=None,
        report_path=None,
    )
    captured: dict[str, runner_module.RunRequest] = {}

    def _fake_run(request: runner_module.RunRequest) -> frame_compare.RunResult:
        captured["request"] = request
        return dummy_result

    monkeypatch.setattr(runner_module, "run", _fake_run)
    result = frame_compare.run_cli(
        "config-path",
        "input-dir",
        root_override=str(tmp_path),
        audio_track_overrides=("A=B",),
        quiet=True,
        verbose=True,
        no_color=True,
        report_enable_override=True,
        skip_wizard=True,
        debug_color=True,
        tonemap_overrides={"preset": "reference"},
    )

    assert result is dummy_result
    request = captured["request"]
    assert request.config_path == "config-path"
    assert request.input_dir == "input-dir"
    assert request.root_override == str(tmp_path)
    assert request.audio_track_overrides == ("A=B",)
    assert request.quiet is True
    assert request.verbose is True
    assert request.no_color is True
    assert request.report_enable_override is True
    assert request.skip_wizard is True
    assert request.debug_color is True
    assert request.tonemap_overrides == {"preset": "reference"}


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
        report=ReportConfig(enable=False),
    )


def _make_runner_preflight(workspace_root: Path, media_root: Path, cfg: AppConfig) -> core_module.PreflightResult:
    """Build a PreflightResult pointing at prepared workspace/media roots for runner tests."""
    config_dir = workspace_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    config_path.write_text("config", encoding="utf-8")
    cfg.paths.input_dir = str(media_root)
    return core_module.PreflightResult(
        workspace_root=workspace_root,
        media_root=media_root,
        config_path=config_path,
        config=cfg,
        warnings=(),
        legacy_config=False,
    )


def test_audio_alignment_manual_vspreview_handles_existing_trim(
    tmp_path: Path,
) -> None:
    """Manual VSPreview flow reports trims without crashing when alignment is off."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = False
    cfg.audio_alignment.use_vspreview = True

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )
    target_plan.trim_start = 42
    target_plan.has_trim_start_override = True

    summary, display = core_module._maybe_apply_audio_alignment(
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
    assert summary.manual_trim_starts[target_path.name] == 42
    assert any("Existing manual trim" in line for line in display.offset_lines)
    assert any("manual alignment enabled" in warning for warning in display.warnings)


def test_audio_alignment_string_false_vspreview_triggers_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """String config values like "off" should disable VSPreview reuse logic."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.use_vspreview = "off"  # type: ignore[assignment]

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )

    manual_entry = {
        "status": "manual",
        "note": "VSPreview delta",
        "frames": 7,
    }

    monkeypatch.setattr(
        core_module.audio_alignment,
        "load_offsets",
        lambda _path: (reference_path.name, {target_path.name: manual_entry}),
    )

    class _SentinelError(Exception):
        pass

    def boom(*_args: object, **_kwargs: object) -> list[object]:
        raise _SentinelError

    _patch_audio_alignment(monkeypatch, "measure_offsets", boom)
    monkeypatch.setattr(
        core_module.audio_alignment,
        "update_offsets_file",
        lambda *args, **kwargs: ({}, {}),
    )

    with pytest.raises(_SentinelError):
        core_module._maybe_apply_audio_alignment(
            [reference_plan, target_plan],
            cfg,
            reference_path,
            tmp_path,
            {},
            reporter=None,
        )


def test_audio_alignment_prompt_reuse_decline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When prompted and declined, cached offsets are reused without recomputation."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.prompt_reuse_offsets = True
    cfg.audio_alignment.confirm_with_screenshots = False
    cfg.audio_alignment.frame_offset_bias = 0

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )

    cached_entry = {
        "frames": 6,
        "seconds": 0.25,
        "correlation": 0.95,
        "target_fps": 24.0,
        "status": "auto",
    }

    monkeypatch.setattr(
        core_module.audio_alignment,
        "load_offsets",
        lambda _path: (reference_path.name, {target_path.name: dict(cached_entry)}),
    )
    def _fail_measure(*_args: object, **_kwargs: object) -> list[AlignmentMeasurement]:
        raise AssertionError("measure_offsets should not run")

    def _fail_update(*_args: object, **_kwargs: object) -> tuple[dict[str, int], dict[str, str]]:
        raise AssertionError("update_offsets_file should not run")

    _patch_audio_alignment(monkeypatch, "measure_offsets", _fail_measure)
    _patch_audio_alignment(monkeypatch, "update_offsets_file", _fail_update)

    class _TTY:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(frame_compare.sys, "stdin", _TTY())

    confirm_calls: dict[str, int] = {"count": 0}

    def _fake_confirm(*_args: object, **_kwargs: object) -> bool:
        confirm_calls["count"] += 1
        return False

    monkeypatch.setattr(frame_compare.click, "confirm", _fake_confirm)

    summary, display = core_module._maybe_apply_audio_alignment(
        [reference_plan, target_plan],
        cfg,
        reference_path,
        tmp_path,
        {},
        reporter=None,
    )

    assert confirm_calls["count"] == 1
    assert summary is not None
    assert display is not None
    assert summary.suggestion_mode is False
    assert summary.applied_frames[target_path.name] == 6
    assert target_plan.trim_start == 6
    assert summary.final_adjustments[target_path.name] == 6
    assert display.estimation_line and "reused" in display.estimation_line.lower()
    assert any("Audio offsets" in line for line in display.offset_lines)
    first_line = display.offset_lines[0]
    assert "[unknown/und/?]" in first_line
    assert "corr=" in first_line
    assert "status=auto/applied" in first_line


def test_audio_alignment_prompt_reuse_affirm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Affirming the prompt (or skipping it) triggers fresh alignment."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.prompt_reuse_offsets = True
    cfg.audio_alignment.confirm_with_screenshots = False
    cfg.audio_alignment.frame_offset_bias = 0

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )

    monkeypatch.setattr(
        core_module.audio_alignment,
        "load_offsets",
        lambda _path: (reference_path.name, {target_path.name: {"frames": 4, "seconds": 0.2}}),
    )

    measure_calls: dict[str, int] = {"count": 0}

    def _fake_measure(
        _ref: Path,
        targets: Sequence[Path],
        *,
        progress_callback,
        **_kwargs: object,
    ) -> list[AlignmentMeasurement]:
        measure_calls["count"] += 1
        progress_callback(len(targets))
        return [
            AlignmentMeasurement(
                file=targets[0],
                offset_seconds=0.3,
                frames=7,
                correlation=0.9,
                reference_fps=24.0,
                target_fps=24.0,
            )
        ]

    _patch_audio_alignment(monkeypatch, "measure_offsets", _fake_measure)
    _patch_audio_alignment(monkeypatch, "probe_audio_streams", lambda _path: [])

    update_calls: dict[str, int] = {"count": 0}

    def _fake_update(
        _path: Path,
        _reference_name: str,
        measurements: Sequence[AlignmentMeasurement],
        _existing: Mapping[str, Mapping[str, object]],
        _notes: Mapping[str, str],
    ) -> tuple[dict[str, int], dict[str, str]]:
        update_calls["count"] += 1
        applied = {m.file.name: int(m.frames or 0) for m in measurements}
        return applied, {name: "auto" for name in applied}

    _patch_audio_alignment(monkeypatch, "update_offsets_file", _fake_update)

    class _TTY:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(frame_compare.sys, "stdin", _TTY())

    def _confirm_true(*_args: object, **_kwargs: object) -> bool:
        return True

    monkeypatch.setattr(frame_compare.click, "confirm", _confirm_true)

    summary, display = core_module._maybe_apply_audio_alignment(
        [reference_plan, target_plan],
        cfg,
        reference_path,
        tmp_path,
        {},
        reporter=None,
    )

    assert measure_calls["count"] == 1
    assert update_calls["count"] == 1
    assert summary is not None
    assert display is not None
    assert summary.applied_frames[target_path.name] == 7
    assert target_plan.trim_start == 7
    assert summary.suggestion_mode is False

def test_run_cli_reuses_vspreview_manual_offsets_when_alignment_disabled(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    """Manual VSPreview offsets should be reused during CLI runs when auto alignment is off."""

    reference_path = cli_runner_env.media_root / "Ref.mkv"
    target_path = cli_runner_env.media_root / "Target.mkv"
    for file_path in (reference_path, target_path):
        file_path.write_bytes(b"data")

    cfg = cli_runner_env.cfg
    cfg.analysis.frame_data_filename = "generated.compframes"
    cfg.audio_alignment.enable = False
    cfg.audio_alignment.use_vspreview = True

    files = [reference_path, target_path]
    metadata = [
        {"label": "Reference", "file_name": reference_path.name},
        {"label": "Target", "file_name": target_path.name},
    ]

    _patch_core_helper(monkeypatch, "_discover_media", lambda _root: list(files))
    _patch_core_helper(
        monkeypatch,
        "_parse_metadata",
        lambda _files, _naming: list(metadata),
    )
    _patch_core_helper(
        monkeypatch,
        "_pick_analyze_file",
        lambda _files, _metadata, _target, **_kwargs: reference_path,
    )

    cache_file = cli_runner_env.media_root / cfg.analysis.frame_data_filename
    cache_file.write_text("cache", encoding="utf-8")

    manual_offsets = {
        reference_path.name: {
            "status": "manual",
            "note": "vspreview reference baseline",
            "frames": 0,
        },
        target_path.name: {
            "status": "manual",
            "note": "vspreview manual trim",
            "frames": 8,
        },
    }

    monkeypatch.setattr(core_module.audio_alignment, "load_offsets", lambda _path: (None, manual_offsets))

    def _fail_measure(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("measure_offsets should not run when manual offsets are reused")

    monkeypatch.setattr(core_module.audio_alignment, "measure_offsets", _fail_measure)
    monkeypatch.setattr(core_module.audio_alignment, "update_offsets_file", _fail_measure)

    init_calls: list[tuple[str, int]] = []

    def fake_init_clip(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
        **_kwargs: object,
    ) -> types.SimpleNamespace:
        init_calls.append((path, trim_start))
        return types.SimpleNamespace(
            path=path,
            width=1920,
            height=1080,
            fps_num=24000,
            fps_den=1001,
            num_frames=2400,
        )

    _patch_vs_core(monkeypatch, "init_clip", fake_init_clip)

    monkeypatch.setattr(runner_module, "write_selection_cache_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner_module, "export_selection_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner_module, "generate_screenshots", lambda *args, **kwargs: [])

    def fake_select(
        clip: types.SimpleNamespace,
        analysis_cfg: AnalysisConfig,
        files_list: list[str],
        file_under_analysis: str,
        cache_info: FrameMetricsCacheInfo | None = None,
        progress: object = None,
        *,
        frame_window: tuple[int, int] | None = None,
        return_metadata: bool = False,
        color_cfg: ColorConfig | None = None,
        cache_probe: CacheLoadResult | None = None,
    ) -> list[int]:
        assert cache_probe is not None and cache_probe.status == "reused"
        return [10, 20]

    monkeypatch.setattr(runner_module, "select_frames", fake_select)

    cache_probes: list[FrameMetricsCacheInfo] = []

    def fake_probe(info: FrameMetricsCacheInfo, _analysis_cfg: AnalysisConfig) -> CacheLoadResult:
        cache_probes.append(info)
        return CacheLoadResult(metrics=None, status="reused", reason=None)

    monkeypatch.setattr(runner_module, "probe_cached_metrics", fake_probe)
    _patch_core_helper(monkeypatch, "Progress", DummyProgress)

    result = frame_compare.run_cli(
        None,
        None,
    )

    assert init_calls, "Clips should be initialised with trims applied"
    trims_by_path = {Path(path).name: trim for path, trim in init_calls}
    assert trims_by_path[target_path.name] == 8
    assert cache_probes and cache_probes[0].path == cache_file.resolve()
    assert result.json_tail is not None
    audio_json = _expect_mapping(result.json_tail["audio_alignment"])
    manual_map = cast(dict[str, int], audio_json.get("manual_trim_starts", {}))
    assert manual_map[target_path.name] == 8
    cache_json = _expect_mapping(result.json_tail["cache"])
    assert cache_json["status"] == "reused"
    analysis_json = _expect_mapping(result.json_tail["analysis"])
    assert analysis_json["cache_reused"] is True
    assert result.json_tail["vspreview_mode"] == "baseline"
    assert result.json_tail["suggested_frames"] == 0
    assert result.json_tail["suggested_seconds"] == 0.0


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

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
        clip=None,
    )
    target_plan = _ClipPlan(
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
        core_module.audio_alignment,
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
        core_module.audio_alignment,
        "measure_offsets",
        _fake_measure,
    )
    monkeypatch.setattr(
        core_module.audio_alignment,
        "load_offsets",
        lambda _path: (None, {}),
    )

    def _fail_update(*_args, **_kwargs):
        raise AssertionError("update_offsets_file should not be called in VSPreview mode")

    monkeypatch.setattr(
        core_module.audio_alignment,
        "update_offsets_file",
        _fail_update,
    )

    summary, display = core_module._maybe_apply_audio_alignment(
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
    assert summary.applied_frames == {target_path.name: 120}
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

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )
    target_plan.trim_start = 10
    target_plan.has_trim_start_override = True
    plans = [reference_plan, target_plan]

    summary = _AudioAlignmentSummary(
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
    monkeypatch.setattr(core_module.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        frame_compare.subprocess,
        "run",
        lambda cmd, env=None, check=False, **kwargs: recorded_command.append(list(cmd)) or _Result(0),
    )

    display = _AudioAlignmentDisplayData(
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
    _patch_core_helper(
        monkeypatch,
        "_prompt_vspreview_offsets",
        lambda *args, **kwargs: prompt_calls.append({}) or {},
    )

    apply_calls: list[Mapping[str, int]] = []

    def _record_apply(
        _plans: Sequence[_ClipPlan],
        _summary: _AudioAlignmentSummary,
        offsets: Mapping[str, int],
        *_args: object,
        **_kwargs: object,
    ) -> None:
        apply_calls.append(dict(offsets))

    _patch_core_helper(monkeypatch, "_apply_vspreview_manual_offsets", _record_apply)

    core_module._launch_vspreview(plans, summary, display, cfg, tmp_path, reporter, json_tail)

    script_path_str = audio_block.get("vspreview_script")
    assert script_path_str, "Script path should be recorded in JSON tail"
    script_path = Path(script_path_str)
    assert script_path.exists()
    script_text = script_path.read_text(encoding="utf-8")
    assert "OFFSET_MAP" in script_text
    assert "vs_core.configure" in script_text
    assert "ColorConfig" in script_text
    assert "AssumeFPS" in script_text
    assert "PREVIEW_MODE = 'baseline'" in script_text
    assert "SHOW_SUGGESTED_OVERLAY = True" in script_text
    assert "'Target': 0,  # Suggested delta +7f" in script_text
    assert "SUGGESTION_MAP" in script_text
    assert "'Target': (7, 0.0)" in script_text
    assert 'seconds_value = f"{suggested_seconds:.3f}"' in script_text
    assert (
        "def _format_overlay_text(label, suggested_frames, suggested_seconds, applied_frames):"
        in script_text
    )
    assert '"{label}: {suggested}f (~{seconds}s) • "' in script_text
    assert "Preview applied: {applied}f ({status})" in script_text
    assert "preview applied=%+df" in script_text
    assert recorded_command, "VSPreview command should be invoked when interactive"
    assert recorded_command[0][0] == frame_compare.sys.executable
    assert recorded_command[0][-1] == str(script_path)
    assert audio_block.get("vspreview_invoked") is True
    assert audio_block.get("vspreview_exit_code") == 0
    assert prompt_calls, "Prompt should be invoked even when returning default offsets"
    assert apply_calls == [{}]


def test_launch_vspreview_baseline_mode_persists_manual_offsets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Baseline preview emits zeroed offsets yet records manual selections."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.use_vspreview = True
    cfg.audio_alignment.vspreview_mode = "baseline"

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )
    target_plan.trim_start = 2
    target_plan.has_trim_start_override = True
    plans = [reference_plan, target_plan]

    measurement = AlignmentMeasurement(
        file=target_path,
        offset_seconds=0.375,
        frames=9,
        correlation=0.91,
        reference_fps=24.0,
        target_fps=24.0,
    )

    summary = _AudioAlignmentSummary(
        offsets_path=tmp_path / "offsets.toml",
        reference_name=reference_path.name,
        measurements=(measurement,),
        applied_frames={},
        baseline_shift=0,
        statuses={},
        reference_plan=reference_plan,
        final_adjustments={},
        swap_details={},
        suggested_frames={target_path.name: 9},
        suggestion_mode=True,
        manual_trim_starts={target_path.name: 2},
    )

    reporter = _RecordingOutputManager()
    json_tail = _make_json_tail_stub()
    audio_block = json_tail["audio_alignment"]

    monkeypatch.setattr(frame_compare.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(frame_compare.shutil, "which", lambda _: None)
    monkeypatch.setattr(core_module.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        frame_compare.subprocess,
        "run",
        lambda cmd, env=None, check=False, **kwargs: types.SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    _patch_core_helper(
        monkeypatch,
        "_prompt_vspreview_offsets",
        lambda *args, **kwargs: {target_path.name: 3},
    )
    _patch_audio_alignment(
        monkeypatch,
        "update_offsets_file",
        lambda *_args, **_kwargs: (
            {reference_path.name: 0, target_path.name: 5},
            {reference_path.name: "manual", target_path.name: "manual"},
        ),
    )

    core_module._launch_vspreview(plans, summary, None, cfg, tmp_path, reporter, json_tail)

    script_path_str = audio_block.get("vspreview_script")
    assert script_path_str, "Script path should be recorded in JSON tail"
    script_text = Path(script_path_str).read_text(encoding="utf-8")
    assert "'Target': 0,  # Suggested delta +9f" in script_text
    assert summary.vspreview_manual_offsets[target_path.name] == 5
    assert summary.vspreview_manual_deltas[target_path.name] == 3
    manual_json = cast(dict[str, int], audio_block.get("vspreview_manual_offsets", {}))
    assert manual_json[target_path.name] == 5
    delta_json = cast(dict[str, int], audio_block.get("vspreview_manual_deltas", {}))
    assert delta_json[target_path.name] == 3

def test_write_vspreview_script_generates_unique_filenames_same_second(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VSPreview script writes should never clobber same-second launches."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.use_vspreview = True

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )
    plans = [reference_plan, target_plan]

    summary = _AudioAlignmentSummary(
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

    fixed_instant = dt.datetime(2024, 1, 1, 12, 34, 56)

    class _FixedDatetime(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> dt.datetime:
            return fixed_instant if tz is None else fixed_instant.replace(tzinfo=tz)

    monkeypatch.setattr(core_module._dt, "datetime", _FixedDatetime)

    first_path = core_module._write_vspreview_script(plans, summary, cfg, tmp_path)
    second_path = core_module._write_vspreview_script(plans, summary, cfg, tmp_path)

    assert first_path != second_path
    assert first_path.exists()
    assert second_path.exists()
    assert first_path.name != second_path.name


def test_launch_vspreview_warns_when_command_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VSPreview launcher should fall back cleanly when no executable is available."""

    cfg = _make_config(tmp_path)
    cfg.audio_alignment.use_vspreview = True

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.write_bytes(b"ref")
    target_path.write_bytes(b"tgt")

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference"},
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target"},
    )
    plans = [reference_plan, target_plan]

    summary = _AudioAlignmentSummary(
        offsets_path=tmp_path / "offsets.toml",
        reference_name=reference_path.name,
        measurements=(),
        applied_frames={},
        baseline_shift=0,
        statuses={},
        reference_plan=reference_plan,
        final_adjustments={},
        swap_details={},
        suggested_frames={target_path.name: 4},
        suggestion_mode=True,
        manual_trim_starts={target_path.name: 2},
    )

    reporter = _RecordingOutputManager()
    json_tail = _make_json_tail_stub()
    audio_block = json_tail["audio_alignment"]

    display = _AudioAlignmentDisplayData(
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

    monkeypatch.setattr(frame_compare.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(frame_compare.shutil, "which", lambda _: None)
    monkeypatch.setattr(core_module.importlib.util, "find_spec", lambda _name: None)

    prompt_called: list[None] = []

    def _fail_prompt(*_args: object, **_kwargs: object) -> dict[str, int]:
        prompt_called.append(None)
        return {}

    _patch_core_helper(monkeypatch, "_prompt_vspreview_offsets", _fail_prompt)

    core_module._launch_vspreview(plans, summary, display, cfg, tmp_path, reporter, json_tail)

    script_path_str = audio_block.get("vspreview_script")
    assert script_path_str, "Script path should still be recorded for manual launches"
    assert Path(script_path_str).exists()
    assert audio_block.get("vspreview_invoked") is False
    assert audio_block.get("vspreview_exit_code") is None
    assert not prompt_called, "Prompt should not run when VSPreview cannot launch"
    warnings = reporter.get_warnings()
    assert any("VSPreview dependencies missing" in warning for warning in warnings)
    layout_state = reporter.values.get("vspreview", {})
    missing_state = cast(dict[str, object], layout_state.get("missing", {}))
    assert missing_state.get("active") is True
    expected_command = frame_compare._format_vspreview_manual_command(
        Path(script_path_str)
    )
    assert missing_state.get("command") == expected_command
    offer_entry = json_tail.get("vspreview_offer")
    assert offer_entry == {"vspreview_offered": False, "reason": "vspreview-missing"}
    console_output = reporter.console.export_text()
    normalized_output = " ".join(console_output.split())
    assert "VSPreview dependency missing" in normalized_output
    expected_windows_install = " ".join(
        frame_compare._VSPREVIEW_WINDOWS_INSTALL.split()
    )
    assert expected_windows_install in normalized_output
    python_executable = frame_compare.sys.executable or "python"
    assert python_executable in normalized_output
    assert "-m vspreview" in normalized_output


def _make_json_tail_stub() -> JsonTail:
    audio_block: AudioAlignmentJSON = {
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
        "use_vspreview": False,
        "vspreview_manual_offsets": {},
        "vspreview_manual_deltas": {},
        "vspreview_reference_trim": None,
        "vspreview_script": None,
        "vspreview_invoked": False,
        "vspreview_exit_code": None,
    }
    tail: JsonTail = {
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
        "report": {
            "enabled": False,
            "path": None,
            "output_dir": "report",
            "open_after_generate": True,
            "opened": False,
            "mode": "slider",
        },
        "viewer": {
            "mode": "none",
            "mode_display": "None",
            "destination": None,
            "destination_label": "",
        },
        "vspreview_mode": None,
        "suggested_frames": 0,
        "suggested_seconds": 0.0,
        "vspreview_offer": None,
    }
    return tail


def _make_display_stub() -> _AudioAlignmentDisplayData:
    return _AudioAlignmentDisplayData(
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
    reference_plan = _ClipPlan(path=reference_path, metadata={"label": "Reference"})
    target_plan = _ClipPlan(path=target_path, metadata={"label": "Target"})
    target_plan.trim_start = 5
    target_plan.has_trim_start_override = True
    summary = _AudioAlignmentSummary(
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

    _patch_audio_alignment(monkeypatch, "update_offsets_file", fake_update)

    core_module._apply_vspreview_manual_offsets(
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
    reference_plan = _ClipPlan(path=reference_path, metadata={"label": "Reference"})
    target_plan = _ClipPlan(path=target_path, metadata={"label": "Target"})
    target_plan.trim_start = 4
    summary = _AudioAlignmentSummary(
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
        core_module.audio_alignment,
        "update_offsets_file",
        lambda *_args, **_kwargs: ({target_path.name: 4, reference_path.name: 0}, {target_path.name: "manual", reference_path.name: "manual"}),
    )

    core_module._apply_vspreview_manual_offsets(
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
    reference_plan = _ClipPlan(path=reference_path, metadata={"label": "Reference"})
    target_plan = _ClipPlan(path=target_path, metadata={"label": "Target"})
    target_plan.trim_start = 3
    summary = _AudioAlignmentSummary(
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
        core_module.audio_alignment,
        "update_offsets_file",
        lambda *_args, **_kwargs: (
            {target_path.name: 0, reference_path.name: 4},
            {target_path.name: "manual", reference_path.name: "manual"},
        ),
    )

    core_module._apply_vspreview_manual_offsets(
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
    reference_plan = _ClipPlan(path=reference_path, metadata={"label": "Reference"})
    target_a_plan = _ClipPlan(path=target_a_path, metadata={"label": "A"})
    target_b_plan = _ClipPlan(path=target_b_path, metadata={"label": "B"})
    target_a_plan.trim_start = 5
    target_b_plan.trim_start = 5
    summary = _AudioAlignmentSummary(
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

    _patch_audio_alignment(monkeypatch, "update_offsets_file", fake_update)

    core_module._apply_vspreview_manual_offsets(
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

    return core_module.PROJECT_ROOT / "comparison_videos"


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
        ["--input", str(override_dir), "--no-color"],
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
        core_module,
        "resolve_tmdb_workflow",
        lambda **_: core_module.TMDBLookupResult(
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
    monkeypatch.setattr(runner_module.core, "_parse_metadata", lambda *_: list(metadata))
    monkeypatch.setattr(runner_module.core, "_build_plans", lambda *_: list(plans))
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
    monkeypatch.setattr(runner_module.core, "_maybe_apply_audio_alignment", lambda *args, **kwargs: (None, None))

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
    )
    result = runner_module.run(request)

    assert uploads, "Slow.pics upload should be invoked"
    assert result.slowpics_url == "https://slow.pics/test"
    assert result.json_tail is not None
    slowpics_json = _expect_mapping(result.json_tail["slowpics"])
    assert slowpics_json["url"] == "https://slow.pics/test"


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


def test_runner_audio_alignment_summary_passthrough(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    media_root = workspace / "media"
    workspace.mkdir(parents=True, exist_ok=True)
    media_root.mkdir(parents=True, exist_ok=True)
    for name in ("Reference.mkv", "Target.mkv"):
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

    files = [media_root / "Reference.mkv", media_root / "Target.mkv"]
    metadata = [{"label": "Reference"}, {"label": "Target"}]
    plans = [
        core_module._ClipPlan(path=files[0], metadata={"label": "Reference"}),
        core_module._ClipPlan(path=files[1], metadata={"label": "Target"}),
    ]
    plans[0].use_as_reference = True

    _patch_core_helper(monkeypatch, "_discover_media", lambda _root: list(files))
    monkeypatch.setattr(runner_module.core, "_parse_metadata", lambda *_: list(metadata))
    monkeypatch.setattr(runner_module.core, "_build_plans", lambda *_: list(plans))
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

    summary = _AudioAlignmentSummary(
        offsets_path=workspace / "generated.audio_offsets.toml",
        reference_name="Reference",
        measurements=[],
        applied_frames={files[1].name: 8},
        baseline_shift=0,
        statuses={files[1].name: "manual"},
        reference_plan=plans[0],
        final_adjustments={files[1].name: 8},
        swap_details={},
        suggested_frames={},
        suggestion_mode=False,
        manual_trim_starts={files[1].name: 8},
        vspreview_manual_offsets={files[1].name: 8},
        vspreview_manual_deltas={files[1].name: 8},
        measured_offsets={},
    )
    display = _AudioAlignmentDisplayData(
        stream_lines=["Reference stream"],
        estimation_line="Audio offsets reused from VSPreview",
        offset_lines=["VSPreview manual trim reused"],
        offsets_file_line="Offsets file: generated.audio_offsets.toml",
        json_reference_stream="Reference",
        json_target_streams={files[1].name: "0"},
        json_offsets_sec={files[1].name: 0.333},
        json_offsets_frames={files[1].name: 8},
        warnings=[],
        preview_paths=[],
        confirmation=None,
        correlations={files[1].name: 0.98},
        threshold=0.55,
        manual_trim_lines=["Target -> 8f"],
        measurements={},
    )

    monkeypatch.setattr(
        runner_module.core,
        "_maybe_apply_audio_alignment",
        lambda *args, **kwargs: (summary, display),
    )

    monkeypatch.setattr(runner_module.vs_core, "configure", lambda **_: None)
    monkeypatch.setattr(runner_module.vs_core, "set_ram_limit", lambda *_: None)
    monkeypatch.setattr(runner_module.vs_core, "init_clip", lambda *args, **kwargs: types.SimpleNamespace(num_frames=120, fps_num=24000, fps_den=1001, width=1280, height=720))
    monkeypatch.setattr(
        runner_module,
        "probe_cached_metrics",
        lambda *_: CacheLoadResult(metrics=None, status="missing", reason=None),
    )
    monkeypatch.setattr(runner_module, "selection_hash_for_config", lambda *_: "selection-hash")
    monkeypatch.setattr(runner_module, "write_selection_cache_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner_module, "export_selection_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner_module,
        "select_frames",
        lambda *args, **kwargs: ([5], {5: "Auto"}, {5: SelectionDetail(frame_index=5, label="Auto", score=None, source="Test", timecode="00:00:05.0")}),
    )
    monkeypatch.setattr(runner_module, "selection_details_to_json", _selection_details_to_json)
    monkeypatch.setattr(runner_module, "generate_screenshots", lambda *args, **kwargs: [str(media_root / "shot.png")])

    monkeypatch.setattr(runner_module, "impl", frame_compare, raising=False)
    request = runner_module.RunRequest(
        config_path=str(preflight.config_path),
        root_override=str(workspace),
    )
    result = runner_module.run(request)

    assert result.json_tail is not None
    audio_json = _expect_mapping(result.json_tail["audio_alignment"])
    manual_trims = cast(dict[str, int], audio_json.get("manual_trim_starts"))
    assert manual_trims[files[1].name] == 8
    assert any("VSPreview" in line for line in audio_json.get("offset_lines", []))
    assert audio_json.get("vspreview_invoked") is False
    assert audio_json.get("offsets_sec").get(files[1].name) == pytest.approx(0.333)  # type: ignore[arg-type]


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
    monkeypatch.setattr(runner_module.core, "_parse_metadata", lambda *_: list(metadata))
    monkeypatch.setattr(runner_module.core, "_build_plans", lambda *_: list(plans))
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
    monkeypatch.setattr(runner_module.core, "_maybe_apply_audio_alignment", lambda *args, **kwargs: (None, None))

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

    def fake_tmdb_workflow(**kwargs: object) -> core_module.TMDBLookupResult:
        tmdb_calls.append(kwargs)
        return core_module.TMDBLookupResult(
            resolution=None,
            manual_override=None,
            error_message=None,
            ambiguous=False,
        )

    monkeypatch.setattr(core_module, "resolve_tmdb_workflow", fake_tmdb_workflow)

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

    _patch_runner_module(monkeypatch, "Progress", DummyProgress)

    result = frame_compare.run_cli(None, None)

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
    _patch_runner_module(monkeypatch, "Progress", DummyProgress)

    result = frame_compare.run_cli(None, None)

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
    _patch_runner_module(monkeypatch, "Progress", DummyProgress)

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
    _patch_core_helper(monkeypatch, "_prompt_manual_tmdb", lambda candidates: ("TV", "9999"))
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(
        monkeypatch,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400),
    )
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [3, 6])
    _patch_runner_module(monkeypatch, "generate_screenshots", lambda *args, **kwargs: [str(cli_runner_env.media_root / "img.png")])
    _patch_runner_module(monkeypatch, "Progress", DummyProgress)

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
    _patch_core_helper(monkeypatch, "_prompt_tmdb_confirmation", lambda res: (True, ("MOVIE", "999")))
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(
        monkeypatch,
        "init_clip",
        lambda *_, **__: types.SimpleNamespace(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400),
    )
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [1, 2])
    _patch_runner_module(monkeypatch, "generate_screenshots", lambda *args, **kwargs: [str(cli_runner_env.media_root / "img.png")])
    _patch_runner_module(monkeypatch, "Progress", DummyProgress)

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
    _patch_core_helper(monkeypatch, "_prompt_tmdb_confirmation", lambda res: (False, None))
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)
    _patch_vs_core(monkeypatch, "init_clip", lambda *_, **__: types.SimpleNamespace(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800))
    _patch_runner_module(monkeypatch, "select_frames", lambda *_, **__: [1, 2])
    _patch_runner_module(monkeypatch, "generate_screenshots", lambda *args, **kwargs: [str(cli_runner_env.media_root / "img.png")])
    _patch_runner_module(monkeypatch, "Progress", DummyProgress)

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
        core_module,
        "_resolve_tmdb_blocking",
        lambda **_: (_ for _ in ()).throw(TMDBAmbiguityError([candidate])),
    )
    prompted = False

    def _fail_prompt(_: Sequence[TMDBCandidate]) -> tuple[str, str] | None:  # pragma: no cover - should not run
        nonlocal prompted
        prompted = True
        return None

    monkeypatch.setattr(core_module, "_prompt_manual_tmdb", _fail_prompt)

    result = core_module.resolve_tmdb_workflow(
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
        core_module,
        "_resolve_tmdb_blocking",
        lambda **_: (_ for _ in ()).throw(TMDBAmbiguityError([candidate])),
    )
    manual_return = ("TV", "999")
    monkeypatch.setattr(core_module, "_prompt_manual_tmdb", lambda _: manual_return)

    result = core_module.resolve_tmdb_workflow(
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

    monkeypatch.setattr(core_module, "resolve_tmdb", fake_resolve)
    monkeypatch.setattr(core_module.time, "sleep", lambda _seconds: None)

    cfg = TMDBConfig(api_key="token")
    result = core_module._resolve_tmdb_blocking(
        file_name="Example.mkv",
        tmdb_cfg=cfg,
        year_hint=None,
        imdb_id=None,
        tvdb_id=None,
    )

    assert isinstance(result, TMDBResolution)
    assert attempts["count"] == 2



def test_audio_alignment_block_and_json(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    reference_path = cli_runner_env.media_root / "ClipA.mkv"
    target_path = cli_runner_env.media_root / "ClipB.mkv"
    for file in (reference_path, target_path):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.confirm_with_screenshots = False
    cfg.audio_alignment.max_offset_seconds = 5.0
    cfg.audio_alignment.offsets_filename = "alignment.toml"
    cfg.audio_alignment.frame_offset_bias = 0
    cfg.audio_alignment.start_seconds = 0.25
    cfg.audio_alignment.duration_seconds = 1.5
    cfg.color.overlay_mode = "diagnostic"

    cli_runner_env.reinstall(cfg)

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

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)

    def fake_init_clip(
        path: str | Path,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | Path | None = None,
        **_kwargs: object,
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

    _patch_vs_core(monkeypatch, "init_clip", fake_init_clip)

    _patch_runner_module(monkeypatch, "select_frames", lambda *args, **kwargs: [42])

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

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

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

    _patch_audio_alignment(monkeypatch, "probe_audio_streams", fake_probe)

    measurement = AlignmentMeasurement(
        file=target_path,
        offset_seconds=0.1,
        frames=3,
        correlation=0.93,
        reference_fps=24.0,
        target_fps=24.0,
    )

    _patch_audio_alignment(monkeypatch, "measure_offsets", lambda *args, **kwargs: [measurement])
    _patch_audio_alignment(monkeypatch, "load_offsets", lambda *_args, **_kwargs: ({}, {}))

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

    _patch_audio_alignment(monkeypatch, "update_offsets_file", fake_update)

    result: Result = runner.invoke(frame_compare.main, ["--no-color"], catch_exceptions=False)
    assert result.exit_code == 0

    output_lines: list[str] = result.output.splitlines()
    assert any("alignment.toml" in line for line in output_lines)
    assert "mode=diagnostic" in result.output

    json_start = result.output.rfind('{"clips":')
    json_payload = result.output[json_start:].replace('\n', '')
    payload: dict[str, Any] = json.loads(json_payload)
    audio_json = _expect_mapping(payload["audio_alignment"])
    ref_label = audio_json["reference_stream"].split("->", 1)[0]
    assert ref_label in {"Clip A", "Reference"}
    tgt_map = _expect_mapping(audio_json["target_stream"])
    assert "Clip B" in tgt_map or "Target" in tgt_map
    tgt_descriptor = tgt_map.get("Clip B") or tgt_map.get("Target")
    assert isinstance(tgt_descriptor, str) and tgt_descriptor.startswith("aac/")
    offsets_sec_map = _expect_mapping(audio_json["offsets_sec"])
    offsets_frames_map = _expect_mapping(audio_json["offsets_frames"])
    clip_key = "Clip B" if "Clip B" in offsets_sec_map else "Target"
    assert offsets_sec_map[clip_key] == pytest.approx(0.1)
    assert offsets_frames_map[clip_key] == 3
    assert audio_json["preview_paths"] == []
    assert audio_json["confirmed"] == "auto"
    offset_lines = audio_json.get("offset_lines")
    assert isinstance(offset_lines, list) and offset_lines, "Expected offset_lines for cached alignment reuse"
    assert any("Clip B" in line for line in offset_lines)
    offset_lines_text = audio_json.get("offset_lines_text")
    assert isinstance(offset_lines_text, str) and "Clip B" in offset_lines_text
    stream_lines = audio_json.get("stream_lines")
    assert isinstance(stream_lines, list) and stream_lines, "Expected stream_lines entries"
    assert any("ref=" in line for line in stream_lines)
    assert any("target=" in line for line in stream_lines)
    measurements_obj = audio_json.get("measurements") or {}
    measurements_map = _expect_mapping(measurements_obj)
    measurement_value = measurements_map.get(clip_key)
    assert measurement_value is not None
    measurement_entry = _expect_mapping(measurement_value)
    stream_value = measurement_entry.get("stream")
    assert isinstance(stream_value, str)
    assert stream_value.startswith("aac/")
    seconds_value = measurement_entry.get("seconds")
    assert isinstance(seconds_value, (int, float))
    assert pytest.approx(seconds_value) == 0.1
    frames_value = measurement_entry.get("frames")
    assert isinstance(frames_value, (int, float))
    assert frames_value == 3
    correlation_value = measurement_entry.get("correlation")
    assert isinstance(correlation_value, (int, float))
    assert pytest.approx(correlation_value) == 0.93
    status_value = measurement_entry.get("status")
    assert status_value == "auto"
    applied_value = measurement_entry.get("applied")
    assert applied_value is True
    tonemap_json = payload["tonemap"]
    assert tonemap_json["overlay_mode"] == "diagnostic"
    assert tonemap_json["smoothing_period"] == pytest.approx(45.0)
    assert tonemap_json["scene_threshold_low"] == pytest.approx(0.8)
    assert tonemap_json["scene_threshold_high"] == pytest.approx(2.4)
    assert tonemap_json["percentile"] == pytest.approx(99.995)
    assert tonemap_json["contrast_recovery"] == pytest.approx(0.3)
    assert "metadata_label" in tonemap_json
    assert "use_dovi_label" in tonemap_json


def test_audio_alignment_default_duration_avoids_zero_window(
    monkeypatch: pytest.MonkeyPatch,
    runner: CliRunner,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    """
    Verifies that leaving audio alignment duration unspecified does not pass a zero-length window to the measurement routine.

    Configures audio alignment with start_seconds and duration_seconds set to None, runs the CLI, and asserts that the call to the alignment measurement does not include a `duration_seconds` value of zero (i.e., it remains `None`).
    """
    reference_path = cli_runner_env.media_root / "ClipA.mkv"
    target_path = cli_runner_env.media_root / "ClipB.mkv"
    for file in (reference_path, target_path):
        file.write_bytes(b"data")

    cfg = _make_config(cli_runner_env.media_root)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.confirm_with_screenshots = False
    cfg.audio_alignment.max_offset_seconds = 5.0
    cfg.audio_alignment.start_seconds = None
    cfg.audio_alignment.duration_seconds = None

    cli_runner_env.reinstall(cfg)

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

    _patch_core_helper(monkeypatch, "parse_filename_metadata", fake_parse)
    _patch_vs_core(monkeypatch, "set_ram_limit", lambda limit: None)

    def fake_init_clip(
        path: str | Path,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | Path | None = None,
        **_kwargs: object,
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

    _patch_vs_core(monkeypatch, "init_clip", fake_init_clip)

    _patch_runner_module(monkeypatch, "select_frames", lambda *args, **kwargs: [42])

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

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

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

    _patch_audio_alignment(monkeypatch, "probe_audio_streams", fake_probe)

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

    _patch_audio_alignment(monkeypatch, "measure_offsets", fake_measure)
    _patch_audio_alignment(monkeypatch, "load_offsets", lambda *_args, **_kwargs: ({}, {}))
    _patch_audio_alignment(
        monkeypatch,
        "update_offsets_file",
        lambda *_args, **_kwargs: ({target_path.name: 3}, {target_path.name: "auto"}),
    )

    result: Result = runner.invoke(frame_compare.main, ["--no-color"], catch_exceptions=False)
    assert result.exit_code == 0
    assert captured_kwargs.get("duration_seconds") is None


def _build_alignment_context(
    tmp_path: Path,
) -> tuple[
    AppConfig,
    list[_ClipPlan],
    _AudioAlignmentSummary,
    _AudioAlignmentDisplayData,
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

    reference_clip = types.SimpleNamespace(
        width=1920,
        height=1080,
        fps_num=24000,
        fps_den=1001,
        num_frames=10,
    )
    target_clip = types.SimpleNamespace(
        width=1920,
        height=1080,
        fps_num=24000,
        fps_den=1001,
        num_frames=10,
    )

    reference_path = tmp_path / "Ref.mkv"
    target_path = tmp_path / "Target.mkv"
    reference_path.touch()
    target_path.touch()

    reference_plan = _ClipPlan(
        path=reference_path,
        metadata={"label": "Reference Clip"},
        clip=reference_clip,
    )
    target_plan = _ClipPlan(
        path=target_path,
        metadata={"label": "Target Clip"},
        clip=target_clip,
    )

    summary = _AudioAlignmentSummary(
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

    display = _AudioAlignmentDisplayData(
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


class _RecordingOutputManager(CliOutputManager):
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

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)
    monkeypatch.setattr(frame_compare.sys, "stdin", types.SimpleNamespace(isatty=lambda: False))

    core_module._confirm_alignment_with_screenshots(
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
            ScreenshotError: Always raised with the message "boom".
        """
        raise ScreenshotError("boom")

    _patch_runner_module(monkeypatch, "generate_screenshots", fake_generate)

    with pytest.raises(core_module.CLIAppError, match="Alignment preview failed"):
        core_module._confirm_alignment_with_screenshots(
            plans,
            summary,
            cfg,
            tmp_path,
            _RecordingOutputManager(),
            display,
        )


def test_run_cli_calls_alignment_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    cli_runner_env: _CliRunnerEnv,
) -> None:
    """
    Verifies that running the CLI triggers the audio-alignment confirmation flow when screenshot confirmation is enabled.

    Sets up a configuration enabling audio alignment with screenshot confirmation, creates two dummy media files, and monkeypatches discovery, metadata parsing, plan building, selection, and alignment application. Replaces the confirmation function with one that records its arguments and raises a sentinel exception so the test can assert the confirmation was invoked with the expected parameters.
    """
    cfg = _make_config(cli_runner_env.media_root)
    cfg.audio_alignment.enable = True
    cfg.audio_alignment.confirm_with_screenshots = True

    cli_runner_env.reinstall(cfg)

    files: list[Path] = [
        cli_runner_env.media_root / "Ref.mkv",
        cli_runner_env.media_root / "Tgt.mkv",
    ]
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
    ) -> list[_ClipPlan]:
        """
        Builds a list of clip plans from input file paths and corresponding metadata, marking the first clip as the reference.

        Parameters:
            _files (Sequence[Path]): Input file paths in the order they should be planned.
            metadata (Sequence): Per-file metadata objects; must have the same length as `_files`.
            _cfg: Configuration object (not used by this fake builder, accepted for signature compatibility).

        Returns:
            list[_ClipPlan]: A list of ClipPlan objects where the first element has `use_as_reference=True` and all others have `use_as_reference=False`.
        """
        plans: list[_ClipPlan] = []
        for idx, path in enumerate(_files):
            plans.append(
                _ClipPlan(
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

    offsets_path = cli_runner_env.workspace_root / "alignment.toml"

    def fake_maybe_apply(
        plans: Sequence[_ClipPlan],
        _cfg: AppConfig,
        _analyze_path: Path,
        _root: Path,
        _overrides: object,
        reporter: object | None = None,
    ) -> tuple[_AudioAlignmentSummary, _AudioAlignmentDisplayData]:
        """
        Create and return a synthetic audio-alignment summary and display objects for testing.

        Parameters:
            plans (Sequence): Sequence of clip plan objects; the first plan is used as the reference.
            reporter (optional): Ignored; present for API compatibility.

        Returns:
            tuple: A pair (summary, display) where:
                - summary: a _AudioAlignmentSummary with the first plan as the reference_plan,
                  empty measurements/applied_frames/statuses, and baseline_shift 0.
                - display: a _AudioAlignmentDisplayData containing empty display lines,
                  an offsets file line referencing the module's offsets path, and JSON-ready fields
                  for a single target with zero offset (0.0 seconds, 0 frames).
        """
        summary = _AudioAlignmentSummary(
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
        display = _AudioAlignmentDisplayData(
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
        plans: Sequence[_ClipPlan],
        summary: _AudioAlignmentSummary,
        cfg_obj: AppConfig,
        root: Path,
        reporter: object,
        display: _AudioAlignmentDisplayData,
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

    _patch_core_helper(monkeypatch, "_discover_media", fake_discover)
    _patch_core_helper(monkeypatch, "_parse_metadata", fake_parse_metadata)
    _patch_core_helper(monkeypatch, "_build_plans", fake_build_plans)
    _patch_core_helper(monkeypatch, "_pick_analyze_file", fake_pick_analyze)
    _patch_core_helper(monkeypatch, "_maybe_apply_audio_alignment", fake_maybe_apply)
    _patch_runner_module(monkeypatch, "CliOutputManager", _DummyReporter)
    _patch_core_helper(monkeypatch, "_confirm_alignment_with_screenshots", fake_confirm)
    _patch_vs_core(monkeypatch, "configure", lambda *args, **kwargs: None)

    with pytest.raises(_SentinelError):
        frame_compare.run_cli(None, None)

    assert "args" in called
