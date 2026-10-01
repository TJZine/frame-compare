"""Pytest fixtures for real-console end-to-end tests."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.harness import (
    ArtifactStep,
    CommandResult,
    Workspace,
    make_workspace,
    read_pyproject_version,
    read_report_data,
    resolve_entry_point,
    run_command,
    write_artifact,
)
from tests.e2e.harness import artifact_root as get_artifact_root


@pytest.fixture
def cli_executable() -> Path:
    return resolve_entry_point()


@pytest.fixture
def run_cli(cli_executable: Path) -> Callable[..., CommandResult]:
    def run(
        workspace: Path,
        arguments: Sequence[str],
        *,
        timeout: float = 30.0,
    ) -> CommandResult:
        return run_command(cli_executable, workspace, arguments, timeout=timeout)

    return run


@pytest.fixture
def workspace(tmp_path: Path) -> Callable[[Mapping[str, Any] | None], Workspace]:
    return lambda config=None: make_workspace(tmp_path, config)


@pytest.fixture
def artifact_root(tmp_path: Path) -> Path:
    return get_artifact_root(tmp_path)


@pytest.fixture
def record(artifact_root: Path) -> Callable[..., None]:
    def record_artifact(
        scenario_id: str,
        workspace: Workspace,
        steps: Sequence[ArtifactStep],
        summary: dict[str, Any],
        expected: dict[str, Any],
        run_dir: Path | None = None,
    ) -> None:
        write_artifact(
            artifact_root,
            scenario_id,
            workspace,
            steps,
            summary,
            expected,
            run_dir,
        )

    return record_artifact


@pytest.fixture(scope="session")
def media_gate() -> Iterator[None]:
    if os.environ.get("FRAME_COMPARE_E2E_REQUIRE_MEDIA") != "1":
        pytest.skip("media E2E tier requires FRAME_COMPARE_E2E_REQUIRE_MEDIA=1")
    yield


@pytest.fixture
def report_data_reader() -> Callable[[Path], Any]:
    return read_report_data


@pytest.fixture
def pyproject_version() -> str:
    return read_pyproject_version(Path(__file__).parents[2] / "pyproject.toml")


@pytest.fixture(scope="session")
def media_files(media_gate: None, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    from tests.e2e.harness import generate_media

    return generate_media(tmp_path_factory.mktemp("media"))
