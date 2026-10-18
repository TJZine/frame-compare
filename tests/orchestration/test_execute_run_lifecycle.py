from __future__ import annotations

import asyncio
import json
from fractions import Fraction
from pathlib import Path
from typing import Never, cast

import httpx
import pytest
from rich.console import Console

from frame_compare.analysis.window import SelectionWindow
from frame_compare.cli import run_command
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.config.overrides import CLIConfigOverrides
from frame_compare.config.schema import ConfigSchema, OverlayMode, TonemapPreset
from frame_compare.orchestration import coordinator
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.errors import MixedSourceFpsError
from frame_compare.orchestration.execution_types import (
    MetadataPrefetch,
    PrepState,
    PublishPhaseOutput,
    RenderPhaseOutput,
    RunArtifacts,
)
from frame_compare.orchestration.selection_domain import PreparedSelectionDomain
from frame_compare.orchestration.types import ReservedRunCapture, RunResult
from frame_compare.services.publishers import PublishResult
from frame_compare.services.run_result_record import read_run_result
from frame_compare.services.slowpics_upload_plan import SlowpicsUploadPlan
from frame_compare.services.types import SlowpicsCollectionMetadata, TmdbMetadata
from frame_compare.utils.post_upload_actions import PostUploadActionResult
from frame_compare.utils.progress import NullProgressReporter
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.vs.errors import TonemapRequiresVapourSynthError
from frame_compare.vs.types import SourceInfo
from tests.render_test_support import prepared_jobs
from tests.run_request_support import make_run_request

from .execute_run_helpers import (
    FakeFFmpegRunner,
    FakeHDRVSLoader,
    FakeVSLoader,
    clip_state,
    create_video_files,
)
from .phase_task_helpers import _render_artifacts, _workspace
from .preparation_test_support import create_config


def _zero_monotonic_timer() -> float:
    return 0.0


def test_execute_run_returns_success_and_records_preflight_timing(
    tmp_path: Path,
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = make_run_request(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        overrides=CLIConfigOverrides(no_upload=True),
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.warnings == []
    assert result.screenshot_dir == (tmp_path / "generated" / "source" / "screenshots").resolve()
    assert result.frame_count == 10
    assert result.clips_processed == 1
    assert result.duration_seconds >= 0.0
    assert result.cache_hit is False
    assert result.slowpics_url is None
    assert result.report_path is None
    expected_keys = {
        "preflight",
        "load_sources",
        "frame_plan",
        "analyze",
        "align",
        "render",
        "metadata",
        "publish",
        "report",
        "post_report_cleanup",
    }
    assert set(result.phase_timings.keys()) == expected_keys
    assert result.phase_timings["preflight"] >= 0.0
    assert result.phase_timings["load_sources"] >= 0.0
    assert result.phase_timings["analyze"] >= 0.0
    assert result.phase_timings["align"] >= 0.0
    assert result.phase_timings["metadata"] >= 0.0
    assert result.phase_timings["publish"] >= 0.0
    assert result.phase_timings["report"] >= 0.0
    assert result.phase_timings["post_report_cleanup"] >= 0.0


def test_execute_run_returns_preflight_and_runtime_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shortcut = PostUploadActionResult(
        kind="shortcut",
        success=True,
        path=tmp_path / "Slowpics.url",
        message="Shortcut written.",
    )
    prep = PrepState(
        workspace=_workspace(tmp_path, run_subdir=None),
        config=ConfigSchema(),
        input_videos=[tmp_path / "reference.mkv"],
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(
            post_upload_actions=(shortcut,),
            warnings=[RunWarning("render", "warning", "report: warned")],
        ),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[RunWarning("sources", "warning", "preflight: warned")],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
            analysis_clip=None,
        ),
    )

    async def fake_execute_prep(_request: RunRequest, _deps: RunDependencies) -> PrepState:
        return prep

    async def fake_execute_phases(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "execute_phases", fake_execute_phases)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda *a, **kw: None)

    result = asyncio.run(
        execute_run(
            make_run_request(config=ConfigSchema(), root=tmp_path, quiet=True),
            deps=RunDependencies(monotonic_timer=_zero_monotonic_timer),
        )
    )

    assert result.success is True
    assert result.post_upload_actions == (shortcut,)
    assert [warning.text for warning in result.warnings] == ["preflight: warned", "report: warned"]


