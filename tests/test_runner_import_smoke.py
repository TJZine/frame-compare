import asyncio
from pathlib import Path
from typing import Any

import pytest

import frame_compare.orchestration.coordinator as coordinator
import frame_compare.runner as runner


def test_runner_exports_public_symbols() -> None:
    assert hasattr(runner, "RunRequest")
    assert hasattr(runner, "RunResult")
    assert hasattr(runner, "RunDependencies")
    assert hasattr(runner, "run")


def test_runner_run_propagates_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    expected = runner.RunResult(success=True)

    async def fake_execute_run(
        request: runner.RunRequest, deps: runner.RunDependencies | None
    ) -> runner.RunResult:
        captured["request"] = request
        captured["deps"] = deps
        return expected

    monkeypatch.setattr(coordinator, "execute_run", fake_execute_run, raising=False)

    request = runner.RunRequest(root=Path("."))
    deps = runner.RunDependencies()

    result = runner.run(request, dependencies=deps)

    assert result is expected
    assert captured["request"] is request
    assert captured["deps"] is deps


def test_runner_run_raises_when_event_loop_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute_run(
        request: runner.RunRequest, deps: runner.RunDependencies | None
    ) -> runner.RunResult:
        return runner.RunResult(success=True)

    monkeypatch.setattr(coordinator, "execute_run", fake_execute_run, raising=False)

    async def _call_run() -> None:
        request = runner.RunRequest(root=Path("."))
        with pytest.raises(
            RuntimeError,
            match=(
                r"^Do not call frame_compare\.runner\.run from an async context; "
                r"await frame_compare\.orchestration\.execute_run instead\.$"
            ),
        ):
            runner.run(request)

    asyncio.run(_call_run())


def test_runner_run_raises_when_execute_run_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(coordinator, "execute_run", raising=False)

    request = runner.RunRequest(root=Path("."))
    with pytest.raises(
        NotImplementedError,
        match=(
            r"^Missing required entry point: "
            r"frame_compare\.orchestration\.coordinator\.execute_run$"
        ),
    ):
        runner.run(request)
