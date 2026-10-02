"""Alignment cancellation containment at the phase-output boundary."""

from __future__ import annotations

import asyncio
import threading
import time
from fractions import Fraction
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from frame_compare.orchestration import execution
from frame_compare.orchestration.execution_types import ExecutionState, RunArtifacts
from frame_compare.services import alignment
from frame_compare.services.errors import raise_if_alignment_cancelled
from frame_compare.services.types import AlignmentConfig
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
        config=config,
        generated_dir=tmp_path,
    )
    started = threading.Event()

    def block(*_args: Any, cancellation: threading.Event, **_kwargs: Any) -> Any:
        started.set()
        while not cancellation.is_set():
            time.sleep(0.001)
        raise_if_alignment_cancelled(cancellation)

    monkeypatch.setattr(alignment, "_estimate_audio_pair", block)
    apply_output = MagicMock()
    monkeypatch.setattr(execution, "apply_phase_output", apply_output)
    state = ExecutionState(artifacts=RunArtifacts())
    timings: dict[str, float] = {}

    async def executor(_ctx: object) -> object:
        return await alignment.align_clips_from_request(
            request,
            config,
            reference_fps=Fraction(24),
        )

    phase = execution._create_timed_phase(
        "align",
        "align",
        None,
        executor,
        state,
        time.monotonic,
        timings,
        [],
    )
    task = asyncio.create_task(phase.execute(_context(tmp_path)))
    for _ in range(200):
        if started.is_set():
            break
        await asyncio.sleep(0.005)
    else:
        raise AssertionError("alignment worker did not start")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    apply_output.assert_not_called()
    assert timings["align"] >= 0