def test_execute_run_propagates_collection_warning_once_through_result_summary_and_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference_path = tmp_path / "comparison_videos" / "Reference.mkv"
    reference_path.parent.mkdir(parents=True)
    reference_path.write_bytes(b"reference")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    workspace = _workspace(
        tmp_path,
        run_subdir="run",
        screenshots_subdir="run/screenshots",
    )

    config = ConfigSchema()
    config.audio_alignment.enable = False
    config.report.enable = False
    config.slowpics.auto_upload = True
    config.slowpics.tmdb_id = 9
    config.slowpics.tmdb_media_type = "movie"
    config.slowpics.title = "Explicit title"
    reference = clip_state(reference_path, label="Reference")
    prep = PrepState(
        workspace=workspace,
        config=config,
        input_videos=[reference_path],
        clips=[reference],
        artifacts=RunArtifacts(
            resolved_metadata=TmdbMetadata(
                tmdb_id=7,
                title="Resolved title",
                original_title="Resolved title",
                year=2024,
                media_type="tv",
            )
        ),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
            analysis_clip=None,
        ),
    )
    capture = ReservedRunCapture(
        workspace=workspace,
        clip_count=1,
        preflight_duration=0.0,
        preflight_warnings=[],
        run_warnings=[],
    )
    captured_collection: SlowpicsCollectionMetadata | None = None

    async def fake_execute_prep(request: RunRequest, deps: RunDependencies) -> PrepState:
        del request
        assert deps.capture_reserved_run is not None
        deps.capture_reserved_run(capture)
        return prep

    def fake_render_phase(
        _ctx: RunContext,
        *,
        frames: list[int],
        runner: object,
    ) -> RenderPhaseOutput:
        del runner
        screenshot_dir = workspace.screenshots_dir
        assert screenshot_dir is not None
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshots = []
        for frame in frames:
            screenshot = screenshot_dir / f"{frame}.png"
            screenshot.write_bytes(b"PNG")
            screenshots.append(screenshot)
        return RenderPhaseOutput(
            render=_render_artifacts(
                screenshots_by_label={"Reference": screenshots},
                screenshot_dir=screenshot_dir,
            )
        )

    async def fake_publish_to_slowpics(**kwargs: object) -> PublishResult:
        nonlocal captured_collection
        captured_collection = cast(SlowpicsCollectionMetadata, kwargs["collection_metadata"])
        upload_plan = cast(SlowpicsUploadPlan, kwargs["upload_plan"])
        file_paths = tuple(upload_plan.file_paths)
        return PublishResult(
            url="https://slow.pics/c/explicit",
            screenshot_count=len(file_paths),
            upload_duration_seconds=0.0,
            uploaded_file_paths=file_paths,
        )

    async def fake_post_upload_actions(
        *_args: object, **_kwargs: object
    ) -> tuple[PostUploadActionResult, ...]:
        return ()

    def reject_unexpected_http(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected HTTP request: {request.method} {request.url}")

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda *a, **kw: None)
    monkeypatch.setattr(coordinator, "emit_final_selection_report", lambda *a, **kw: None)
    monkeypatch.setattr(coordinator, "emit_frame_alignment_report", lambda *a, **kw: None)
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_render_phase",
        fake_render_phase,
    )
    monkeypatch.setattr(
        "frame_compare.orchestration.phase_post_render.publish_to_slowpics",
        fake_publish_to_slowpics,
    )
    monkeypatch.setattr(
        "frame_compare.orchestration.phase_post_render.run_slowpics_post_upload_actions",
        fake_post_upload_actions,
    )

    async def invoke() -> object:
        transport = httpx.MockTransport(reject_unexpected_http)
        async with httpx.AsyncClient(transport=transport) as client:
            return await execute_run(
                make_run_request(
                    root=tmp_path, config=config, skip_analysis=True, skip_metadata=True
                ),
                deps=RunDependencies(
                    ffmpeg_runner=FakeFFmpegRunner(),
                    http_client=client,
                    monotonic_timer=_zero_monotonic_timer,
                    progress=NullProgressReporter(),
                ),
            )

    result = cast(RunResult, asyncio.run(invoke()))
    mismatch = (
        "slow.pics: explicit TMDB association differs from resolved metadata; "
        "automatic title metadata was not combined with the explicit association"
    )
    assert [warning.text for warning in result.warnings] == [mismatch]
    assert result.slowpics_url == "https://slow.pics/c/explicit"
    assert captured_collection is not None
    assert captured_collection.title == "Explicit title"
    assert (captured_collection.tmdb_id, captured_collection.tmdb_media_type) == (9, "movie")

    record = read_run_result(run_dir / "run_result.toml")
    assert record.status == "completed_with_warnings"
    assert record.warning_count == 1
    assert record.warning_summaries == ("A run warning was reported.",)
    console = Console(record=True, color_system=None, width=120)
    from frame_compare.cli.output import print_result_summary

    print_result_summary(console, result=result, quiet=False, root=tmp_path)
    summary = console.export_text()
    assert "Comparison complete · 1 warning" in summary
    assert summary.count("explicit TMDB association differs") == 1

    json_output: list[str] = []
    monkeypatch.setattr(run_command.typer, "echo", json_output.append)
    run_command.handle_json_output(result)
    payload = json.loads(json_output[0])
    assert set(payload) == {
        "cache_hit",
        "clips_processed",
        "duration_seconds",
        "errors",
        "frame_count",
        "report_path",
        "screenshots_dir",
        "slowpics_url",
        "success",
    }
    assert payload["slowpics_url"] == "https://slow.pics/c/explicit"


@pytest.mark.parametrize(
    ("enabled", "confirm_after_report", "expected"),
    [
        (True, True, ["Analyze", "Align", "Render", "Report", "Publish"]),
        (True, False, ["Analyze", "Align", "Render", "Publish", "Report"]),
        (False, False, ["Render"]),
    ],
)
def test_execute_run_initializes_enabled_step_map_before_phase_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    confirm_after_report: bool,
    expected: list[str],
) -> None:
    config = ConfigSchema()
    config.analysis.dark_frame_count = 1 if enabled else 0
    config.analysis.bright_frame_count = 0
    config.analysis.motion_frame_count = 0
    config.analysis.random_frame_count = 0
    config.audio_alignment.enable = enabled
    config.report.enable = enabled
    config.slowpics.auto_upload = enabled
    config.slowpics.confirm_upload_after_report = confirm_after_report
    prep = PrepState(
        workspace=_workspace(tmp_path, run_subdir=None),
        config=config,
        input_videos=[tmp_path / "reference.mkv"],
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
            analysis_clip=None,
        ),
    )
    steps: list[str] = []

    class RecordingReporter(NullProgressReporter):
        def set_phase_steps(self, labels: list[str]) -> None:
            steps.extend(labels)

    phase_error = RuntimeError("phase failed")

    async def _execute_prep(_request: RunRequest, _deps: RunDependencies) -> PrepState:
        return prep

    async def _execute_phases(*_args: object, **_kwargs: object) -> None:
        raise phase_error

    monkeypatch.setattr(coordinator, "execute_prep", _execute_prep)
    monkeypatch.setattr(coordinator, "execute_phases", _execute_phases)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda **_kwargs: None)
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            execute_run(
                make_run_request(config=ConfigSchema(), root=tmp_path),
                deps=RunDependencies(
                    monotonic_timer=_zero_monotonic_timer, progress=RecordingReporter()
                ),
            )
        )

    assert exc_info.value is phase_error
    assert steps == expected


