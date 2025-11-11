from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from src.frame_compare.cli_runtime import JsonTail
from tests.helpers.runner_env import (
    DummyProgress,
    _CliRunnerEnv,
    _make_json_tail_stub,
    _RecordingOutputManager,
    install_dummy_progress,
    install_vs_core_stub,
)


@pytest.fixture
def cli_runner_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _CliRunnerEnv:
    """Install a deterministic CLI harness for CLI-heavy tests."""

    return _CliRunnerEnv(monkeypatch, tmp_path)


@pytest.fixture
def recording_output_manager() -> _RecordingOutputManager:
    """Provide a CliOutputManager test double that records emitted lines."""

    return _RecordingOutputManager()


@pytest.fixture
def json_tail_stub() -> JsonTail:
    """Expose a reusable JsonTail stub for telemetry assertions."""

    return _make_json_tail_stub()


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click runner configured for CLI smoke tests."""

    return CliRunner()


@pytest.fixture
def runner_vs_core_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Automatically stub VapourSynth bindings for runner-heavy suites."""

    install_vs_core_stub(monkeypatch)


@pytest.fixture
def dummy_progress(monkeypatch: pytest.MonkeyPatch) -> type[DummyProgress]:
    """Install the DummyProgress stub so runner suites share a consistent Progress helper."""

    install_dummy_progress(monkeypatch)
    return DummyProgress
