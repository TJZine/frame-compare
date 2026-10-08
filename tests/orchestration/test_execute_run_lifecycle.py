"""Lifecycle-level tests for execute_run."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from typing import Never, cast

import pytest

from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.errors import ConfigNotFoundError
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
from frame_compare.utils.post_upload_actions import PostUploadActionResult
from frame_compare.utils.run_warnings import RunWarning
from frame_compare.vs.errors import TonemapRequiresVapourSynthError
from frame_compare.vs.types import SourceInfo

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
    """Return a stable monotonic timestamp for tests that do not exercise timing."""
    return 0.0


def test_execute_run_returns_success_and_records_preflight_timing(
    tmp_path: Path,
) -> None:
    """Given valid workspace -> returns success and records preflight timing."""
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
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
        analysis_selection_domain="test-selection-domain",
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(
            post_upload_actions=(shortcut,),
            warnings=[RunWarning("render", "warning", "report: warned")],
        ),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[RunWarning("sources", "warning", "preflight: warned")],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
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
            RunRequest(root=tmp_path, quiet=True),
            deps=RunDependencies(monotonic_timer=_zero_monotonic_timer),
        )
    )

    assert result.success is True
    assert result.post_upload_actions == (shortcut,)
    assert [warning.text for warning in result.warnings] == ["preflight: warned", "report: warned"]


def test_execute_run_closes_execution_section_without_masking_phase_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prep = PrepState(
        workspace=_workspace(tmp_path, run_subdir=None),
        config=ConfigSchema(),
        input_videos=[tmp_path / "reference.mkv"],
        analysis_selection_domain="test-selection-domain",
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
    )
    events: list[str] = []
    phase_error = RuntimeError("phase failed")

    async def _execute_prep(_request: RunRequest, _deps: RunDependencies) -> PrepState:
        return prep

    async def _execute_phases(*_args: object, **_kwargs: object) -> None:
        raise phase_error

    monkeypatch.setattr(coordinator, "execute_prep", _execute_prep)
    monkeypatch.setattr(coordinator, "execute_phases", _execute_phases)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda **_kwargs: None)
    monkeypatch.setattr(
        coordinator,
        "emit_execution_section_start",
        lambda *_args, **_kwargs: events.append("start"),
    )

    def _failing_close(*_args: object, **_kwargs: object) -> None:
        events.append("end")
        raise KeyboardInterrupt

    monkeypatch.setattr(coordinator, "emit_execution_section_end", _failing_close)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            execute_run(
                RunRequest(root=tmp_path),
                deps=RunDependencies(monotonic_timer=_zero_monotonic_timer),
            )
        )

    assert exc_info.value is phase_error


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
        analysis_selection_domain="test-selection-domain",
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
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

    request = RunRequest(
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
        analysis_selection_domain="test-selection-domain",
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
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

    request = RunRequest(
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
        analysis_selection_domain="test-selection-domain",
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=_zero_monotonic_timer(),
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
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

    request = RunRequest(
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

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=FakeHDRVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(TonemapRequiresVapourSynthError):
        asyncio.run(execute_run(request, deps=deps))


def test_execute_run_propagates_config_not_found_error(tmp_path: Path) -> None:
    """Given missing config -> preflight error is raised."""
    request = RunRequest(root=tmp_path)

    with pytest.raises(ConfigNotFoundError):
        asyncio.run(execute_run(request))


def test_execute_run_applies_cli_overrides_before_phase_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI overrides are applied to config before phase execution begins."""
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

    request = RunRequest(
        root=tmp_path,
        tm_preset=TonemapPreset.FILMIC,
        tm_target_nits=203,
        overlay_mode=OverlayMode.DIAGNOSTIC,
        seed=123,
        no_upload=True,
        force_interactive_alignment=True,
        skip_analysis=True,
        skip_metadata=True,
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

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=False,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    result = asyncio.run(execute_run(request, deps=deps))

    assert result.success is True
    assert result.slowpics_url is None
    assert result.phase_timings["publish"] >= 0.0
    assert publish_attempts == []


def test_execute_run_uses_and_populates_probe_cache_without_reprobing(tmp_path: Path) -> None:
    """Prove that probe cache is populated on first run and reused on second run without reprobe calls."""
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
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

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
    )
    deps = RunDependencies(vs_loader=MixedFpsVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    with pytest.raises(MixedSourceFpsError, match="Mixed source FPS is not supported"):
        asyncio.run(execute_run(request, deps=deps))


def first_sigint_lifecycle_probe(root: Path, owner: str) -> None:
    """Child entry point: real CLI, runner signals, owners and failed-record writer."""
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
            analysis_selection_domain="test",
            selection_window=SelectionWindow(0, 100),
        )

    def interrupt() -> None:
        assert ready.wait(3)
        os.kill(os.getpid(), signal.SIGINT)
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
            batch.render_batch_detailed(requests, parallelism=2)
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
            os.kill(os.getpid(), signal.SIGINT)
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
    result = subprocess.run(  # noqa: S603 - explicit interpreter and test-owned arguments
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
                RunRequest(
                    root=tmp_path,
                    quiet=True,
                    skip_analysis=True,
                    skip_metadata=True,
                    no_upload=True,
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
    result = subprocess.run(  # noqa: S603 - explicit interpreter and test-owned arguments
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
                RunRequest(
                    root=tmp_path,
                    quiet=True,
                    skip_analysis=True,
                    skip_metadata=True,
                    no_upload=True,
                ),
                RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner()),
            )
        )
    records = list((tmp_path / "generated").rglob(RUN_RESULT_FILENAME))
    assert len(records) == 1
    assert read_run_result(records[0]).status == "failed"