def test_execute_run_cleanup_delete_error_returns_warning_not_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ConfigSchema()
    config.slowpics.auto_upload = True
    config.slowpics.confirm_upload_after_report = False
    config.slowpics.delete_after_upload = True
    config.report.enable = False
    uploaded = tmp_path / "screenshots" / "planned.png"
    uploaded.parent.mkdir(parents=True, exist_ok=True)
    uploaded.write_bytes(b"\x89PNG\r\n\x1a\n")
    render = _render_artifacts(
        screenshots_by_label={"Reference": [uploaded]},
        screenshot_dir=uploaded.parent,
    )
    prep = PrepState(
        workspace=_workspace(tmp_path, run_subdir=None),
        config=config,
        input_videos=[tmp_path / "reference.mkv"],
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
            analysis_clip=None,
        ),
    )

    async def fake_execute_prep(_request: RunRequest, _deps: RunDependencies) -> PrepState:
        return prep

    def fake_render_phase(*_args: object, **_kwargs: object) -> RenderPhaseOutput:
        return RenderPhaseOutput(render=render)

    async def fake_publish_phase(*_args: object, **_kwargs: object) -> PublishPhaseOutput:
        return PublishPhaseOutput(
            slowpics_url="https://slow.pics/c/example",
            uploaded_file_paths=(uploaded,),
            post_upload_actions=(
                PostUploadActionResult(
                    kind="shortcut",
                    success=False,
                    warning=RunWarning(
                        "slow.pics",
                        "warning",
                        "slow.pics shortcut:",
                        "could not choose a safe output directory",
                    ),
                ),
            ),
        )

    def fake_unlink(self: Path) -> None:
        if self == uploaded:
            raise PermissionError("locked")
        Path.unlink(self)

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda *a, **kw: None)
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_render_phase",
        fake_render_phase,
    )
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        fake_publish_phase,
    )
    monkeypatch.setattr(Path, "unlink", fake_unlink)

    request = make_run_request(
        config=ConfigSchema(),
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        quiet=True,
    )
    deps = RunDependencies(
        vs_loader=FakeVSLoader(),
        ffmpeg_runner=FakeFFmpegRunner(),
        monotonic_timer=_zero_monotonic_timer,
    )

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.slowpics_url == "https://slow.pics/c/example"
    assert [warning.text for warning in result.warnings] == [
        f"cleanup: failed to delete uploaded screenshot {uploaded}: locked",
        "slow.pics shortcut: could not choose a safe output directory",
    ]


def test_execute_run_webhook_action_warning_is_warning_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ConfigSchema()
    config.slowpics.auto_upload = True
    config.slowpics.confirm_upload_after_report = False
    config.report.enable = False
    webhook_warning = RunWarning("slow.pics", "warning", "slow.pics webhook: delivery failed")
    render = _render_artifacts(
        screenshots_by_label={"Reference": [tmp_path / "screenshots" / "planned.png"]},
        screenshot_dir=tmp_path / "screenshots",
    )
    prep = PrepState(
        workspace=_workspace(tmp_path, run_subdir=None),
        config=config,
        input_videos=[tmp_path / "reference.mkv"],
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
            analysis_clip=None,
        ),
    )

    async def fake_execute_prep(_request: RunRequest, _deps: RunDependencies) -> PrepState:
        return prep

    def fake_render_phase(*_args: object, **_kwargs: object) -> RenderPhaseOutput:
        return RenderPhaseOutput(render=render)

    async def fake_publish_phase(*_args: object, **_kwargs: object) -> PublishPhaseOutput:
        return PublishPhaseOutput(
            slowpics_url="https://slow.pics/c/example",
            post_upload_actions=(
                PostUploadActionResult(
                    kind="webhook",
                    success=False,
                    warning=webhook_warning,
                ),
            ),
        )

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda *a, **kw: None)
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_render_phase",
        fake_render_phase,
    )
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        fake_publish_phase,
    )

    request = make_run_request(
        config=ConfigSchema(),
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        quiet=True,
    )
    deps = RunDependencies(
        vs_loader=FakeVSLoader(),
        ffmpeg_runner=FakeFFmpegRunner(),
        monotonic_timer=_zero_monotonic_timer,
    )

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.post_upload_actions == (
        PostUploadActionResult(kind="webhook", success=False, warning=webhook_warning),
    )
    assert result.warnings == [webhook_warning]


