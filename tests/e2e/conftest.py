"""Pytest fixtures for real-console end-to-end tests."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
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
def run_cli(cli_executable: Path, raw_artifact_dir: Path) -> Callable[..., CommandResult]:
    step = 0

    def run(
        workspace: Path,
        arguments: Sequence[str],
        *,
        timeout: float = 30.0,
    ) -> CommandResult:
        nonlocal step
        step += 1
        step_dir = raw_artifact_dir / str(step)
        step_dir.mkdir(parents=True)
        (step_dir / "command.txt").write_text(
            shlex.join([str(cli_executable), *arguments]) + "\n", encoding="utf-8"
        )
        captured: CommandResult | subprocess.TimeoutExpired | None = None
        try:
            captured = run_command(cli_executable, workspace, arguments, timeout=timeout)
            (step_dir / "exit-code.txt").write_text(f"{captured.exit_code}\n", encoding="utf-8")
            return captured
        except subprocess.TimeoutExpired as exc:
            captured = exc
            (step_dir / "timeout.txt").write_text(f"{timeout} seconds\n", encoding="utf-8")
            raise
        finally:
            if captured is not None:
                for name in ("stdout", "stderr"):
                    stream = getattr(captured, name)
                    (step_dir / f"{name}.txt").write_bytes(
                        stream.encode("utf-8") if isinstance(stream, str) else stream or b""
                    )

    return run


@pytest.fixture
def workspace(tmp_path: Path) -> Callable[[Mapping[str, Any] | None], Workspace]:
    return lambda config=None: make_workspace(tmp_path, config)


@pytest.fixture
def artifact_root(tmp_path: Path) -> Path:
    return get_artifact_root(tmp_path)


@pytest.fixture
def raw_artifact_dir(artifact_root: Path, request: pytest.FixtureRequest) -> Path:
    directory = artifact_root / f"raw-{request.node.name}"
    if directory.exists():
        shutil.rmtree(directory)
    return directory


@pytest.fixture
def record(artifact_root: Path, raw_artifact_dir: Path) -> Callable[..., None]:
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
        # A checked scenario already contains these streams. Retain raw evidence
        # only when parsing, execution or summary validation fails first.
        if raw_artifact_dir.exists():
            shutil.rmtree(raw_artifact_dir)

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
