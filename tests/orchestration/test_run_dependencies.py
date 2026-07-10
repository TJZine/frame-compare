from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration import RunDependencies as PublicRunDependencies
from frame_compare.orchestration.coordinator import (
    RunDependencies,
    execute_run,
)
from frame_compare.orchestration.types import (
    RunRequest,
    SlowpicsUploadConfirmationDecision,
    SlowpicsUploadConfirmationRequest,
)
from frame_compare.utils.progress import NullProgressReporter
from frame_compare.vs.loader import VSLoader
from frame_compare.vs.types import HDRMetadata, SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs


class StopAfterDependencyInit(RuntimeError):
    pass


class DummyVSLoader:
    def load(self, path: Path) -> SourceInfo:
        raise RuntimeError("Not used in tests.")

    def ensure_core(self) -> vs.Core:
        raise RuntimeError("Not used in tests.")


class DummyFFmpegRunner:
    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None:
        raise RuntimeError("Not used in tests.")

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        return None


def test_run_dependencies_exported_from_orchestration() -> None:
    assert PublicRunDependencies is RunDependencies


def test_run_dependencies_returns_injected_dependencies() -> None:
    loader = DummyVSLoader()
    runner = DummyFFmpegRunner()

    deps = RunDependencies(vs_loader=loader, ffmpeg_runner=runner)

    assert deps.vs_loader is loader
    assert deps.ffmpeg_runner is runner


def test_run_dependencies_accepts_slowpics_confirmation_callback() -> None:
    def _confirm(
        _request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        return "confirmed"

    deps = RunDependencies(confirm_slowpics_upload=_confirm)

    assert deps.confirm_slowpics_upload is _confirm


def test_run_dependencies_clock_returns_datetime() -> None:
    deps = RunDependencies()

    now = deps.clock()

    assert isinstance(now, datetime)


def test_run_dependencies_accepts_vs_loader_protocol() -> None:
    loader: VSLoader = DummyVSLoader()
    deps = RunDependencies(vs_loader=loader)

    assert deps.vs_loader is loader


def test_execute_run_initializes_local_dependencies_without_mutating_injected_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.orchestration import coordinator

    captured_local_deps: RunDependencies | None = None
    prep_completed = False
    configured_timeouts: list[float] = []

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        nonlocal captured_local_deps, prep_completed
        captured_local_deps = local_deps
        assert local_deps is not deps
        assert local_deps.vs_loader is not None
        assert local_deps.ffmpeg_runner is None
        assert local_deps.progress is not None
        assert local_deps.http_client is not None
        prep_completed = True
        return SimpleNamespace(
            config=ConfigSchema(
                screenshots={"ffmpeg_timeout_seconds": 47.0},
            )
        )

    def fake_default_ffmpeg_runner(*, extraction_timeout_seconds: float):
        assert prep_completed is True
        configured_timeouts.append(extraction_timeout_seconds)
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "DefaultFFmpegRunner", fake_default_ffmpeg_runner)

    request = RunRequest(root=tmp_path, quiet=True)
    deps = RunDependencies()

    assert deps.vs_loader is None
    assert deps.ffmpeg_runner is None
    assert deps.progress is None

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(request, deps=deps))

    assert captured_local_deps is not None
    assert configured_timeouts == [47.0]
    assert deps.vs_loader is None
    assert deps.ffmpeg_runner is None
    assert deps.progress is None
    assert deps.http_client is None


def test_execute_run_preserves_injected_ffmpeg_runner_after_prep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.orchestration import coordinator

    injected_runner = DummyFFmpegRunner()

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        assert local_deps.ffmpeg_runner is injected_runner
        return SimpleNamespace(config=ConfigSchema(), artifacts=None)

    def fail_default_ffmpeg_runner(*, extraction_timeout_seconds: float):
        del extraction_timeout_seconds
        raise AssertionError("injected FFmpeg runner must not be replaced")

    def stop_after_ffmpeg_resolution(*, artifacts: object):
        del artifacts
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "DefaultFFmpegRunner", fail_default_ffmpeg_runner)
    monkeypatch.setattr(coordinator, "ExecutionState", stop_after_ffmpeg_resolution)

    deps = RunDependencies(ffmpeg_runner=injected_runner)
    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(RunRequest(root=tmp_path, quiet=True), deps=deps))

    assert deps.ffmpeg_runner is injected_runner


def test_execute_run_passes_no_color_to_progress_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.orchestration import coordinator

    captured: dict[str, bool] = {}
    progress = NullProgressReporter()

    def fake_select_reporter(
        *,
        quiet: bool = False,
        json_output: bool = False,
        no_color: bool = False,
        force_tty: bool | None = None,
    ) -> NullProgressReporter:
        del force_tty
        captured["quiet"] = quiet
        captured["json_output"] = json_output
        captured["no_color"] = no_color
        return progress

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        assert local_deps.progress is progress
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "select_reporter", fake_select_reporter)
    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(RunRequest(root=tmp_path, no_color=True), deps=RunDependencies()))

    assert captured == {
        "quiet": False,
        "json_output": False,
        "no_color": True,
    }


def test_execute_run_preserves_slowpics_confirmation_callback_when_cloning_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from frame_compare.orchestration import coordinator

    captured_local_deps: RunDependencies | None = None

    def _confirm(
        _request: SlowpicsUploadConfirmationRequest,
    ) -> SlowpicsUploadConfirmationDecision:
        return "confirmed"

    async def fake_execute_prep(_request: RunRequest, local_deps: RunDependencies):
        nonlocal captured_local_deps
        captured_local_deps = local_deps
        raise StopAfterDependencyInit

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)

    deps = RunDependencies(confirm_slowpics_upload=_confirm)

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(RunRequest(root=tmp_path, quiet=True), deps=deps))

    assert captured_local_deps is not None
    assert captured_local_deps.confirm_slowpics_upload is _confirm
