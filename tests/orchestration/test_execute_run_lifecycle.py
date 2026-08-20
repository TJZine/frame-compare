"""Lifecycle-level tests for execute_run."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest

from frame_compare.analysis.types import SelectionBreakdown
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.config.schema import ConfigSchema, OverlayMode, TonemapPreset
from frame_compare.orchestration import coordinator
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.errors import MixedSourceFpsError
from frame_compare.orchestration.execution_types import (
    ExecutionPhasePlan,
    ExecutionState,
    MetadataPrefetch,
    PrepState,
    PublishPhaseOutput,
    RenderPhaseOutput,
    RunArtifacts,
)
from frame_compare.orchestration.phases import Phase
from frame_compare.utils.post_upload_actions import PostUploadActionResult
from frame_compare.utils.types import WorkspacePaths
from frame_compare.vs.errors import TonemapRequiresVapourSynthError
from frame_compare.vs.types import SourceInfo

from .execute_run_helpers import (
    FakeFFmpegRunner,
    FakeHDRVSLoader,
    FakeVSLoader,
    clip_state,
    create_config,
    create_video_files,
)
from .phase_task_helpers import _render_artifacts


def _workspace(tmp_path: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        generated_root=tmp_path / "generated",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )


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
        workspace=_workspace(tmp_path),
        config=ConfigSchema(),
        input_videos=[tmp_path / "reference.mkv"],
        analysis_selection_domain="test-selection-domain",
        clips=[clip_state(tmp_path / "reference.mkv", label="Reference")],
        artifacts=RunArtifacts(
            post_upload_actions=(shortcut,),
            warnings=["report: warned"],
        ),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=["preflight: warned"],
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
    assert result.warnings == ["preflight: warned", "report: warned"]


def test_execute_run_closes_execution_section_without_masking_phase_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prep = PrepState(
        workspace=_workspace(tmp_path),
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
    assert events == ["start", "end"]


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
        workspace=_workspace(tmp_path),
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
                    warning="slow.pics shortcut: could not choose a safe output directory",
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
    assert result.warnings == [
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
    webhook_warning = "slow.pics webhook: delivery failed"
    render = _render_artifacts(
        screenshots_by_label={"Reference": [tmp_path / "screenshots" / "planned.png"]},
        screenshot_dir=tmp_path / "screenshots",
    )
    prep = PrepState(
        workspace=_workspace(tmp_path),
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
        workspace=_workspace(tmp_path),
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
    assert any(warning.startswith("report:") for warning in result.warnings)
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


def test_execute_run_creates_and_discards_http_client_when_missing(
    tmp_path: Path,
) -> None:
    """Given no injected http client, execute_run must not leak the temporary client."""
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv")

    request = RunRequest(root=tmp_path, quiet=True)
    deps = RunDependencies(
        http_client=None,
        vs_loader=FakeVSLoader(),
        ffmpeg_runner=FakeFFmpegRunner(),
    )

    asyncio.run(execute_run(request, deps=deps))

    assert deps.http_client is None


def test_execute_run_emits_reports_after_load_sources_and_after_align(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Post-load and post-align diagnostics are emitted from the coordinator seam."""
    create_config(tmp_path)
    input_dir = tmp_path / "comparison_videos"
    create_video_files(input_dir, "source.mkv", "comp.mkv")

    request = RunRequest(
        root=tmp_path,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
        no_color=True,
    )
    deps = RunDependencies(vs_loader=FakeVSLoader(), ffmpeg_runner=FakeFFmpegRunner())

    fps_calls: list[tuple[str, bool, tuple[str, ...], Path, bool]] = []
    alignment_calls: list[tuple[str, bool, bool, bool, tuple[int, ...], bool]] = []

    def _record_emit(
        *,
        stage: str,
        no_color: bool,
        clips: Any,
        input_dir: Path,
        verbose: bool,
        **_kwargs: Any,
    ) -> None:
        clip_labels = tuple(clip.label for clip in clips)
        fps_calls.append((stage, no_color, clip_labels, input_dir, verbose))

    def _record_alignment_emit(
        *,
        stage: str,
        no_color: bool,
        json_output: bool,
        quiet: bool,
        selected_frames: Any,
        verbose: bool,
        **_kwargs: Any,
    ) -> None:
        alignment_calls.append(
            (
                stage,
                no_color,
                json_output,
                quiet,
                tuple(cast(list[int], selected_frames)),
                verbose,
            )
        )

    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", _record_emit)
    monkeypatch.setattr(coordinator, "emit_frame_alignment_report", _record_alignment_emit)

    asyncio.run(execute_run(request, deps=deps))

    assert fps_calls == [
        ("after_load_sources", True, ("comp", "source"), tmp_path / "comparison_videos", False),
        ("after_align", True, ("comp", "source"), tmp_path / "comparison_videos", False),
    ]
    assert len(alignment_calls) == 1
    assert alignment_calls[0][:4] == ("after_align", True, False, False)
    assert len(alignment_calls[0][4]) == 10
    assert alignment_calls[0][5] is False
    assert all(isinstance(frame, int) for frame in alignment_calls[0][4])


