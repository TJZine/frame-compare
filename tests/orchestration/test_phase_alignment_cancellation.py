"""Alignment cancellation containment at the phase-output boundary."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from frame_compare.orchestration.context import RunContext
from frame_compare.orchestration.execution import RunSteps
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    ExecutionState,
    RunArtifacts,
)
from frame_compare.services import alignment
from frame_compare.services.errors import raise_if_alignment_cancelled
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.progress import NullProgressReporter
from tests.orchestration.phase_task_helpers import _context
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
    reference_before, comparisons_before, selection_before = (
        ctx.reference,
        ctx.comparisons,
        ctx.selection,
    )
    state = ExecutionState()
    steps = RunSteps(reporter=NullProgressReporter(), state=state, monotonic_timer=time.monotonic)

    async def executor(ctx: RunContext) -> AlignPhaseOutput:
        await alignment.align_clips_from_request(
            request,
            config,
        )
        return AlignPhaseOutput(
            reference=ctx.reference, comparisons=ctx.comparisons, selected_frames=[]
        )

    async def run_phase() -> None:
        await steps.run("align", lambda: executor(ctx), warning_source="alignment")

    task = asyncio.create_task(run_phase())
    for _ in range(200):
        if started.is_set():
            break
        await asyncio.sleep(0.005)
    else:
        raise AssertionError("alignment worker did not start")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert ctx.reference is reference_before
    assert ctx.comparisons is comparisons_before
    assert ctx.selection is selection_before
    assert state.artifacts == RunArtifacts()
    assert state.vsview_review_seconds == 0.0
