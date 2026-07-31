"""Apply orchestration phase outputs to mutable run state."""

from __future__ import annotations

from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    AnalyzePhaseOutput,
    ConfirmSlowpicsUploadPhaseOutput,
    ExecutionState,
    FramePlanPhaseOutput,
    MetadataPhaseOutput,
    PhaseOutput,
    PostReportCleanupPhaseOutput,
    PublishPhaseOutput,
    RenderPhaseOutput,
    ReportPhaseOutput,
)

__all__ = ["apply_phase_output"]


def apply_phase_output(*, ctx: RunContext, state: ExecutionState, output: PhaseOutput) -> None:
    match output:
        case FramePlanPhaseOutput() as phase_output:
            state.selected_frames[:] = phase_output.selected_frames
            ctx.selection_breakdown = phase_output.selection_breakdown
            ctx.selection_details_by_source_frame = phase_output.selection_details_by_source_frame
            state.warnings.extend(phase_output.warnings)
        case AnalyzePhaseOutput() as phase_output:
            state.selected_frames[:] = phase_output.selected_frames
            state.artifacts.metrics_cache_hit = phase_output.metrics_cache_hit
            state.artifacts.metrics_cache_status = (
                "hit" if phase_output.metrics_cache_hit else "miss"
            )
            ctx.selection_breakdown = phase_output.selection_breakdown
            ctx.selection_details_by_source_frame = phase_output.selection_details_by_source_frame
            ctx.analysis_metrics = phase_output.analysis_metrics
        case AlignPhaseOutput() as phase_output:
            ctx.reference = phase_output.reference
            ctx.comparisons = phase_output.comparisons
            state.selected_frames[:] = phase_output.selected_frames
            state.warnings.extend(phase_output.warnings)
            if phase_output.selection_breakdown is not None:
                ctx.selection_breakdown = phase_output.selection_breakdown
            if phase_output.selection_details_by_source_frame is not None:
                ctx.selection_details_by_source_frame = (
                    phase_output.selection_details_by_source_frame
                )
        case RenderPhaseOutput() as phase_output:
            state.artifacts.render = phase_output.render
            state.warnings.extend(phase_output.render.warnings)
        case MetadataPhaseOutput() as phase_output:
            state.artifacts.resolved_metadata = phase_output.resolved_metadata
        case PublishPhaseOutput() as phase_output:
            state.artifacts.slowpics_url = phase_output.slowpics_url
            state.artifacts.uploaded_slowpics_file_paths = phase_output.uploaded_file_paths
            state.artifacts.post_upload_actions = phase_output.post_upload_actions
            state.warnings.extend(
                action.warning
                for action in phase_output.post_upload_actions
                if action.warning is not None
            )
        case ReportPhaseOutput() as phase_output:
            state.artifacts.report_path = phase_output.report_path
            state.artifacts.report_succeeded = phase_output.report_succeeded
        case ConfirmSlowpicsUploadPhaseOutput() as phase_output:
            state.artifacts.slowpics_upload_confirmation_status = phase_output.status
            state.warnings.extend(phase_output.warnings)
        case PostReportCleanupPhaseOutput() as phase_output:
            state.warnings.extend(phase_output.warnings)
        case _:
            raise TypeError(f"Unsupported phase output type: {output.__class__.__qualname__}")