def test_execute_run_emits_final_selection_at_post_align_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The selection summary receives final aligned frames before later phases run."""
    prep = PrepState(
        workspace=_workspace(tmp_path),
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
    breakdown = SelectionBreakdown(user=[101], random=[205])
    events: list[str] = []
    selection_calls: list[dict[str, object]] = []

    async def _execute_prep(_request: RunRequest, _deps: RunDependencies) -> PrepState:
        return prep

    def _build_phase_plan(
        *,
        state: ExecutionState,
        **_kwargs: object,
    ) -> ExecutionPhasePlan:
        async def _align(context: RunContext) -> None:
            events.append("align")
            state.selected_frames[:] = [2, 6]
            context.selection_breakdown = breakdown

        async def _after_align(_context: RunContext) -> None:
            events.append("after_align_phase")

        return ExecutionPhasePlan(
            before_align=[Phase(name="align", execute=_align)],
            after_align=[Phase(name="render", execute=_after_align)],
        )

    def _record_selection(**kwargs: object) -> None:
        events.append("selection_report")
        selection_calls.append(kwargs)

    monkeypatch.setattr(coordinator, "execute_prep", _execute_prep)
    monkeypatch.setattr(coordinator, "build_execution_phase_plan", _build_phase_plan)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda **_kwargs: None)
    monkeypatch.setattr(coordinator, "emit_frame_alignment_report", lambda **_kwargs: None)
    monkeypatch.setattr(coordinator, "emit_final_selection_report", _record_selection)
    monkeypatch.setattr(
        coordinator,
        "emit_execution_section_start",
        lambda *_args, **_kwargs: events.append("execution_start"),
    )
    monkeypatch.setattr(
        coordinator,
        "emit_execution_section_end",
        lambda *_args, **_kwargs: events.append("execution_end"),
    )

    request = RunRequest(
        root=tmp_path,
        verbose=True,
        json_output=False,
        quiet=False,
        no_color=True,
    )
    asyncio.run(
        execute_run(
            request,
            deps=RunDependencies(monotonic_timer=_zero_monotonic_timer),
        )
    )

    assert events == [
        "execution_start",
        "align",
        "selection_report",
        "after_align_phase",
        "execution_end",
    ]
    assert len(selection_calls) == 1
    assert selection_calls[0] == {
        "selected_frames": [2, 6],
        "breakdown": breakdown,
        "verbose": True,
        "json_output": False,
        "quiet": False,
        "no_color": True,
    }


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
use_vspreview = false

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

    async def _capture_execute_phases(_phases: object, context: object, _reporter: object) -> None:
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
    assert config.audio_alignment.use_vspreview is True


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

    async def _unexpected_publish(**_kwargs: object) -> object:
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

        def ensure_core(self) -> object:
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

    assert phases_started is False
