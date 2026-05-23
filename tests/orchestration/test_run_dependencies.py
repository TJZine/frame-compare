from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from frame_compare.orchestration import RunDependencies as PublicRunDependencies
from frame_compare.orchestration.coordinator import (
    RunDependencies,
    execute_run,
)
from frame_compare.orchestration.types import RunRequest
from frame_compare.vs.loader import VSLoader
from frame_compare.vs.types import HDRMetadata


class StopAfterDependencyInit(RuntimeError):
    pass


class DummyVSLoader:
    def load(self, path: Path):  # type: ignore[override]
        raise RuntimeError("Not used in tests.")

    def ensure_core(self):  # type: ignore[override]
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


def test_run_dependencies_clock_returns_datetime() -> None:
    deps = RunDependencies()

    now = deps.clock()

    assert isinstance(now, datetime)


def test_run_dependencies_accepts_vs_loader_protocol() -> None:
    loader: VSLoader = DummyVSLoader()
    deps = RunDependencies(vs_loader=loader)

    assert deps.vs_loader is loader


def test_execute_run_populates_missing_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # We will use monkeypatch to avoid actually running execute_prep which tries to load configuration
    # from the filesystem, but still let execute_run initialize default dependencies.
    from frame_compare.orchestration import coordinator

    async def fake_execute_prep(*args, **kwargs):
        raise StopAfterDependencyInit

    async def fake_execute_phases(*args, **kwargs):
        pass

    monkeypatch.setattr(coordinator, "execute_prep", fake_execute_prep)
    monkeypatch.setattr(coordinator, "execute_phases", fake_execute_phases)
    monkeypatch.setattr(coordinator, "emit_consolidated_fps_report", lambda *a, **kw: None)

    request = RunRequest(root=tmp_path, quiet=True)
    deps = RunDependencies()

    assert deps.vs_loader is None
    assert deps.ffmpeg_runner is None
    assert deps.progress is None

    with pytest.raises(StopAfterDependencyInit):
        asyncio.run(execute_run(request, deps=deps))

    assert deps.vs_loader is None
    assert deps.ffmpeg_runner is None
    assert deps.progress is None
    assert deps.http_client is None
