"""Behavior of the fixed selection and output steps."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from frame_compare.analysis.types import (
    SelectionBreakdown,
    SelectionDetail,
)
from frame_compare.config.loader import get_default_config
from frame_compare.orchestration import execution
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.coordinator import RunDependencies
from frame_compare.orchestration.execution import RunSteps
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    AnalyzePhaseOutput,
    ExecutionState,
    FramePlanPhaseOutput,
    MetadataPhaseOutput,
    PostReportCleanupPhaseOutput,
    PublishPhaseOutput,
    RenderPhaseOutput,
    ReportPhaseOutput,
    RunArtifacts,
)
from frame_compare.services.errors import AudioAlignmentCleanupError
from frame_compare.utils.post_upload_actions import PostUploadActionResult
from frame_compare.utils.progress import NullProgressReporter
from frame_compare.utils.progress_protocol import ProgressPhaseStatus
from frame_compare.utils.run_warnings import RunWarning
from tests.run_request_support import make_run_request

from .execute_run_helpers import (
    clip_state,
    execution_context,
)
from .phase_task_helpers import _context, _frame_metrics, _render_artifacts, _workspace
from .test_run_steps import prep_for_context


async def test_frame_plan_step_applies_selection_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    monkeypatch.setattr(
        execution,
        "select_initial_frame_plan",
        lambda *a, **kw: FramePlanPhaseOutput(
            selected_frames=[0, 66],
            selection_breakdown=breakdown,
            selection_details_by_source_frame=details,
        ),
    )

    ctx.config.audio_alignment.enable = False
    await _run_selection(ctx, state, skip_analysis=True)
    assert list(ctx.selection.frames) == [0, 66]
    assert ctx.selection.breakdown == breakdown
    assert ctx.selection.details_by_source_frame == details


async def test_analyze_retry_replaces_superseded_frame_plan_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    monkeypatch.setattr(
        execution,
        "select_initial_frame_plan",
        lambda *a, **kw: FramePlanPhaseOutput(selected_frames=[20], warnings=[stale_warning]),
    )
    monkeypatch.setattr(
        execution,
        "run_analyze_phase",
        lambda *a, **kw: AnalyzePhaseOutput(
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

    ctx.config.analysis.dark_frame_count = 1
    ctx.config.audio_alignment.enable = False
    await _run_selection(ctx, state)
    assert state.artifacts.metrics_cache_hit is False
    assert state.artifacts.metrics_cache_status == "miss"
    assert ctx.selection.analysis_metrics is not None
    assert list(ctx.selection.frames) == [4, 20]
    assert [warning.text for warning in state.warnings] == [
        "preflight warning",
        "accepted override warning",
    ]
    assert state.frame_plan_warnings == []


async def test_publish_step_keeps_post_upload_actions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    monkeypatch.setattr(
        execution,
        "run_publish_phase",
        lambda *a, **kw: PublishPhaseOutput(
            slowpics_url="https://slow.pics/c/example",
            uploaded_file_paths=(uploaded,),
            post_upload_actions=(shortcut, webhook),
            warnings=(collection_warning,),
        ),
    )

    ctx.config.slowpics.auto_upload = True
    ctx.config.slowpics.confirm_upload_after_report = False
    ctx.config.report.enable = False
    monkeypatch.setattr(
        execution,
        "run_render_phase",
        lambda *a, **kw: RenderPhaseOutput(
            _render_artifacts(screenshots_by_label={}, screenshot_dir=None)
        ),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(_reject_request)) as client:
        await _run_output(ctx, state, deps=RunDependencies(http_client=client))
    assert state.artifacts.slowpics_url == "https://slow.pics/c/example"
    assert state.artifacts.uploaded_slowpics_file_paths == (uploaded,)
    assert state.artifacts.post_upload_actions == (shortcut, webhook)
    assert state.warnings == [collection_warning, webhook.warning]


async def test_render_step_extends_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    ctx.config.slowpics.auto_upload = False
    ctx.config.report.enable = False
    monkeypatch.setattr(execution, "run_render_phase", lambda *a, **kw: RenderPhaseOutput(render))
    await _run_output(ctx, state, deps=RunDependencies())

    assert state.artifacts.render is render
    assert [warning.text for warning in state.warnings] == [
        "pre-existing warning",
        "Screenshot geometry alignment skipped: using native geometry.",
    ]


async def test_align_step_extends_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(
        execution,
        "run_align_phase",
        lambda *a, **kw: AlignPhaseOutput(
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

    ctx.config.audio_alignment.enable = True
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    await _run_selection(ctx, state, skip_analysis=True)
    assert ctx.reference is reference
    assert ctx.comparisons == [comparison]
    assert list(ctx.selection.frames) == [0, 2, 50]
    assert [warning.text for warning in state.warnings] == [
        "pre-existing warning",
        "align: encode_b low confidence; left unapplied and untrimmed",
    ]


def _reject_request(_request: httpx.Request) -> httpx.Response:
    raise AssertionError("unexpected network request")


async def _run_selection(
    ctx: RunContext, state: ExecutionState, *, skip_analysis: bool = False
) -> None:
    await execution.run_selection_steps(
        ctx,
        RunSteps(
            reporter=ctx.reporter or NullProgressReporter(),
            state=state,
            monotonic_timer=lambda: 0.0,
        ),
        request=make_run_request(
            root=ctx.workspace.root, config=ctx.config, skip_analysis=skip_analysis
        ),
        prep=prep_for_context(ctx, state),
        state=state,
        deps=RunDependencies(),
    )


async def _run_output(ctx: RunContext, state: ExecutionState, *, deps: RunDependencies) -> None:
    await execution.run_output_steps(
        ctx,
        RunSteps(
            reporter=ctx.reporter or NullProgressReporter(),
            state=state,
            monotonic_timer=lambda: 0.0,
        ),
        request=make_run_request(root=ctx.workspace.root, config=ctx.config, skip_metadata=True),
        prep=prep_for_context(ctx, state),
        state=state,
        deps=deps,
    )


async def test_steps_preserve_align_boundary_and_progress_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(
        tmp_path,
        comparisons=[
            clip_state(tmp_path / "c1.mkv", label="Encode 1"),
            clip_state(tmp_path / "c2.mkv", label="Encode 2"),
        ],
    )
    ctx.config.analysis.dark_frame_count = 1
    ctx.config.slowpics.auto_upload = True
    ctx.config.slowpics.confirm_upload_after_report = False
    ctx.config.report.enable = True
    state = ExecutionState()
    request = make_run_request(root=tmp_path, config=ctx.config)
    prep = prep_for_context(ctx, state)
    starts = Mock(wraps=execution.start_phase_progress)
    monkeypatch.setattr(execution, "start_phase_progress", starts)
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(
        execution,
        "run_analyze_phase",
        lambda *a, **kw: AnalyzePhaseOutput(
            [1],
            SelectionBreakdown(),
            False,
            _frame_metrics(luminance=[0.5], motion=[0.0], frame_count=1, fps=Fraction(24)),
        ),
    )
    monkeypatch.setattr(
        execution,
        "run_align_phase",
        lambda *a, **kw: AlignPhaseOutput(ctx.reference, ctx.comparisons, [1]),
    )
    monkeypatch.setattr(
        execution,
        "run_render_phase",
        lambda *a, **kw: RenderPhaseOutput(
            _render_artifacts(screenshots_by_label={}, screenshot_dir=None)
        ),
    )
    monkeypatch.setattr(execution, "run_metadata_phase", lambda *a, **kw: MetadataPhaseOutput(None))
    monkeypatch.setattr(execution, "run_publish_phase", lambda *a, **kw: PublishPhaseOutput(None))
    monkeypatch.setattr(execution, "run_report_phase", lambda *a, **kw: ReportPhaseOutput(None))
    monkeypatch.setattr(
        execution, "run_post_report_cleanup_phase", lambda *a, **kw: PostReportCleanupPhaseOutput()
    )
    steps = RunSteps(
        reporter=ctx.reporter or NullProgressReporter(), state=state, monotonic_timer=lambda: 0.0
    )

    assert execution.progress_step_names(request, ctx.config) == [
        "Analyze",
        "Align",
        "Render",
        "Publish",
        "Report",
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(_reject_request)) as client:
        deps = RunDependencies(http_client=client)
        await execution.run_selection_steps(
            ctx, steps, request=request, prep=prep, state=state, deps=deps
        )
        assert [call.kwargs["name"] for call in starts.call_args_list] == [
            "frame_plan",
            "analyze",
            "align",
        ]
        assert starts.call_args.kwargs["total"] == 3
        starts.reset_mock()
        await execution.run_output_steps(
            ctx, steps, request=request, prep=prep, state=state, deps=deps
        )
    assert [call.kwargs["name"] for call in starts.call_args_list] == [
        "render",
        "metadata",
        "publish",
        "report",
        "post_report_cleanup",
    ]


async def test_analyze_step_skips_when_request_disables_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    ctx.config.analysis.dark_frame_count = 1
    ctx.config.audio_alignment.enable = False
    reporter = Mock(spec=NullProgressReporter)
    ctx.reporter = reporter
    state = ExecutionState()
    analyze = Mock(side_effect=AssertionError("disabled analysis ran"))
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(execution, "run_analyze_phase", analyze)

    await _run_selection(ctx, state, skip_analysis=True)

    analyze.assert_not_called()
    reporter.start_phase.assert_any_call(
        "ANALYZE  Disabled", total=execution.ANALYZE_PROGRESS_TOTAL
    )
    reporter.complete_phase.assert_any_call(ProgressPhaseStatus.SKIPPED, summary="disabled")
    assert "analyze" not in state.phase_timings
    request = make_run_request(root=tmp_path, config=ctx.config, skip_analysis=True)
    assert "Analyze" not in execution.progress_step_names(request, ctx.config)


@pytest.mark.parametrize("force_interactive", [False, True])
async def test_align_warns_on_ordinary_error_unless_prepared_config_forces_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, force_interactive: bool
) -> None:
    ctx = _context(tmp_path)
    ctx.config.audio_alignment.force_interactive = force_interactive
    state = ExecutionState()
    prep = prep_for_context(ctx, state)
    # Step policy must use the prepared config, regardless of the effective config.
    ctx.config = ctx.config.model_copy(deep=True)
    ctx.config.audio_alignment.force_interactive = not force_interactive
    reporter = Mock(spec=NullProgressReporter)
    render = Mock(
        return_value=RenderPhaseOutput(
            _render_artifacts(screenshots_by_label={}, screenshot_dir=None)
        )
    )
    monkeypatch.setattr(execution, "run_render_phase", render)
    ctx.config.report.enable = False
    ctx.config.slowpics.auto_upload = False
    error = RuntimeError("align failed")
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(execution, "run_align_phase", Mock(side_effect=error))

    async def run() -> None:
        await execution.run_selection_steps(
            ctx,
            RunSteps(reporter=reporter, state=state, monotonic_timer=lambda: 0.0),
            request=make_run_request(root=tmp_path, config=ctx.config, skip_analysis=True),
            prep=prep,
            state=state,
            deps=RunDependencies(),
        )
        await _run_output(ctx, state, deps=RunDependencies())

    if force_interactive:
        with pytest.raises(RuntimeError) as caught:
            await run()
        assert caught.value is error
        assert state.warnings == []
        render.assert_not_called()
        status = ProgressPhaseStatus.FAILED
    else:
        await run()
        assert state.warnings == [RunWarning("alignment", "warning", "align: align failed")]
        status = ProgressPhaseStatus.WARNED
        render.assert_called_once()
    reporter.complete_phase.assert_called_with(status, summary=None, duration_text=None)


async def test_align_cleanup_error_is_fatal_and_still_records_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    state = ExecutionState()
    error = AudioAlignmentCleanupError("could not release alignment resources")
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(execution, "run_align_phase", Mock(side_effect=error))

    with pytest.raises(AudioAlignmentCleanupError) as caught:
        await _run_selection(ctx, state, skip_analysis=True)
    assert caught.value is error
    assert state.warnings == [RunWarning("alignment", "warning", f"align: {error}")]


async def test_align_step_records_review_split_duration_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    state = ExecutionState()
    reporter = Mock(spec=NullProgressReporter)
    clock = iter([0.0, 0.0, 100.0, 160.0])
    output = AlignPhaseOutput(
        reference=ctx.reference,
        comparisons=ctx.comparisons,
        selected_frames=[1],
        success_summary="1 pair confirmed in VSView",
        review_seconds=42.5,
    )
    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(execution, "run_align_phase", lambda *a, **kw: output)
    await execution.run_selection_steps(
        ctx,
        RunSteps(reporter=reporter, state=state, monotonic_timer=lambda: next(clock)),
        request=make_run_request(root=tmp_path, config=ctx.config, skip_analysis=True),
        prep=prep_for_context(ctx, state),
        state=state,
        deps=RunDependencies(),
    )

    assert state.phase_timings["align"] == pytest.approx(60.0)
    reporter.complete_phase.assert_called_with(
        ProgressPhaseStatus.COMPLETED,
        summary="1 pair confirmed in VSView",
        duration_text="17s + 42s review",
    )
    assert state.vsview_review_seconds == pytest.approx(42.5)
