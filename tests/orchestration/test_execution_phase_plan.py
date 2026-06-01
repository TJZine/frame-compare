"""Tests for execute_run phase planning and request override contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from frame_compare.config.schema import ConfigSchema, OverlayMode, TonemapPreset
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest
from frame_compare.orchestration.execution import _apply_phase_output, build_execution_phase_plan
from frame_compare.orchestration.types import (
    AlignPhaseOutput,
    ExecutionState,
    MetadataPrefetch,
    PostUploadActionResult,
    PrepState,
    PublishPhaseOutput,
    RenderArtifacts,
    RenderPhaseOutput,
    RunArtifacts,
)
from frame_compare.utils.types import WorkspacePaths

from .execute_run_helpers import FakeFFmpegRunner, clip_state


def test_build_execution_phase_plan_preserves_align_boundary_and_progress_total(
    tmp_path: Path,
) -> None:
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )

    prep = PrepState(
        workspace=workspace,
        config=ConfigSchema(),
        input_videos=[
            tmp_path / "ref.mkv",
            tmp_path / "comp_a.mkv",
            tmp_path / "comp_b.mkv",
        ],
        clips=[
            clip_state(tmp_path / "ref.mkv", label="Reference"),
            clip_state(tmp_path / "comp_a.mkv", label="Encode 1"),
            clip_state(tmp_path / "comp_b.mkv", label="Encode 2"),
        ],
        artifacts=RunArtifacts(),
        metadata_prefetch=MetadataPrefetch(None, False),
        preflight_warnings=[],
        preflight_duration=0.0,
        load_sources_start=datetime.now(),
    )

    plan = build_execution_phase_plan(
        request=RunRequest(root=tmp_path),
        deps=RunDependencies(ffmpeg_runner=FakeFFmpegRunner()),
        prep=prep,
        state=ExecutionState(artifacts=prep.artifacts),
    )

    assert [phase.name for phase in plan.before_align] == ["frame_plan", "analyze", "align"]
    assert [phase.name for phase in plan.after_align] == [
        "render",
        "metadata",
        "dovi",
        "publish",
        "report",
        "post_report_cleanup",
    ]

    align_phase = next(phase for phase in plan.before_align if phase.name == "align")
    assert align_phase.progress_total == 1


def test_run_request_cli_config_overrides_capture_runtime_override_contract(tmp_path: Path) -> None:
    request = RunRequest(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        tm_preset=TonemapPreset.FILMIC,
        tm_target_nits=203,
        overlay_mode=OverlayMode.DIAGNOSTIC,
        frame_count=12,
        seed=123,
        no_upload=True,
        force_interactive_alignment=True,
    )

    overrides = request.cli_config_overrides()

    assert overrides.input_dir == tmp_path / "comparison_videos"
    assert overrides.tm_preset == TonemapPreset.FILMIC
    assert overrides.tm_target_nits == 203
    assert overrides.tm_curve is None
    assert overrides.frame_count == 12
    assert overrides.seed == 123
    assert overrides.overlay_mode == OverlayMode.DIAGNOSTIC
    assert overrides.no_upload is True
    assert overrides.force_interactive_alignment is True


def test_apply_phase_output_handles_report_output_explicitly(tmp_path: Path) -> None:
    from frame_compare.orchestration.types import ReportPhaseOutput

    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = RunContext(
        config=ConfigSchema(),
        workspace=workspace,
        reference=reference,
        comparisons=[],
    )
    state = ExecutionState(artifacts=RunArtifacts())
    report_path = tmp_path / "report.html"

    _apply_phase_output(
        ctx=ctx,
        state=state,
        output=ReportPhaseOutput(report_path=report_path, report_succeeded=True),
    )

    assert state.artifacts.report_path == report_path
    assert state.artifacts.report_succeeded is True


def test_apply_phase_output_retains_publish_post_upload_actions(tmp_path: Path) -> None:
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = RunContext(
        config=ConfigSchema(),
        workspace=workspace,
        reference=reference,
        comparisons=[],
    )
    state = ExecutionState(artifacts=RunArtifacts())
    uploaded = tmp_path / "screenshots" / "reference.png"
    shortcut = PostUploadActionResult(
        kind="shortcut",
        success=True,
        path=tmp_path / "Slowpics.url",
        message="Shortcut written.",
    )
    webhook = PostUploadActionResult(
        kind="webhook",
        success=False,
        warning="webhook: delivery failed",
    )

    _apply_phase_output(
        ctx=ctx,
        state=state,
        output=PublishPhaseOutput(
            slowpics_url="https://slow.pics/c/example",
            uploaded_file_paths=(uploaded,),
            post_upload_actions=(shortcut, webhook),
        ),
    )

    assert state.artifacts.slowpics_url == "https://slow.pics/c/example"
    assert state.artifacts.uploaded_slowpics_file_paths == (uploaded,)
    assert state.artifacts.post_upload_actions == (shortcut, webhook)


def test_apply_phase_output_extends_warnings_from_render_output(tmp_path: Path) -> None:
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = RunContext(
        config=ConfigSchema(),
        workspace=workspace,
        reference=reference,
        comparisons=[],
    )
    state = ExecutionState(artifacts=RunArtifacts(warnings=["pre-existing warning"]))
    render = RenderArtifacts(
        screenshots_by_label={"Reference": [tmp_path / "reference.png"]},
        screenshot_dir=tmp_path / "screenshots",
        warnings=["Screenshot geometry alignment skipped: using native geometry."],
    )

    _apply_phase_output(ctx=ctx, state=state, output=RenderPhaseOutput(render=render))

    assert state.artifacts.render is render
    assert state.warnings == [
        "pre-existing warning",
        "Screenshot geometry alignment skipped: using native geometry.",
    ]


def test_apply_phase_output_extends_warnings_from_align_output(tmp_path: Path) -> None:
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    comparison = clip_state(tmp_path / "encode_b.mkv", label="Encode B")
    ctx = RunContext(
        config=ConfigSchema(),
        workspace=workspace,
        reference=reference,
        comparisons=[comparison],
    )
    state = ExecutionState(artifacts=RunArtifacts(warnings=["pre-existing warning"]))

    _apply_phase_output(
        ctx=ctx,
        state=state,
        output=AlignPhaseOutput(
            reference=reference,
            comparisons=[comparison],
            selected_frames=[0, 2, 50],
            warnings=["align: encode_b low confidence; left unapplied and untrimmed"],
        ),
    )

    assert ctx.reference is reference
    assert ctx.comparisons == [comparison]
    assert state.selected_frames == [0, 2, 50]
    assert state.warnings == [
        "pre-existing warning",
        "align: encode_b low confidence; left unapplied and untrimmed",
    ]


def test_apply_phase_output_rejects_unknown_output_type(tmp_path: Path) -> None:
    import pytest

    class UnknownPhaseOutput:
        pass

    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "comparison_videos",
        run_dir=None,
        screenshots_dir=tmp_path / "screenshots",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = RunContext(
        config=ConfigSchema(),
        workspace=workspace,
        reference=reference,
        comparisons=[],
    )
    state = ExecutionState(artifacts=RunArtifacts())

    with pytest.raises(TypeError, match="UnknownPhaseOutput"):
        _apply_phase_output(ctx=ctx, state=state, output=UnknownPhaseOutput())  # type: ignore[arg-type]
