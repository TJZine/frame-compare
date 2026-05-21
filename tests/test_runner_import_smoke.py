import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

import frame_compare.orchestration.coordinator as coordinator
import frame_compare.runner as runner


def test_runner_exports_public_symbols() -> None:
    assert hasattr(runner, "RunRequest")
    assert hasattr(runner, "RunResult")
    assert hasattr(runner, "RunDependencies")
    assert hasattr(runner, "run")


def test_runner_run_propagates_result_and_copies_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    expected = runner.RunResult(success=True)

    async def fake_execute_run(
        request: runner.RunRequest, deps: runner.RunDependencies
    ) -> runner.RunResult:
        captured["request"] = request
        captured["deps"] = deps
        return expected

    monkeypatch.setattr(coordinator, "execute_run", fake_execute_run, raising=False)

    request = runner.RunRequest(root=Path("."))
    original_deps = runner.RunDependencies()

    result = runner.run(request, dependencies=original_deps)

    assert result is expected
    assert captured["deps"] is not None
    assert captured["deps"] is not original_deps
    assert original_deps.progress is None


def test_runner_run_creates_and_closes_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    expected = runner.RunResult(success=True)

    async def fake_execute_run(
        request: runner.RunRequest, deps: runner.RunDependencies
    ) -> runner.RunResult:
        captured["http_client"] = deps.http_client
        return expected

    monkeypatch.setattr(coordinator, "execute_run", fake_execute_run, raising=False)

    request = runner.RunRequest(root=Path("."))
    result = runner.run(request, dependencies=runner.RunDependencies())

    assert result is expected
    http_client = captured["http_client"]
    assert isinstance(http_client, httpx.AsyncClient)
    assert http_client.is_closed


def test_runner_run_does_not_close_caller_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = runner.RunResult(success=True)

    async def fake_execute_run(
        request: runner.RunRequest, deps: runner.RunDependencies
    ) -> runner.RunResult:
        return expected

    monkeypatch.setattr(coordinator, "execute_run", fake_execute_run, raising=False)

    client = httpx.AsyncClient()
    request = runner.RunRequest(root=Path("."))
    deps = runner.RunDependencies(http_client=client)

    try:
        result = runner.run(request, dependencies=deps)
        was_closed = client.is_closed
    finally:
        asyncio.run(client.aclose())

    assert result is expected
    assert not was_closed


def test_runner_run_raises_when_event_loop_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_execute_run(
        request: runner.RunRequest, deps: runner.RunDependencies
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