def test_execute_run_report_warning_blocks_delete_after_upload_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ConfigSchema()
    config.slowpics.auto_upload = True
    config.slowpics.confirm_upload_after_report = False
    config.slowpics.delete_after_upload = True
    config.report.enable = True
    config.report.embed_images = True
    uploaded = tmp_path / "screenshots" / "planned.png"
    uploaded.parent.mkdir(parents=True, exist_ok=True)
    uploaded.write_bytes(b"\x89PNG\r\n\x1a\n")
    render = _render_artifacts(
        screenshots_by_label={"Reference": [uploaded]},
        screenshot_dir=uploaded.parent,
    )
    prep = PrepState(
        workspace=_workspace(tmp_path, run_subdir=None),
        config=config,
        input_videos=[tmp_path / "reference.mkv"],
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
            analysis_clip=None,
        ),
    )

    async def fake_execute_prep(_request: RunRequest, _deps: RunDependencies) -> PrepState:
        return prep

    def fake_render_phase(*_args: object, **_kwargs: object) -> RenderPhaseOutput:
        return RenderPhaseOutput(render=render)

    async def fake_publish_phase(*_args: object, **_kwargs: object) -> PublishPhaseOutput:
        return PublishPhaseOutput(
            slowpics_url="https://slow.pics/c/example",
            uploaded_file_paths=(uploaded,),
        )

    def fake_report_phase(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("report write failed")

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda *a, **kw: None)
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_render_phase",
        fake_render_phase,
    )
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_publish_phase",
        fake_publish_phase,
    )
    monkeypatch.setattr(
        "frame_compare.orchestration.execution.run_report_phase",
        fake_report_phase,
    )

    request = make_run_request(
        config=ConfigSchema(),
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        quiet=True,
    )
    deps = RunDependencies(
        vs_loader=FakeVSLoader(),
        ffmpeg_runner=FakeFFmpegRunner(),
        monotonic_timer=_zero_monotonic_timer,
    )

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.slowpics_url == "https://slow.pics/c/example"
    assert any(warning.text.startswith("report:") for warning in result.warnings)
    assert uploaded.exists()


