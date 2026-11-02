"""Selection replacements propagate through a plan built before selection exists."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from time import monotonic

import pytest

from frame_compare.analysis.types import SelectionBreakdown, SelectionDetail
from frame_compare.analysis.window import SelectionWindow
from frame_compare.orchestration import execution
from frame_compare.orchestration.context import RunContext, SelectionSnapshot
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    AnalyzePhaseOutput,
    ExecutionState,
    FramePlanPhaseOutput,
    MetadataPrefetch,
    PublishPhaseOutput,
    RunArtifacts,
)
from frame_compare.orchestration.selection_domain import (
    build_prepared_selection_domain,
    metric_request_for_domain,
)
from frame_compare.orchestration.selection_rows import selection_rows
from frame_compare.render.types import OverlayConfig
from frame_compare.services.report.payload import ReportData
from frame_compare.utils.media_facts import RenderedFrameFacts
from tests.orchestration.execute_run_helpers import FakeFFmpegRunner
from tests.orchestration.phase_task_helpers import _context, _frame_metrics
from tests.run_request_support import make_run_request


async def test_late_snapshot_replacements_reach_align_render_publish_and_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context(tmp_path)
    ctx.reference = ctx.reference.with_trim(trim_start_frames=10, trim_end_frame_inclusive=99)
    ctx.workspace = replace(
        ctx.workspace, run_dir=tmp_path / "run", screenshots_dir=tmp_path / "run/screenshots"
    )
    ctx.config.report.enable = True
    ctx.config.slowpics.auto_upload = True
    metrics = _frame_metrics(
        luminance=[0.1] * 10, motion=[0.0] * 10, frame_count=10, fps=Fraction(24)
    )
    ctx.selection = SelectionSnapshot(analysis_metrics=metrics)
    observed: dict[str, object] = {}
    labels: list[str | None] = []

    def frame_plan(_ctx: RunContext, **_kwargs) -> FramePlanPhaseOutput:
        return FramePlanPhaseOutput(
            selected_frames=[1], selection_breakdown=SelectionBreakdown(user=[11])
        )

    def analyze(current: RunContext, **_kwargs) -> AnalyzePhaseOutput:
        assert current.selection.frames == (2,)
        return AnalyzePhaseOutput(
            selected_frames=[3],
            selection_breakdown=SelectionBreakdown(quantile_dark=[13]),
            metrics_cache_hit=False,
            analysis_metrics=metrics,
        )

    async def align(
        current: RunContext, *, selected_frames: list[int], **_kwargs
    ) -> AlignPhaseOutput:
        observed["align"] = selected_frames
        rows = selection_rows(current, frames=selected_frames)
        assert [(row.reference_source_frame, row.label) for row in rows] == [(14, "After analysis")]
        return AlignPhaseOutput(
            reference=current.reference.with_trim(
                trim_start_frames=20, trim_end_frame_inclusive=99
            ),
            comparisons=current.comparisons,
            selected_frames=[5],
            selection_breakdown=SelectionBreakdown(motion=[25]),
            selection_details_by_source_frame={
                25: SelectionDetail(
                    frame_index=25, label="Aligned latest", source="test", notes="motion"
                )
            },
        )

    async def publish(
        _ctx: RunContext, *, selected_frames: list[int], **_kwargs
    ) -> PublishPhaseOutput:
        observed["publish"] = selected_frames
        return PublishPhaseOutput(slowpics_url="https://slow.pics/c/latest")

    def generate_report(data: ReportData, _config, *, output_path: Path) -> Path:
        observed["report"] = data.frames
        observed["details"] = [(detail.label, detail.category) for detail in data.frame_details]
        return output_path

    def overlay(_path: Path, config: OverlayConfig, _facts: RenderedFrameFacts) -> None:
        labels.append(config.selection_label)

    monkeypatch.setattr(execution, "select_initial_frame_plan", frame_plan)
    monkeypatch.setattr(execution, "run_analyze_phase", analyze)
    monkeypatch.setattr(execution, "run_align_phase", align)
    monkeypatch.setattr(execution, "run_publish_phase", publish)
    monkeypatch.setattr(
        "frame_compare.orchestration.phase_post_render.generate_report", generate_report
    )
    monkeypatch.setattr("frame_compare.render.encoders.apply_overlay_to_file", overlay)
    state = ExecutionState(artifacts=RunArtifacts())
    request = make_run_request(root=tmp_path, config=ctx.config)
    runner = FakeFFmpegRunner()
    before = execution.build_phases_before_align(
        request=request,
        config=ctx.config,
        monotonic_timer=monotonic,
        state=state,
        input_videos=[ctx.reference.path],
        workspace=ctx.workspace,
    )
    after = execution.build_phases_after_align(
        request=request,
        config=ctx.config,
        monotonic_timer=monotonic,
        ffmpeg_runner=runner,
        http_client=None,
        state=state,
        metadata_prefetch=MetadataPrefetch(None, False),
    )
    assert ctx.selection.frames == ()
    await before[0].execute(ctx)
    assert ctx.selection.analysis_metrics is None
    ctx.selection = replace(ctx.selection, frames=(2,))
    await before[1].execute(ctx)
    assert ctx.selection.analysis_metrics == metrics
    ctx.selection = replace(
        ctx.selection,
        frames=(4,),
        details_by_source_frame={
            14: SelectionDetail(
                frame_index=14, label="After analysis", source="test", notes="motion"
            )
        },
    )
    await before[2].execute(ctx)
    assert ctx.reference.trim.trim_start_frames == 20
    for name in ["render", "publish", "report"]:
        phase = next(phase for phase in after if phase.name == name)
        await phase.execute(ctx)
    assert observed == {
        "align": [4],
        "publish": [5],
        "report": [5],
        "details": [("Aligned latest", "motion")],
    }
    assert labels == ["Aligned latest"]
    assert [call[1] for call in runner.calls] == [25]
    assert ctx.selection.frames == (5,)


def test_domain_build_keeps_metric_range_validation_at_use_boundary(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    domain = build_prepared_selection_domain(
        clips=[ctx.reference],
        config=ctx.config,
        analysis_clip=ctx.reference,
        selection_window=SelectionWindow(200, 201),
        override=None,
    )
    assert domain.selection_window == SelectionWindow(200, 201)
    with pytest.raises(ValueError, match="exceeds the source frame count"):
        metric_request_for_domain(domain, ctx.config)
