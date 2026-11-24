"""Alignment cancellation containment at the phase-output boundary."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from frame_compare.orchestration import execution
from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution import RunSteps
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    ExecutionState,
    FramePlanPhaseOutput,
    RunArtifacts,
)
from frame_compare.orchestration.types import RunDependencies
from frame_compare.services import alignment
from frame_compare.services.errors import raise_if_alignment_cancelled
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.progress import NullProgressReporter
from tests.orchestration.phase_task_helpers import _context, prep_for_context
from tests.run_request_support import make_run_request
from tests.services.alignment_request_test_support import alignment_request


@pytest.mark.anyio
async def test_cancelled_alignment_never_applies_phase_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    config = AlignmentConfig(cache_results=False)
    request = alignment_request(
        reference=reference,
        comparisons=[comparison],
        generated_dir=tmp_path,
    )
    started = threading.Event()

    def block(*_args: Any, cancellation: threading.Event, **_kwargs: Any) -> Any:
        started.set()
        while not cancellation.is_set():
            time.sleep(0.001)
        raise_if_alignment_cancelled(cancellation)

    monkeypatch.setattr(alignment, "_estimate_audio_pair", block)
    ctx = _context(tmp_path)
    ctx.config.audio_alignment.enable = True
    state = ExecutionState()
    steps = RunSteps(reporter=NullProgressReporter(), state=state, monotonic_timer=time.monotonic)
    before_align: list[tuple[object, object, object]] = []

    async def align_phase(ctx: RunContext, **_kwargs: object) -> AlignPhaseOutput:
        before_align.append((ctx.reference, ctx.comparisons, ctx.selection))
        await alignment.align_clips_from_request(
            request,
            config,
        )
        return AlignPhaseOutput(
            reference=ctx.reference, comparisons=ctx.comparisons, selected_frames=[]
        )

    monkeypatch.setattr(
        execution, "select_initial_frame_plan", lambda *a, **kw: FramePlanPhaseOutput([0])
    )
    monkeypatch.setattr(execution, "run_align_phase", align_phase)
    task = asyncio.create_task(
        execution.run_selection_steps(
            ctx,
            steps,
            request=make_run_request(root=tmp_path, config=ctx.config, skip_analysis=True),
            prep=prep_for_context(ctx, state),
            state=state,
            deps=RunDependencies(),
        )
    )
    for _ in range(200):
        if started.is_set():
            break
        await asyncio.sleep(0.005)
    else:
        raise AssertionError("alignment worker did not start")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    [(reference_before, comparisons_before, selection_before)] = before_align
    assert ctx.reference is reference_before
    assert ctx.comparisons is comparisons_before
    assert ctx.selection is selection_before
    assert steps.interrupted_step == "align"
    assert state.artifacts == RunArtifacts()
    assert state.vsview_review_seconds == 0.0
