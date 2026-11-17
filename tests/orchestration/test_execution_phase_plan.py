"""Tests for execute_run phase planning and request override contracts."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import httpx
import pytest
from rich.text import Text
from structlog.testing import capture_logs

from frame_compare.analysis.types import (
    SelectionBreakdown,
    SelectionDetail,
)
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.loader import get_default_config
from frame_compare.orchestration import execution
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.coordinator import RunDependencies
from frame_compare.orchestration.execution import (
    build_execution_phase_plan,
    build_phases_after_align,
    build_phases_before_align,
)
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    AnalyzePhaseOutput,
    ExecutionState,
    FramePlanPhaseOutput,
    MetadataPrefetch,
    PrepState,
    PublishPhaseOutput,
    RenderPhaseOutput,
    RunArtifacts,
)
from frame_compare.orchestration.phase_output_application import apply_phase_output
from frame_compare.orchestration.phases import PhaseStatus, execute_phases
from frame_compare.orchestration.selection_domain import PreparedSelectionDomain
from frame_compare.services.errors import AudioAlignmentCleanupError
from frame_compare.utils.post_upload_actions import PostUploadActionResult
from frame_compare.utils.progress import (
    LogProgressReporter,
    PlainProgressReporter,
    RichProgressReporter,
)
from frame_compare.utils.run_warnings import RunWarning
from tests.run_request_support import make_run_request

from .execute_run_helpers import FakeFFmpegRunner, FakeVSLoader, clip_state, execution_context
from .phase_task_helpers import _context, _frame_metrics, _render_artifacts, _workspace


@pytest.mark.anyio
@pytest.mark.parametrize("transport", ["tty", "pipe", "json"])
@pytest.mark.parametrize("configured", [True, False])
async def test_phase_output_distinguishes_disabled_from_runtime_skips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    transport: str,
    configured: bool,
) -> None:
    from rich.console import Console

    config = get_default_config()
    config.audio_alignment.enable = not configured
    config.report.enable = not configured
    config.slowpics.auto_upload = not configured
    config.slowpics.confirm_upload_after_report = not configured
    config.analysis.dark_frame_count = 0
    config.analysis.bright_frame_count = 0
    config.analysis.motion_frame_count = 0
    state = ExecutionState()
    state.artifacts.slowpics_upload_confirmation_status = "declined"
    request = make_run_request(
        config=config, root=tmp_path, skip_analysis=configured, skip_metadata=configured
    )
    ctx = _context(tmp_path)
    ctx.config = config
    reporter: RichProgressReporter | PlainProgressReporter | LogProgressReporter
    if transport == "tty":
        console = Console(stderr=True, force_terminal=True, no_color=True, width=120)
        monkeypatch.setattr("frame_compare.utils.progress.human_console", lambda **_: console)
        reporter = RichProgressReporter()
    elif transport == "pipe":
        reporter = PlainProgressReporter()
    else:
        reporter = LogProgressReporter()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: pytest.fail("this phase test must not call a network service")
        )
    ) as client:
        before = build_phases_before_align(
            request=request,
            config=config,
            monotonic_timer=lambda: 0.0,
            state=state,
            input_videos=[ctx.reference.path],
            workspace=ctx.workspace,
        )
        after = build_phases_after_align(
            request=request,
            config=config,
            monotonic_timer=lambda: 0.0,
            state=state,
            ffmpeg_runner=FakeFFmpegRunner(),
            http_client=client,
            metadata_prefetch=MetadataPrefetch(None, False),
        )
        expected = (
            {"analyze", "align", "metadata", "publish", "report"}
            if configured
            else {
                "analyze",
                "publish",
            }
        )
        phases = [phase for phase in [*before, *after] if phase.name in expected]
        with capture_logs() as logs:
            await execute_phases(phases, ctx, reporter)

    assert {phase.name for phase in phases if phase.status == PhaseStatus.SKIPPED} == expected
    output = capsys.readouterr().err
    if transport == "json":
        assert output == ""
        assert {
            event["phase"]
            for event in logs
            if event.get("event") == "phase_completed" and event.get("status") == "skipped"
        } == expected
    elif configured:
        assert output == ""
    elif transport == "tty":
        output = Text.from_ansi(output).plain
        assert "– Analyze         not required" in output
        assert "– Publish         declined" in output
    else:
        assert output.splitlines() == ["[SKIP] ANALYZE  Not required", "[SKIP] PUBLISH  Declined"]


def test_build_execution_phase_plan_preserves_align_boundary_and_progress_total(
    tmp_path: Path,
) -> None:
    workspace = _workspace(
        tmp_path,
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
    )

    config = get_default_config()
    config.slowpics.confirm_upload_after_report = False
    config.analysis = config.analysis.model_copy(
        update={"random_frame_count": 0, "dark_frame_count": 1}
    )
    prep = PrepState(
        workspace=workspace,
        config=config,
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
        load_sources_start=0.0,
        selection_domain=PreparedSelectionDomain(
            token="test-selection-domain",
            selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
            analysis_clip=None,
        ),
    )

    plan = build_execution_phase_plan(
        request=make_run_request(config=get_default_config(), root=tmp_path),
        deps=RunDependencies(ffmpeg_runner=FakeFFmpegRunner()),
        prep=prep,
        state=ExecutionState(artifacts=prep.artifacts),
    )

    assert [phase.name for phase in plan.before_align] == ["frame_plan", "analyze", "align"]
    assert [phase.name for phase in plan.after_align] == [
        "render",
        "metadata",
        "publish",
        "report",
        "post_report_cleanup",
    ]

    align_phase = next(phase for phase in plan.before_align if phase.name == "align")
    assert align_phase.progress_total == 3
    assert align_phase.warn_only is True
    assert AudioAlignmentCleanupError in align_phase.fatal_exceptions

    config.audio_alignment.force_interactive = True
    forced_plan = build_execution_phase_plan(
        request=make_run_request(config=get_default_config(), root=tmp_path),
        deps=RunDependencies(ffmpeg_runner=FakeFFmpegRunner()),
        prep=prep,
        state=ExecutionState(artifacts=prep.artifacts),
    )
    forced_align_phase = next(phase for phase in forced_plan.before_align if phase.name == "align")
    assert forced_align_phase.warn_only is False


def test_build_phases_before_align_skips_analyze_when_request_skips_analysis(
    tmp_path: Path,
) -> None:
    workspace = _workspace(
        tmp_path,
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
    )
    state = ExecutionState(artifacts=RunArtifacts())

    phases = build_phases_before_align(
        request=make_run_request(config=get_default_config(), root=tmp_path, skip_analysis=True),
        config=get_default_config(),
        monotonic_timer=lambda: 0.0,
        state=state,
        input_videos=[tmp_path / "ref.mkv"],
        workspace=workspace,
        vs_loader=FakeVSLoader(),
    )

    analyze_phase = next(phase for phase in phases if phase.name == "analyze")
    config = get_default_config()
    config.analysis = config.analysis.model_copy(
        update={"random_frame_count": 0, "dark_frame_count": 1}
    )

    assert analyze_phase.skip_condition is not None
    assert analyze_phase.skip_condition(config) is True


def test_apply_phase_output_records_frame_plan_selection_labels(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = execution_context(
        config=get_default_config(),
        workspace=workspace,
        reference=reference,
        comparisons=[],
    )
    state = ExecutionState(artifacts=RunArtifacts())
    breakdown = SelectionBreakdown(user=[0], random=[66])
    details = {
        0: SelectionDetail(frame_index=0, label="User", source="frame_plan"),
        66: SelectionDetail(frame_index=66, label="Random", source="frame_plan"),
    }

    apply_phase_output(
        ctx=ctx,
        state=state,
        output=FramePlanPhaseOutput(
            selected_frames=[0, 66],
            selection_breakdown=breakdown,
            selection_details_by_source_frame=details,
        ),
    )

    assert list(ctx.selection.frames) == [0, 66]
    assert ctx.selection.breakdown == breakdown
    assert ctx.selection.details_by_source_frame == details


def test_analyze_retry_replaces_superseded_frame_plan_warnings(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = execution_context(
        config=get_default_config(),
        workspace=workspace,
        reference=reference,
        comparisons=[],
    )
    state = ExecutionState(
        artifacts=RunArtifacts(warnings=[RunWarning("sources", "warning", "preflight warning")])
    )
    stale_warning = RunWarning(
        "frame selection",
        "warning",
        "frame selection: dropped user frame(s) outside trims/windowing: 4",
    )

    apply_phase_output(
        ctx=ctx,
        state=state,
        output=FramePlanPhaseOutput(selected_frames=[20], warnings=[stale_warning]),
    )
    apply_phase_output(
        ctx=ctx,
        state=state,
        output=AnalyzePhaseOutput(
            selected_frames=[4, 20],
            selection_breakdown=SelectionBreakdown(user=[4], random=[20]),
            metrics_cache_hit=False,
            analysis_metrics=_frame_metrics(
                luminance=[0.5],
                motion=[0.0],
                frame_count=1,
                fps=Fraction(24, 1),
                config_fingerprint="test",
                clips=[],
            ),
            warnings=[RunWarning("analysis", "warning", "accepted override warning")],
            replaces_frame_plan_selection=True,
        ),
    )

    assert list(ctx.selection.frames) == [4, 20]
    assert [warning.text for warning in state.warnings] == [
        "preflight warning",
        "accepted override warning",
    ]
    assert state.frame_plan_warnings == []


def test_apply_phase_output_retains_publish_post_upload_actions(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = execution_context(
        config=get_default_config(),
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
        warning=RunWarning("sources", "warning", "webhook: delivery failed"),
    )
    collection_warning = RunWarning(
        "slow.pics", "warning", "slow.pics: collection metadata differed"
    )

    apply_phase_output(
        ctx=ctx,
        state=state,
        output=PublishPhaseOutput(
            slowpics_url="https://slow.pics/c/example",
            uploaded_file_paths=(uploaded,),
            post_upload_actions=(shortcut, webhook),
            warnings=(collection_warning,),
        ),
    )

    assert state.artifacts.slowpics_url == "https://slow.pics/c/example"
    assert state.artifacts.uploaded_slowpics_file_paths == (uploaded,)
    assert state.artifacts.post_upload_actions == (shortcut, webhook)
    assert state.warnings == [collection_warning, webhook.warning]


def test_apply_phase_output_extends_warnings_from_render_output(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = execution_context(
        config=get_default_config(),
        workspace=workspace,
        reference=reference,
        comparisons=[],
    )
    state = ExecutionState(
        artifacts=RunArtifacts(warnings=[RunWarning("sources", "warning", "pre-existing warning")])
    )
    render = _render_artifacts(
        screenshots_by_label={"Reference": [tmp_path / "reference.png"]},
        screenshot_dir=tmp_path / "screenshots",
    )
    render.warnings.append(
        RunWarning(
            "sources", "warning", "Screenshot geometry alignment skipped: using native geometry."
        )
    )

    apply_phase_output(ctx=ctx, state=state, output=RenderPhaseOutput(render=render))

    assert state.artifacts.render is render
    assert [warning.text for warning in state.warnings] == [
        "pre-existing warning",
        "Screenshot geometry alignment skipped: using native geometry.",
    ]


def test_apply_phase_output_extends_warnings_from_align_output(tmp_path: Path) -> None:
    workspace = _workspace(
        tmp_path,
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    comparison = clip_state(tmp_path / "encode_b.mkv", label="Encode B")
    ctx = execution_context(
        config=get_default_config(),
        workspace=workspace,
        reference=reference,
        comparisons=[comparison],
    )
    state = ExecutionState(
        artifacts=RunArtifacts(warnings=[RunWarning("sources", "warning", "pre-existing warning")])
    )

    apply_phase_output(
        ctx=ctx,
        state=state,
        output=AlignPhaseOutput(
            reference=reference,
            comparisons=[comparison],
            selected_frames=[0, 2, 50],
            warnings=[
                RunWarning(
                    "alignment",
                    "warning",
                    "align: encode_b low confidence; left unapplied and untrimmed",
                )
            ],
        ),
    )

    assert ctx.reference is reference
    assert ctx.comparisons == [comparison]
    assert list(ctx.selection.frames) == [0, 2, 50]
    assert [warning.text for warning in state.warnings] == [
        "pre-existing warning",
        "align: encode_b low confidence; left unapplied and untrimmed",
    ]


def test_apply_phase_output_rejects_unknown_output_type(tmp_path: Path) -> None:
    import pytest

    class UnknownPhaseOutput:
        pass

    workspace = _workspace(
        tmp_path,
        input_subdir="comparison_videos",
        run_subdir=None,
        screenshots_subdir="screenshots",
    )
    reference = clip_state(tmp_path / "ref.mkv", label="Reference")
    ctx = execution_context(
        config=get_default_config(),
        workspace=workspace,
        reference=reference,
        comparisons=[],
    )
    state = ExecutionState(artifacts=RunArtifacts())

    with pytest.raises(TypeError, match="UnknownPhaseOutput"):
        apply_phase_output(ctx=ctx, state=state, output=UnknownPhaseOutput())  # type: ignore[arg-type]  # Exercise rejection of an unsupported carrier.


@pytest.mark.anyio
async def test_align_phase_records_review_split_duration_text(tmp_path: Path) -> None:
    output = AlignPhaseOutput(
        reference=clip_state(tmp_path / "ref.mkv", label="Reference"),
        comparisons=[clip_state(tmp_path / "comp.mkv", label="Encode")],
        selected_frames=[1],
        success_summary="1 pair confirmed in VSView",
        review_seconds=42.5,
    )

    async def executor(_ctx: RunContext) -> AlignPhaseOutput:
        return output

    state = ExecutionState(artifacts=RunArtifacts())
    timings: dict[str, float] = {}
    clock = iter([100.0, 160.0])
    phase = execution._create_timed_phase(
        "align",
        "align",
        None,
        executor,
        state,
        lambda: next(clock),
        timings,
        [],
    )
    await phase.execute(_context(tmp_path))

    assert timings["align"] == pytest.approx(60.0)
    assert phase.duration_text == "17.5 s + 42.5 s review"
    assert phase.success_summary == "1 pair confirmed in VSView"
    assert state.vsview_review_seconds == pytest.approx(42.5)
