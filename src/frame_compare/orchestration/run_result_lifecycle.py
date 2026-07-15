"""Best-effort run-result persistence at the orchestration lifecycle boundary."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

import structlog

from frame_compare.orchestration.execution_types import RunArtifacts
from frame_compare.orchestration.types import RunResult
from frame_compare.services.run_result_record import (
    CompletedRunFacts,
    FailedRunFacts,
    completed_record,
    failed_record,
    write_run_result,
)
from frame_compare.utils.types import WorkspacePaths

log = structlog.get_logger()

RUN_RESULT_WRITE_WARNING = "history: run result could not be recorded"


def record_completed_run_result(
    *,
    workspace: WorkspacePaths | None,
    result: RunResult,
    started_at: datetime,
    completed_at: datetime,
) -> RunResult:
    """Persist a completed outcome without turning persistence failure into run failure."""
    if workspace is None or workspace.run_dir is None:
        return result
    try:
        write_run_result(
            workspace.run_dir,
            completed_record(
                workspace=workspace,
                facts=CompletedRunFacts(
                    report_path=result.report_path,
                    screenshot_dir=result.screenshot_dir,
                    clip_count=result.clips_processed,
                    selected_frame_count=result.frame_count,
                    warnings=tuple(result.warnings),
                    metrics_cache_status=result.metrics_cache_status,
                    phase_timings=result.phase_timings,
                    slowpics_url=result.slowpics_url,
                    slowpics_confirmation_status=result.slowpics_upload_confirmation_status,
                ),
                started_at=started_at,
                completed_at=completed_at,
            ),
        )
    except Exception:
        with contextlib.suppress(Exception):
            log.warning("run_result_write_degraded", status="completed")
        return replace(result, warnings=[*result.warnings, RUN_RESULT_WRITE_WARNING])
    return result


def record_failed_run_best_effort(
    *,
    workspace: WorkspacePaths | None,
    error: BaseException,
    started_at: datetime | None,
    completed_at: Callable[[], datetime],
    artifacts: RunArtifacts | None,
    clip_count: int,
    selected_frame_count: int,
    phase_timings: dict[str, float],
    warnings: tuple[str, ...],
) -> None:
    """Avoid masking the original with ordinary failed-outcome recording failures."""
    if started_at is None or workspace is None or workspace.run_dir is None:
        return
    try:
        write_run_result(
            workspace.run_dir,
            failed_record(
                error=error,
                started_at=started_at,
                completed_at=completed_at(),
                facts=FailedRunFacts(
                    clip_count=clip_count,
                    selected_frame_count=selected_frame_count,
                    phase_timings=phase_timings,
                    report_path=None if artifacts is None else artifacts.report_path,
                    screenshot_dir=(
                        None
                        if artifacts is None or artifacts.render is None
                        else artifacts.render.screenshot_dir
                    ),
                    metrics_cache_status=(
                        "skipped" if artifacts is None else artifacts.metrics_cache_status
                    ),
                    slowpics_url=None if artifacts is None else artifacts.slowpics_url,
                    warnings=(
                        warnings if artifacts is None else (*warnings, *sorted(artifacts.warnings))
                    ),
                ),
                workspace=workspace,
            ),
        )
    except Exception:
        with contextlib.suppress(Exception):
            log.warning("run_result_write_degraded", status="failed")
