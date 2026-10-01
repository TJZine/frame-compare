"""Unit tests for orchestration phase execution helpers."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path
from time import monotonic

import pytest
from structlog.testing import capture_logs

from frame_compare.analysis.errors import ExclusionRecoverySelectionError
from frame_compare.analysis.window import SelectionWindow
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.execution import _create_timed_phase, build_phases_after_align
from frame_compare.orchestration.execution_types import (
    AlignPhaseOutput,
    ExecutionState,
    MetadataPrefetch,
    RunArtifacts,
)
from frame_compare.orchestration.phases import Phase, PhaseStatus, execute_phases
from frame_compare.orchestration.types import RunRequest
from frame_compare.utils.progress import (
    LogProgressReporter,
    NullProgressReporter,
    PlainProgressReporter,
    RichProgressReporter,
)
from frame_compare.utils.progress_protocol import ProgressPhaseStatus
from frame_compare.utils.types import WorkspacePaths


def _make_context(tmp_path: Path) -> RunContext:
    config = ConfigSchema()
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "input",
        generated_root=tmp_path / "generated",
        run_dir=None,
        screenshots_dir=tmp_path / "screens",
        generated_dir=tmp_path / "generated",
        config_dir=tmp_path / "config",
        config_file=tmp_path / "config" / "config.toml",
    )
    fingerprint = ClipFingerprint(
        path=tmp_path / "source.mkv",
        size_bytes=0,
        mtime_ns=0,
    )
    probe = ClipProbeSnapshot(
        fingerprint=fingerprint,
        width=1920,
        height=1080,
        num_frames=100,
        fps=Fraction(24, 1),
        is_hdr=False,
        hdr_metadata=None,
    )
    reference = ClipState(
        path=fingerprint.path,
        label="Reference",
        probe=probe,
        source_fps=probe.fps,
        effective_fps=probe.fps,
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


def test_execute_phases_unresolved_review_warns_and_keeps_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    context = _make_context(tmp_path)

    async def phase_align(_: RunContext) -> None:
        return None

    asyncio.run(
        execute_phases(
            [
                Phase(
                    name="align",
                    execute=phase_align,
                    success_summary="SCOPE needs visual confirmation",
                    success_status=ProgressPhaseStatus.WARNED,
                )
            ],
            context,
            RichProgressReporter(no_color=True),
        )
    )

    err = capsys.readouterr().err
    assert "!" in err
    assert "✓" not in err
    assert "SCOPE needs visual confirmation" in err


def test_timed_align_phase_with_unresolved_review_keeps_ok_on_plain_reporter(
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

    asyncio.run(execute_phases([phase], context, PlainProgressReporter()))

    assert phase.status is PhaseStatus.COMPLETED
    err = capsys.readouterr().err
    assert "[OK] ALIGN  Completed in " in err
    assert "[WARN]" not in err


def test_timed_align_phase_with_unresolved_review_keeps_completed_on_log_reporter(
    tmp_path: Path,
) -> None:
    context = _make_context(tmp_path)
    state = ExecutionState()
    phase_timings: dict[str, float] = {}
    reporter = LogProgressReporter()

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

    with capture_logs() as captured:
        asyncio.run(execute_phases([phase], context, reporter))

    assert phase.status is PhaseStatus.COMPLETED
    completed = [
        event
        for event in captured
        if event.get("event") == "phase_completed" and event.get("phase") == "align"
    ]
    assert len(completed) == 1
    assert completed[0].get("status") == "completed"


def test_timed_align_phase_with_unresolved_review_completes_as_warned(
    tmp_path: Path,
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

    asyncio.run(execute_phases([phase], context, NullProgressReporter()))

    assert phase.status is PhaseStatus.COMPLETED
    assert phase.success_status is ProgressPhaseStatus.WARNED
    assert phase.success_summary == "SCOPE needs visual confirmation"


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

    assert executed == ["analyze"]
    assert phases[0].status is PhaseStatus.FAILED
    assert phases[1].status is PhaseStatus.PENDING


def test_execute_phases_marks_cancellation_failed_before_propagating(
    tmp_path: Path,
) -> None:
    context = _make_context(tmp_path)

    class SpyReporter:
        def __init__(self) -> None:
            self.complete_phase_calls: list[ProgressPhaseStatus] = []

        def start_phase(self, name: str, total: int) -> None:
            del name, total

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

    assert phase.status is PhaseStatus.FAILED
    assert reporter.complete_phase_calls == [ProgressPhaseStatus.FAILED]


def test_execute_phases_fail_fast_failure_with_skip_condition_marks_failed_and_raises(
    tmp_path: Path,
) -> None:
    context = _make_context(tmp_path)
    reporter = NullProgressReporter()
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
            skip_condition=lambda config: False,
        ),
        Phase(name="after", execute=phase_after),
    ]

    try:
        asyncio.run(execute_phases(phases, context, reporter))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError from required phase")

    assert executed == ["fail"]
    assert phases[0].status is PhaseStatus.FAILED
    assert phases[1].status is PhaseStatus.PENDING


def test_execute_phases_fail_fast_failure_marks_failed_and_raises(
    tmp_path: Path,
) -> None:
    context = _make_context(tmp_path)
    reporter = NullProgressReporter()
    executed: list[str] = []

    async def phase_fail(_: RunContext) -> None:
        executed.append("fail")
        raise RuntimeError("boom")

    async def phase_after(_: RunContext) -> None:
        executed.append("after")

    phases = [
        Phase(name="fail", execute=phase_fail),
        Phase(name="after", execute=phase_after),
    ]

    try:
        asyncio.run(execute_phases(phases, context, reporter))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError from required phase")

    assert executed == ["fail"]
    assert phases[0].status is PhaseStatus.FAILED
    assert phases[1].status is PhaseStatus.PENDING


def test_publish_phase_skip_condition_uses_effective_slowpics_config() -> None:
    artifacts = RunArtifacts()
    state = ExecutionState(artifacts=artifacts)

    phases = build_phases_after_align(
        request=RunRequest(root=Path("."), no_upload=False),
        monotonic_timer=lambda: 0.0,
        ffmpeg_runner=object(),
        http_client=None,
        state=state,
        metadata_prefetch=MetadataPrefetch(None, False),
        config=ConfigSchema(),
    )

    publish_phase = next(phase for phase in phases if phase.name == "publish")
    config = ConfigSchema()
    config.slowpics.auto_upload = False

    assert publish_phase.skip_condition is not None
    assert publish_phase.skip_condition(config) is True
    assert callable(publish_phase.skip_detail)
    assert publish_phase.skip_detail(config) == "Disabled"