def test_execute_run_ffmpeg_render_rejects_hdr_when_tonemap_enabled(
    tmp_path: Path,
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = make_run_request(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        overrides=CLIConfigOverrides(no_upload=True),
    )
    deps = RunDependencies(vs_loader=FakeHDRVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(TonemapRequiresVapourSynthError):
        asyncio.run(execute_run(request, deps=deps))


def test_run_acquisition_propagates_config_not_found_error(tmp_path: Path) -> None:
    from frame_compare.orchestration.run_inputs import build_run_request

    with pytest.raises(ConfigNotFoundError):
        build_run_request(root=tmp_path)


def test_execute_run_applies_cli_overrides_before_phase_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = false
force_interactive = false
use_vsview = false

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv", "comp.mkv")

    request = make_run_request(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        overrides=CLIConfigOverrides(
            tm_preset=TonemapPreset.FILMIC,
            tm_target_nits=203,
            overlay_mode=OverlayMode.DIAGNOSTIC,
            seed=123,
            no_upload=True,
            force_interactive_alignment=True,
        ),
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    captured: dict[str, object] = {}

    async def _capture_execute_phases(
        _phases: object, context: RunContext, _reporter: object
    ) -> None:
        if "config" not in captured:
            captured["config"] = context.config

    monkeypatch.setattr(coordinator, "execute_phases", _capture_execute_phases)

    asyncio.run(execute_run(request, deps=deps))

    config = cast(ConfigSchema, captured["config"])
    assert config.color.preset == TonemapPreset.FILMIC
    assert config.color.target_nits == 203
    assert config.screenshots.overlay_mode == OverlayMode.DIAGNOSTIC
    assert config.analysis.random_seed == 123
    assert config.slowpics.auto_upload is False
    assert config.audio_alignment.force_interactive is True
    assert config.audio_alignment.use_vsview is True


def test_execute_run_publish_skip_follows_effective_slowpics_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_content = """\
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[slowpics]
auto_upload = false

[report]
enable = false
"""
    create_config(tmp_path, content=config_content)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    publish_attempts: list[None] = []

    async def _unexpected_publish(**_kwargs: object) -> object:
        publish_attempts.append(None)
        raise AssertionError("publish should be skipped by effective slowpics config")

    from frame_compare.orchestration import phase_post_render

    monkeypatch.setattr(phase_post_render, "publish_to_slowpics", _unexpected_publish)

    request = make_run_request(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        overrides=CLIConfigOverrides(no_upload=False),
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.slowpics_url is None
    assert result.phase_timings["publish"] >= 0.0
    assert publish_attempts == []


def test_execute_run_uses_and_populates_probe_cache_without_reprobing(tmp_path: Path) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = make_run_request(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        overrides=CLIConfigOverrides(no_upload=True),
    )

    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())
    result = asyncio.run(execute_run(request, deps=deps))
    assert result.success is True

    cache_path = tmp_path / "generated" / "clip_probe.toml"
    assert cache_path.exists()
    cache_before = cache_path.read_text(encoding="utf-8")

    class RaisingFakeVSLoader:
        def load(self, path: Path) -> SourceInfo:
            raise AssertionError(f"Fake VS loader should not be called: {path}")

        def ensure_core(self) -> Never:
            raise AssertionError("Fake VS core should not be requested when cache is warm")

    reuse_deps = RunDependencies(vs_loader=RaisingFakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())
    reuse_result = asyncio.run(execute_run(request, deps=reuse_deps))
    assert reuse_result.success is True

    cache_after = cache_path.read_text(encoding="utf-8")
    assert cache_after == cache_before


def test_execute_run_mixed_source_fps_rejects_before_phase_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "a_reference.mkv", "b_comparison.mkv")

    class MixedFpsVSLoader(FakeVSLoader):
        def load(self, path: Path) -> SourceInfo:
            source_info = super().load(path)
            source_info.fps = (
                Fraction(24000, 1001) if path.name == "a_reference.mkv" else Fraction(30000, 1001)
            )
            return source_info

    phases_started = False

    async def _unexpected_execute_phases(*_args: object, **_kwargs: object) -> None:
        nonlocal phases_started
        phases_started = True

    monkeypatch.setattr(coordinator, "execute_phases", _unexpected_execute_phases)

    request = make_run_request(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        overrides=CLIConfigOverrides(no_upload=True),
    )
    deps = RunDependencies(vs_loader=MixedFpsVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(MixedSourceFpsError, match="Mixed source FPS is not supported"):
        asyncio.run(execute_run(request, deps=deps))


def first_sigint_lifecycle_probe(root: Path, owner: str) -> None:
    import json
    import os
    import signal
    import subprocess
    import sys
    import threading
    import time
    from typing import Any

    import httpx
    from typer.testing import CliRunner

    from frame_compare.cli.entry import app
    from frame_compare.orchestration import execution
    from frame_compare.orchestration.execution_types import ExecutionState, PhaseOutput
    from frame_compare.orchestration.types import ReservedRunCapture
    from frame_compare.render.batch import orchestrator as batch
    from frame_compare.render.errors import RenderError
    from frame_compare.render.types import EncoderSettings, RenderedFrameResult, RenderRequest
    from frame_compare.services.run_result_record import RUN_RESULT_FILENAME, read_run_result
    from frame_compare.utils.media_facts import RenderedFrameFacts
    from frame_compare.vsview import adapter

    create_config(root)
    workspace = _workspace(root)
    assert workspace.run_dir is not None
    workspace.run_dir.mkdir(parents=True)
    config = ConfigSchema()
    config.audio_alignment.enable = False
    config.report.enable = True
    artifacts = RunArtifacts()
    ready = threading.Event()
    interrupted = threading.Event()
    release_render = threading.Event()
    close_completed: list[bool] = []
    calls: list[int] = []
    applied: list[str] = []
    children: list[subprocess.Popen[Any]] = []
    later: list[str] = []

    async def prep(_request: RunRequest, deps: RunDependencies) -> PrepState:
        assert deps.capture_reserved_run is not None
        deps.capture_reserved_run(
            ReservedRunCapture(
                workspace=workspace,
                clip_count=1,
                preflight_duration=0.0,
                preflight_warnings=[],
                run_warnings=artifacts.warnings,
            )
        )
        return PrepState(
            workspace=workspace,
            config=config,
            input_videos=[root / "reference.mkv"],
            clips=[clip_state(root / "reference.mkv", label="Reference")],
            artifacts=artifacts,
            metadata_prefetch=MetadataPrefetch(None, False),
            preflight_warnings=[],
            preflight_duration=0.0,
            load_sources_start=time.monotonic(),
            selection_domain=PreparedSelectionDomain(
                token="test", selection_window=SelectionWindow(0, 100), analysis_clip=None
            ),
        )

    def interrupt() -> None:
        assert ready.wait(3)
        # os.kill(..., SIGINT) forcibly terminates Windows instead of invoking Runner.
        signal.raise_signal(signal.SIGINT)
        interrupted.set()
        release_render.set()

    class DelayedCloseTransport(httpx.AsyncBaseTransport):
        async def aclose(self) -> None:
            await asyncio.sleep(0)
            close_completed.append(True)

    def render_frame(request: RenderRequest) -> RenderedFrameResult:
        calls.append(request.frame_number)
        if owner == "failure" and request.frame_number == 0:
            raise RenderError("render failed before interrupt")
        ready.set()
        assert release_render.wait(3)
        return RenderedFrameResult(
            request.output_path,
            RenderedFrameFacts(
                source_frame=request.frame_number,
            ),
        )

    real_popen = adapter.subprocess.Popen

    def popen(command: list[str], **kwargs: Any) -> subprocess.Popen[Any]:
        child = real_popen(command, **kwargs)
        children.append(child)
        ready.set()
        return child

    def render(*_args: object, **_kwargs: object) -> RenderPhaseOutput:
        if owner == "httpx":
            ready.set()
            assert interrupted.wait(3)
            raise asyncio.CancelledError()
        if owner == "startup":
            adapter._run_startup_probe(
                [sys.executable, "-c", "import threading; threading.Event().wait(0.5)"],
                env=os.environ.copy(),
            )
        elif owner == "vsview":
            adapter._run_vsview_command(
                [sys.executable, "-c", "import threading; threading.Event().wait(0.5)"],
                env=os.environ.copy(),
            )
        else:
            requests = [
                RenderRequest(
                    clip=root / "reference.mkv",
                    diagnostic_source=root / "reference.mkv",
                    frame_number=index,
                    output_path=root / f"{index}.png",
                    overlay=None,
                    encoder_settings=EncoderSettings(),
                )
                for index in range(6)
            ]
            batch.render_clip_jobs(
                prepared_jobs(*[(request,) for request in requests]), parallelism=2
            )
        return RenderPhaseOutput(
            _render_artifacts(
                screenshots_by_label={},
                screenshot_dir=workspace.screenshots_dir,
            )
        )

    real_wait = batch.wait
    failure_interrupted: list[bool] = []

    def wait_for_failure(*args: Any, **kwargs: Any) -> Any:
        done, pending = real_wait(*args, **kwargs)
        if done and not failure_interrupted:
            failure_interrupted.append(True)
            signal.raise_signal(signal.SIGINT)
            release_render.set()
        return done, pending

    real_apply = execution.apply_phase_output

    def apply(*, ctx: RunContext, state: ExecutionState, output: PhaseOutput) -> None:
        if isinstance(output, RenderPhaseOutput):
            applied.append("render")
        real_apply(ctx=ctx, state=state, output=output)

    def report(*_args: object, **_kwargs: object) -> Never:
        later.append("report")
        raise AssertionError("later phase admitted")

    sender = threading.Thread(target=interrupt)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(coordinator, "execute_prep", prep)
        patch.setattr(execution, "run_render_phase", render)
        patch.setattr(execution, "run_report_phase", report)
        patch.setattr(execution, "apply_phase_output", apply)
        patch.setattr(batch, "render_frame_detailed", render_frame)
        patch.setattr(adapter.subprocess, "Popen", popen)
        if owner in {"httpx", "failure"}:
            client = httpx.AsyncClient(transport=DelayedCloseTransport())
            patch.setattr(coordinator.httpx, "AsyncClient", lambda: client)
        if owner == "failure":
            patch.setattr(batch, "wait", wait_for_failure)
        else:
            sender.start()
        result = CliRunner().invoke(
            app,
            [
                "run",
                "--root",
                str(root),
                "--quiet",
                "--skip-analysis",
                "--skip-metadata",
                "--no-upload",
            ],
        )
        if owner != "failure":
            sender.join(3)
    record = read_run_result(workspace.run_dir / RUN_RESULT_FILENAME)
    print(
        json.dumps(
            {
                "exit": result.exit_code,
                "status": record.status,
                "calls": sorted(calls),
                "later": later,
                "applied": applied,
                "reaped": all(child.poll() is not None for child in children),
                "children": len(children),
                "close_completed": close_completed,
            }
        )
    )
    raise SystemExit(result.exit_code)


@pytest.mark.parametrize("owner", ["vsview", "startup", "render", "httpx"])
def test_first_sigint_stops_admission_and_records_failure(tmp_path: Path, owner: str) -> None:
    import json
    import subprocess
    import sys

    code = (
        "from pathlib import Path; import sys; "
        "from tests.orchestration.test_execute_run_lifecycle import first_sigint_lifecycle_probe; "
        "first_sigint_lifecycle_probe(Path(sys.argv[1]), sys.argv[2])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), owner],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 130, result.stderr
    observed = json.loads(result.stdout)
    assert observed["status"] == "failed"
    assert observed["later"] == []
    assert observed["applied"] == []
    assert observed["reaped"] is True
    if owner in {"vsview", "startup"}:
        assert observed["children"] == 1
    elif owner == "render":
        assert observed["calls"] in ([0], [0, 1])
    else:
        assert observed["close_completed"] == [True]


def test_interrupt_after_native_source_load_skips_probe_cache_and_records_failure(
    tmp_path: Path,
) -> None:
    from frame_compare.services.run_result_record import RUN_RESULT_FILENAME, read_run_result

    create_config(tmp_path)
    create_video_files(tmp_path / "comparison_videos", "source.mkv", "comparison.mkv")
    calls: list[Path] = []

    class InterruptedLoader(FakeVSLoader):
        def load(self, path: Path) -> SourceInfo:
            source = super().load(path)
            calls.append(path)
            task = asyncio.current_task()
            assert task is not None
            task.cancel()
            return source

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            execute_run(
                make_run_request(
                    root=tmp_path,
                    quiet=True,
                    skip_analysis=True,
                    skip_metadata=True,
                    overrides=CLIConfigOverrides(no_upload=True),
                ),
                RunDependencies(vs_loader=InterruptedLoader(), ffmpeg_runner=FakeFFmpegRunner()),
            )
        )
    assert len(calls) == 1
    assert list((tmp_path / "generated").rglob("clip_probe.toml")) == []
    records = list((tmp_path / "generated").rglob(RUN_RESULT_FILENAME))
    assert len(records) == 1
    assert read_run_result(records[0]).status == "failed"


def test_real_render_failure_wins_over_queued_sigint_and_client_close(tmp_path: Path) -> None:
    import json
    import subprocess
    import sys

    code = (
        "from pathlib import Path; import sys; "
        "from tests.orchestration.test_execute_run_lifecycle import first_sigint_lifecycle_probe; "
        "first_sigint_lifecycle_probe(Path(sys.argv[1]), 'failure')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        timeout=10,
    )
    from frame_compare.cli.errors import ExitCode

    assert result.returncode == int(ExitCode.PROCESSING_ERROR), result.stderr
    observed = json.loads(result.stdout)
    assert observed["status"] == "failed"
    assert observed["later"] == []
    assert observed["applied"] == []
    assert observed["close_completed"] == [True]
    assert observed["calls"] in ([0], [0, 1])


def test_reservation_is_captured_before_interrupted_run_info_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from frame_compare.orchestration import preparation
    from frame_compare.services.run_info import RunInfo
    from frame_compare.services.run_result_record import RUN_RESULT_FILENAME, read_run_result
    from frame_compare.utils.cancellation import raise_if_cancelling

    create_config(tmp_path)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")
    write_info = preparation.write_run_info

    def interrupted_write(path: Path, info: RunInfo) -> None:
        write_info(path, info)
        task = asyncio.current_task()
        assert task is not None
        task.cancel()
        raise_if_cancelling()

    monkeypatch.setattr(preparation, "write_run_info", interrupted_write)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            execute_run(
                make_run_request(
                    root=tmp_path,
                    quiet=True,
                    skip_analysis=True,
                    skip_metadata=True,
                    overrides=CLIConfigOverrides(no_upload=True),
                ),
                RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner()),
            )
        )
    records = list((tmp_path / "generated").rglob(RUN_RESULT_FILENAME))
    assert len(records) == 1
    assert read_run_result(records[0]).status == "failed"


@pytest.mark.parametrize("confirm_after_report", [False, True])
@pytest.mark.parametrize(
    "outcome", ["success", "webhook_cancel", "publisher_handoff", "phase_handoff", "upload_failure"]
)
async def test_confirmed_upload_facts_survive_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    confirm_after_report: bool,
    outcome: str,
) -> None:
    from threading import Event

    from frame_compare.orchestration import execution, phase_post_render
    from frame_compare.orchestration.execution_types import (
        ExecutionState,
        PhaseOutput,
        PostReportCleanupPhaseOutput,
        ReportPhaseOutput,
    )
    from frame_compare.services import slowpics_webhook
    from frame_compare.services.errors import SlowpicsError
    from frame_compare.services.slowpics_post_upload import SlowpicsPostUploadRequest
    from frame_compare.services.slowpics_webhook import SlowpicsWebhookResult

    workspace = _workspace(tmp_path, run_subdir="run", screenshots_subdir="run/screenshots")
    assert workspace.run_dir is not None
    workspace.run_dir.mkdir()
    config = ConfigSchema()
    config.audio_alignment.enable = False
    config.report.enable = confirm_after_report
    config.report.embed_images = True
    config.slowpics.auto_upload = True
    config.slowpics.confirm_upload_after_report = confirm_after_report
    config.slowpics.create_url_shortcut = outcome == "publisher_handoff"
    config.slowpics.delete_after_upload = True
    config.slowpics.webhook_url = "https://hooks.example.test/offline"
    config.slowpics.title = "Offline cancellation test"
    artifacts = RunArtifacts()
    source = tmp_path / "reference.mkv"
    prep = PrepState(
        workspace=workspace,
        config=config,
        input_videos=[source],
        clips=[clip_state(source, label="Reference")],
        artifacts=artifacts,
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=0.0,
        selection_domain=PreparedSelectionDomain(
            token="test", selection_window=SelectionWindow(0, 100), analysis_clip=None
        ),
    )
    known_url = "https://slow.pics/c/confirmed-offline"
    uploaded_paths: tuple[Path, ...] = ()
    connector_started = Event()
    connector_finished = Event()
    release_connector = Event()
    applied_publish: list[bool] = []
    post_upload_started: list[bool] = []
    cleanup_started: list[bool] = []

    async def fake_prep(_request: RunRequest, deps: RunDependencies) -> PrepState:
        assert deps.capture_reserved_run is not None
        deps.capture_reserved_run(
            ReservedRunCapture(
                workspace=workspace,
                clip_count=1,
                preflight_duration=0.0,
                preflight_warnings=[],
                run_warnings=artifacts.warnings,
            )
        )
        return prep

    def fake_render(_ctx: RunContext, *, frames: list[int], runner: object) -> RenderPhaseOutput:
        del runner
        screenshots = workspace.screenshots_dir
        assert screenshots is not None
        screenshots.mkdir()
        paths = [screenshots / f"{frame}.png" for frame in frames]
        for path in paths:
            path.write_bytes(b"PNG")
        # A leftover screenshot must never be mistaken for part of this upload.
        (screenshots / "stale.png").write_bytes(b"PNG")
        return RenderPhaseOutput(
            _render_artifacts(screenshots_by_label={"Reference": paths}, screenshot_dir=screenshots)
        )

    def fake_report(*_args: object, **_kwargs: object) -> ReportPhaseOutput:
        assert workspace.run_dir is not None
        path = workspace.run_dir / "report.html"
        path.write_text("offline report", encoding="utf-8")
        return ReportPhaseOutput(path, report_succeeded=True)

    async def fake_publish(**kwargs: object) -> PublishResult:
        nonlocal uploaded_paths
        if outcome == "upload_failure":
            raise SlowpicsError("Image upload failed with status 400")
        uploaded_paths = tuple(cast(SlowpicsUploadPlan, kwargs["upload_plan"]).file_paths)
        if outcome == "publisher_handoff":
            task = asyncio.current_task()
            assert task is not None
            task.cancel()
        return PublishResult(
            url=known_url,
            screenshot_count=len(uploaded_paths),
            upload_duration_seconds=0.0,
            uploaded_file_paths=uploaded_paths,
        )

    def connector(
        _request: slowpics_webhook.WebhookDeliveryRequest,
    ) -> slowpics_webhook.WebhookResponse:
        connector_started.set()
        try:
            if outcome == "webhook_cancel":
                assert release_connector.wait(5), "test did not release webhook worker"
            return slowpics_webhook.WebhookResponse(status_code=204)
        finally:
            connector_finished.set()

    async def injected_webhook(*, webhook_url: str, slowpics_url: str) -> SlowpicsWebhookResult:
        return await slowpics_webhook.deliver_slowpics_webhook(
            webhook_url=webhook_url,
            slowpics_url=slowpics_url,
            resolver=lambda _host, _port: ("8.8.8.8",),
            connector=connector,
        )

    real_post_upload = phase_post_render.run_slowpics_post_upload_actions

    async def post_upload(request: SlowpicsPostUploadRequest) -> tuple[PostUploadActionResult, ...]:
        post_upload_started.append(True)
        if outcome == "phase_handoff":
            task = asyncio.current_task()
            assert task is not None
            task.cancel()
            return ()
        return await real_post_upload(request)

    real_apply = execution.apply_phase_output

    def apply(*, ctx: RunContext, state: ExecutionState, output: PhaseOutput) -> None:
        if isinstance(output, PublishPhaseOutput):
            applied_publish.append(True)
        real_apply(ctx=ctx, state=state, output=output)

    real_cleanup = execution.run_post_report_cleanup_phase

    def cleanup(
        ctx: RunContext, *, uploaded_file_paths: tuple[Path, ...], report_succeeded: bool
    ) -> PostReportCleanupPhaseOutput:
        cleanup_started.append(True)
        return real_cleanup(
            ctx, uploaded_file_paths=uploaded_file_paths, report_succeeded=report_succeeded
        )

    def reject_network(*_args: object, **_kwargs: object) -> Never:
        raise AssertionError("Unexpected network access in offline lifecycle test")

    monkeypatch.setattr(coordinator, "execute_prep", fake_prep)
    for name in (
        "emit_consolidated_fps_report",
        "emit_final_selection_report",
        "emit_frame_alignment_report",
    ):
        monkeypatch.setattr(coordinator, name, lambda *a, **kw: None)
    monkeypatch.setattr(execution, "run_render_phase", fake_render)
    monkeypatch.setattr(execution, "run_report_phase", fake_report)
    monkeypatch.setattr(execution, "apply_phase_output", apply)
    monkeypatch.setattr(execution, "run_post_report_cleanup_phase", cleanup)
    monkeypatch.setattr(phase_post_render, "publish_to_slowpics", fake_publish)
    monkeypatch.setattr(phase_post_render, "run_slowpics_post_upload_actions", post_upload)
    monkeypatch.setattr(
        "frame_compare.services.slowpics_post_upload.deliver_slowpics_webhook", injected_webhook
    )
    monkeypatch.setattr("socket.getaddrinfo", reject_network)
    monkeypatch.setattr("socket.create_connection", reject_network)
    monkeypatch.setattr("socket.socket.connect", reject_network)

    async with httpx.AsyncClient(transport=httpx.MockTransport(reject_network)) as client:
        worker = asyncio.create_task(
            execute_run(
                make_run_request(
                    root=tmp_path, config=config, skip_analysis=True, skip_metadata=True
                ),
                deps=RunDependencies(
                    ffmpeg_runner=FakeFFmpegRunner(),
                    http_client=client,
                    monotonic_timer=_zero_monotonic_timer,
                    progress=NullProgressReporter(),
                    confirm_slowpics_upload=lambda request: "confirmed",
                ),
            )
        )
        try:
            if outcome == "webhook_cancel":
                async with asyncio.timeout(3):
                    while not connector_started.is_set():
                        if worker.done():
                            await worker
                        await asyncio.sleep(0.005)
                worker.cancel()
                await asyncio.sleep(0)
                worker.cancel()
                await asyncio.sleep(0)
                assert not worker.done(), "cancellation abandoned the blocked webhook worker"
                release_connector.set()
            if outcome in {"webhook_cancel", "publisher_handoff", "phase_handoff"}:
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(worker, 3)
            else:
                result = await asyncio.wait_for(worker, 3)
                assert result.success
                assert result.slowpics_url == (None if outcome == "upload_failure" else known_url)
        finally:
            release_connector.set()
            if not worker.done():
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)

    record = read_run_result(workspace.run_dir / "run_result.toml")
    cancelled = outcome in {"webhook_cancel", "publisher_handoff", "phase_handoff"}
    confirmed = outcome != "upload_failure"
    assert record.status == (
        "failed" if cancelled else "completed_with_warnings" if not confirmed else "completed"
    )
    assert record.slowpics_outcome == ("uploaded" if confirmed else "not_uploaded")
    assert record.slowpics_url == (known_url if confirmed else None)
    assert artifacts.slowpics_url == record.slowpics_url
    assert artifacts.uploaded_slowpics_file_paths == uploaded_paths
    assert bool(applied_publish) == (outcome == "success")
    assert bool(cleanup_started) == (not cancelled)
    assert bool(post_upload_started) == (outcome not in {"publisher_handoff", "upload_failure"})
    assert connector_started.is_set() == (outcome in {"success", "webhook_cancel"})
    assert connector_finished.is_set() == connector_started.is_set()
    if cancelled:
        assert all(path.exists() for path in uploaded_paths)
        assert artifacts.post_upload_actions == ()
        assert not list(workspace.run_dir.glob("*.url"))
    else:
        assert all(not path.exists() for path in uploaded_paths)
    assert workspace.screenshots_dir is not None
    assert (workspace.screenshots_dir / "stale.png").exists()
    if outcome == "upload_failure":
        assert artifacts.render is not None
        assert all(
            shot.result.path.exists()
            for clip in artifacts.render.clips
            for shot in clip.screenshots
        )
