"""Unit tests for orchestration phase execution helpers."""

from __future__ import annotations

import asyncio
from fractions import Fraction
from pathlib import Path

from frame_compare.config import ConfigSchema
from frame_compare.orchestration.context import (
    ClipFingerprint,
    ClipProbeSnapshot,
    ClipState,
    RunContext,
)
from frame_compare.orchestration.phases import Phase, PhaseStatus, execute_phases
from frame_compare.utils.progress import NullProgressReporter
from frame_compare.utils.types import WorkspacePaths


def _make_context(tmp_path: Path) -> RunContext:
    config = ConfigSchema()
    workspace = WorkspacePaths(
        root=tmp_path,
        input_dir=tmp_path / "input",
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
            self.complete_phase_calls: list[None] = []
            self.advance_calls: list[int] = []

        def start_phase(self, name: str, total: int) -> None:
            self.start_phase_calls.append((name, total))

        def advance(self, amount: int = 1) -> None:
            self.advance_calls.append(amount)

        def set_description(self, desc: str) -> None:
            self.set_description_calls.append(desc)

        def complete_phase(self) -> None:
            self.complete_phase_calls.append(None)

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

    assert reporter.start_phase_calls == [("skip", 1), ("next", 1)]
    assert reporter.set_description_calls == ["Skipped"]
    assert len(reporter.complete_phase_calls) == 2
    assert phases[0].status is PhaseStatus.SKIPPED
    assert phases[1].status is PhaseStatus.COMPLETED


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
        ),
        Phase(name="after", execute=phase_after),
    ]

    asyncio.run(execute_phases(phases, context, reporter))

    assert executed == ["warn", "after"]
    assert phases[0].status is PhaseStatus.WARNED
    assert phases[1].status is PhaseStatus.COMPLETED


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
