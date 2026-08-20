"""Unit tests for orchestration phase execution helpers."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path

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
from frame_compare.orchestration.execution import build_phases_after_align
from frame_compare.orchestration.execution_types import (
    ExecutionState,
    MetadataPrefetch,
    RunArtifacts,
)
from frame_compare.orchestration.phases import Phase, PhaseStatus, execute_phases
from frame_compare.orchestration.types import RunRequest
from frame_compare.utils.progress import LogProgressReporter, NullProgressReporter
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


def test_execute_phases_runs_in_order_and_marks_completed(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    reporter = NullProgressReporter()
    executed: list[str] = []

    async def phase_a(_: RunContext) -> None:
        executed.append("a")

    async def phase_b(_: RunContext) -> None:
        executed.append("b")

    async def phase_c(_: RunContext) -> None:
        executed.append("c")

    phases = [
        Phase(name="a", execute=phase_a),
        Phase(name="b", execute=phase_b),
        Phase(name="c", execute=phase_c),
    ]

    asyncio.run(execute_phases(phases, context, reporter))

    assert executed == ["a", "b", "c"]
    assert [phase.status for phase in phases] == [
        PhaseStatus.COMPLETED,
        PhaseStatus.COMPLETED,
        PhaseStatus.COMPLETED,
    ]


def test_execute_phases_skips_when_skip_condition_true(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    reporter = NullProgressReporter()
    called = False

    async def phase_skip(_: RunContext) -> None:
        nonlocal called
        called = True

    async def phase_next(_: RunContext) -> None:
        return None

    phases = [
        Phase(
            name="skip",
            execute=phase_skip,
            skip_condition=lambda config: True,
        ),
        Phase(name="next", execute=phase_next),
    ]

    asyncio.run(execute_phases(phases, context, reporter))

    assert called is False
    assert phases[0].status is PhaseStatus.SKIPPED
    assert phases[1].status is PhaseStatus.COMPLETED


def test_execute_phases_reports_skipped_phase_lifecycle(tmp_path: Path) -> None:
    context = _make_context(tmp_path)

    class SpyReporter:
        def __init__(self) -> None:
            self.start_phase_calls: list[tuple[str, int]] = []
            self.set_description_calls: list[str] = []
            self.complete_phase_calls: list[ProgressPhaseStatus] = []
            self.advance_calls: list[int] = []

        def start_phase(self, name: str, total: int) -> None:
            self.start_phase_calls.append((name, total))

        def advance(self, amount: int = 1) -> None:
            self.advance_calls.append(amount)

        def set_description(self, desc: str) -> None:
            self.set_description_calls.append(desc)

        def complete_phase(
            self,
            status: ProgressPhaseStatus = ProgressPhaseStatus.COMPLETED,
        ) -> None:
            self.complete_phase_calls.append(status)

    reporter = SpyReporter()

    async def phase_skip(_: RunContext) -> None:
        return None

    async def phase_next(_: RunContext) -> None:
        return None

    phases = [
        Phase(
            name="skip",
            execute=phase_skip,
            skip_condition=lambda config: True,
        ),
        Phase(name="next", execute=phase_next),
    ]

    asyncio.run(execute_phases(phases, context, reporter))

    assert reporter.start_phase_calls == [("SKIP", 1), ("NEXT", 1)]
    assert reporter.set_description_calls == ["Skipped"]
    assert reporter.complete_phase_calls == [
        ProgressPhaseStatus.SKIPPED,
        ProgressPhaseStatus.COMPLETED,
    ]
    assert phases[0].status is PhaseStatus.SKIPPED
    assert phases[1].status is PhaseStatus.COMPLETED


def test_execute_phases_preserves_internal_phase_name_for_log_progress(
    tmp_path: Path,
) -> None:
    context = _make_context(tmp_path)
    reporter = LogProgressReporter()

    async def phase_analyze(_: RunContext) -> None:
        return None

    phases = [Phase(name="analyze", execute=phase_analyze)]

    with capture_logs() as captured:
        asyncio.run(execute_phases(phases, context, reporter))

    assert any(
        event.get("event") == "phase_started"
        and event.get("phase") == "analyze"
        and event.get("total") == 1
        for event in captured
    )


def test_execute_phases_forwards_success_retention_hint(tmp_path: Path) -> None:
    context = _make_context(tmp_path)

    class SpyReporter:
        def __init__(self) -> None:
            self.complete_phase_calls: list[tuple[ProgressPhaseStatus, bool | None]] = []

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
        ) -> None:
            self.complete_phase_calls.append((status, retain))

    reporter = SpyReporter()

    async def phase_publish(_: RunContext) -> None:
        return None

    asyncio.run(
        execute_phases(
            [Phase(name="publish", execute=phase_publish, retain_on_success=True)],
            context,
            reporter,
        )
    )

    assert reporter.complete_phase_calls == [(ProgressPhaseStatus.COMPLETED, True)]


def test_execute_phases_warn_only_failure_marks_warned_and_continues(
    tmp_path: Path,
) -> None:
    context = _make_context(tmp_path)
    reporter = NullProgressReporter()
    executed: list[str] = []

    async def phase_warn(_: RunContext) -> None:
        executed.append("warn")
        raise RuntimeError("boom")

    async def phase_after(_: RunContext) -> None:
        executed.append("after")

    phases = [
        Phase(
            name="warn",
            execute=phase_warn,
            skip_condition=lambda config: False,
            warn_only=True,
        ),
        Phase(name="after", execute=phase_after),
    ]

    asyncio.run(execute_phases(phases, context, reporter))

    assert executed == ["warn", "after"]
    assert phases[0].status is PhaseStatus.WARNED
    assert phases[1].status is PhaseStatus.COMPLETED


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


def test_execute_phases_warn_only_failure_reports_warned_progress_status(
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
        ) -> None:
            self.complete_phase_calls.append(status)

    reporter = SpyReporter()

    async def phase_warn(_: RunContext) -> None:
        raise RuntimeError("boom")

    async def phase_after(_: RunContext) -> None:
        return None

    phases = [
        Phase(name="warn", execute=phase_warn, warn_only=True),
        Phase(name="after", execute=phase_after),
    ]

    asyncio.run(execute_phases(phases, context, reporter))

    assert reporter.complete_phase_calls == [
        ProgressPhaseStatus.WARNED,
        ProgressPhaseStatus.COMPLETED,
    ]


def test_execute_phases_fail_fast_failure_reports_failed_progress_status(
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
        ) -> None:
            self.complete_phase_calls.append(status)

    reporter = SpyReporter()

    async def phase_fail(_: RunContext) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(execute_phases([Phase(name="fail", execute=phase_fail)], context, reporter))

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


def test_execute_phases_empty_list_noop(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    reporter = NullProgressReporter()

    asyncio.run(execute_phases([], context, reporter))


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
