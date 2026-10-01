"""Mechanics shared by real-console end-to-end tests."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

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


ArtifactStep = tuple[Sequence[str], CommandResult]

_SAFE_DEFAULTS = {
    "slowpics": {"auto_upload": False},
    "tmdb": {"enabled": False},
    "report": {"auto_open": False},
}


def resolve_entry_point() -> Path:
    executable_dir = Path(sys.executable).resolve().parent
    for name in ("frame-compare.exe", "frame-compare"):
        candidate = executable_dir / name
        if candidate.is_file():
            return candidate
    found = shutil.which("frame-compare")
    if found is not None:
        return Path(found)
    raise FileNotFoundError("could not find frame-compare next to sys.executable or on PATH")


def _child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in list(environment):
        if re.match(r"^FRAME_COMPARE_[A-Za-z0-9_]+__", key):
            del environment[key]
    environment.update({"NO_COLOR": "1", "PYTHONUTF8": "1"})
    return environment


def run_command(
    executable: Path,
    workspace: Path,
    arguments: Sequence[str],
    *,
    timeout: float,
) -> CommandResult:
    completed = subprocess.run(
        [str(executable), *(str(argument) for argument in arguments)],
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


def make_workspace(tmp_path: Path, config: Mapping[str, Any] | None = None) -> Workspace:
    root = tmp_path / "workspace"
    input_dir = root / "comparison_videos"
    generated_dir = root / "generated"
    config_path = root / "config" / "config.toml"
    input_dir.mkdir(parents=True)
    generated_dir.mkdir(parents=True)
    config_path.parent.mkdir(parents=True)

    values: dict[str, dict[str, Any]] = {
        section: dict(table) for section, table in _SAFE_DEFAULTS.items()
    }
    if config is not None:
        for section, table in config.items():
            if not isinstance(table, Mapping):
                raise TypeError(f"workspace config section {section!r} must be a table")
            merged_table = values.setdefault(section, {})
            merged_table.update(table)
        for section, safe_table in _SAFE_DEFAULTS.items():
            configured_table = config.get(section)
            if configured_table is None:
                continue
            for key, safe_value in safe_table.items():
                if key in configured_table and configured_table[key] != safe_value:
                    raise ValueError(
                        f"workspace config cannot override safe default {section}.{key}"
                    )

    config_path.write_text(tomli_w.dumps(values), encoding="utf-8")
    return Workspace(root, input_dir, generated_dir, config_path)


def artifact_root(tmp_path: Path) -> Path:
    configured = os.environ.get("FRAME_COMPARE_E2E_ARTIFACTS")
    root = Path(configured) if configured else tmp_path / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _rendered_argv(arguments: Sequence[str], workspace: Path) -> str:
    rendered = ["frame-compare", *(str(argument) for argument in arguments)]
    rendered = [item.replace(str(workspace), "<root>") for item in rendered]
    return shlex.join(rendered)


def _rendered_stream(steps: Sequence[ArtifactStep], workspace: Path, stream_name: str) -> str:
    if len(steps) == 1:
        return getattr(steps[0][1], stream_name)
    chunks: list[str] = []
    for index, (arguments, result) in enumerate(steps, start=1):
        stream = getattr(result, stream_name)
        chunks.append(f"== step {index}: {_rendered_argv(arguments, workspace)} ==\n{stream}")
        if not stream.endswith("\n"):
            chunks.append("\n")
    return "".join(chunks)


def write_artifact(
    root: Path,
    scenario_id: str,
    workspace: Workspace,
    steps: Sequence[ArtifactStep],
    summary: dict[str, Any],
    expected: dict[str, Any],
    run_dir: Path | None = None,
) -> None:
    scenario_dir = root / scenario_id
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True)

    command_lines = "".join(
        f"{_rendered_argv(arguments, workspace.root)}\n" for arguments, _ in steps
    )
    (scenario_dir / "command.txt").write_text(command_lines, encoding="utf-8")
    (scenario_dir / "stdout.txt").write_text(
        _rendered_stream(steps, workspace.root, "stdout"), encoding="utf-8"
    )
    (scenario_dir / "stderr.txt").write_text(
        _rendered_stream(steps, workspace.root, "stderr"), encoding="utf-8"
    )
    if run_dir is not None and run_dir.is_dir():
        shutil.copytree(run_dir, scenario_dir / run_dir.name)
    (scenario_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert summary == expected


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


def read_report_data(report_path: Path) -> Any:
    parser = _ReportDataParser()
    parser.feed(report_path.read_text(encoding="utf-8"))
    return parser.result()


def read_pyproject_version(project_path: Path) -> str:
    with project_path.open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


__all__ = [
    "ArtifactStep",
    "CommandResult",
    "Workspace",
    "artifact_root",
    "make_workspace",
    "read_pyproject_version",
    "read_report_data",
    "resolve_entry_point",
    "run_command",
    "write_artifact",
]
