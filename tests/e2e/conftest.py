"""Shared fixtures for real-console end-to-end tests."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
import tomli_w


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Decoded result from one real CLI child process."""

    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class Workspace:
    """Isolated root and its standard Frame Compare directories."""

    root: Path
    input_dir: Path
    generated_dir: Path
    config_path: Path


def _resolve_entry_point() -> Path:
    executable_dir = Path(sys.executable).resolve().parent
    for name in ("frame-compare.exe", "frame-compare"):
        candidate = executable_dir / name
        if candidate.is_file():
            return candidate
    found = shutil.which("frame-compare")
    if found is not None:
        return Path(found)
    pytest.fail("could not find frame-compare next to sys.executable or on PATH")


def _child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in list(environment):
        if re.match(r"^FRAME_COMPARE_[A-Za-z0-9_]+__", key):
            del environment[key]
    environment.update({"NO_COLOR": "1", "PYTHONUTF8": "1"})
    return environment


def _run_cli(
    executable: Path,
    workspace: Path,
    arguments: list[str],
    *,
    timeout: float,
) -> CommandResult:
    completed = subprocess.run(
        [str(executable), *arguments],
        cwd=workspace,
        env=_child_environment(),
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout.decode("utf-8"),
        stderr=completed.stderr.decode("utf-8"),
    )


def _make_workspace(tmp_path: Path, config: Mapping[str, Any] | None = None) -> Workspace:
    root = tmp_path / "workspace"
    input_dir = root / "comparison_videos"
    generated_dir = root / "generated"
    config_path = root / "config" / "config.toml"
    input_dir.mkdir(parents=True)
    generated_dir.mkdir(parents=True)
    config_path.parent.mkdir(parents=True)
    values: Mapping[str, Any] = config or {
        "slowpics": {"auto_upload": False},
        "tmdb": {"enabled": False},
        "report": {"auto_open": False},
    }
    config_path.write_text(tomli_w.dumps(dict(values)), encoding="utf-8")
    return Workspace(root, input_dir, generated_dir, config_path)


def _artifact_root(tmp_path: Path) -> Path:
    configured = os.environ.get("FRAME_COMPARE_E2E_ARTIFACTS")
    root = Path(configured) if configured else tmp_path / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_artifact(
    artifact_root: Path,
    scenario_id: str,
    arguments: list[str],
    workspace: Path,
    result: CommandResult,
    summary: dict[str, Any],
    *,
    run_dir: Path | None = None,
) -> None:
    scenario_dir = artifact_root / scenario_id
    shutil.rmtree(scenario_dir, ignore_errors=True)
    scenario_dir.mkdir(parents=True)
    rendered_argv = ["frame-compare", *(str(item) for item in arguments)]
    rendered_argv = [str(item).replace(str(workspace), "<root>") for item in rendered_argv]
    (scenario_dir / "command.txt").write_text(shlex.join(rendered_argv) + "\n", encoding="utf-8")
    (scenario_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (scenario_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    if run_dir is not None and run_dir.is_dir():
        shutil.copytree(run_dir, scenario_dir / run_dir.name)
    (scenario_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert json.loads((scenario_dir / "summary.json").read_text(encoding="utf-8")) == summary


class _ReportDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_report_data = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if (
            tag == "script"
            and attributes.get("type") == "application/json"
            and attributes.get("id") == "report-data"
        ):
            self._in_report_data = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_report_data:
            self._in_report_data = False

    def handle_data(self, data: str) -> None:
        if self._in_report_data:
            self._chunks.append(data)

    def result(self) -> Any:
        if not self._chunks:
            raise AssertionError("report.html has no report-data script")
        return json.loads("".join(self._chunks))


def _read_report_data(report_path: Path) -> Any:
    parser = _ReportDataParser()
    parser.feed(report_path.read_text(encoding="utf-8"))
    return parser.result()


@pytest.fixture
def cli_executable() -> Path:
    return _resolve_entry_point()


@pytest.fixture
def run_cli(cli_executable: Path) -> Callable[..., CommandResult]:
    def run(
        workspace: Path,
        arguments: list[str],
        *,
        timeout: float = 30.0,
    ) -> CommandResult:
        return _run_cli(cli_executable, workspace, arguments, timeout=timeout)

    return run


@pytest.fixture
def workspace(tmp_path: Path) -> Callable[[Mapping[str, Any] | None], Workspace]:
    return lambda config=None: _make_workspace(tmp_path, config)


@pytest.fixture
def artifact_root(tmp_path: Path) -> Path:
    return _artifact_root(tmp_path)


@pytest.fixture
def media_gate() -> Iterator[None]:
    if os.environ.get("FRAME_COMPARE_E2E_REQUIRE_MEDIA") != "1":
        pytest.skip("media E2E tier requires FRAME_COMPARE_E2E_REQUIRE_MEDIA=1")
    yield


@pytest.fixture
def report_data_reader() -> Callable[[Path], Any]:
    return _read_report_data


@pytest.fixture
def pyproject_version() -> str:
    project_path = Path(__file__).parents[2] / "pyproject.toml"
    with project_path.open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


__all__ = ["CommandResult", "Workspace", "_write_artifact"]
