from __future__ import annotations

from datetime import datetime
from pathlib import Path

from frame_compare.orchestration import RunDependencies as PublicRunDependencies
from frame_compare.orchestration.coordinator import (
    DefaultFFmpegRunner,
    RunDependencies,
)
from frame_compare.vs.loader import DefaultVSLoader, VSLoader
from frame_compare.vs.types import HDRMetadata


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

    assert deps.get_vs_loader() is loader
    assert deps.get_ffmpeg_runner() is runner


def test_run_dependencies_creates_default_vs_loader_lazily() -> None:
    deps = RunDependencies()

    assert deps.vs_loader is None

    loader = deps.get_vs_loader()

    assert isinstance(loader, DefaultVSLoader)
    assert deps.vs_loader is loader


def test_run_dependencies_creates_default_ffmpeg_runner_lazily() -> None:
    deps = RunDependencies()

    assert deps.ffmpeg_runner is None

    runner = deps.get_ffmpeg_runner()

    assert isinstance(runner, DefaultFFmpegRunner)
    assert deps.ffmpeg_runner is runner


def test_run_dependencies_clock_returns_datetime() -> None:
    deps = RunDependencies()

    now = deps.clock()

    assert isinstance(now, datetime)


def test_run_dependencies_accepts_vs_loader_protocol() -> None:
    loader: VSLoader = DummyVSLoader()
    deps = RunDependencies(vs_loader=loader)

    assert deps.get_vs_loader() is loader
