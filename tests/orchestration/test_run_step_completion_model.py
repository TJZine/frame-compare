"""Exhaust the transition relation for an admitted warn-only alignment step."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Literal

import pytest

from frame_compare.orchestration.execution import RunSteps, StepCompletion
from frame_compare.orchestration.execution_types import ExecutionState
from frame_compare.services.errors import AudioAlignmentCleanupError
from frame_compare.utils.progress import NullProgressReporter
from frame_compare.utils.progress_protocol import ProgressPhaseStatus as Status

type Action = Literal["body", "describe", "advance"]
type Outcome = Literal["ok", "error", "cleanup-error", "cancel"]
type Trace = tuple[tuple[Action, Outcome], ...]

TRANSITIONS: dict[Action, dict[Outcome, Action | Status]] = {
    "body": {
        "ok": "describe",
        "error": Status.WARNED,
        "cleanup-error": Status.FAILED,
        "cancel": Status.INTERRUPTED,
    },
    "describe": {"ok": "advance", "error": Status.FAILED},
    "advance": {"ok": Status.COMPLETED, "error": Status.FAILED},
}


def terminal_traces(state: Action = "body", prefix: Trace = ()) -> Iterator[tuple[Trace, Status]]:
    for outcome, target in TRANSITIONS[state].items():
        trace: Trace = (*prefix, (state, outcome))
        if isinstance(target, Status):
            yield trace, target
        else:
            yield from terminal_traces(target, trace)


@pytest.mark.parametrize(
    ("trace", "status"),
    [
        pytest.param(trace, status, id="-".join(f"{action}.{outcome}" for action, outcome in trace))
        for trace, status in terminal_traces()
    ],
)
@pytest.mark.parametrize("write_fails", [False, True], ids=["written", "write-failed"])
@pytest.mark.parametrize("handling_error", [False, True], ids=["normal-caller", "caller-in-except"])
async def test_completion_model(
    trace: Trace, status: Status, write_fails: bool, handling_error: bool
) -> None:
    faults = dict(trace)
    step_error: BaseException = RuntimeError("step failure")
    if faults["body"] == "cleanup-error":
        step_error = AudioAlignmentCleanupError("resource not released")
    elif faults["body"] == "cancel":
        step_error = asyncio.CancelledError()
    write_error = OSError("stderr closed")
    expected_error = write_error if write_fails else None
    if status in (Status.FAILED, Status.INTERRUPTED):
        expected_error = step_error

    observed_actions: list[Action | Status] = []

    def act(action: Action) -> None:
        observed_actions.append(action)
        if faults[action] != "ok":
            raise step_error

    class Reporter(NullProgressReporter):
        def advance(self, amount: int = 1) -> None:
            act("advance")

        def complete_phase(self, status: Status = Status.COMPLETED, **_details: object) -> None:
            observed_actions.append(status)
            if write_fails:
                raise write_error

    def body() -> str:
        act("body")
        return "output"

    def describe(_result: str, _elapsed: float) -> StepCompletion:
        act("describe")
        return StepCompletion()

    async def run() -> str | None:
        steps = RunSteps(reporter=Reporter(), state=ExecutionState(), monotonic_timer=lambda: 0.0)
        return await steps.run(
            "align",
            body,
            warning_source="alignment",
            warn_only=True,
            fatal=(AudioAlignmentCleanupError,),
            describe=describe,
        )

    result = None
    observed_error = None
    try:
        if handling_error:
            try:
                raise LookupError("unrelated caller error")
            except LookupError:
                result = await run()
        else:
            result = await run()
    except BaseException as error:
        observed_error = error

    assert observed_error is expected_error
    assert observed_actions == [*(action for action, _ in trace), status]
    if expected_error is None:
        assert result == (None if status is Status.WARNED else "output")
