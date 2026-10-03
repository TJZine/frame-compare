"""Unit tests for orchestration phase execution helpers."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from time import monotonic

import pytest

from frame_compare.analysis.errors import ExclusionRecoverySelectionError
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    RunContext,
)
from frame_compare.orchestration.execution import _create_timed_phase
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    ExecutionState,
)
from frame_compare.orchestration.phases import Phase, execute_phases
from frame_compare.utils.progress import (
    NullProgressReporter,
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus

from .execute_run_helpers import clip_state
from .phase_task_helpers import _workspace


def _make_context(tmp_path: Path) -> RunContext:
    config = ConfigSchema()
    workspace = _workspace(
        tmp_path, input_subdir="input", run_subdir=None, screenshots_subdir="screens"
    )
    fingerprint = ClipFingerprint(
        path=tmp_path / "source.mkv",
        size_bytes=0,
        mtime_ns=0,
    )
    reference = clip_state(
        fingerprint.path,
        label="Reference",
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=100,
        fps=Fraction(24, 1),
        is_hdr=False,
    )
    return RunContext(
        config=config,
        workspace=workspace,
        reference=reference,
        comparisons=[],
        analysis_selection_domain="test-selection-domain",
        selection_window=SelectionWindow(start_frame=0, end_frame_exclusive=100),
        reporter=NullProgressReporter(),
    )


def test_timed_align_phase_with_unresolved_review_renders_warning_line(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    context = _make_context(tmp_path)
    state = ExecutionState()
    phase_timings: dict[str, float] = {}

    async def _executor(_: RunContext) -> AlignPhaseOutput:
        return AlignPhaseOutput(
            reference=context.reference,
            comparisons=[],
            selected_frames=[],
            success_summary="SCOPE needs visual confirmation",
            review_unresolved=True,
        )

    phase = _create_timed_phase(
        "align",
        "align",
        None,
        _executor,
        state,
        monotonic,
        phase_timings,
        [],
    )

    asyncio.run(execute_phases([phase], context, RichProgressReporter(no_color=True)))

    err = capsys.readouterr().err
    assert "!" in err
    assert "✓" not in err
    assert "SCOPE needs visual confirmation" in err


def test_execute_phases_fatal_exclusion_recovery_stops_warn_only_pipeline(
    tmp_path: Path,
) -> None:
    context = _make_context(tmp_path)
    executed: list[str] = []

    async def phase_recovery_failure(_: RunContext) -> None:
        executed.append("analyze")
        raise ExclusionRecoverySelectionError(
            "configured exclusions leave too little media for frame selection",
            requested=8,
            found=4,
        )

    async def downstream_side_effect(_: RunContext) -> None:
        executed.append("render")

    phases = [
        Phase(
            name="analyze",
            execute=phase_recovery_failure,
            warn_only=True,
            fatal_exceptions=(ExclusionRecoverySelectionError,),
        ),
        Phase(name="render", execute=downstream_side_effect),
    ]

    with pytest.raises(ExclusionRecoverySelectionError):
        asyncio.run(execute_phases(phases, context, NullProgressReporter()))


def test_execute_phases_marks_cancellation_failed_before_propagating(
    tmp_path: Path,
) -> None:
    context = _make_context(tmp_path)

    class SpyReporter(NullProgressReporter):
        def __init__(self) -> None:
            self.complete_phase_calls: list[ProgressPhaseStatus] = []

        def start_phase(self, name: str, total: int, *, presentation: str | None = None) -> None:
            del name, total, presentation

        def advance(self, amount: int = 1) -> None:
            del amount

        def set_description(self, desc: str) -> None:
            del desc

        def complete_phase(
            self,
            status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
            *,
            retain: bool | None = None,
            summary: str | None = None,
            duration_text: str | None = None,
            presentation: str | None = None,
        ) -> None:
            del retain, summary, duration_text, presentation
            self.complete_phase_calls.append(status)

    reporter = SpyReporter()

    async def phase_cancel(_: RunContext) -> None:
        raise asyncio.CancelledError

    phase = Phase(name="cancel", execute=phase_cancel)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(execute_phases([phase], context, reporter))


@pytest.mark.parametrize("explicit_skip", [True, False], ids=["false-predicate", "no-predicate"])
def test_execute_phases_fail_fast_failure_marks_failed_and_raises(
    tmp_path: Path,
    explicit_skip: bool,
) -> None:
    context = _make_context(tmp_path)
    executed: list[str] = []

    async def phase_fail(_: RunContext) -> None:
        executed.append("fail")
        raise RuntimeError("boom")

    async def phase_after(_: RunContext) -> None:
        executed.append("after")

    phases = [
        Phase(
            name="fail",
            execute=phase_fail,
            skip_condition=(lambda config: False) if explicit_skip else None,
        ),
        Phase(name="after", execute=phase_after),
    ]

    try:
        asyncio.run(execute_phases(phases, context, NullProgressReporter()))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError from required phase")

    assert executed == ["fail"]
